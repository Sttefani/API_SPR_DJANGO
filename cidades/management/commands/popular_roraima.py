from django.core.management.base import BaseCommand
from cidades.models import Cidade, Bairro


class Command(BaseCommand):
    help = "Popula o banco com todas as 15 cidades de RR e uma lista abrangente de bairros oficiais"

    def handle(self, *args, **options):
        self.stdout.write("Iniciando carga de dados de Roraima (Versão Melhorada)...")

        # Estrutura de Dados: Cidade -> Lista de Bairros
        # Dados atualizados com base em fontes oficiais (Prefeitura de Boa Vista, IBGE e CEP Brasil)
        dados_roraima = {
            "BOA VISTA": [
                "13 DE SETEMBRO",
                "31 DE MARÇO",
                "AEROPORTO",
                "ALVORADA",
                "APARECIDA",
                "ARACELI SOUTO MAIOR",
                "ASA BRANCA",
                "BAIRRO DOS ESTADOS",
                "BELA VISTA",
                "BURITIS",
                "CAÇARI",
                "CAIMBÉ",
                "CALUNGÁ",
                "CAMBARÁ",
                "CANARINHO",
                "CARANÃ",
                "CAUAMÉ",
                "CENTENÁRIO",
                "CENTRO",
                "CIDADE SATÉLITE",
                "CINTURÃO VERDE",
                "DISTRITO INDUSTRIAL GOVERNADOR AQUILINO MOTA DUARTE",
                "DOUTOR AIRTON ROCHA",
                "DOUTOR SILVIO BOTELHO",
                "DOUTOR SILVIO LEITE",
                "EQUATORIAL",
                "FELIX VALOIS DE ARAÚJO",
                "JARDIM CARANÃ",
                "JARDIM FLORESTA",
                "JARDIM PRIMAVERA",
                "JARDIM TROPICAL",
                "JOQUEI CLUBE",
                "LAURA MOREIRA",
                "LIBERDADE",
                "MARECHAL RONDON",
                "MECEJANA",
                "MURILO TEIXEIRA CIDADE",
                "NOSSA SENHORA APARECIDA",
                "NOVA CANAÃ",
                "NOVA CIDADE",
                "OLÍMPICO",
                "OPERÁRIO",
                "PARAVIANA",
                "PEDRA PINTADA",
                "PINTOLÂNDIA",
                "PISCICULTURA",
                "PRICUMÃ",
                "PROFESSORA ARACELI SOUTO MAIOR",
                "RAIAR DO SOL",
                "RIVER PARK",
                "SAID SALOMÃO",
                "SANTA CECÍLIA",
                "SANTA LUZIA",
                "SANTA TEREZA",
                "SÃO BENTO",
                "SÃO FRANCISCO",
                "SÃO PEDRO",
                "SÃO VICENTE",
                "SENADOR HÉLIO CAMPOS",
                "TANCREDO NEVES",
                "UNIÃO",
                "VILA JARDIM",
                "ZONA RURAL",
            ],
            "RORAINÓPOLIS": [
                "CENTRO",
                "NOVA ESPERANÇA",
                "PARQUE DAS ORQUÍDEAS",
                "GENTIL LINHARES",
                "SUELÂNDIA",
                "ANDRÁRA",
                "VILA MARTINS PEREIRA",
                "VILA NOVA COLINA",
                "VILA DO EQUADOR",
                "VILA DO JUNDIÁ",
                "VILA SANTA MARIA DO BOIAÇU",
                "ZONA RURAL",
            ],
            "CARACARAÍ": [
                "CENTRO",
                "BARÃO DO RIO BRANCO",
                "CINTURÃO VERDE",
                "MONTE SINAI",
                "NOSSA SENHORA DO LIVRAMENTO",
                "SANTA LUZIA",
                "SÃO FRANCISCO",
                "SÃO JOSÉ OPERÁRIO",
                "SÃO JORGE",
                "ZONA INDUSTRIAL",
                "ZONA RURAL",
            ],
            "ALTO ALEGRE": ["CENTRO", "VILA TAIAU", "ZONA RURAL"],
            "AMAJARI": ["CENTRO", "VILA BRASIL", "VILA TEPEQUÉM", "ZONA RURAL"],
            "BONFIM": [
                "CENTRO",
                "CIDADE NOVA",
                "1º DE JULHO",
                "VILA SÃO FRANCISCO",
                "ZONA RURAL",
            ],
            "CANTÁ": ["CENTRO", "VILA FÉLIX PINTO", "VILA CENTRAL", "ZONA RURAL"],
            "CAROEBE": ["CENTRO", "VILA ENTRE RIOS", "ZONA RURAL"],
            "IRACEMA": ["CENTRO", "VILA CAMPOS NOVOS", "ZONA RURAL"],
            "MUCAJAÍ": ["CENTRO", "SAGRADA FAMÍLIA", "VILA APUIAÚ", "ZONA RURAL"],
            "NORMANDIA": ["CENTRO", "ZONA RURAL"],
            "PACARAIMA": ["CENTRO", "VILA NOVA", "SUAPI", "ZONA RURAL"],
            "SÃO JOÃO DA BALIZA": ["CENTRO", "ZONA RURAL"],
            "SÃO LUIZ": ["CENTRO", "ZONA RURAL"],
            "UIRAMUTÃ": ["CENTRO", "ZONA RURAL"],
        }

        total_cidades = 0
        total_bairros = 0

        for nome_cidade, lista_bairros in dados_roraima.items():
            # 1. Cria a Cidade (Normalizando para Capitalize ou Upper conforme preferência)
            nome_cidade_norm = nome_cidade.strip().upper()
            cidade_obj, created_cid = Cidade.objects.get_or_create(
                nome=nome_cidade_norm
            )

            if created_cid:
                self.stdout.write(f"📍 Criada cidade: {nome_cidade_norm}")
                total_cidades += 1

            # 2. Cria os Bairros dessa cidade
            for nome_bairro in lista_bairros:
                nome_bairro_norm = nome_bairro.strip().upper()
                _, created_bairro = Bairro.objects.get_or_create(
                    nome=nome_bairro_norm, cidade=cidade_obj
                )
                if created_bairro:
                    total_bairros += 1

        self.stdout.write(self.style.SUCCESS("=" * 40))
        self.stdout.write(self.style.SUCCESS(f"✅ FINALIZADO COM SUCESSO!"))
        self.stdout.write(f"Cidades processadas: {len(dados_roraima)}")
        self.stdout.write(f"Novos bairros cadastrados: {total_bairros}")
        self.stdout.write(self.style.SUCCESS("=" * 40))
