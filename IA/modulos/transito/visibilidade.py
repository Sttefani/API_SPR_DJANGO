import math
from typing import Dict, Any, List, Tuple, Optional

class CalculadoraVisibilidade:
    """
    Análise de visibilidade e linha de visada
    Considera obstáculos, vegetação, curvatura, topografia
    
    Baseado na metodologia do laudo (seção sobre vegetação bloqueando visão)
    """
    
    def calcular_linha_visada(
        self,
        observador: Dict[str, Any],
        alvo: Dict[str, Any],
        obstaculos: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calcula se há linha de visada livre entre dois pontos
        
        Args:
            observador: {
                'posicao': (x, y, z),  # z = altura dos olhos
                'altura_olhos_m': 1.65  # altura padrão sentado em carro
            }
            alvo: {
                'posicao': (x, y, z),
                'altura_m': 1.4  # altura do que se quer ver (ex: moto)
            }
            obstaculos: [
                {
                    'tipo': 'vegetacao',
                    'posicao': (x, y),
                    'altura_m': 1.6,
                    'largura_m': 3.0
                }
            ]
        """
        
        pos_obs = observador['posicao']
        pos_alvo = alvo['posicao']
        altura_olhos = observador.get('altura_olhos_m', 1.65)
        altura_alvo = alvo.get('altura_m', 1.4)
        
        # Distância horizontal
        dx = pos_alvo[0] - pos_obs[0]
        dy = pos_alvo[1] - pos_obs[1]
        distancia_horizontal = math.sqrt(dx**2 + dy**2)
        
        # Diferença de altura
        dz = (pos_alvo[2] + altura_alvo) - (pos_obs[2] + altura_olhos)
        
        # Ângulo de elevação da linha de visada
        angulo_elevacao = math.degrees(math.atan2(dz, distancia_horizontal))
        
        # Verifica obstáculos
        bloqueios = []
        visibilidade_livre = True
        
        if obstaculos:
            for obstaculo in obstaculos:
                bloqueio = self._verificar_bloqueio(
                    pos_obs, altura_olhos,
                    pos_alvo, altura_alvo,
                    obstaculo
                )
                
                if bloqueio['bloqueia']:
                    bloqueios.append(bloqueio)
                    visibilidade_livre = False
        
        return {
            'distancia_horizontal_m': round(distancia_horizontal, 2),
            'diferenca_altura_m': round(dz, 2),
            'angulo_elevacao_graus': round(angulo_elevacao, 2),
            'visibilidade_livre': visibilidade_livre,
            'bloqueios_encontrados': bloqueios,
            'numero_obstaculos_analisados': len(obstaculos) if obstaculos else 0,
            'altura_observador_m': altura_olhos,
            'altura_alvo_m': altura_alvo,
            'fundamentacao': [
                'Análise geométrica de linha de visada',
                'Considera altura do observador e do objeto observado',
                'Verifica interseção com obstáculos no caminho',
                'Referências:',
                '  - AASHTO Green Book - Sight Distance',
                '  - Rose & Fricke (2018). Visibility Analysis',
                '  - MUTCD - Intersection Sight Distance'
            ]
        }
    
    def _verificar_bloqueio(
        self,
        pos_obs: Tuple,
        altura_obs: float,
        pos_alvo: Tuple,
        altura_alvo: float,
        obstaculo: Dict
    ) -> Dict[str, Any]:
        """Verifica se obstáculo bloqueia linha de visada"""
        
        pos_obst = obstaculo['posicao']
        altura_obst = obstaculo['altura_m']
        
        # Distância do observador ao obstáculo
        dx_obst = pos_obst[0] - pos_obs[0]
        dy_obst = pos_obst[1] - pos_obs[1]
        dist_obst = math.sqrt(dx_obst**2 + dy_obst**2)
        
        # Distância total observador-alvo
        dx_total = pos_alvo[0] - pos_obs[0]
        dy_total = pos_alvo[1] - pos_obs[1]
        dist_total = math.sqrt(dx_total**2 + dy_total**2)
        
        # Verifica se obstáculo está no caminho (produto escalar)
        if dist_total > 0:
            projecao = (dx_obst * dx_total + dy_obst * dy_total) / dist_total
            
            # Se projeção está fora do segmento, não bloqueia
            if projecao < 0 or projecao > dist_total:
                return {
                    'bloqueia': False,
                    'razao': 'Obstáculo fora da linha de visada'
                }
            
            # Distância perpendicular do obstáculo à linha
            dist_perp = abs(dx_obst * dy_total - dy_obst * dx_total) / dist_total
            
            # Se muito longe lateralmente, não bloqueia
            largura_obst = obstaculo.get('largura_m', 1.0)
            if dist_perp > largura_obst / 2:
                return {
                    'bloqueia': False,
                    'razao': 'Obstáculo lateral à linha de visada'
                }
        
        # Altura da linha de visada no ponto do obstáculo
        if dist_total > 0:
            fracao = dist_obst / dist_total
            dz_total = (pos_alvo[2] + altura_alvo) - (pos_obs[2] + altura_obs)
            altura_linha_no_obstaculo = pos_obs[2] + altura_obs + (dz_total * fracao)
            
            # Compara com altura do obstáculo
            if altura_obst >= altura_linha_no_obstaculo:
                return {
                    'bloqueia': True,
                    'tipo': obstaculo['tipo'],
                    'altura_bloqueio_m': altura_obst,
                    'altura_necessaria_m': altura_linha_no_obstaculo,
                    'diferenca_m': altura_obst - altura_linha_no_obstaculo,
                    'distancia_do_observador_m': round(dist_obst, 2),
                    'razao': f"{obstaculo['tipo'].title()} de {altura_obst:.2f}m bloqueia linha de visada a {altura_linha_no_obstaculo:.2f}m"
                }
        
        return {
            'bloqueia': False,
            'razao': 'Obstáculo abaixo da linha de visada'
        }
    
    def calcular_distancia_visibilidade_minima(
        self,
        velocidade_kmh: float,
        tempo_reacao_s: float = 1.5,
        tempo_frenagem_s: float = 3.0
    ) -> Dict[str, Any]:
        """
        Calcula distância mínima de visibilidade necessária
        
        Baseado em AASHTO Green Book
        
        Args:
            velocidade_kmh: Velocidade do veículo
            tempo_reacao_s: Tempo de reação do motorista
            tempo_frenagem_s: Tempo estimado de frenagem até parada
        """
        
        velocidade_ms = velocidade_kmh / 3.6
        
        # Distância percorrida durante reação
        dist_reacao = velocidade_ms * tempo_reacao_s
        
        # Distância percorrida durante frenagem
        dist_frenagem = velocidade_ms * tempo_frenagem_s / 2  # média
        
        # Distância total necessária
        dist_total = dist_reacao + dist_frenagem
        
        # Margem de segurança (AASHTO recomenda +25%)
        margem_seguranca = dist_total * 0.25
        dist_recomendada = dist_total + margem_seguranca
        
        return {
            'distancia_minima_m': round(dist_total, 2),
            'distancia_recomendada_m': round(dist_recomendada, 2),
            'distancia_reacao_m': round(dist_reacao, 2),
            'distancia_frenagem_m': round(dist_frenagem, 2),
            'margem_seguranca_m': round(margem_seguranca, 2),
            'velocidade_kmh': velocidade_kmh,
            'tempo_reacao_s': tempo_reacao_s,
            'tempo_frenagem_s': tempo_frenagem_s,
            'fundamentacao': [
                'Distância mínima de visibilidade (Sight Distance)',
                'Baseado em: AASHTO - A Policy on Geometric Design',
                'Considera tempo de reação + tempo de frenagem',
                'Margem de segurança de 25% sobre o mínimo',
                'Fundamental para projeto de vias e análise de acidentes',
                'Referências:',
                '  - AASHTO Green Book (2018)',
                '  - MUTCD - Sight Distance Requirements'
            ]
        }
    
    def analisar_triangulo_visibilidade_intersecao(
        self,
        velocidade_via_principal_kmh: float,
        velocidade_via_secundaria_kmh: float,
        angulo_intersecao_graus: float = 90,
        tempo_atravessamento_s: float = 5.0
    ) -> Dict[str, Any]:
        """
        Calcula triângulo de visibilidade necessário em interseção
        
        Metodologia AASHTO para sight triangle
        
        Args:
            velocidade_via_principal_kmh: Velocidade da via principal
            velocidade_via_secundaria_kmh: Velocidade da via secundária
            angulo_intersecao_graus: Ângulo entre as vias
            tempo_atravessamento_s: Tempo para atravessar a via principal
        """
        
        v_principal_ms = velocidade_via_principal_kmh / 3.6
        v_secundaria_ms = velocidade_via_secundaria_kmh / 3.6
        
        # Distância que veículo na via principal percorre durante atravessamento
        dist_via_principal = v_principal_ms * tempo_atravessamento_s
        
        # Distância que veículo da secundária precisa até a principal
        # (simplificado - na prática depende da largura das faixas)
        dist_via_secundaria = 15.0  # metros (típico)
        
        # Área do triângulo de visibilidade
        angulo_rad = math.radians(angulo_intersecao_graus)
        area_triangulo = 0.5 * dist_via_principal * dist_via_secundaria * math.sin(angulo_rad)
        
        return {
            'distancia_via_principal_m': round(dist_via_principal, 2),
            'distancia_via_secundaria_m': dist_via_secundaria,
            'area_triangulo_m2': round(area_triangulo, 2),
            'angulo_intersecao': angulo_intersecao_graus,
            'tempo_atravessamento_s': tempo_atravessamento_s,
            'interpretacao': f'Área livre de obstáculos necessária: {area_triangulo:.0f} m²',
            'fundamentacao': [
                'Triângulo de visibilidade em interseções (Sight Triangle)',
                'Baseado em AASHTO Chapter 9 - Intersections',
                'Garante que motoristas vejam uns aos outros com antecedência',
                'Área deve estar livre de obstáculos > 0.6m de altura',
                'Referências:',
                '  - AASHTO Green Book Chapter 9',
                '  - MUTCD Section 2C - Warning Signs',
                '  - Rose & Fricke (2018). Intersection Analysis'
            ]
        }
    
    def interpretar_linha_visada(self, resultado: Dict[str, Any]) -> str:
        """Interpretação da análise de linha de visada"""
        
        texto = f"""ANÁLISE DE LINHA DE VISADA

Parâmetros:
- Altura do observador: {resultado['altura_observador_m']:.2f} m
- Altura do alvo: {resultado['altura_alvo_m']:.2f} m
- Distância horizontal: {resultado['distancia_horizontal_m']:.2f} m
- Diferença de altura: {resultado['diferenca_altura_m']:.2f} m
- Ângulo de elevação: {resultado['angulo_elevacao_graus']:.2f}°

Obstáculos analisados: {resultado['numero_obstaculos_analisados']}

RESULTADO: {'✅ VISIBILIDADE LIVRE' if resultado['visibilidade_livre'] else '❌ VISIBILIDADE OBSTRUÍDA'}

"""
        
        if not resultado['visibilidade_livre']:
            texto += "BLOQUEIOS ENCONTRADOS:\n"
            for i, bloqueio in enumerate(resultado['bloqueios_encontrados'], 1):
                texto += f"\n{i}. {bloqueio['razao']}\n"
                if 'diferenca_m' in bloqueio:
                    texto += f"   - Obstáculo está {bloqueio['diferenca_m']:.2f}m ACIMA da linha necessária\n"
                texto += f"   - Distância do observador: {bloqueio['distancia_do_observador_m']:.2f}m\n"
        
        texto += f"""
INTERPRETAÇÃO:
{'A linha de visada está desobstruída. Observador conseguiria ver o alvo.' if resultado['visibilidade_livre'] else 'Obstáculos impedem visualização direta. Análise crítica para determinar se motoristas poderiam se ver mutuamente.'}

Fundamentação:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto
    
    def interpretar_distancia_visibilidade(self, resultado: Dict[str, Any]) -> str:
        """Interpretação da distância de visibilidade mínima"""
        
        texto = f"""DISTÂNCIA DE VISIBILIDADE NECESSÁRIA

Velocidade: {resultado['velocidade_kmh']:.0f} km/h
Tempo de reação: {resultado['tempo_reacao_s']:.1f} segundos
Tempo de frenagem: {resultado['tempo_frenagem_s']:.1f} segundos

COMPONENTES:
1. Distância durante reação: {resultado['distancia_reacao_m']:.2f} m
2. Distância durante frenagem: {resultado['distancia_frenagem_m']:.2f} m
3. Margem de segurança (25%): {resultado['margem_seguranca_m']:.2f} m

RESULTADOS:
- Distância mínima absoluta: {resultado['distancia_minima_m']:.2f} metros
- Distância recomendada (com margem): {resultado['distancia_recomendada_m']:.2f} metros

INTERPRETAÇÃO:
Para segurança, o motorista deve ter visibilidade de pelo menos 
{resultado['distancia_recomendada_m']:.0f} metros à frente para poder parar com segurança
caso surja um obstáculo inesperado.

Se a visibilidade for menor que isso, a via é considerada INSEGURA
para essa velocidade, ou a velocidade deve ser reduzida.

Fundamentação:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto
    
    def interpretar_triangulo_visibilidade(self, resultado: Dict[str, Any]) -> str:
        """Interpretação do triângulo de visibilidade"""
        
        texto = f"""TRIÂNGULO DE VISIBILIDADE EM INTERSEÇÃO

Velocidades:
- Via principal: {resultado['distancia_via_principal_m'] / resultado['tempo_atravessamento_s'] * 3.6:.0f} km/h
- Tempo para atravessar: {resultado['tempo_atravessamento_s']:.1f} segundos

DIMENSÕES DO TRIÂNGULO:
- Lado via principal: {resultado['distancia_via_principal_m']:.2f} metros
- Lado via secundária: {resultado['distancia_via_secundaria_m']:.2f} metros
- Ângulo: {resultado['angulo_intersecao']:.0f}°

ÁREA NECESSÁRIA: {resultado['area_triangulo_m2']:.0f} m²

INTERPRETAÇÃO:
{resultado['interpretacao']}

Esta área triangular deve estar LIVRE de:
- Vegetação > 0.6m de altura
- Construções
- Veículos estacionados
- Outdoors ou placas
- Qualquer obstáculo que bloqueie visão

Caso contrário, motoristas não conseguem ver uns aos outros com
antecedência suficiente, aumentando risco de colisões.

Fundamentação:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto