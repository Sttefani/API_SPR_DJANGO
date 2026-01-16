# ============================================
# ocorrencias/utils/geocoding.py
#
# FUNÇÃO AUXILIAR DE GEOCODIFICAÇÃO COM FALLBACKS
# NÃO MODIFICA O MODEL - SEGURO PARA PRODUÇÃO
# ============================================

import logging
import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

logger = logging.getLogger(__name__)


def geocodificar_com_fallback(endereco, dry_run=False):
    """
    Geocodifica um EnderecoOcorrencia usando múltiplas estratégias de fallback.

    SEGURO: Não modifica o model, apenas usa os métodos existentes.

    Estratégia:
    1. Tenta endereço completo (logradouro + bairro + cidade)
    2. Tenta bairro + cidade (se bairro não for "zona rural")
    3. Tenta apenas cidade (coordenadas da sede do município)

    Args:
        endereco: Instância de EnderecoOcorrencia
        dry_run: Se True, não salva no banco (apenas simula)

    Returns:
        dict: {
            'sucesso': bool,
            'nivel': int (1, 2 ou 3),
            'nivel_nome': str,
            'latitude': float ou None,
            'longitude': float ou None,
            'query_usada': str
        }
    """

    resultado = {
        "sucesso": False,
        "nivel": None,
        "nivel_nome": None,
        "latitude": None,
        "longitude": None,
        "query_usada": None,
    }

    # Validações básicas
    if endereco.tipo != "EXTERNA":
        logger.info(f"Endereço ID {endereco.id}: Tipo INTERNA, ignorando.")
        return resultado

    if endereco.coordenadas_manuais:
        logger.info(f"Endereço ID {endereco.id}: Coordenadas manuais, ignorando.")
        return resultado

    if endereco.latitude and endereco.longitude:
        logger.info(f"Endereço ID {endereco.id}: Já possui coordenadas.")
        resultado["sucesso"] = True
        resultado["latitude"] = float(endereco.latitude)
        resultado["longitude"] = float(endereco.longitude)
        return resultado

    # Obter dados para montar as queries
    cidade_nome = ""
    if (
        hasattr(endereco, "ocorrencia")
        and endereco.ocorrencia
        and endereco.ocorrencia.cidade
    ):
        cidade_nome = endereco.ocorrencia.cidade.nome

    # Obter nome do bairro (prioriza novo, depois legado)
    bairro_nome = ""
    if endereco.bairro_novo:
        bairro_nome = endereco.bairro_novo.nome
    elif endereco.bairro_legado:
        bairro_nome = endereco.bairro_legado

    logradouro = endereco.logradouro.strip() if endereco.logradouro else ""
    numero = endereco.numero.strip() if endereco.numero else ""

    # =========================================
    # MONTAR QUERIES (do mais específico ao genérico)
    # =========================================
    queries = []

    # NÍVEL 1: Endereço completo
    if logradouro:
        partes = [logradouro]
        if numero:
            partes.append(numero)
        if bairro_nome:
            partes.append(bairro_nome)
        if cidade_nome:
            partes.append(cidade_nome)
        partes.extend(["Roraima", "Brasil"])
        queries.append(
            {"nivel": 1, "nivel_nome": "ENDERECO_COMPLETO", "query": ", ".join(partes)}
        )

    # NÍVEL 2: Bairro + Cidade (se não for zona rural genérico)
    if bairro_nome and cidade_nome:
        bairro_lower = bairro_nome.lower()
        # Pula se for zona rural genérica (não vai encontrar)
        if "zona rural" not in bairro_lower and "rural" not in bairro_lower:
            queries.append(
                {
                    "nivel": 2,
                    "nivel_nome": "BAIRRO_CIDADE",
                    "query": f"{bairro_nome}, {cidade_nome}, Roraima, Brasil",
                }
            )

    # NÍVEL 3: Apenas Cidade (fallback final - sede do município)
    if cidade_nome:
        queries.append(
            {
                "nivel": 3,
                "nivel_nome": "CIDADE_SEDE",
                "query": f"{cidade_nome}, Roraima, Brasil",
            }
        )

    if not queries:
        logger.warning(
            f"Endereço ID {endereco.id}: Sem dados suficientes para geocodificar."
        )
        return resultado

    # =========================================
    # TENTAR CADA QUERY
    # =========================================
    geolocator = Nominatim(user_agent="spr_roraima_pericia_v2", timeout=10)

    for item in queries:
        nivel = item["nivel"]
        nivel_nome = item["nivel_nome"]
        query = item["query"]

        logger.info(
            f"Endereço ID {endereco.id}: Tentativa nível {nivel} ({nivel_nome})"
        )
        logger.info(f"  Query: {query}")

        try:
            location = geolocator.geocode(query, exactly_one=True, timeout=10)

            if location:
                lat = float(location.latitude)
                lon = float(location.longitude)

                logger.info(f"  ✅ ENCONTRADO: [{lat}, {lon}]")

                resultado["sucesso"] = True
                resultado["nivel"] = nivel
                resultado["nivel_nome"] = nivel_nome
                resultado["latitude"] = lat
                resultado["longitude"] = lon
                resultado["query_usada"] = query

                # Salvar no banco (se não for dry_run)
                if not dry_run:
                    endereco.latitude = str(lat)
                    endereco.longitude = str(lon)
                    # Usar o modo_entrada existente ou manter o atual
                    # NÃO alteramos modo_entrada pois pode não ter o choice novo
                    endereco.save(update_fields=["latitude", "longitude", "updated_at"])
                    logger.info(f"  💾 SALVO no banco de dados!")
                else:
                    logger.info(f"  🔍 DRY-RUN: Não salvo no banco.")

                return resultado
            else:
                logger.info(f"  ❌ Não encontrado neste nível")

            # Rate limit entre tentativas
            time.sleep(1.2)

        except GeocoderTimedOut:
            logger.warning(f"  ⏱️ Timeout no nível {nivel}")
            time.sleep(2)
            continue

        except GeocoderServiceError as e:
            logger.error(f"  🌐 Erro de serviço no nível {nivel}: {e}")
            time.sleep(2)
            continue

        except Exception as e:
            logger.error(f"  ❌ Erro inesperado no nível {nivel}: {e}")
            continue

    logger.warning(f"Endereço ID {endereco.id}: ❌ Não geocodificado em nenhum nível.")
    return resultado


def reprocessar_enderecos_sem_coordenadas(limite=None, dry_run=False):
    """
    Função auxiliar para reprocessar endereços sem coordenadas.

    Pode ser chamada de qualquer lugar:
    - Management command
    - Django shell
    - View/endpoint

    Args:
        limite: Número máximo de endereços a processar
        dry_run: Se True, não salva no banco

    Returns:
        dict: Estatísticas do processamento
    """
    from ocorrencias.endereco_models import EnderecoOcorrencia

    # Buscar endereços sem coordenadas
    queryset = EnderecoOcorrencia.objects.filter(
        tipo="EXTERNA", latitude__isnull=True, coordenadas_manuais=False
    ).select_related("ocorrencia", "ocorrencia__cidade", "bairro_novo")

    if limite:
        queryset = queryset[:limite]

    total = queryset.count()

    estatisticas = {
        "total": total,
        "sucesso": 0,
        "falha": 0,
        "por_nivel": {
            1: 0,  # ENDERECO_COMPLETO
            2: 0,  # BAIRRO_CIDADE
            3: 0,  # CIDADE_SEDE
        },
        "detalhes": [],
    }

    if total == 0:
        logger.info("✅ Todos os endereços já possuem coordenadas!")
        return estatisticas

    logger.info(f"📍 Iniciando geocodificação de {total} endereços...")

    for i, endereco in enumerate(queryset, 1):
        logger.info(f"\n[{i}/{total}] Processando ID {endereco.id}")

        resultado = geocodificar_com_fallback(endereco, dry_run=dry_run)

        detalhe = {
            "id": endereco.id,
            "ocorrencia": (
                endereco.ocorrencia.numero_ocorrencia if endereco.ocorrencia else None
            ),
            "sucesso": resultado["sucesso"],
            "nivel": resultado["nivel"],
            "nivel_nome": resultado["nivel_nome"],
        }
        estatisticas["detalhes"].append(detalhe)

        if resultado["sucesso"]:
            estatisticas["sucesso"] += 1
            if resultado["nivel"]:
                estatisticas["por_nivel"][resultado["nivel"]] += 1
        else:
            estatisticas["falha"] += 1

        # Rate limit entre endereços
        if i < total:
            time.sleep(1.5)

    # Log do resumo
    logger.info("\n" + "=" * 50)
    logger.info("📊 RESUMO DA GEOCODIFICAÇÃO")
    logger.info("=" * 50)
    logger.info(f"Total processado: {estatisticas['total']}")
    logger.info(f"✅ Sucesso: {estatisticas['sucesso']}")
    logger.info(f"❌ Falha: {estatisticas['falha']}")
    logger.info(f"  - Nível 1 (Endereço completo): {estatisticas['por_nivel'][1]}")
    logger.info(f"  - Nível 2 (Bairro + Cidade): {estatisticas['por_nivel'][2]}")
    logger.info(f"  - Nível 3 (Sede do município): {estatisticas['por_nivel'][3]}")

    if dry_run:
        logger.info("⚠️ MODO DRY-RUN: Nada foi salvo no banco!")

    return estatisticas
