import math
from typing import Dict, Any, List, Tuple

class CalculadoraPontoImpacto:
    """
    Determina ponto de impacto baseado em marcas e danos
    Metodologia baseada em Rose & Fricke (2018)
    """
    
    def calcular_por_marcas_solo(
        self,
        marcas: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Calcula ponto de impacto baseado em marcas no solo
        
        Args:
            marcas: Lista de marcas com formato:
                [
                    {'tipo': 'arrasto', 'inicio_x': 0, 'inicio_y': 0, 'fim_x': 5, 'fim_y': 2},
                    {'tipo': 'raspagem', 'x': 2, 'y': 1}
                ]
        
        Returns:
            Coordenadas do ponto de impacto provável
        """
        
        if not marcas:
            raise ValueError("É necessário fornecer pelo menos uma marca")
        
        # Análise de marcas de arrasto (método de triangulação reversa)
        pontos_origem = []
        
        for marca in marcas:
            if marca['tipo'] == 'arrasto':
                # Ponto de impacto está na origem do arrasto
                pontos_origem.append({
                    'x': marca['inicio_x'],
                    'y': marca['inicio_y'],
                    'confianca': 0.9
                })
            elif marca['tipo'] == 'raspagem':
                # Raspagem indica proximidade do impacto
                pontos_origem.append({
                    'x': marca['x'],
                    'y': marca['y'],
                    'confianca': 0.7
                })
            elif marca['tipo'] == 'fluido':
                # Fluidos (óleo, líquido de arrefecimento) caem no impacto
                pontos_origem.append({
                    'x': marca['x'],
                    'y': marca['y'],
                    'confianca': 0.85
                })
        
        # Calcula centroide ponderado
        if pontos_origem:
            peso_total = sum(p['confianca'] for p in pontos_origem)
            x_medio = sum(p['x'] * p['confianca'] for p in pontos_origem) / peso_total
            y_medio = sum(p['y'] * p['confianca'] for p in pontos_origem) / peso_total
            
            # Calcula desvio (margem de erro espacial)
            desvio_x = math.sqrt(sum((p['x'] - x_medio)**2 for p in pontos_origem) / len(pontos_origem))
            desvio_y = math.sqrt(sum((p['y'] - y_medio)**2 for p in pontos_origem) / len(pontos_origem))
            
            return {
                'ponto_impacto_x': round(x_medio, 2),
                'ponto_impacto_y': round(y_medio, 2),
                'margem_erro_x': round(desvio_x, 2),
                'margem_erro_y': round(desvio_y, 2),
                'confianca_geral': round(sum(p['confianca'] for p in pontos_origem) / len(pontos_origem), 2),
                'marcas_analisadas': len(marcas),
                'fundamentacao': [
                    'Método de triangulação reversa baseado em marcas físicas',
                    'Centroide ponderado por confiabilidade de cada marca',
                    'Marcas de arrasto indicam origem do deslizamento pós-colisão',
                    'Fluidos derramados marcam proximidade do ponto de impacto',
                    'Referências:',
                    '  - Rose & Fricke (2018). Traffic Crash Reconstruction',
                    '  - Daily (2010). Accident Scene Documentation',
                    '  - Brach (2005). Impact Configuration Analysis'
                ]
            }
        
        raise ValueError("Nenhuma marca válida para análise")
    
    def calcular_por_danos(
        self,
        dano_veiculo1: Dict[str, Any],
        dano_veiculo2: Dict[str, Any],
        posicao_final_v1: Tuple[float, float],
        posicao_final_v2: Tuple[float, float]
    ) -> Dict[str, Any]:
        """
        Estima ponto de impacto baseado nos danos e posições finais
        
        Args:
            dano_veiculo1: {'localizacao': 'frontal_direita', 'severidade': 'alta'}
            dano_veiculo2: {'localizacao': 'lateral_esquerda', 'severidade': 'media'}
            posicao_final_v1: (x, y) coordenadas finais do veículo 1
            posicao_final_v2: (x, y) coordenadas finais do veículo 2
        """
        
        # Análise de compatibilidade de danos
        compatibilidade = self._analisar_compatibilidade_danos(dano_veiculo1, dano_veiculo2)
        
        # Estimativa de deslocamento pós-impacto baseado em severidade
        deslocamentos = {
            'baixa': 2.0,  # metros
            'media': 5.0,
            'alta': 10.0,
            'muito_alta': 15.0
        }
        
        desl_v1 = deslocamentos.get(dano_veiculo1.get('severidade', 'media'), 5.0)
        desl_v2 = deslocamentos.get(dano_veiculo2.get('severidade', 'media'), 5.0)
        
        # Retroage da posição final (engenharia reversa)
        # Assumindo direção aproximada baseada na localização do dano
        direcoes = {
            'frontal': 180,  # graus (veio de trás)
            'frontal_direita': 135,
            'lateral_direita': 90,
            'traseira_direita': 45,
            'traseira': 0,
            'lateral_esquerda': 270,
            'frontal_esquerda': 225
        }
        
        angulo_v1 = direcoes.get(dano_veiculo1.get('localizacao', 'frontal'), 180)
        angulo_v2 = direcoes.get(dano_veiculo2.get('localizacao', 'frontal'), 180)
        
        # Converte para radianos e calcula ponto de origem
        ang_v1_rad = math.radians(angulo_v1)
        ang_v2_rad = math.radians(angulo_v2)
        
        origem_v1_x = posicao_final_v1[0] + desl_v1 * math.cos(ang_v1_rad)
        origem_v1_y = posicao_final_v1[1] + desl_v1 * math.sin(ang_v1_rad)
        
        origem_v2_x = posicao_final_v2[0] + desl_v2 * math.cos(ang_v2_rad)
        origem_v2_y = posicao_final_v2[1] + desl_v2 * math.sin(ang_v2_rad)
        
        # Ponto médio entre as origens estimadas
        ponto_impacto_x = (origem_v1_x + origem_v2_x) / 2
        ponto_impacto_y = (origem_v1_y + origem_v2_y) / 2
        
        # Calcula incerteza (distância entre estimativas)
        incerteza = math.sqrt((origem_v2_x - origem_v1_x)**2 + (origem_v2_y - origem_v1_y)**2) / 2
        
        return {
            'ponto_impacto_x': round(ponto_impacto_x, 2),
            'ponto_impacto_y': round(ponto_impacto_y, 2),
            'incerteza_metros': round(incerteza, 2),
            'compatibilidade_danos': compatibilidade,
            'confianca': 'media' if incerteza < 3 else 'baixa',
            'fundamentacao': [
                'Método de análise reversa baseado em danos e posição final',
                'Estimativa de deslocamento pós-impacto por severidade',
                'Compatibilidade geométrica entre danos dos veículos',
                'Incerteza proporcional à distância entre estimativas',
                'Referências:',
                '  - Brach (2005). Vehicle Accident Analysis Methods',
                '  - Daily (2010). Damage Analysis and Reconstruction',
                '  - SAE J224 - Collision Deformation Classification'
            ]
        }
    
    def _analisar_compatibilidade_danos(self, dano1: Dict, dano2: Dict) -> str:
        """Verifica se os danos são geometricamente compatíveis"""
        
        # Pares compatíveis (onde um atinge o outro)
        compatibilidades = {
            'frontal': ['traseira', 'lateral_esquerda', 'lateral_direita'],
            'frontal_direita': ['lateral_esquerda', 'traseira_esquerda'],
            'frontal_esquerda': ['lateral_direita', 'traseira_direita'],
            'lateral_direita': ['lateral_esquerda', 'frontal', 'frontal_esquerda'],
            'lateral_esquerda': ['lateral_direita', 'frontal', 'frontal_direita'],
            'traseira': ['frontal', 'frontal_direita', 'frontal_esquerda']
        }
        
        loc1 = dano1.get('localizacao', '')
        loc2 = dano2.get('localizacao', '')
        
        if loc2 in compatibilidades.get(loc1, []):
            return 'COMPATÍVEL'
        else:
            return 'INCOMPATÍVEL (verifique análise)'
    
    def interpretar_resultado(self, resultado: Dict[str, Any]) -> str:
        """Interpretação do ponto de impacto"""
        
        x = resultado['ponto_impacto_x']
        y = resultado['ponto_impacto_y']
        
        if 'margem_erro_x' in resultado:
            # Resultado por marcas
            texto = f"""DETERMINAÇÃO DO PONTO DE IMPACTO (Por Marcas no Solo)

Coordenadas estimadas:
- X: {x:.2f} m (±{resultado['margem_erro_x']:.2f} m)
- Y: {y:.2f} m (±{resultado['margem_erro_y']:.2f} m)

Confiabilidade: {resultado['confianca_geral']*100:.0f}%
Marcas analisadas: {resultado['marcas_analisadas']}

INTERPRETAÇÃO:
O ponto de impacto foi determinado através da análise de marcas físicas no solo.
A margem de erro considera a dispersão espacial das marcas encontradas.
Quanto maior o número de marcas consistentes, maior a precisão.

Fundamentação:
"""
            for fund in resultado['fundamentacao']:
                texto += f"{fund}\n"
        
        else:
            # Resultado por danos
            texto = f"""ESTIMATIVA DO PONTO DE IMPACTO (Por Análise de Danos)

Coordenadas estimadas:
- X: {x:.2f} m
- Y: {y:.2f} m

Incerteza: ±{resultado['incerteza_metros']:.2f} m
Compatibilidade dos danos: {resultado['compatibilidade_danos']}
Confiabilidade: {resultado['confianca'].upper()}

INTERPRETAÇÃO:
Este método estima o ponto através de engenharia reversa dos danos e posições finais.
A incerteza reflete a complexidade da dinâmica pós-impacto.
{'ATENÇÃO: Danos incompatíveis sugerem revisão da análise.' if resultado['compatibilidade_danos'] == 'INCOMPATÍVEL' else 'Danos geometricamente compatíveis reforçam a estimativa.'}

Fundamentação:
"""
            for fund in resultado['fundamentacao']:
                texto += f"{fund}\n"
        
        return texto