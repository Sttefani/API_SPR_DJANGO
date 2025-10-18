import math
from typing import Dict, Any

class CalculadoraEnergiaCinetica:
    """
    Calculadora de energia cinética em acidentes de trânsito
    Fundamental para análise de severidade de colisões
    """
    
    # Constantes para comparações
    EQUIVALENCIAS = {
        'queda_1m': 9.81,  # Joules por kg
        'queda_10m': 98.1,
        'explosao_granada': 400000,  # ~400kJ
    }
    
    def calcular(
        self,
        massa_kg: float,
        velocidade_kmh: float
    ) -> Dict[str, Any]:
        """
        Calcula energia cinética do veículo
        
        Fórmula: Ec = (m × v²) / 2
        
        Args:
            massa_kg: Massa do veículo em kg
            velocidade_kmh: Velocidade em km/h
            
        Returns:
            Dict com resultado e comparações
        """
        
        # Validações
        if massa_kg <= 0:
            raise ValueError("Massa deve ser maior que zero")
        if velocidade_kmh < 0:
            raise ValueError("Velocidade não pode ser negativa")
        
        # Conversão para m/s
        velocidade_ms = velocidade_kmh / 3.6
        
        # Cálculo da energia cinética
        energia_joules = (massa_kg * velocidade_ms ** 2) / 2
        energia_kj = energia_joules / 1000
        
        # Energia por kg (para comparações)
        energia_por_kg = energia_joules / massa_kg
        
        # Comparações intuitivas
        equivalente_queda = energia_por_kg / 9.81  # metros de queda
        
        return {
            'energia_joules': round(energia_joules, 2),
            'energia_kilojoules': round(energia_kj, 2),
            'energia_por_kg': round(energia_por_kg, 2),
            'equivalente_queda_metros': round(equivalente_queda, 2),
            'parametros': {
                'massa_kg': massa_kg,
                'velocidade_kmh': velocidade_kmh,
                'velocidade_ms': round(velocidade_ms, 2)
            },
            'formula': 'Ec = (m × v²) / 2',
            'unidade': 'Joules (J)',
            'fundamentacao': [
                'Fórmula clássica de energia cinética da mecânica newtoniana',
                'Representa a energia que deve ser dissipada para parar o veículo',
                'Fundamental para análise de severidade de colisões',
                'Energia aumenta com o QUADRADO da velocidade (duplicar v = 4x energia)',
                'Referências bibliográficas:',
                '  - Brach, R.M. (2005). Mechanical Impact Dynamics',
                '  - Limpert, R. (1999). Motor Vehicle Accident Reconstruction',
                '  - SAE J224 - Collision Deformation Classification'
            ]
        }
    
    def interpretar_resultado(self, resultado: Dict[str, Any]) -> str:
        """Gera interpretação do cálculo de energia"""
        
        params = resultado['parametros']
        ec_j = resultado['energia_joules']
        ec_kj = resultado['energia_kilojoules']
        queda = resultado['equivalente_queda_metros']
        
        texto = f"""CÁLCULO DE ENERGIA CINÉTICA

Parâmetros:
- Massa do veículo: {params['massa_kg']:.0f} kg
- Velocidade: {params['velocidade_kmh']:.2f} km/h ({params['velocidade_ms']:.2f} m/s)

Fórmula: {resultado['formula']}

RESULTADO:
Energia cinética: {ec_kj:.2f} kJ ({ec_j:.2f} Joules)

INTERPRETAÇÃO:
- Energia equivale a uma queda de {queda:.1f} metros de altura
- Essa energia precisa ser dissipada na colisão (deformação + calor)
- Dobrar a velocidade QUADRUPLICA a energia!

Fundamentação:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto
    
    def comparar_velocidades(self, massa_kg: float, velocidades: list) -> str:
        """Compara energia em diferentes velocidades"""
        
        texto = f"\nCOMPARAÇÃO DE ENERGIAS (Veículo de {massa_kg:.0f} kg):\n\n"
        
        for vel in velocidades:
            resultado = self.calcular(massa_kg, vel)
            ec_kj = resultado['energia_kilojoules']
            texto += f"  {vel:>3.0f} km/h → {ec_kj:>8.2f} kJ\n"
        
        return texto