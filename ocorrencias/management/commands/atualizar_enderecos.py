from django.core.management.base import BaseCommand
from ocorrencias.endereco_models import EnderecoOcorrencia
from cidades.models import Bairro, Cidade
from geopy.geocoders import Nominatim
from django.db.models import Q
import time
import logging
import unicodedata
import re

logger = logging.getLogger(__name__)


def normalizar(texto):
    """Remove acentos e caixa alta para comparação"""
    if not texto:
        return ""
    return (
        unicodedata.normalize("NFKD", texto)
        .encode("ASCII", "ignore")
        .decode("ASCII")
        .upper()
        .strip()
    )


class Command(BaseCommand):
    help = "Script TOTAL: Correções Manuais + Geocodificação Automática"

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=None)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        limite = options.get("limite")
        dry_run = options.get("dry_run")

        # ==============================================================================
        # 1. LISTA DE CORREÇÕES MANUAIS (Sua lista VIP)
        # ==============================================================================
        correcoes_manuais = {
            85: "CENTRO",
            80: "CENTRO",
            71: "SANTA TEREZA",
            63: "DOUTOR SILVIO LEITE",
            57: "ASA BRANCA",
            42: "SÃO BENTO",
            40: "CENTRO",
            70: "DISTRITO INDUSTRIAL GOVERNADOR AQUILINO MOTA DUARTE",
            61: "ZONA RURAL",
            31: "LIBERDADE",
            29: "SANTA LUZIA",
            27: "ASA BRANCA",
            47: "ZONA RURAL",
            24: "ZONA RURAL",
            76: "DOUTOR SILVIO LEITE",
        }

        # Carrega nomes de cidades para evitar erros
        nomes_cidades = set(Cidade.objects.values_list("nome", flat=True))

        self.stdout.write("Buscando endereços pendentes...")

        # Busca endereços que precisam de Bairro OU Latitude
        enderecos = (
            EnderecoOcorrencia.objects.filter(tipo="EXTERNA", logradouro__isnull=False)
            .exclude(logradouro__exact="")
            .filter(Q(latitude__isnull=True) | Q(bairro_novo__isnull=True))
        )

        if limite:
            enderecos = enderecos[:limite]

        total = enderecos.count()

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(
            self.style.WARNING(f"📍 PROCESSAMENTO TOTAL ({total} registros)")
        )
        self.stdout.write("=" * 70)

        geolocator = Nominatim(user_agent="spr_roraima_total_fix_v1", timeout=10)

        sucesso = 0
        falha = 0

        for i, endereco in enumerate(enderecos, 1):
            log_original = endereco.logradouro
            self.stdout.write(f"\n[{i}/{total}] ID {endereco.id} - {log_original}")

            alteracoes = []
            processado_manualmente = False

            # ==========================================================================
            # PASSO A: VERIFICA SE É CORREÇÃO MANUAL
            # ==========================================================================
            if endereco.id in correcoes_manuais:
                nome_manual = correcoes_manuais[endereco.id]

                # Busca o bairro no banco
                bairro_obj = Bairro.objects.filter(nome__iexact=nome_manual).first()
                if not bairro_obj:
                    bairro_obj = Bairro.objects.filter(
                        nome__icontains=nome_manual
                    ).first()

                if bairro_obj:
                    endereco.bairro_novo = bairro_obj
                    alteracoes.append(f"MANUAL -> {bairro_obj.nome}")
                    processado_manualmente = True
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"   ❌ Erro Manual: Bairro '{nome_manual}' não cadastrado no sistema!"
                        )
                    )

            # ==========================================================================
            # PASSO B: SE NÃO FOI MANUAL, TENTA AUTOMÁTICO
            # ==========================================================================

            # Regra Vicinal (Só aplica se ainda não tiver bairro definido)
            if not endereco.bairro_novo and "VICINAL" in log_original.upper():
                cidade_obj = endereco.ocorrencia.cidade
                zona_rural = Bairro.objects.filter(
                    cidade=cidade_obj, nome="ZONA RURAL"
                ).first()
                if zona_rural:
                    endereco.bairro_novo = zona_rural
                    alteracoes.append("Regra Vicinal -> ZONA RURAL")

            # Preparação para GPS (Limpeza de cruzamentos)
            log_busca = log_original
            separadores = [" com ", " c/", " e ", " esquina ", ","]
            for sep in separadores:
                if sep in log_busca.lower():
                    partes = re.split(f"{sep}", log_busca, flags=re.IGNORECASE)
                    if len(partes) > 0:
                        log_busca = partes[0].strip()
                        if not processado_manualmente:
                            self.stdout.write(f"   ✂️  Simplificado: '{log_busca}'")
                        break

            # ==========================================================================
            # PASSO C: BUSCA NO MAPA (GPS)
            # ==========================================================================
            try:
                # Só busca no mapa se não tiver coordenadas OU (não tiver bairro E não foi manual)
                precisa_gps = endereco.latitude is None
                precisa_bairro = endereco.bairro_novo is None

                if precisa_gps or precisa_bairro:
                    cidade_ocorrencia = endereco.ocorrencia.cidade
                    nome_cidade_bd = (
                        cidade_ocorrencia.nome if cidade_ocorrencia else "BOA VISTA"
                    )
                    busca = f"{log_busca}, {endereco.numero or ''}, {nome_cidade_bd}, Roraima, Brasil"

                    location = geolocator.geocode(
                        busca, exactly_one=True, addressdetails=True
                    )

                    if location:
                        # Pega Lat/Long
                        if not endereco.latitude:
                            endereco.latitude = location.latitude
                            endereco.longitude = location.longitude
                            endereco.coordenadas_manuais = False
                            alteracoes.append("GPS Adicionado")

                        # Pega Bairro (Só se ainda não tiver)
                        if not endereco.bairro_novo:
                            raw = location.raw.get("address", {})
                            bairro_api = (
                                raw.get("suburb")
                                or raw.get("neighbourhood")
                                or raw.get("city_district")
                            )

                            if bairro_api:
                                bairro_norm = normalizar(bairro_api)

                                if bairro_norm in nomes_cidades:
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f"   ⚠️  Ignorando nome de cidade: {bairro_api}"
                                        )
                                    )
                                elif (
                                    re.search(r"\bS-?\d+", log_original.upper())
                                    and "PARAVIANA" in bairro_norm
                                ):
                                    self.stdout.write(
                                        self.style.WARNING(
                                            "   ⚠️  Ignorando Paraviana (Rua S-**)"
                                        )
                                    )
                                else:
                                    # Busca Oficial no Banco
                                    bairro_oficial = Bairro.objects.filter(
                                        cidade=cidade_ocorrencia,
                                        nome__iexact=bairro_norm,
                                    ).first()
                                    if not bairro_oficial:
                                        bairro_oficial = Bairro.objects.filter(
                                            cidade=cidade_ocorrencia,
                                            nome__icontains=bairro_norm,
                                        ).first()

                                    if bairro_oficial:
                                        endereco.bairro_novo = bairro_oficial
                                        alteracoes.append(
                                            f"Mapa -> {bairro_oficial.nome}"
                                        )
                                    elif not endereco.bairro_legado:
                                        endereco.bairro_legado = bairro_api.upper()
                                        alteracoes.append(f"Legado: {bairro_api}")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Erro GPS: {e}"))

            # ==========================================================================
            # PASSO D: SALVAR
            # ==========================================================================
            if alteracoes:
                if not dry_run:
                    endereco.save()
                    self.stdout.write(
                        self.style.SUCCESS(f"   ✅ Salvo: {', '.join(alteracoes)}")
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"   ✅ [SIMULAÇÃO]: {', '.join(alteracoes)}"
                        )
                    )
                sucesso += 1
            else:
                self.stdout.write("   ℹ️  Sem alterações.")
                falha += 1

            # Pausa para não bloquear a API (exceto se foi puramente manual)
            if i < total and not processado_manualmente:
                time.sleep(1.2)

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(f"FIM. Processados com sucesso: {sucesso}")
