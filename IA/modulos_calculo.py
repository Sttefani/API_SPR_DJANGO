# IA/modulos_calculo.py
import math

def calcular_velocidade_frenagem(distancia_m: float, tipo_pista: str, condicao_pista: str) -> dict:
    """
    Calcula a velocidade de um veículo com base nas marcas de frenagem (arrasto).
    Fórmula: v = sqrt(2 * μ * g * d)
    
    Args:
        distancia_m (float): O comprimento da marca de frenagem em metros.
        tipo_pista (str): O tipo de superfície (ex: 'asfalto', 'concreto', 'terra').
        condicao_pista (str): A condição da superfície (ex: 'seco', 'molhado').

    Returns:
        dict: Um dicionário com o resultado do cálculo e a fundamentação.
    """
    g = 9.81  # Aceleração da gravidade (m/s²)
    
    # Dicionário de coeficientes de atrito (μ) - (EXPANDA ISSO!)
    # Chave: "tipo_condicao"
    coeficientes_atrito = {
        "asfalto_seco": 0.80,
        "asfalto_molhado": 0.60,
        "concreto_seco": 0.75,
        "concreto_molhado": 0.55,
        "terra_compactada_seco": 0.50,
        "cascalho_solto": 0.45,
    }
    
    chave_mu = f"{tipo_pista.lower()}_{condicao_pista.lower()}"
    
    if chave_mu not in coeficientes_atrito:
        return {
            "erro": f"Coeficiente de atrito não encontrado para '{tipo_pista}' em condição '{condicao_pista}'.",
            "tipos_disponiveis": list(coeficientes_atrito.keys())
        }
        
    mu = coeficientes_atrito[chave_mu]
    
    # Cálculo: v = sqrt(2 * μ * g * d)
    velocidade_ms = math.sqrt(2 * mu * g * distancia_m)
    velocidade_kmh = velocidade_ms * 3.6
    
    # Retorna um JSON/dicionário estruturado para a IA ler
    return {
        "velocidade_kmh": round(velocidade_kmh, 2),
        "velocidade_ms": round(velocidade_ms, 2),
        "formula_utilizada": "v = sqrt(2 * μ * g * d)",
        "parametros_utilizados": {
            "distancia_m": distancia_m,
            "coeficiente_atrito_mu": mu,
            "gravidade_g": g,
            "referencia_mu": f"{tipo_pista} ({condicao_pista})"
        },
        "fundamentacao": "Cálculo baseado na conservação de energia e atrito cinético."
    }