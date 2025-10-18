import math
from typing import Dict, Any

class CalculadoraVelocidadeDanos:
    """
    Calcula velocidade baseado em danos dos veículos (EES)
    Metodologia do laudo: seção 4.1.4.3
    """
    
    def calcular_energia_cinetica_simples(
        self,
        massa_kg: float,
        velocidade_kmh: float
    ) -> float:
        """Calcula energia cinética em Joules"""
        velocidade_ms = velocidade_kmh / 3.6
        return 0.5 * massa_kg * (velocidade_ms ** 2)
    
    def calcular_velocidade_por_energia(
        self,
        energia_joules: float,
        massa_kg: float
    ) -> float:
        """Calcula velocidade a partir de energia (reverso)"""
        # E = (m × v²)/2  →  v = √(2E/m)
        velocidade_ms = math.sqrt((2 * energia_joules) / massa_kg)
        return velocidade_ms * 3.6
    
    def calcular_velocidade_dano_colisao(
        self,
        massa_veiculo1_kg: float,
        velocidade_veiculo1_kmh: float,
        massa_veiculo2_kg: float,
        velocidade_veiculo2_kmh: float,
        mesmo_sentido: bool = True
    ) -> Dict[str, Any]:
        """
        Calcula velocidade de dano em colisão entre dois veículos
        
        Metodologia do laudo (seção 4.1.4.3):
        - Calcula energia de cada veículo
        - Soma ou subtrai dependendo do sentido
        - Retorna velocidade combinada
        
        Args:
            massa_veiculo1_kg: Massa do veículo 1 (ex: moto)
            velocidade_veiculo1_kmh: Velocidade do veículo 1
            massa_veiculo2_kg: Massa do veículo 2 (ex: pickup)
            velocidade_veiculo2_kmh: Velocidade do veículo 2
            mesmo_sentido: True se colidem no mesmo sentido
        """
        
        # Energias individuais
        e1 = self.calcular_energia_cinetica_simples(massa_veiculo1_kg, velocidade_veiculo1_kmh)
        e2 = self.calcular_energia_cinetica_simples(massa_veiculo2_kg, velocidade_veiculo2_kmh)
        
        # Velocidades combinadas
        if mesmo_sentido:
            # Exemplo do laudo: moto 60km/h + pickup 12km/h = 72km/h
            velocidade_dano = velocidade_veiculo1_kmh + velocidade_veiculo2_kmh
        else:
            # Colisão frontal
            velocidade_dano = velocidade_veiculo1_kmh - velocidade_veiculo2_kmh
        
        return {
            'velocidade_dano_kmh': abs(round(velocidade_dano, 2)),
            'energia_veiculo1_joules': round(e1, 2),
            'energia_veiculo2_joules': round(e2, 2),
            'energia_total_joules': round(e1 + e2, 2),
            'parametros': {
                'massa1_kg': massa_veiculo1_kg,
                'vel1_kmh': velocidade_veiculo1_kmh,
                'massa2_kg': massa_veiculo2_kg,
                'vel2_kmh': velocidade_veiculo2_kmh,
                'mesmo_sentido': mesmo_sentido
            },
            'formula': 'V_dano = V1 + V2 (mesmo sentido) ou V1 - V2 (sentido oposto)',
            'fundamentacao': [
                'Velocidade Equivalente de Dano (EES - Energy Equivalent Speed)',
                'Princípio da Conservação de Energia aplicado',
                'Energia cinética convertida em trabalho de deformação',
                'Método simplificado para estimativa inicial',
                'Referências:',
                '  - Rose & Fricke (2018). Traffic Crash Reconstruction',
                '  - SAE J224 - Collision Deformation Classification',
                '  - Daily (2010). Traffic Crash Reconstruction Methods'
            ]
        }
    
    def calcular_velocidade_total_estimada(
        self,
        velocidade_dano_kmh: float,
        velocidade_arrasto_kmh: float
    ) -> Dict[str, Any]:
        """
        Calcula velocidade total pré-impacto
        
        Metodologia do laudo (final da seção 4.1.4.3):
        V_total = √(V_dano² + V_arrasto²)
        
        Args:
            velocidade_dano_kmh: Velocidade de dano calculada
            velocidade_arrasto_kmh: Velocidade de arrastamento
        """
        
        # Fórmula do laudo
        velocidade_total = math.sqrt(
            (velocidade_dano_kmh ** 2) + (velocidade_arrasto_kmh ** 2)
        )
        
        return {
            'velocidade_total_kmh': round(velocidade_total, 2),
            'velocidade_dano_kmh': velocidade_dano_kmh,
            'velocidade_arrasto_kmh': velocidade_arrasto_kmh,
            'formula': 'V_total = √(V_dano² + V_arrasto²)',
            'fundamentacao': [
                'Combinação vetorial de velocidades',
                'V_dano: velocidade relativa da colisão',
                'V_arrasto: velocidade residual pós-colisão',
                'Soma vetorial considera ambas as componentes',
                'Referências:',
                '  - Daily, J. (2010). Fundamentals of Traffic Crash Reconstruction',
                '  - Rose & Fricke (2018). Traffic Crash Reconstruction'
            ]
        }
    
    def interpretar_velocidade_dano(self, resultado: Dict[str, Any]) -> str:
        """Interpretação do resultado de velocidade de dano"""
        
        params = resultado['parametros']
        v_dano = resultado['velocidade_dano_kmh']
        e1 = resultado['energia_veiculo1_joules']
        e2 = resultado['energia_veiculo2_joules']
        
        texto = f"""CÁLCULO DE VELOCIDADE DE DANO (EES)

Parâmetros:
- Veículo 1: {params['massa1_kg']:.0f} kg a {params['vel1_kmh']:.2f} km/h
- Veículo 2: {params['massa2_kg']:.0f} kg a {params['vel2_kmh']:.2f} km/h
- Sentido: {'Mesmo sentido' if params['mesmo_sentido'] else 'Sentidos opostos'}

Energias:
- Veículo 1: {e1/1000:.2f} kJ
- Veículo 2: {e2/1000:.2f} kJ

RESULTADO:
Velocidade de dano combinada: {v_dano:.2f} km/h

INTERPRETAÇÃO:
Esta é a velocidade relativa efetiva da colisão.
Representa a "severidade" do impacto em termos de energia dissipada.

Fundamentação:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto
    
    def interpretar_velocidade_total(self, resultado: Dict[str, Any]) -> str:
        """Interpretação da velocidade total estimada"""
        
        v_total = resultado['velocidade_total_kmh']
        v_dano = resultado['velocidade_dano_kmh']
        v_arrasto = resultado['velocidade_arrasto_kmh']
        
        texto = f"""CÁLCULO DE VELOCIDADE TOTAL ESTIMADA (PRÉ-IMPACTO)

Componentes:
- Velocidade de dano (colisão): {v_dano:.2f} km/h
- Velocidade de arrastamento (pós-colisão): {v_arrasto:.2f} km/h

Fórmula: {resultado['formula']}

RESULTADO:
Velocidade total estimada no momento do impacto: {v_total:.2f} km/h

INTERPRETAÇÃO:
Esta é a velocidade estimada do veículo ANTES da colisão.
Combina:
1. Energia usada para causar danos (velocidade de dano)
2. Energia residual após colisão (velocidade de arrastamento)

A soma vetorial captura o movimento total do veículo no momento do impacto.

Fundamentação:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto