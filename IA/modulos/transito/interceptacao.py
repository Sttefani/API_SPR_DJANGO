import math
from typing import Dict, Any, Tuple, Optional

class CalculadoraInterceptacao:
    """
    Calcula se um veículo pode interceptar a trajetória de outro
    Fundamental para análise de conversões, cruzamentos e ultrapassagens
    
    Baseado na metodologia do laudo fornecido (seção sobre testes de interceptação)
    """
    
    def calcular_possibilidade_interceptacao(
        self,
        veiculo_interceptador: Dict[str, Any],
        veiculo_interceptado: Dict[str, Any],
        distancia_ate_cruzamento_m: float,
        largura_via_m: float = 7.5
    ) -> Dict[str, Any]:
        """
        Calcula se um veículo consegue completar manobra antes do outro chegar
        
        Cenário típico: Veículo A faz conversão à esquerda enquanto B se aproxima
        
        Args:
            veiculo_interceptador: {
                'velocidade_kmh': 12,  # Velocidade do que faz manobra
                'distancia_inicial_m': 0,  # Distância do ponto de conversão
                'tempo_reacao_s': 1.5  # Tempo para iniciar manobra
            }
            veiculo_interceptado: {
                'velocidade_kmh': 60,  # Velocidade do que vem
                'distancia_inicial_m': 50  # Distância do ponto de cruzamento
            }
            distancia_ate_cruzamento_m: Distância que interceptador precisa percorrer
            largura_via_m: Largura da via a ser cruzada
        """
        
        # Conversões
        v_interceptador_ms = veiculo_interceptador['velocidade_kmh'] / 3.6
        v_interceptado_ms = veiculo_interceptado['velocidade_kmh'] / 3.6
        
        tempo_reacao = veiculo_interceptador.get('tempo_reacao_s', 1.0)
        
        # TEMPO NECESSÁRIO PARA INTERCEPTADOR COMPLETAR MANOBRA
        # Tempo = tempo_reação + distância/velocidade
        tempo_manobra = tempo_reacao + (distancia_ate_cruzamento_m + largura_via_m) / v_interceptador_ms
        
        # TEMPO ATÉ INTERCEPTADO CHEGAR AO PONTO
        tempo_chegada_interceptado = veiculo_interceptado['distancia_inicial_m'] / v_interceptado_ms
        
        # ANÁLISE
        diferenca_tempo = tempo_chegada_interceptado - tempo_manobra
        
        # Distância de segurança percorrida pelo interceptado durante a manobra
        dist_percorrida_durante_manobra = v_interceptado_ms * tempo_manobra
        
        # Folga espacial
        folga_espacial = veiculo_interceptado['distancia_inicial_m'] - dist_percorrida_durante_manobra
        
        # Veredicto
        if diferenca_tempo > 2.0:
            resultado_analise = 'SEGURA'
            explicacao = f'Interceptador completa manobra com {diferenca_tempo:.1f}s de folga.'
        elif diferenca_tempo > 0:
            resultado_analise = 'ARRISCADA'
            explicacao = f'Manobra possível mas com apenas {diferenca_tempo:.1f}s de margem.'
        else:
            resultado_analise = 'COLISÃO INEVITÁVEL'
            explicacao = f'Interceptado chegaria {abs(diferenca_tempo):.1f}s ANTES do interceptador completar.'
        
        return {
            'resultado': resultado_analise,
            'tempo_manobra_s': round(tempo_manobra, 2),
            'tempo_chegada_outro_s': round(tempo_chegada_interceptado, 2),
            'diferenca_tempo_s': round(diferenca_tempo, 2),
            'folga_espacial_m': round(folga_espacial, 2),
            'distancia_seguranca_necessaria_m': round(dist_percorrida_durante_manobra, 2),
            'explicacao': explicacao,
            'parametros': {
                'vel_interceptador_kmh': veiculo_interceptador['velocidade_kmh'],
                'vel_interceptado_kmh': veiculo_interceptado['velocidade_kmh'],
                'dist_manobra_m': distancia_ate_cruzamento_m,
                'dist_inicial_outro_m': veiculo_interceptado['distancia_inicial_m'],
                'largura_via_m': largura_via_m,
                'tempo_reacao_s': tempo_reacao
            },
            'fundamentacao': [
                'Análise de conflito de trajetórias (path conflict analysis)',
                'Tempo total = tempo de reação + tempo de deslocamento',
                'Considera distância necessária para completar manobra completamente',
                'Margem de segurança mínima recomendada: 2 segundos',
                'Referências:',
                '  - Rose & Fricke (2018). Intersection Collision Analysis',
                '  - AASHTO Green Book - Intersection Sight Distance',
                '  - Taoka (1989). Brake Reaction Times',
                '  - Daily (2010). Time-Distance Analysis'
            ]
        }
    
    def calcular_velocidade_maxima_segura(
        self,
        veiculo_interceptador: Dict[str, Any],
        distancia_ate_cruzamento_m: float,
        distancia_outro_veiculo_m: float,
        largura_via_m: float = 7.5,
        margem_seguranca_s: float = 2.0
    ) -> Dict[str, Any]:
        """
        Calcula velocidade máxima que o veículo interceptado pode ter
        para que a manobra seja segura
        
        Baseado no laudo: "entre 40km/h e 60km/h o acidente não ocorreria"
        
        Args:
            veiculo_interceptador: Dados do que faz manobra
            distancia_ate_cruzamento_m: Distância a percorrer
            distancia_outro_veiculo_m: Distância inicial do outro veículo
            largura_via_m: Largura da via
            margem_seguranca_s: Margem de tempo desejada
        """
        
        v_interceptador_ms = veiculo_interceptador['velocidade_kmh'] / 3.6
        tempo_reacao = veiculo_interceptador.get('tempo_reacao_s', 1.0)
        
        # Tempo total da manobra
        tempo_manobra = tempo_reacao + (distancia_ate_cruzamento_m + largura_via_m) / v_interceptador_ms
        
        # Tempo disponível para o outro veículo (com margem)
        tempo_disponivel = tempo_manobra + margem_seguranca_s
        
        # Velocidade máxima = distância / tempo
        v_maxima_ms = distancia_outro_veiculo_m / tempo_disponivel
        v_maxima_kmh = v_maxima_ms * 3.6
        
        # Calcula também para diferentes margens
        velocidades_diferentes_margens = []
        for margem in [0, 1.0, 2.0, 3.0]:
            t_disp = tempo_manobra + margem
            v_ms = distancia_outro_veiculo_m / t_disp
            v_kmh = v_ms * 3.6
            velocidades_diferentes_margens.append({
                'margem_s': margem,
                'velocidade_maxima_kmh': round(v_kmh, 2),
                'classificacao': self._classificar_margem(margem)
            })
        
        return {
            'velocidade_maxima_segura_kmh': round(v_maxima_kmh, 2),
            'margem_seguranca_aplicada_s': margem_seguranca_s,
            'tempo_manobra_s': round(tempo_manobra, 2),
            'tempo_total_disponivel_s': round(tempo_disponivel, 2),
            'velocidades_por_margem': velocidades_diferentes_margens,
            'interpretacao': f'Velocidades até {v_maxima_kmh:.0f} km/h permitiriam manobra segura com {margem_seguranca_s}s de margem.',
            'fundamentacao': [
                'Cálculo reverso: dado tempo disponível, qual velocidade máxima?',
                'Velocidade = Distância / Tempo disponível',
                'Margem de 2s é padrão recomendado para segurança',
                'Útil para determinar contribuição de excesso de velocidade',
                'Referências:',
                '  - Rose & Fricke (2018). Critical Speed Analysis',
                '  - MUTCD - Manual on Uniform Traffic Control Devices'
            ]
        }
    
    def _classificar_margem(self, margem_s: float) -> str:
        """Classifica margem de segurança"""
        if margem_s >= 3.0:
            return 'MUITO SEGURA'
        elif margem_s >= 2.0:
            return 'SEGURA'
        elif margem_s >= 1.0:
            return 'MARGINAL'
        else:
            return 'INSEGURA'
    
    def simular_cenarios_velocidade(
        self,
        veiculo_interceptador: Dict[str, Any],
        distancia_ate_cruzamento_m: float,
        distancia_outro_inicial_m: float,
        velocidades_testar: list = None,
        largura_via_m: float = 7.5
    ) -> Dict[str, Any]:
        """
        Testa múltiplas velocidades para ver em quais haveria colisão
        
        Reproduz os testes da Tabela 1 do laudo fornecido
        
        Args:
            velocidades_testar: Lista de velocidades em km/h (ex: [40, 60, 80])
        """
        
        if velocidades_testar is None:
            velocidades_testar = [40, 60, 80]
        
        resultados_testes = []
        
        for vel_kmh in velocidades_testar:
            # Cria configuração do veículo interceptado
            veiculo_teste = {
                'velocidade_kmh': vel_kmh,
                'distancia_inicial_m': distancia_outro_inicial_m
            }
            
            # Calcula interceptação
            resultado = self.calcular_possibilidade_interceptacao(
                veiculo_interceptador=veiculo_interceptador,
                veiculo_interceptado=veiculo_teste,
                distancia_ate_cruzamento_m=distancia_ate_cruzamento_m,
                largura_via_m=largura_via_m
            )
            
            resultados_testes.append({
                'velocidade_testada_kmh': vel_kmh,
                'resultado': resultado['resultado'],
                'diferenca_tempo_s': resultado['diferenca_tempo_s'],
                'colidiria': resultado['resultado'] == 'COLISÃO INEVITÁVEL',
                'pararia_antes_m': resultado['folga_espacial_m'] if resultado['folga_espacial_m'] > 0 else None,
                'colidiria_a_m': abs(resultado['folga_espacial_m']) if resultado['folga_espacial_m'] < 0 else None
            })
        
        # Encontra velocidade crítica (transição entre seguro e colisão)
        velocidade_critica = None
        for i in range(len(resultados_testes) - 1):
            if not resultados_testes[i]['colidiria'] and resultados_testes[i+1]['colidiria']:
                # Está entre essas duas velocidades
                velocidade_critica = {
                    'entre_kmh': (resultados_testes[i]['velocidade_testada_kmh'], 
                                  resultados_testes[i+1]['velocidade_testada_kmh']),
                    'interpretacao': f"Entre {resultados_testes[i]['velocidade_testada_kmh']} e {resultados_testes[i+1]['velocidade_testada_kmh']} km/h"
                }
                break
        
        return {
            'testes_realizados': resultados_testes,
            'velocidade_critica': velocidade_critica,
            'resumo': self._gerar_resumo_testes(resultados_testes),
            'fundamentacao': [
                'Metodologia de testes incrementais de velocidade',
                'Identifica velocidade crítica (threshold) para colisão',
                'Reproduz ensaios realizados em campo',
                'Baseado em: Laudo de Reprodução Simulada de Fatos',
                'Referências:',
                '  - Rose & Fricke (2018). Simulation and Testing Methods',
                '  - Daily (2010). Critical Speed Determination'
            ]
        }
    
    def _gerar_resumo_testes(self, resultados: list) -> str:
        """Gera resumo dos testes"""
        seguras = [r for r in resultados if not r['colidiria']]
        colisoes = [r for r in resultados if r['colidiria']]
        
        resumo = f"Testes realizados: {len(resultados)}\n"
        resumo += f"Velocidades seguras: {[r['velocidade_testada_kmh'] for r in seguras]} km/h\n"
        resumo += f"Velocidades com colisão: {[r['velocidade_testada_kmh'] for r in colisoes]} km/h"
        
        return resumo
    
    def interpretar_interceptacao(self, resultado: Dict[str, Any]) -> str:
        """Interpretação do resultado de interceptação"""
        
        params = resultado['parametros']
        
        texto = f"""ANÁLISE DE INTERCEPTAÇÃO DE TRAJETÓRIAS

CENÁRIO:
- Veículo que faz manobra: {params['vel_interceptador_kmh']:.0f} km/h
- Veículo que se aproxima: {params['vel_interceptado_kmh']:.0f} km/h
- Distância inicial do que se aproxima: {params['dist_inicial_outro_m']:.0f} metros
- Distância da manobra: {params['dist_manobra_m']:.0f} metros
- Largura da via: {params['largura_via_m']:.1f} metros
- Tempo de reação: {params['tempo_reacao_s']:.1f} segundos

TEMPOS CALCULADOS:
- Tempo para completar manobra: {resultado['tempo_manobra_s']:.2f} segundos
- Tempo até outro veículo chegar: {resultado['tempo_chegada_outro_s']:.2f} segundos
- Diferença (margem): {resultado['diferenca_tempo_s']:.2f} segundos

ANÁLISE ESPACIAL:
- Distância que o outro percorre durante manobra: {resultado['distancia_seguranca_necessaria_m']:.2f} m
- Folga espacial: {resultado['folga_espacial_m']:.2f} metros

RESULTADO: {resultado['resultado']}

INTERPRETAÇÃO:
{resultado['explicacao']}

{'✅ Manobra seria concluída com segurança.' if resultado['resultado'] == 'SEGURA' else ''}
{'⚠️ Manobra possível mas com risco elevado.' if resultado['resultado'] == 'ARRISCADA' else ''}
{'❌ Colisão seria inevitável nessas condições.' if resultado['resultado'] == 'COLISÃO INEVITÁVEL' else ''}

Fundamentação:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto
    
    def interpretar_velocidade_maxima(self, resultado: Dict[str, Any]) -> str:
        """Interpretação da velocidade máxima segura"""
        
        texto = f"""CÁLCULO DE VELOCIDADE MÁXIMA SEGURA

Tempo da manobra: {resultado['tempo_manobra_s']:.2f} segundos
Margem de segurança aplicada: {resultado['margem_seguranca_aplicada_s']:.1f} segundos
Tempo total disponível: {resultado['tempo_total_disponivel_s']:.2f} segundos

RESULTADO:
Velocidade máxima segura: {resultado['velocidade_maxima_segura_kmh']:.0f} km/h

ANÁLISE POR DIFERENTES MARGENS:
"""
        for item in resultado['velocidades_por_margem']:
            texto += f"  Margem {item['margem_s']:.1f}s: {item['velocidade_maxima_kmh']:.0f} km/h ({item['classificacao']})\n"
        
        texto += f"""
INTERPRETAÇÃO:
{resultado['interpretacao']}

Velocidades acima de {resultado['velocidade_maxima_segura_kmh']:.0f} km/h não permitiriam 
tempo suficiente para a manobra ser completada com segurança.

Fundamentação:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto
    
    def interpretar_simulacao(self, resultado: Dict[str, Any]) -> str:
        """Interpretação da simulação de cenários"""
        
        texto = f"""SIMULAÇÃO DE CENÁRIOS DE VELOCIDADE

{resultado['resumo']}

RESULTADOS DETALHADOS:
"""
        for teste in resultado['testes_realizados']:
            simbolo = '❌' if teste['colidiria'] else '✅'
            texto += f"\n{simbolo} {teste['velocidade_testada_kmh']:.0f} km/h: {teste['resultado']}\n"
            texto += f"   Diferença de tempo: {teste['diferenca_tempo_s']:.2f}s\n"
            
            if teste['pararia_antes_m']:
                texto += f"   Pararia {teste['pararia_antes_m']:.2f}m antes do ponto\n"
            elif teste['colidiria_a_m']:
                texto += f"   Colidiria faltando {teste['colidiria_a_m']:.2f}m\n"
        
        if resultado['velocidade_critica']:
            texto += f"\nVELOCIDADE CRÍTICA:\n"
            texto += f"A colisão ocorreria com velocidades {resultado['velocidade_critica']['interpretacao']}\n"
        
        texto += f"""
INTERPRETAÇÃO:
Os testes demonstram experimentalmente as velocidades nas quais a colisão
seria ou não evitável, reproduzindo a metodologia de ensaios de campo.

Fundamentação:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto