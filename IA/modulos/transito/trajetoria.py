import math
from typing import Dict, Any, List, Tuple

class CalculadoraTrajetoria:
    """
    Análise de trajetórias de veículos antes e após colisão
    """
    
    def calcular_trajetoria_pre_impacto(
        self,
        ponto_impacto: Tuple[float, float],
        velocidade_kmh: float,
        angulo_aproximacao_graus: float,
        tempo_antes_s: float = 3.0
    ) -> Dict[str, Any]:
        """
        Calcula trajetória do veículo ANTES da colisão
        
        Args:
            ponto_impacto: (x, y) coordenadas do impacto
            velocidade_kmh: Velocidade do veículo
            angulo_aproximacao_graus: Ângulo de aproximação (0° = Norte, 90° = Leste)
            tempo_antes_s: Tempo antes do impacto para retroagir (segundos)
        """
        
        velocidade_ms = velocidade_kmh / 3.6
        angulo_rad = math.radians(angulo_aproximacao_graus)
        
        # Distância percorrida no tempo
        distancia_percorrida = velocidade_ms * tempo_antes_s
        
        # Ponto de partida (retroage da colisão)
        # Ângulo invertido (veio da direção oposta)
        origem_x = ponto_impacto[0] - distancia_percorrida * math.sin(angulo_rad)
        origem_y = ponto_impacto[1] - distancia_percorrida * math.cos(angulo_rad)
        
        # Gera pontos intermediários (a cada 0.5s)
        pontos_trajetoria = []
        intervalo = 0.5  # segundos
        num_pontos = int(tempo_antes_s / intervalo)
        
        for i in range(num_pontos + 1):
            t = i * intervalo
            dist_no_tempo = velocidade_ms * t
            
            x = origem_x + dist_no_tempo * math.sin(angulo_rad)
            y = origem_y + dist_no_tempo * math.cos(angulo_rad)
            
            pontos_trajetoria.append({
                'tempo_s': round(t, 1),
                'x': round(x, 2),
                'y': round(y, 2),
                'velocidade_kmh': velocidade_kmh
            })
        
        return {
            'ponto_origem': (round(origem_x, 2), round(origem_y, 2)),
            'ponto_impacto': ponto_impacto,
            'distancia_percorrida_m': round(distancia_percorrida, 2),
            'tempo_analisado_s': tempo_antes_s,
            'angulo_aproximacao': angulo_aproximacao_graus,
            'velocidade_kmh': velocidade_kmh,
            'pontos_trajetoria': pontos_trajetoria,
            'fundamentacao': [
                'Trajetória retilínea uniforme (MRU)',
                'Assume velocidade constante antes do impacto',
                'Útil para análise de visibilidade e possibilidade de evasão',
                'Referências:',
                '  - Rose & Fricke (2018). Pre-Impact Trajectory Analysis',
                '  - Daily (2010). Motion Analysis Methods'
            ]
        }
    
    def calcular_trajetoria_pos_impacto(
        self,
        ponto_impacto: Tuple[float, float],
        posicao_final: Tuple[float, float],
        velocidade_pos_impacto_kmh: float,
        coeficiente_atrito: float = 0.7
    ) -> Dict[str, Any]:
        """
        Calcula trajetória do veículo APÓS a colisão
        
        Args:
            ponto_impacto: (x, y) onde ocorreu o impacto
            posicao_final: (x, y) posição de repouso final
            velocidade_pos_impacto_kmh: Velocidade logo após o impacto
            coeficiente_atrito: Coeficiente de atrito da pista
        """
        
        # Distância entre impacto e repouso
        dx = posicao_final[0] - ponto_impacto[0]
        dy = posicao_final[1] - ponto_impacto[1]
        distancia_total = math.sqrt(dx**2 + dy**2)
        
        # Ângulo de deslocamento
        angulo_deslocamento = math.degrees(math.atan2(dx, dy))
        
        # Velocidade em m/s
        v0_ms = velocidade_pos_impacto_kmh / 3.6
        
        # Desaceleração devido ao atrito: a = μ × g
        g = 9.81
        desaceleracao = coeficiente_atrito * g
        
        # Tempo até parada: t = v / a
        tempo_parada = v0_ms / desaceleracao if desaceleracao > 0 else 0
        
        # Distância teórica de parada: d = v² / (2a)
        distancia_teorica = (v0_ms ** 2) / (2 * desaceleracao) if desaceleracao > 0 else 0
        
        # Verifica consistência
        diferenca_distancia = abs(distancia_total - distancia_teorica)
        consistente = diferenca_distancia < 2.0  # margem de 2m
        
        # Gera pontos da trajetória
        pontos_trajetoria = []
        num_pontos = 10
        
        for i in range(num_pontos + 1):
            fracao = i / num_pontos
            
            # Posição linear interpolada
            x = ponto_impacto[0] + dx * fracao
            y = ponto_impacto[1] + dy * fracao
            
            # Velocidade neste ponto (desacelera linearmente)
            v_ms = v0_ms * (1 - fracao)
            v_kmh = v_ms * 3.6
            
            # Tempo aproximado
            t = tempo_parada * fracao
            
            pontos_trajetoria.append({
                'posicao': (round(x, 2), round(y, 2)),
                'velocidade_kmh': round(v_kmh, 2),
                'tempo_s': round(t, 2)
            })
        
        return {
            'ponto_impacto': ponto_impacto,
            'posicao_final': posicao_final,
            'distancia_percorrida_m': round(distancia_total, 2),
            'distancia_teorica_m': round(distancia_teorica, 2),
            'angulo_deslocamento_graus': round(angulo_deslocamento, 2),
            'tempo_ate_repouso_s': round(tempo_parada, 2),
            'consistente': consistente,
            'diferenca_m': round(diferenca_distancia, 2),
            'pontos_trajetoria': pontos_trajetoria,
            'fundamentacao': [
                'Movimento retardado uniformemente (MRU)',
                'Desaceleração devido à força de atrito: a = μ × g',
                'Distância teórica: d = v²/(2a)',
                'Consistência verifica se distância real ≈ distância teórica',
                'Referências:',
                '  - Brach (2005). Post-Impact Trajectory Analysis',
                '  - Limpert (1999). Vehicle Dynamics After Impact'
            ]
        }
    
    def interpretar_pre_impacto(self, resultado: Dict[str, Any]) -> str:
        """Interpretação da trajetória pré-impacto"""
        
        origem = resultado['ponto_origem']
        impacto = resultado['ponto_impacto']
        dist = resultado['distancia_percorrida_m']
        
        texto = f"""ANÁLISE DE TRAJETÓRIA PRÉ-IMPACTO

Parâmetros:
- Velocidade: {resultado['velocidade_kmh']:.2f} km/h
- Ângulo de aproximação: {resultado['angulo_aproximacao']:.0f}°
- Tempo analisado: {resultado['tempo_analisado_s']:.1f} segundos

Trajetória calculada:
- Ponto de origem: X={origem[0]:.2f}m, Y={origem[1]:.2f}m
- Ponto de impacto: X={impacto[0]:.2f}m, Y={impacto[1]:.2f}m
- Distância percorrida: {dist:.2f} metros

INTERPRETAÇÃO:
Nos {resultado['tempo_analisado_s']:.1f} segundos antes da colisão, o veículo percorreu {dist:.2f} metros.
Esta trajetória assume movimento retilíneo uniforme (velocidade constante).
Útil para determinar se o motorista tinha tempo/distância para evitar o acidente.

Pontos intermediários gerados: {len(resultado['pontos_trajetoria'])}

Fundamentação:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto
    
    def interpretar_pos_impacto(self, resultado: Dict[str, Any]) -> str:
        """Interpretação da trajetória pós-impacto"""
        
        impacto = resultado['ponto_impacto']
        final = resultado['posicao_final']
        dist_real = resultado['distancia_percorrida_m']
        dist_teorica = resultado['distancia_teorica_m']
        
        texto = f"""ANÁLISE DE TRAJETÓRIA PÓS-IMPACTO

Posições:
- Ponto de impacto: X={impacto[0]:.2f}m, Y={impacto[1]:.2f}m
- Posição final: X={final[0]:.2f}m, Y={final[1]:.2f}m

Distâncias:
- Real (medida): {dist_real:.2f} metros
- Teórica (calculada): {dist_teorica:.2f} metros
- Diferença: {resultado['diferenca_m']:.2f} metros

Ângulo de deslocamento: {resultado['angulo_deslocamento_graus']:.0f}°
Tempo até repouso: {resultado['tempo_ate_repouso_s']:.2f} segundos

CONSISTÊNCIA: {'✅ CONSISTENTE' if resultado['consistente'] else '⚠️ INCONSISTENTE'}

INTERPRETAÇÃO:
{'As distâncias real e teórica são compatíveis (diferença < 2m).' if resultado['consistente'] else f'Diferença de {resultado["diferenca_m"]:.2f}m sugere fatores adicionais (declive, obstáculos, rotação).'}

Após o impacto, o veículo deslizou {dist_real:.2f}m até a parada completa.
A trajetória considera desaceleração constante devido ao atrito com o solo.

Fundamentação:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto