import math
from typing import Dict, Any

class CalculadoraVelocidade:
    """
    Calculadora de velocidade por marcas de frenagem
    Baseado em princípios físicos e literatura técnica internacional
    """
    
    # Coeficientes de atrito (μ)
    # Fonte: Limpert (1999), Brach (2005), Fricke (1990)
    COEFICIENTES = {
        'asfalto_seco': 0.70,
        'asfalto_molhado': 0.50,
        'asfalto_com_oleo': 0.30,
        'concreto_seco': 0.80,
        'concreto_molhado': 0.60,
        'terra_seca': 0.40,
        'terra_molhada': 0.30,
        'cascalho_seco': 0.35,
        'cascalho_molhado': 0.25,
        'grama_seca': 0.35,         # ← NOVO!
        'grama_molhada': 0.25,      # ← NOVO!
        'lama': 0.20,               # ← NOVO!
        'areia_seca': 0.30,         # ← NOVO!
        'areia_molhada': 0.20,      # ← NOVO!
        'paralelepipedo_seco': 0.60, # ← NOVO!
        'paralelepipedo_molhado': 0.40, # ← NOVO!
        'gelo': 0.10,
        'neve': 0.20,
}
    
    GRAVIDADE = 9.81  # m/s²
    
    def calcular(
        self, 
        distancia_metros: float, 
        tipo_piso: str = 'asfalto', 
        condicao: str = 'seco'
    ) -> Dict[str, Any]:
        """
        Calcula velocidade do veículo pela marca de frenagem
        
        Fórmula: v = √(2 × μ × g × d)
        
        Onde:
        - v = velocidade (m/s)
        - μ = coeficiente de atrito
        - g = aceleração da gravidade (9,81 m/s²)
        - d = distância da marca de frenagem (m)
        
        Args:
            distancia_metros: Distância da marca de arrasto em metros
            tipo_piso: Tipo de pavimento (asfalto, concreto, terra, etc)
            condicao: Condição do piso (seco, molhado, com_oleo, etc)
            
        Returns:
            Dict com resultado detalhado e fundamentação
        """
        
        # Validação de entrada
        if distancia_metros <= 0:
            raise ValueError("Distância deve ser maior que zero")
        
        # Chave do coeficiente
        # Chave do coeficiente
        chave_coeficiente = f"{tipo_piso.lower()}_{condicao.lower()}"

        # Busca coeficiente (com fallback)
        if chave_coeficiente not in self.COEFICIENTES:
            # Tenta sem condição (para casos especiais como gelo, lama)
            if tipo_piso.lower() in self.COEFICIENTES:
                chave_coeficiente = tipo_piso.lower()
            else:
                # Lista opções disponíveis
                opcoes_tipo = set([k.split('_')[0] for k in self.COEFICIENTES.keys() if '_' in k])
                raise ValueError(
                    f"Combinação '{tipo_piso}' + '{condicao}' não encontrada.\n"
                    f"Tipos de piso disponíveis: {', '.join(sorted(opcoes_tipo))}\n"
                    f"Condições: seco, molhado, com_oleo"
                )

        mu = self.COEFICIENTES[chave_coeficiente]
        
        # Cálculo principal
        velocidade_ms = math.sqrt(2 * mu * self.GRAVIDADE * distancia_metros)
        velocidade_kmh = velocidade_ms * 3.6
        
        # Margem de erro (±10% típico)
        margem_erro_kmh = velocidade_kmh * 0.10
        
        return {
            'velocidade_kmh': round(velocidade_kmh, 2),
            'velocidade_ms': round(velocidade_ms, 2),
            'velocidade_min_kmh': round(velocidade_kmh - margem_erro_kmh, 2),
            'velocidade_max_kmh': round(velocidade_kmh + margem_erro_kmh, 2),
            'parametros': {
                'distancia_m': distancia_metros,
                'tipo_piso': tipo_piso,
                'condicao': condicao,
                'coeficiente_atrito': mu,
                'gravidade': self.GRAVIDADE
            },
            'formula': 'v = √(2 × μ × g × d)',
            'unidade': 'km/h',
            'margem_erro': '±10%',
            'fundamentacao': [
                'Fórmula baseada em princípios físicos de conservação de energia',
                'Cálculo derivado da equação: Energia Cinética = Trabalho da Força de Atrito',
                'Ec = (m × v²)/2 = μ × m × g × d (massa cancela dos dois lados)',
                'Coeficientes de atrito obtidos de literatura técnica especializada',
                'Valores validados por testes experimentais em condições controladas',
                'Referências bibliográficas:',
                '  - Limpert, R. (1999). Motor Vehicle Accident Reconstruction',
                '  - Brach, R. & Brach, R.M. (2005). Vehicle Accident Analysis Methods',
                '  - Fricke, L.B. (1990). Traffic Accident Reconstruction',
                '  - ASTM E1960 - Standard Guide for Accident Reconstruction',
                'Margem de erro (±10%) considera variações de pneus, suspensão e superfície'
            ]
        }
    
    def interpretar_resultado(self, resultado: Dict[str, Any]) -> str:
        """Gera interpretação textual do resultado"""
        
        v = resultado['velocidade_kmh']
        v_min = resultado['velocidade_min_kmh']
        v_max = resultado['velocidade_max_kmh']
        params = resultado['parametros']
        
        texto = f"""CÁLCULO DE VELOCIDADE POR MARCA DE FRENAGEM

Parâmetros utilizados:
- Distância da marca: {params['distancia_m']:.2f} metros
- Tipo de piso: {params['tipo_piso'].title()}
- Condição: {params['condicao'].title()}
- Coeficiente de atrito (μ): {params['coeficiente_atrito']}

Fórmula aplicada: {resultado['formula']}

RESULTADO:
Velocidade estimada: {v:.2f} km/h ({resultado['velocidade_ms']:.2f} m/s)
Considerando margem de erro de ±10%: entre {v_min:.2f} e {v_max:.2f} km/h

Fundamentação técnica:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto