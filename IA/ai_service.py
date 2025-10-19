from groq import Groq
from django.conf import settings
from .rag_service import LaudoRAGService
import json
import re

class LaudoAIService:
    """Serviço de IA para geração de laudos com RAG + Cálculos Completos"""
    
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.rag = LaudoRAGService()
        
        # Importa TODAS as calculadoras
        from .modulos.transito import (
            CalculadoraVelocidade,
            CalculadoraEnergiaCinetica,
            CalculadoraTempoReacao,
            CalculadoraArrastamentoSolo,
            CalculadoraVelocidadeDanos,
            CalculadoraPontoImpacto,
            CalculadoraTrajetoria,
            CalculadoraInterceptacao,
            CalculadoraVisibilidade
        )
        
        self.calc_velocidade = CalculadoraVelocidade()
        self.calc_energia = CalculadoraEnergiaCinetica()
        self.calc_tempo = CalculadoraTempoReacao()
        self.calc_arrastamento = CalculadoraArrastamentoSolo()
        self.calc_velocidade_danos = CalculadoraVelocidadeDanos()
        self.calc_ponto_impacto = CalculadoraPontoImpacto()
        self.calc_trajetoria = CalculadoraTrajetoria()
        self.calc_interceptacao = CalculadoraInterceptacao()
        self.calc_visibilidade = CalculadoraVisibilidade()
        
        self.model = "llama-3.3-70b-versatile"
    
    def detectar_e_executar_calculo(self, mensagem: str) -> tuple:
        """
        Detecta se a mensagem pede um cálculo e executa
        
        Returns:
            (tem_calculo, resultado)
        """
        mensagem_lower = mensagem.lower()
        
        # ========== VELOCIDADE POR FRENAGEM ==========
        if any(palavra in mensagem_lower for palavra in ['velocidade', 'frenag', 'marca']) and not any(palavra in mensagem_lower for palavra in ['dano', 'arrast']):
            match_metros = re.search(r'(\d+(?:\.\d+)?)\s*m(?:etros)?', mensagem_lower)
            if match_metros:
                distancia = float(match_metros.group(1))
                
                # Detecta tipo de piso (prioriza detecção específica)
                tipo_piso = 'asfalto'
                if 'grama' in mensagem_lower or 'gramas' in mensagem_lower or 'gramado' in mensagem_lower:
                    tipo_piso = 'grama'
                elif 'areia' in mensagem_lower:
                    tipo_piso = 'areia'
                elif 'lama' in mensagem_lower or 'barro' in mensagem_lower:
                    tipo_piso = 'lama'
                elif 'paralelepipedo' in mensagem_lower or 'paralelepípedo' in mensagem_lower or 'pedra' in mensagem_lower:
                    tipo_piso = 'paralelepipedo'
                elif 'concreto' in mensagem_lower or 'cimento' in mensagem_lower:
                    tipo_piso = 'concreto'
                elif 'terra' in mensagem_lower or 'chao de terra' in mensagem_lower:
                    tipo_piso = 'terra'
                elif 'cascalho' in mensagem_lower:
                    tipo_piso = 'cascalho'
                elif 'gelo' in mensagem_lower or 'gelado' in mensagem_lower:
                    tipo_piso = 'gelo'
                elif 'neve' in mensagem_lower:
                    tipo_piso = 'neve'

                # Detecta condição
                condicao = 'seco'
                if 'molhad' in mensagem_lower or 'chuva' in mensagem_lower or 'umid' in mensagem_lower:
                    condicao = 'molhado'
                elif 'óleo' in mensagem_lower or 'oleo' in mensagem_lower or 'graxa' in mensagem_lower:
                    condicao = 'com_oleo'
                elif tipo_piso == 'lama':
                    condicao = 'molhado'
                
                try:
                    resultado = self.calc_velocidade.calcular(distancia, tipo_piso, condicao)
                    interpretacao = self.calc_velocidade.interpretar_resultado(resultado)
                    
                    return True, {
                        'tipo': 'calculo_velocidade_frenagem',
                        'resultado': resultado,
                        'interpretacao': interpretacao
                    }
                except Exception as e:
                    return True, {'tipo': 'erro_calculo', 'erro': str(e)}
        
        # ========== VELOCIDADE POR ARRASTAMENTO ==========
        if any(palavra in mensagem_lower for palavra in ['arrast', 'desliz']):
            match_metros = re.search(r'(\d+(?:\.\d+)?)\s*m(?:etros)?', mensagem_lower)
            if match_metros:
                distancia = float(match_metros.group(1))
                
                try:
                    resultado = self.calc_arrastamento.calcular_com_margem_erro(distancia)
                    interpretacao = self.calc_arrastamento.interpretar_resultado(resultado)
                    
                    return True, {
                        'tipo': 'calculo_arrastamento_solo',
                        'resultado': resultado,
                        'interpretacao': interpretacao
                    }
                except Exception as e:
                    return True, {'tipo': 'erro_calculo', 'erro': str(e)}
        
        # ========== ENERGIA CINÉTICA ==========
        if any(palavra in mensagem_lower for palavra in ['energia', 'cinética', 'cinetica']):
            match_massa = re.search(r'(\d+(?:\.\d+)?)\s*(?:kg|quilos?)', mensagem_lower)
            match_vel = re.search(r'(\d+(?:\.\d+)?)\s*(?:km/?h|kmh)', mensagem_lower)
            
            if match_massa and match_vel:
                massa = float(match_massa.group(1))
                velocidade = float(match_vel.group(1))
                
                try:
                    resultado = self.calc_energia.calcular(massa, velocidade)
                    interpretacao = self.calc_energia.interpretar_resultado(resultado)
                    
                    return True, {
                        'tipo': 'calculo_energia',
                        'resultado': resultado,
                        'interpretacao': interpretacao
                    }
                except Exception as e:
                    return True, {'tipo': 'erro_calculo', 'erro': str(e)}
        
        # ========== TEMPO DE REAÇÃO ==========
        if any(palavra in mensagem_lower for palavra in ['tempo', 'reação', 'reacao', 'parada']):
            match_vel = re.search(r'(\d+(?:\.\d+)?)\s*(?:km/?h|kmh)', mensagem_lower)
            
            if match_vel:
                velocidade = float(match_vel.group(1))
                
                condicao = 'normal'
                if 'alerta' in mensagem_lower:
                    condicao = 'alerta_bom'
                elif 'distraído' in mensagem_lower or 'distraido' in mensagem_lower:
                    condicao = 'distraido'
                elif 'cansado' in mensagem_lower:
                    condicao = 'cansado'
                elif 'álcool' in mensagem_lower or 'alcool' in mensagem_lower:
                    condicao = 'alcool'
                
                try:
                    resultado = self.calc_tempo.calcular_distancia_reacao(velocidade, condicao=condicao)
                    interpretacao = self.calc_tempo.interpretar_distancia_reacao(resultado)
                    
                    return True, {
                        'tipo': 'calculo_tempo_reacao',
                        'resultado': resultado,
                        'interpretacao': interpretacao
                    }
                except Exception as e:
                    return True, {'tipo': 'erro_calculo', 'erro': str(e)}
        
        # ========== VELOCIDADE DE DANOS (EES) ==========
        if any(palavra in mensagem_lower for palavra in ['velocidade de dano', 'danos', 'ees', 'deformação', 'deformacao']):
            matches_kg = re.findall(r'(\d+(?:\.\d+)?)\s*(?:kg|quilos?)', mensagem_lower)
            matches_vel = re.findall(r'(\d+(?:\.\d+)?)\s*(?:km/?h|kmh)', mensagem_lower)
            
            if len(matches_kg) >= 2 and len(matches_vel) >= 2:
                massa1 = float(matches_kg[0])
                massa2 = float(matches_kg[1])
                vel1 = float(matches_vel[0])
                vel2 = float(matches_vel[1])
                
                mesmo_sentido = 'mesmo sentido' in mensagem_lower or 'mesma direção' in mensagem_lower or 'mesma direcao' in mensagem_lower
                
                try:
                    resultado = self.calc_velocidade_danos.calcular_velocidade_dano_colisao(
                        massa1, vel1, massa2, vel2, mesmo_sentido
                    )
                    interpretacao = self.calc_velocidade_danos.interpretar_velocidade_dano(resultado)
                    
                    return True, {
                        'tipo': 'calculo_velocidade_danos',
                        'resultado': resultado,
                        'interpretacao': interpretacao
                    }
                except Exception as e:
                    return True, {'tipo': 'erro_calculo', 'erro': str(e)}
            
            elif len(matches_vel) >= 2:
                vel_dano = float(matches_vel[0])
                vel_arrasto = float(matches_vel[1])
                
                try:
                    resultado = self.calc_velocidade_danos.calcular_velocidade_total_estimada(
                        vel_dano, vel_arrasto
                    )
                    interpretacao = self.calc_velocidade_danos.interpretar_velocidade_total(resultado)
                    
                    return True, {
                        'tipo': 'calculo_velocidade_total',
                        'resultado': resultado,
                        'interpretacao': interpretacao
                    }
                except Exception as e:
                    return True, {'tipo': 'erro_calculo', 'erro': str(e)}

        # ========== PONTO DE IMPACTO ==========
        if any(palavra in mensagem_lower for palavra in ['ponto de impacto', 'ponto impacto', 'onde colidir', 'local colisão', 'local colisao']):
            matches_coord = re.findall(r'(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)', mensagem_lower)
            
            if len(matches_coord) >= 2:
                marcas = []
                
                if 'arrasto' in mensagem_lower or 'arrast' in mensagem_lower:
                    marcas.append({
                        'tipo': 'arrasto',
                        'inicio_x': float(matches_coord[0][0]),
                        'inicio_y': float(matches_coord[0][1]),
                        'fim_x': float(matches_coord[1][0]),
                        'fim_y': float(matches_coord[1][1])
                    })
                elif 'fluido' in mensagem_lower or 'óleo' in mensagem_lower or 'oleo' in mensagem_lower:
                    for coord in matches_coord:
                        marcas.append({
                            'tipo': 'fluido',
                            'x': float(coord[0]),
                            'y': float(coord[1])
                        })
                elif 'raspagem' in mensagem_lower:
                    for coord in matches_coord:
                        marcas.append({
                            'tipo': 'raspagem',
                            'x': float(coord[0]),
                            'y': float(coord[1])
                        })
                
                if marcas:
                    try:
                        resultado = self.calc_ponto_impacto.calcular_por_marcas_solo(marcas)
                        interpretacao = self.calc_ponto_impacto.interpretar_resultado(resultado)
                        
                        return True, {
                            'tipo': 'calculo_ponto_impacto',
                            'resultado': resultado,
                            'interpretacao': interpretacao
                        }
                    except Exception as e:
                        return True, {'tipo': 'erro_calculo', 'erro': str(e)}
            else:
                return True, {
                    'tipo': 'info_ponto_impacto',
                    'mensagem': """Para calcular o ponto de impacto, preciso de coordenadas das marcas no solo.

FORMATO:
"Marca de arrasto de 10,5 ate 15,8"
"Fluido em 10.2,5.1 e 10.5,5.3"
"Raspagem em 11,6"

TIPOS DE MARCA:
- Arrasto (precisa inicio e fim)
- Fluido (oleo, liquido de arrefecimento)
- Raspagem

Exemplo: "Ponto de impacto: arrasto de 10,5 ate 15,8 e fluido em 10.2,5.1"
"""
                }

        # ========== TRAJETÓRIAS ==========
        if any(palavra in mensagem_lower for palavra in ['trajetoria', 'trajetória', 'trajeto', 'caminho do veiculo', 'caminho do veículo']):
            match_vel = re.search(r'(\d+(?:\.\d+)?)\s*(?:km/?h|kmh)', mensagem_lower)
            match_dist = re.search(r'(\d+(?:\.\d+)?)\s*m(?:etros)?', mensagem_lower)
            match_tempo = re.search(r'(\d+(?:\.\d+)?)\s*(?:segundos?|s\b)', mensagem_lower)
            
            if match_vel and ('pre' in mensagem_lower or 'antes' in mensagem_lower or 'pré' in mensagem_lower):
                velocidade = float(match_vel.group(1))
                tempo_antes = float(match_tempo.group(1)) if match_tempo else 3.0
                
                match_coord = re.search(r'(?:impacto|colisão|colisao)[^\d]*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)', mensagem_lower)
                if match_coord:
                    ponto_impacto = (float(match_coord.group(1)), float(match_coord.group(2)))
                else:
                    ponto_impacto = (0, 0)
                
                match_angulo = re.search(r'(?:angulo|ângulo)[^\d]*(\d+)', mensagem_lower)
                angulo = float(match_angulo.group(1)) if match_angulo else 0
                
                try:
                    resultado = self.calc_trajetoria.calcular_trajetoria_pre_impacto(
                        ponto_impacto, velocidade, angulo, tempo_antes
                    )
                    interpretacao = self.calc_trajetoria.interpretar_pre_impacto(resultado)
                    
                    return True, {
                        'tipo': 'calculo_trajetoria_pre',
                        'resultado': resultado,
                        'interpretacao': interpretacao
                    }
                except Exception as e:
                    return True, {'tipo': 'erro_calculo', 'erro': str(e)}
            
            elif match_vel and match_dist and ('pos' in mensagem_lower or 'apos' in mensagem_lower or 'após' in mensagem_lower):
                velocidade_pos = float(match_vel.group(1))
                distancia = float(match_dist.group(1))
                
                try:
                    resultado = self.calc_trajetoria.calcular_trajetoria_pos_impacto(
                        ponto_impacto=(0, 0),
                        posicao_final=(distancia, 0),
                        velocidade_pos_impacto_kmh=velocidade_pos
                    )
                    interpretacao = self.calc_trajetoria.interpretar_pos_impacto(resultado)
                    
                    return True, {
                        'tipo': 'calculo_trajetoria_pos',
                        'resultado': resultado,
                        'interpretacao': interpretacao
                    }
                except Exception as e:
                    return True, {'tipo': 'erro_calculo', 'erro': str(e)}
            else:
                return True, {
                    'tipo': 'info_trajetoria',
                    'mensagem': """Para calcular trajetorias, especifique:

PRE-IMPACTO:
"Trajetoria antes da colisao: 60km/h, 3 segundos antes, angulo 45 graus"

POS-IMPACTO:
"Trajetoria apos colisao: 30km/h, deslizou 15 metros"

Parametros necessarios:
- Velocidade (km/h)
- Tempo (para pre) ou Distancia (para pos)
- Angulo de aproximacao (opcional)
"""
                }

        # ========== INTERCEPTAÇÃO ==========
        if any(palavra in mensagem_lower for palavra in ['intercepta', 'cruzamento', 'conversão', 'conversao', 'ultrapassagem']):
            matches_vel = re.findall(r'(\d+(?:\.\d+)?)\s*(?:km/?h|kmh)', mensagem_lower)
            matches_dist = re.findall(r'(\d+(?:\.\d+)?)\s*m(?:etros)?', mensagem_lower)
            
            if len(matches_vel) >= 2 and len(matches_dist) >= 2:
                vel_interceptador = float(matches_vel[0])
                vel_interceptado = float(matches_vel[1])
                dist_manobra = float(matches_dist[0])
                dist_outro = float(matches_dist[1])
                
                try:
                    interceptador = {'velocidade_kmh': vel_interceptador, 'tempo_reacao_s': 1.5}
                    interceptado = {'velocidade_kmh': vel_interceptado, 'distancia_inicial_m': dist_outro}
                    
                    resultado = self.calc_interceptacao.calcular_possibilidade_interceptacao(
                        interceptador, interceptado, dist_manobra
                    )
                    interpretacao = self.calc_interceptacao.interpretar_interceptacao(resultado)
                    
                    return True, {
                        'tipo': 'calculo_interceptacao',
                        'resultado': resultado,
                        'interpretacao': interpretacao
                    }
                except Exception as e:
                    return True, {'tipo': 'erro_calculo', 'erro': str(e)}
            else:
                return True, {
                    'tipo': 'info_interceptacao',
                    'mensagem': """Para calcular interceptacao, preciso de:

VEICULO QUE FAZ MANOBRA:
- Velocidade (km/h)
- Distancia a percorrer para completar manobra (metros)

VEICULO QUE SE APROXIMA:
- Velocidade (km/h)
- Distancia inicial ate o ponto de cruzamento (metros)

EXEMPLO:
"Interceptacao: veiculo a 12km/h precisa percorrer 10 metros, outro veiculo a 60km/h esta a 50 metros"
"""
                }

        # ========== VISIBILIDADE ==========
        if any(palavra in mensagem_lower for palavra in ['visibilidade', 'linha de visada', 'consegue ver', 'obstáculo', 'obstaculo', 'vegetação', 'vegetacao']):
            return True, {
                'tipo': 'info_visibilidade',
                'mensagem': """Para analisar visibilidade, preciso de:

OBSERVADOR:
- Posicao (X, Y, Z em metros)
- Altura dos olhos (padrao: 1.65m se sentado em carro)

ALVO:
- Posicao (X, Y, Z em metros)
- Altura (ex: moto = 1.4m, carro = 1.5m)

OBSTACULOS (se houver):
- Tipo (vegetacao, construcao, veiculo)
- Posicao (X, Y)
- Altura (metros)
- Largura (metros)

EXEMPLO:
"Visibilidade: motorista a 30m de distancia, vegetacao de 1.6m no meio do caminho"
"""
            }
        
        return False, {}
    
    def _gerar_explicacao_contexto(self, resultado_calculo, pergunta_original):
        """Gera explicação adicional contextualizada para cálculos"""
        
        # SEMPRE gera contexto adicional agora (removido o limite de 100 caracteres)
        system_prompt = f"""Voce acabou de fazer um calculo tecnico pericial.

Tipo de calculo: {resultado_calculo.get('tipo', 'calculo')}

O usuario disse: "{pergunta_original}"

IMPORTANTE: Forneca uma explicacao adicional conversacional e humanizada (3-6 frases) sobre:

1. O que esse resultado SIGNIFICA na pratica pericial
2. Contexto do caso (se o usuario mencionou detalhes como distracao, celular, etc, COMENTE sobre isso)
3. Se ha pontos de atencao importantes para este caso especifico
4. Implicacoes periciais ou juridicas relevantes

Seja TECNICO mas CONVERSACIONAL e EMPATICO.
Conecte o calculo com o contexto fornecido pelo usuario.
Nao repita o que ja foi dito no calculo, ADICIONE valor.
Use tom profissional mas humano, como um perito experiente conversando com um colega."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": system_prompt}],
                temperature=0.5,  # aumentado de 0.4 para mais naturalidade
                max_tokens=600,   # AUMENTADO de 300 para 600
                top_p=0.9
            )
            return "\n\n" + response.choices[0].message.content
        except:
            return ""
    
    def detectar_fase_conversa(self, historico):
        """Detecta em que fase da conversa está"""
        
        if not historico or len(historico) <= 2:
            return 'ACOLHIMENTO'
        
        dados_estruturados = 0
        for msg in historico:
            if msg['role'] == 'user':
                conteudo = msg['content'].lower()
                if any(palavra in conteudo for palavra in ['delegado', 'promotor', 'juiz', 'doutor', 'dr.']):
                    dados_estruturados += 1
                if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', conteudo):
                    dados_estruturados += 1
                if any(palavra in conteudo for palavra in ['rua', 'avenida', 'rodovia', 'km']):
                    dados_estruturados += 1
        
        if dados_estruturados >= 3:
            return 'COLETA'
        
        return 'CONTEXTO'
    
    def gerar_resposta(self, pergunta, tipo_laudo=None, contexto_chat=None):
        """Gera resposta usando RAG + Cálculos + Conversação Natural"""
        
        print("\n" + "="*60)
        print("AI_SERVICE.GERAR_RESPOSTA CHAMADO!")
        print(f"Pergunta: {pergunta}")
        print("="*60)
        
        pergunta_lower = pergunta.lower()
        
        fase = self.detectar_fase_conversa(contexto_chat or [])
        print(f"Fase da conversa: {fase}")
        
        # Detecta tipo de cálculo
        tipo_calculo = None
        
        if any(palavra in pergunta_lower for palavra in ['calcul', 'quero calcular', 'preciso calcular']):
            if 'danos' in pergunta_lower:
                tipo_calculo = 'velocidade_danos'
            elif 'arrast' in pergunta_lower:
                tipo_calculo = 'arrastamento_solo'
            elif 'energia' in pergunta_lower:
                tipo_calculo = 'energia_cinetica'
            elif 'tempo' in pergunta_lower or 'reação' in pergunta_lower or 'reacao' in pergunta_lower:
                tipo_calculo = 'tempo_reacao'
            elif 'velocidade' in pergunta_lower or 'frenag' in pergunta_lower:
                tipo_calculo = 'velocidade_frenagem'
        
        if tipo_calculo:
            print(f"Calculo detectado: {tipo_calculo}")
            fase = 'CALCULO'
            
            tem_calculo, resultado_calculo = self.detectar_e_executar_calculo(pergunta)
            
            if tem_calculo and resultado_calculo.get('tipo') != 'erro_calculo':
                explicacao_adicional = self._gerar_explicacao_contexto(resultado_calculo, pergunta)
                
                return f"""{resultado_calculo['interpretacao']}
{explicacao_adicional}

---

Precisa de mais algum calculo ou quer que eu ajude com o laudo completo?"""
            
            elif tem_calculo and resultado_calculo.get('tipo') == 'erro_calculo':
                return f"""Erro ao executar calculo: {resultado_calculo['erro']}

Tente reformular ou me diga os parametros claramente.
Exemplo: "30 metros em grama seca" ou "25m asfalto molhado"
"""
            
            else:
                perguntas_parametros = {
                    'velocidade_frenagem': """Entendido! Para calcular a velocidade pela marca de frenagem, preciso de:

📏 DISTANCIA DA MARCA EM METROS - O comprimento da marca de arrasto no solo

🛣️ TIPO DE PISO - Qual superficie? (asfalto, concreto, terra, cascalho, grama, areia, paralelepipedo)

💧 CONDICAO DO PISO - Como estava? (seco, molhado, com oleo)

Exemplo: "A marca tem 25 metros em asfalto seco" ou "15m em grama molhada"

Pode me passar essas informacoes?""",
                    
                    'arrastamento_solo': """Certo! Para calcular a velocidade de arrastamento pos-colisao:

📏 DISTANCIA DO ARRASTO - Quantos metros o veiculo deslizou apos a colisao?

Este calculo e diferente da frenagem, pois considera o veiculo ja sem controle, deslizando lateralmente ou capotado.

Qual foi a distancia?""",
                    
                    'energia_cinetica': """Ok! Para calcular a energia cinetica envolvida:

⚖️ MASSA DO VEICULO EM KG - Peso aproximado
   (carro popular ~1200kg, SUV ~2000kg, moto ~150kg, caminhao ~8000kg)

🏎️ VELOCIDADE EM KM/H - A velocidade no momento que voce quer analisar

A energia cinetica cresce com o QUADRADO da velocidade, entao pequenas diferencas de velocidade resultam em grandes diferencas de energia.

Tem esses dados?""",
                    
                    'tempo_reacao': """Entendi! Para calcular tempo de reacao e distancia percorrida durante a reacao:

🏎️ VELOCIDADE DO VEICULO EM KM/H - A velocidade no momento da percepcao do perigo

👤 CONDICAO DO MOTORISTA - Como ele estava?
   • Normal/Alerta (1.0s)
   • Distraido (1.5s)
   • Cansado/Sono (2.0s)
   • Sob efeito de alcool (2.5s+)

Durante o tempo de reacao, o veiculo continua em velocidade CONSTANTE antes de comecar a frear.

Quais sao essas informacoes?""",
                }
                
                return perguntas_parametros.get(tipo_calculo, "Preciso de mais informacoes. Pode detalhar?")
        
        # Tenta executar cálculo
        tem_calculo, resultado_calculo = self.detectar_e_executar_calculo(pergunta)
        
        if tem_calculo:
            calculos_validos = [
                'calculo_velocidade_frenagem',
                'calculo_arrastamento_solo',
                'calculo_energia',
                'calculo_tempo_reacao',
                'calculo_velocidade_danos',
                'calculo_velocidade_total',
                'calculo_ponto_impacto',
                'calculo_trajetoria_pre',
                'calculo_trajetoria_pos',
                'calculo_interceptacao'
            ]
            
            calculos_info = [
                'info_ponto_impacto',
                'info_trajetoria',
                'info_interceptacao',
                'info_visibilidade'
            ]
            
            if resultado_calculo['tipo'] in calculos_validos:
                explicacao_adicional = self._gerar_explicacao_contexto(resultado_calculo, pergunta)
                
                return f"""{resultado_calculo['interpretacao']}
{explicacao_adicional}

---

Precisa de mais algum calculo ou quer continuar com o laudo?"""
            
            elif resultado_calculo['tipo'] in calculos_info:
                return resultado_calculo['mensagem']
            
            elif resultado_calculo['tipo'] == 'erro_calculo':
                return f"""Erro ao executar calculo: {resultado_calculo['erro']}

Tente reformular ou me diga os parametros claramente.
"""
        
        # Perguntas técnicas
        perguntas_tecnicas = ['por que', 'porque', 'como funciona', 'explica', 'metodologia', 'como calcula']
        
        if any(palavra in pergunta_lower for palavra in perguntas_tecnicas):
            print("Pergunta tecnica detectada")
            
            referencias = self.rag.buscar_similares(pergunta, tipo_laudo, n_results=3)
            contexto_rag = "\n\n".join([f"Referencia {i+1}:\n{ref[:400]}..." for i, ref in enumerate(referencias)])
            
            system_prompt = f"""Voce e um perito criminal experiente e didatico, especializado em pericia forense.

O usuario fez uma pergunta tecnica: "{pergunta}"

INSTRUCOES:
- Responda de forma COMPLETA e DETALHADA
- Seja tecnico MAS acessivel e didatico
- Use EXEMPLOS PRATICOS quando apropriado
- Fundamente cientificamente com referencias
- Explique o CONTEXTO e a APLICACAO pratica
- Se houver formulas, EXPLIQUE o significado de cada variavel
- Seja CONVERSACIONAL, como um professor experiente ensinando

REFERENCIAS DISPONIVEIS:
{contexto_rag}

Pode usar ate 800 palavras para responder BEM e COMPLETAMENTE.
O usuario merece uma resposta de QUALIDADE."""
            
            messages = [{"role": "system", "content": system_prompt}]
            if contexto_chat:
                messages.extend(contexto_chat[-10:])  # mais contexto
            messages.append({"role": "user", "content": pergunta})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.5,  # aumentado de 0.4
                max_tokens=1200,  # AUMENTADO de 600 para 1200!
                top_p=0.9
            )
            
            return response.choices[0].message.content
        
        # Conversação por fase
        if fase == 'ACOLHIMENTO':
            system_prompt = """Voce e um assistente de pericia criminal EXTREMAMENTE amigavel, acolhedor e profissional.

O usuario acabou de iniciar a conversa. Sua missao:

1. Cumprimente de forma CALOROSA e HUMANA (sem ser excessivo)
2. Apresente-se brevemente como um assistente especializado
3. Pergunte GENUINAMENTE como pode ajudar
4. Mencione suas capacidades:
   • Elaborar laudos periciais completos e tecnicos
   • Realizar calculos tecnicos complexos (velocidade, energia, trajetorias, etc)
   • Tirar duvidas sobre metodologias e fundamentacao cientifica
   • Orientar sobre melhores praticas periciais

Seja HUMANO, EMPATICO, ACOLHEDOR e PROFISSIONAL ao mesmo tempo.
Transmita confianca e competencia, mas com calor humano.
Use 5-8 linhas para criar uma conexao genuina."""

        elif fase == 'CONTEXTO':
            system_prompt = """Voce e um perito criminal experiente conversando NATURALMENTE com um colega.

O usuario esta explicando o que precisa. Sua missao:

1. OUÇA ATIVAMENTE - demonstre que entendeu o contexto dele
2. Se ele mencionou detalhes especificos (tipo de caso, circunstancias, etc), RECONHECA e COMENTE brevemente
3. Seja EMPATICO com a situacao (ex: se e um caso dificil, reconheca isso)
4. Pergunte de forma CONVERSACIONAL (nao robotica) se ele quer:
   • Elaborar um laudo pericial completo
   • Fazer calculos tecnicos especificos
   • Entender metodologias ou tirar duvidas
   • Orientacao sobre como proceder

Seja GENUINAMENTE INTERESSADO e PRESTATIVO.
Use tom de COLEGA EXPERIENTE ajudando outro profissional.
Fale de forma NATURAL, nao como robo.
Use 6-10 linhas para construir rapport e entendimento."""

        else:  # COLETA
            referencias = self.rag.buscar_similares(pergunta, tipo_laudo, n_results=2)
            contexto_rag = "\n\n".join([f"Exemplo {i+1}:\n{ref[:300]}..." for i, ref in enumerate(referencias)])
            
            system_prompt = f"""Voce esta coletando informacoes para um laudo pericial DE FORMA CONVERSACIONAL.

CONTEXTO: Ja entendeu o que o usuario precisa. Agora precisa coletar dados estruturados.

PROIBICOES ABSOLUTAS:
- NAO gere o laudo ainda
- NAO invente dados
- NAO seja robotico ou burocratico

INSTRUCOES:
1. Analise a resposta anterior do usuario COM ATENCAO
2. Agradeca/reconheca a informacao de forma NATURAL (ex: "Entendi!", "Perfeito!", "Obrigado pela informacao")
3. Se o usuario forneceu algo interessante/importante, COMENTE brevemente (1 frase)
4. Faca a PROXIMA pergunta necessaria de forma CONVERSACIONAL
5. Explique BREVEMENTE por que essa informacao e importante (se relevante)
6. Seja CONTEXTUALIZADO - mencione o que ele ja disse quando fizer sentido

Dados tipicos para laudo:
1. Autoridade requisitante (delegado, promotor, juiz)
2. Data e hora do fato
3. Local do fato (endereco completo)
4. Material examinado / Objetos da pericia
5. Circunstancias / Historico
6. Quesitos a responder
7. Resultados/Conclusoes

Exemplos de estrutura de laudos similares:
{contexto_rag}

Seja HUMANO, PROFISSIONAL e CONVERSACIONAL.
Fale como um perito experiente coletando informacoes de forma natural.
Use 4-8 linhas."""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if contexto_chat:
            messages.extend(contexto_chat[-10:])  # AUMENTADO de 6 para 10
        
        messages.append({"role": "user", "content": pergunta})
        
        # TOKENS MASSIVOS POR FASE
        if fase == 'ACOLHIMENTO':
            max_tokens = 600   # era 300
            temperature = 0.7
        elif fase == 'CONTEXTO':
            max_tokens = 900   # era 400
            temperature = 0.6  # era 0.5
        else:  # COLETA
            max_tokens = 500   # era 250
            temperature = 0.4  # era 0.2
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.9  # era 0.85
        )
        
        return response.choices[0].message.content
    def gerar_laudo_thc(self, dados_conversa: dict) -> dict:
        """
        Gera laudo químico THC usando template fixo
        
        Args:
            dados_conversa: Histórico completo da conversa
        
        Returns:
            {
                'status': 'sucesso' | 'incompleto' | 'erro',
                'laudo_texto': texto do laudo (se sucesso),
                'campos_faltantes': lista de campos faltantes (se incompleto),
                'mensagem': mensagem para o usuário
            }
        """
        from .models import TemplateLaudo, LaudoGerado
        
        try:
            # Busca template
            template = TemplateLaudo.objects.get(tipo='quimico_preliminar_thc', ativo=True)
        except TemplateLaudo.DoesNotExist:
            return {
                'status': 'erro',
                'mensagem': 'Template de laudo químico THC não encontrado. Execute: python manage.py criar_template_thc'
            }
        
        # Extrai dados estruturados da conversa
        dados_extraidos = self._extrair_dados_thc(dados_conversa)
        
        # Valida se tem todos os campos
        valido, faltantes, invalidos = template.validar_dados(dados_extraidos)
        
        if not valido:
            # Gera pergunta sobre campos faltantes
            mensagem = self._gerar_pergunta_thc_faltantes(faltantes, invalidos)
            
            return {
                'status': 'incompleto',
                'campos_faltantes': faltantes,
                'campos_invalidos': invalidos,
                'mensagem': mensagem
            }
        
        # Preenche template
        try:
            laudo_texto = template.preencher(dados_extraidos)
            
            # Salva no banco
            laudo_obj = LaudoGerado.objects.create(
                template=template,
                dados_preenchimento=dados_extraidos,
                laudo_texto=laudo_texto,
                resultado=dados_extraidos.get('resultado', ''),
                status='rascunho'
            )
            
            return {
                'status': 'sucesso',
                'laudo_texto': laudo_texto,
                'laudo_id': laudo_obj.id,
                'mensagem': f'✅ Laudo gerado com sucesso! ID: {laudo_obj.id}'
            }
        
        except Exception as e:
            return {
                'status': 'erro',
                'mensagem': f'Erro ao gerar laudo: {str(e)}'
            }

    def _extrair_dados_thc(self, dados_conversa: dict) -> dict:
        """
        Extrai dados estruturados do histórico de conversa para laudo THC
        USA IA apenas para EXTRAIR (não inventar!)
        """
        
        historico = dados_conversa.get('historico', [])
        historico_texto = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in historico
        ])
        
        prompt = f"""Analise o histórico de conversa e EXTRAIA os dados estruturados para laudo químico de THC.

    HISTÓRICO DA CONVERSA:
    {historico_texto}

    IMPORTANTE: 
    - NÃO invente nada
    - APENAS extraia o que o usuário disse explicitamente
    - Se um dado não foi fornecido, retorne null
    - Seja PRECISO e LITERAL

    Retorne JSON com estes campos (use null se não fornecido):
    {{
        "numero_laudo": "número do laudo",
        "servico_pericial": "ex: DPE/IC/PC/SESP/RR",
        "nome_diretor": "nome do diretor do IC",
        "nome_perito": "nome completo do perito",
        "tipo_autoridade": "do Delegado | da Delegada | do Promotor | etc",
        "nome_autoridade": "nome da autoridade requisitante",
        "numero_requisicao": "número da requisição",
        "data_requisicao": "data no formato DD/MM/AAAA",
        "tipo_procedimento": "TCO | IP | APF | IPL",
        "numero_procedimento": "número do procedimento",
        "descricao_material": "descrição completa do material",
        "massa_bruta_total": "ex: 2,30g (dois gramas e trinta centigramas)",
        "lacres_entrada": "números dos lacres",
        "resultado": "POSITIVO | NEGATIVO",
        "peso_consumido": "ex: 0,50g",
        "peso_contraprova": "ex: 1,50g",
        "lacres_contraprova": "números dos lacres",
        "massa_liquida_final": "ex: 0,30g",
        "lacres_saida": "números dos lacres",
        "numero_paginas": "ex: 02",
        "nome_perito_assinatura": "nome para assinatura",
        "matricula_perito": "matrícula do perito"
    }}

    Retorne APENAS o JSON, sem texto adicional."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # baixíssimo para não inventar
                max_tokens=1000
            )
            
            # Extrai JSON da resposta
            resposta_texto = response.choices[0].message.content.strip()
            
            # Remove markdown se houver
            if resposta_texto.startswith('```'):
                resposta_texto = resposta_texto.split('```')[1]
                if resposta_texto.startswith('json'):
                    resposta_texto = resposta_texto[4:]
            
            dados = json.loads(resposta_texto)
            
            # Remove valores null
            dados_limpos = {k: v for k, v in dados.items() if v is not None}
            
            return dados_limpos
        
        except Exception as e:
            print(f"Erro ao extrair dados THC: {e}")
            return {}

    def _gerar_pergunta_thc_faltantes(self, faltantes: list, invalidos: list) -> str:
        """Gera pergunta conversacional sobre campos faltantes do laudo THC"""
        
        if not faltantes and not invalidos:
            return ""
        
        # Tradução dos campos para linguagem natural
        campos_traducao = {
            'numero_laudo': 'número do laudo',
            'servico_pericial': 'sigla do serviço pericial (ex: DPE/IC/PC/SESP/RR)',
            'nome_diretor': 'nome do Diretor do Instituto de Criminalística',
            'nome_perito': 'nome completo do Perito que realizou o exame',
            'tipo_autoridade': 'tipo da autoridade (Delegado/Delegada/Promotor/etc)',
            'nome_autoridade': 'nome completo da autoridade requisitante',
            'numero_requisicao': 'número da Requisição de Exame Pericial',
            'data_requisicao': 'data da requisição (DD/MM/AAAA)',
            'tipo_procedimento': 'tipo de procedimento (TCO, IP, APF ou IPL)',
            'numero_procedimento': 'número do procedimento',
            'descricao_material': 'descrição detalhada do material examinado',
            'massa_bruta_total': 'massa bruta total do material (ex: 2,30g)',
            'lacres_entrada': 'número(s) dos lacres de entrada',
            'resultado': 'resultado do exame (POSITIVO ou NEGATIVO)',
            'peso_consumido': 'peso consumido no exame',
            'peso_contraprova': 'peso encaminhado para contraprova',
            'lacres_contraprova': 'número(s) dos lacres da contraprova',
            'massa_liquida_final': 'massa líquida final a ser devolvida',
            'lacres_saida': 'número(s) dos lacres de saída',
            'numero_paginas': 'número de páginas do laudo',
            'nome_perito_assinatura': 'nome do perito para assinatura',
            'matricula_perito': 'matrícula do perito'
        }
        
        prompt = f"""O usuário quer gerar um laudo químico de THC, mas faltam dados.

    CAMPOS FALTANTES:
    {chr(10).join([f'- {campos_traducao.get(campo, campo)}' for campo in faltantes])}

    {f"CAMPOS INVÁLIDOS:{chr(10)}" + chr(10).join([f"- {inv['campo']}: valor '{inv['valor_fornecido']}' não é válido. Opções: {inv['valores_permitidos']}" for inv in invalidos]) if invalidos else ''}

    Faça UMA pergunta conversacional, amigável e clara pedindo essas informações.
    Agrupe os campos relacionados quando possível.
    Seja específico mas não intimidador.
    Use no máximo 6-8 linhas."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=400
            )
            
            return response.choices[0].message.content
        
        except:
            # Fallback se IA falhar
            campos_texto = ', '.join([campos_traducao.get(c, c) for c in faltantes[:5]])
            return f"Para gerar o laudo, ainda preciso de: {campos_texto}. Pode me fornecer essas informações?"
    
    
    def gerar_laudo_completo(self, tipo_laudo, dados_coletados):
        """Gera laudo completo baseado nas informacoes coletadas"""
        
        referencias = self.rag.buscar_similares(f"Laudo pericial de {tipo_laudo}", tipo_laudo, n_results=5)
        contexto_rag = "\n\n".join([f"EXEMPLO {i+1}:\n{ref}" for i, ref in enumerate(referencias)])
        
        prompt = f"""GERE O LAUDO PERICIAL COMPLETO, DETALHADO E PROFISSIONAL.

TIPO: {tipo_laudo}

INFORMACOES COLETADAS:
{dados_coletados['historico']}

EXEMPLOS DE ESTRUTURA DE LAUDOS SIMILARES:
{contexto_rag}

INSTRUCOES DETALHADAS:
1. Siga a estrutura formal dos exemplos fornecidos
2. Use APENAS os dados fornecidos pelo usuario (NAO invente)
3. Seja formal, tecnico e profissional no estilo
4. Inclua TODAS as secoes necessarias (preambulo, historico, exames, discussao, conclusoes)
5. Use terminologia tecnica apropriada
6. Fundamente tecnicamente quando necessario
7. Seja COMPLETO e DETALHADO
8. Use formatacao clara com secoes bem definidas
9. Se houver calculos mencionados, inclua-os com fundamentacao
10. Mantenha tom impessoal e objetivo

O laudo deve ser PROFISSIONAL e pronto para uso oficial."""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=8000  # AUMENTADO de 4000 para 8000!
        )
        
        return response.choices[0].message.content