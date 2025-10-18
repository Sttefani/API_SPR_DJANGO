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
                tipo_piso = 'asfalto'  # padrão
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

                # Detecta condição (funciona com qualquer tipo de piso)
                condicao = 'seco'  # padrão
                if 'molhad' in mensagem_lower or 'chuva' in mensagem_lower or 'umid' in mensagem_lower:
                    condicao = 'molhado'
                elif 'óleo' in mensagem_lower or 'oleo' in mensagem_lower or 'graxa' in mensagem_lower:
                    condicao = 'com_oleo'
                elif tipo_piso == 'lama':  # lama já é implicitamente molhado
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
        
        return False, {}
    
    def _gerar_explicacao_contexto(self, resultado_calculo, pergunta_original):
        """Gera explicação adicional contextualizada para cálculos"""
        
        pergunta_lower = pergunta_original.lower()
        
        # Se usuário fez pergunta elaborada ou tem "?", dá resposta mais elaborada
        if len(pergunta_original) > 100 or '?' in pergunta_original:
            system_prompt = f"""Você acabou de fazer um cálculo técnico pericial.

Resultado: {resultado_calculo.get('tipo', 'cálculo')}

O usuário perguntou: "{pergunta_original}"

Forneça uma breve explicação adicional (2-4 frases) sobre:
- O que esse resultado significa na prática pericial
- Se há pontos de atenção importantes
- Contexto forense relevante

Seja técnico mas acessível. Não repita o que já foi dito no cálculo."""
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": system_prompt}],
                    temperature=0.4,
                    max_tokens=300,
                    top_p=0.9
                )
                return "\n" + response.choices[0].message.content
            except:
                return ""
        
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
        
        # ========== DETECTA FASE DA CONVERSA ==========
        fase = self.detectar_fase_conversa(contexto_chat or [])
        print(f"Fase da conversa: {fase}")
        
        # ========== 1. DETECTA SE É PEDIDO DE CÁLCULO ==========
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
        
        # ========== 2. SE DETECTOU CÁLCULO, COLETA PARÂMETROS ==========
        if tipo_calculo:
            print(f"Calculo detectado: {tipo_calculo}")
            fase = 'CALCULO'
            
            tem_calculo, resultado_calculo = self.detectar_e_executar_calculo(pergunta)
            
            if tem_calculo and resultado_calculo.get('tipo') != 'erro_calculo':
                # Gera explicação adicional contextualizada
                explicacao_adicional = self._gerar_explicacao_contexto(resultado_calculo, pergunta)
                
                return f"""CALCULO EXECUTADO!

{resultado_calculo['interpretacao']}
{explicacao_adicional}

Precisa de mais algum calculo ou quer que eu ajude com o laudo?"""
            
            elif tem_calculo and resultado_calculo.get('tipo') == 'erro_calculo':
                # Mostra o erro ao usuário
                return f"""Erro ao executar calculo: {resultado_calculo['erro']}

Tente reformular ou me diga os parametros claramente.
Exemplo: "30 metros em grama seca" ou "25m asfalto molhado"
"""
            
            else:
                perguntas_parametros = {
                    'velocidade_frenagem': """Entendido! Para calcular a velocidade pela marca de frenagem, preciso de algumas informacoes:

DISTANCIA DA MARCA EM METROS - O comprimento da marca de arrasto no solo

TIPO DE PISO - Qual superficie? (asfalto, concreto, terra, cascalho, grama)

CONDICAO DO PISO - Como estava? (seco, molhado, com oleo)

Exemplo: "A marca tem 25 metros em asfalto seco"

Pode me passar essas informacoes?""",
                    
                    'arrastamento_solo': """Certo! Para calcular a velocidade de arrastamento pos-colisao, preciso de:

DISTANCIA DO ARRASTO - Quantos metros o veiculo deslizou apos a colisao?

Este calculo e diferente da frenagem, pois considera o veiculo ja sem controle, deslizando lateralmente ou capotado.

Qual foi a distancia?""",
                    
                    'energia_cinetica': """Ok! Para calcular a energia cinetica envolvida, preciso de:

MASSA DO VEICULO EM KG - Peso aproximado (ex: carro popular ~1200kg, SUV ~2000kg, moto ~150kg)

VELOCIDADE EM KM/H - A velocidade no momento que voce quer analisar

A energia cinetica cresce com o QUADRADO da velocidade, entao pequenas diferencas de velocidade resultam em grandes diferencas de energia.

Tem esses dados?""",
                    
                    'tempo_reacao': """Entendi! Para calcular tempo de reacao e distancia percorrida durante a reacao, preciso de:

VELOCIDADE DO VEICULO EM KM/H - A velocidade no momento da percepcao do perigo

CONDICAO DO MOTORISTA - Como ele estava?
   - Normal/Alerta (1.0s)
   - Distraido (1.5s)
   - Cansado/Sono (2.0s)
   - Sob efeito de alcool (2.5s+)

Durante o tempo de reacao, o veiculo continua em velocidade CONSTANTE antes de comecar a frear.

Quais sao essas informacoes?""",
                }
                
                return perguntas_parametros.get(tipo_calculo, "Preciso de mais informacoes. Pode detalhar?")
        
        # ========== 3. TENTA EXECUTAR CÁLCULO ==========
        tem_calculo, resultado_calculo = self.detectar_e_executar_calculo(pergunta)
        
        if tem_calculo:
            calculos_validos = ['calculo_velocidade_frenagem', 'calculo_arrastamento_solo', 'calculo_energia', 'calculo_tempo_reacao']
            
            if resultado_calculo['tipo'] in calculos_validos:
                # Gera explicação adicional
                explicacao_adicional = self._gerar_explicacao_contexto(resultado_calculo, pergunta)
                
                return f"""CALCULO EXECUTADO!

{resultado_calculo['interpretacao']}
{explicacao_adicional}

Precisa de mais algum calculo ou quer continuar com o laudo?"""
            
            elif resultado_calculo['tipo'] == 'erro_calculo':
                return f"""Erro ao executar calculo: {resultado_calculo['erro']}

Tente reformular ou me diga os parametros claramente.
Exemplo: "30 metros em grama seca" ou "25m asfalto molhado"
"""
        
        # ========== 4. PERGUNTAS TÉCNICAS ==========
        perguntas_tecnicas = ['por que', 'porque', 'como funciona', 'explica', 'metodologia', 'como calcula']
        
        if any(palavra in pergunta_lower for palavra in perguntas_tecnicas):
            print("Pergunta tecnica detectada")
            
            referencias = self.rag.buscar_similares(pergunta, tipo_laudo, n_results=3)
            contexto_rag = "\n\n".join([f"Referencia {i+1}:\n{ref[:300]}..." for i, ref in enumerate(referencias)])
            
            system_prompt = f"""Voce e um assistente especializado em pericia forense.

O usuario fez uma pergunta tecnica. Responda de forma:
- Tecnica mas acessivel
- Fundamentada cientificamente
- Com referencias quando possivel
- Clara e objetiva
- Use exemplos praticos se apropriado

REFERENCIAS:
{contexto_rag}

Pode usar ate 500 palavras se necessario para responder bem."""
            
            messages = [{"role": "system", "content": system_prompt}]
            if contexto_chat:
                messages.extend(contexto_chat[-8:])
            messages.append({"role": "user", "content": pergunta})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.4,
                max_tokens=600,
                top_p=0.9
            )
            
            return response.choices[0].message.content
        
        # ========== 5. CONVERSAÇÃO POR FASE ==========
        if fase == 'ACOLHIMENTO':
            system_prompt = f"""Voce e um assistente de pericia criminal amigavel e profissional.

O usuario acabou de iniciar a conversa. Sua missao:

1. Cumprimente de forma calorosa mas profissional
2. Apresente-se brevemente
3. Pergunte como pode ajudar
4. Mencione que voce pode:
   - Ajudar a elaborar laudos periciais
   - Fazer calculos tecnicos (velocidade, energia, etc)
   - Tirar duvidas sobre metodologias

Seja HUMANO, EMPATICO e ACOLHEDOR.
Use no maximo 4-5 linhas.

Tipo de laudo contexto: {tipo_laudo}"""

        elif fase == 'CONTEXTO':
            system_prompt = f"""Voce e um assistente de pericia criminal conversando naturalmente.

O usuario esta explicando o que precisa. Sua missao:

1. ENTENDA o contexto e a necessidade dele
2. Se ele mencionou um tipo de caso (acidente, homicidio, etc), RECONHECA isso
3. Pergunte se ele quer:
   - Elaborar um laudo completo
   - Fazer algum calculo especifico
   - Tirar duvidas tecnicas

Seja NATURAL, nao robotizado.
Faca NO MAXIMO 2 perguntas por vez.
Use tom profissional mas acessivel.
Pode usar ate 6-7 linhas.

Tipo de laudo: {tipo_laudo}"""

        else:  # COLETA
            referencias = self.rag.buscar_similares(pergunta, tipo_laudo, n_results=2)
            contexto_rag = "\n\n".join([f"Ex {i+1}:\n{ref[:250]}..." for i, ref in enumerate(referencias)])
            
            system_prompt = f"""Voce esta coletando informacoes para um laudo pericial.

CONTEXTO: Ja entendeu o que o usuario precisa. Agora esta coletando dados estruturados.

PROIBICOES:
- NAO gere o laudo ainda
- NAO invente dados

INSTRUCOES:
1. Analise a resposta anterior do usuario
2. Agradeca brevemente (ex: "Entendi!")
3. Faca a PROXIMA pergunta necessaria (apenas UMA)
4. Seja contextualizado (mencione o que ele ja disse se relevante)

Dados tipicos:
1. Autoridade requisitante
2. Data do fato
3. Local
4. Material examinado
5. Resultados/Conclusoes

Exemplos de estrutura:
{contexto_rag}

Tipo: {tipo_laudo}"""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if contexto_chat:
            messages.extend(contexto_chat[-6:])
        
        messages.append({"role": "user", "content": pergunta})
        
        # Ajusta parametros por fase (TOKENS AUMENTADOS!)
        if fase == 'ACOLHIMENTO':
            max_tokens = 300
            temperature = 0.7
        elif fase == 'CONTEXTO':
            max_tokens = 400
            temperature = 0.5
        else:  # COLETA
            max_tokens = 250
            temperature = 0.2
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=0.85
        )
        
        return response.choices[0].message.content
    
    def gerar_laudo_completo(self, tipo_laudo, dados_coletados):
        """Gera laudo completo baseado nas informacoes coletadas"""
        
        referencias = self.rag.buscar_similares(f"Laudo pericial de {tipo_laudo}", tipo_laudo, n_results=5)
        contexto_rag = "\n\n".join([f"EXEMPLO {i+1}:\n{ref}" for i, ref in enumerate(referencias)])
        
        prompt = f"""GERE O LAUDO PERICIAL COMPLETO.

TIPO: {tipo_laudo}

INFORMACOES COLETADAS:
{dados_coletados['historico']}

EXEMPLOS DE ESTRUTURA:
{contexto_rag}

REGRAS:
- Siga a estrutura dos exemplos
- Use APENAS dados fornecidos
- NAO invente informacoes
- Seja formal e tecnico
- Inclua todas as secoes necessarias"""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4000
        )
        
        return response.choices[0].message.content