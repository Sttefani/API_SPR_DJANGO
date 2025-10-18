import math
from typing import Dict, Any, List

class CalculadoraArrastamentoSolo:
    """
    Calcula velocidade baseado em marca de arrastamento pós-colisão
    Diferente da frenagem: aqui o veículo já está sem controle
    """
    
    # Coeficientes para arrastamento (diferentes de frenagem!)
    # Fonte: Limpert (1999), Rose & Fricke (2018)
    COEFICIENTES = {
        'moto_deitada_asfalto_seco': 0.65,  # Valor médio (0.5-0.8)
        'moto_deitada_asfalto_molhado': 0.45,
        'carro_capotado_asfalto': 0.55,
        'carro_lateral_asfalto': 0.60,
    }
    
    GRAVIDADE = 9.81  # m/s²
    
    def calcular_com_margem_erro(
        self,
        distancia_metros: float,
        coeficiente_medio: float = 0.65,
        coef_min: float = 0.5,
        coef_max: float = 0.8
    ) -> Dict[str, Any]:
        """
        Calcula velocidade de arrastamento com margem de erro
        
        Metodologia do laudo fornecido (seção 4.1.4)
        
        Args:
            distancia_metros: Distância da marca de arrastamento
            coeficiente_medio: Coeficiente médio (padrão 0.65)
            coef_min: Coeficiente mínimo (padrão 0.5)
            coef_max: Coeficiente máximo (padrão 0.8)
        """
        
        if distancia_metros <= 0:
            raise ValueError("Distância deve ser maior que zero")
        
        # Cálculo com valor médio
        v_medio_ms = math.sqrt(2 * coeficiente_medio * self.GRAVIDADE * distancia_metros)
        v_medio_kmh = v_medio_ms * 3.6
        
        # Cálculo com valor mínimo
        v_min_ms = math.sqrt(2 * coef_min * self.GRAVIDADE * distancia_metros)
        v_min_kmh = v_min_ms * 3.6
        
        # Cálculo com valor máximo
        v_max_ms = math.sqrt(2 * coef_max * self.GRAVIDADE * distancia_metros)
        v_max_kmh = v_max_ms * 3.6
        
        # Margens de erro
        erro_absoluto_inf = abs(v_medio_ms - v_min_ms)
        erro_absoluto_sup = abs(v_medio_ms - v_max_ms)
        erro_absoluto_max = max(erro_absoluto_inf, erro_absoluto_sup)
        
        erro_percentual_inf = (erro_absoluto_inf / v_medio_ms) * 100
        erro_percentual_sup = (erro_absoluto_sup / v_medio_ms) * 100
        
        return {
            'velocidade_media_kmh': round(v_medio_kmh, 2),
            'velocidade_media_ms': round(v_medio_ms, 2),
            'velocidade_min_kmh': round(v_min_kmh, 2),
            'velocidade_max_kmh': round(v_max_kmh, 2),
            'erro_absoluto_ms': round(erro_absoluto_max, 2),
            'erro_percentual_min': round(erro_percentual_inf, 2),
            'erro_percentual_max': round(erro_percentual_sup, 2),
            'parametros': {
                'distancia_m': distancia_metros,
                'coef_medio': coeficiente_medio,
                'coef_min': coef_min,
                'coef_max': coef_max,
                'gravidade': self.GRAVIDADE
            },
            'formula': 'v = √(2 × μ × g × d)',
            'fundamentacao': [
                'Cálculo baseado no Teorema do Trabalho e Energia',
                'Energia cinética dissipada = Trabalho da força de atrito',
                'Ec = (m × v²)/2 = μ × m × g × d (massa cancela)',
                'Margem de erro considera variação do coeficiente de atrito',
                'Arrastamento difere de frenagem (veículo sem controle)',
                'Referências:',
                '  - Rose, N.A. & Fricke, L.B. (2018). Traffic Crash Reconstruction',
                '  - Daily, J. (2010). Fundamentals of Traffic Crash Reconstruction',
                '  - Limpert, R. (1999). Motor Vehicle Accident Reconstruction'
            ]
        }
    
    def interpretar_resultado(self, resultado: Dict[str, Any]) -> str:
        """Interpretação do cálculo de arrastamento"""
        
        params = resultado['parametros']
        v_med = resultado['velocidade_media_kmh']
        v_min = resultado['velocidade_min_kmh']
        v_max = resultado['velocidade_max_kmh']
        erro_pct = resultado['erro_percentual_max']
        
        texto = f"""CÁLCULO DE VELOCIDADE POR MARCA DE ARRASTAMENTO

Parâmetros:
- Distância de arrastamento: {params['distancia_m']:.2f} metros
- Coeficiente de atrito médio (μ): {params['coef_medio']}
- Coeficiente mínimo: {params['coef_min']}
- Coeficiente máximo: {params['coef_max']}

Fórmula: {resultado['formula']}

RESULTADO:
Velocidade média no início do arrastamento: {v_med:.2f} km/h ({resultado['velocidade_media_ms']:.2f} m/s)

MARGEM DE ERRO:
Considerando variação do coeficiente de atrito:
- Velocidade pode variar entre {v_min:.2f} km/h e {v_max:.2f} km/h
- Margem de erro percentual: ±{erro_pct:.2f}%

INTERPRETAÇÃO:
Esta é a velocidade que o veículo tinha no INÍCIO do arrastamento,
imediatamente após a colisão ou perda de controle.
NÃO é a velocidade no momento do impacto (que era maior).

Fundamentação:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto