from typing import Dict, Any

class CalculadoraTempoReacao:
    """
    Cálculos de tempo de reação e distância de parada total
    """
    
    # Tempos de reação típicos (segundos)
    TEMPOS_REACAO = {
        'alerta_bom': 0.75,      # Motorista atento, boas condições
        'normal': 1.0,            # Situação normal
        'distraido': 1.5,         # Distraído, situação complexa
        'cansado': 2.0,           # Cansaço, sono
        'alcool': 2.5,            # Sob efeito de álcool
        'surpresa': 1.5,          # Situação inesperada
    }
    
    def calcular_distancia_reacao(
        self,
        velocidade_kmh: float,
        tempo_reacao_s: float = None,
        condicao: str = 'normal'
    ) -> Dict[str, Any]:
        """
        Calcula distância percorrida durante tempo de reação
        
        Durante este tempo, o veículo mantém velocidade constante
        (motorista ainda não acionou freios)
        
        Fórmula: d = v × t
        
        Args:
            velocidade_kmh: Velocidade em km/h
            tempo_reacao_s: Tempo de reação em segundos (opcional)
            condicao: Condição do motorista (se tempo_reacao não informado)
        """
        
        if velocidade_kmh < 0:
            raise ValueError("Velocidade não pode ser negativa")
        
        # Define tempo de reação
        if tempo_reacao_s is None:
            if condicao not in self.TEMPOS_REACAO:
                raise ValueError(f"Condição inválida. Opções: {list(self.TEMPOS_REACAO.keys())}")
            tempo_reacao_s = self.TEMPOS_REACAO[condicao]
        
        if tempo_reacao_s <= 0:
            raise ValueError("Tempo de reação deve ser maior que zero")
        
        # Conversão
        velocidade_ms = velocidade_kmh / 3.6
        
        # Distância = velocidade × tempo
        distancia_m = velocidade_ms * tempo_reacao_s
        
        return {
            'distancia_reacao_m': round(distancia_m, 2),
            'tempo_reacao_s': tempo_reacao_s,
            'velocidade_kmh': velocidade_kmh,
            'velocidade_ms': round(velocidade_ms, 2),
            'condicao': condicao,
            'formula': 'd = v × t',
            'fundamentacao': [
                'Distância percorrida entre detecção do perigo e início da frenagem',
                'Durante este tempo o veículo mantém velocidade constante',
                'Tempo de reação varia conforme estado do motorista:',
                f'  - Alerta/Bom: {self.TEMPOS_REACAO["alerta_bom"]}s',
                f'  - Normal: {self.TEMPOS_REACAO["normal"]}s',
                f'  - Distraído: {self.TEMPOS_REACAO["distraido"]}s',
                f'  - Cansado: {self.TEMPOS_REACAO["cansado"]}s',
                'Referências:',
                '  - Green, M. (2000). How Long Does It Take to Stop?',
                '  - Taoka, G.T. (1989). Brake Reaction Times of Unalerted Drivers',
                '  - AASHTO - A Policy on Geometric Design of Highways'
            ]
        }
    
    def calcular_distancia_parada_total(
        self,
        velocidade_kmh: float,
        distancia_frenagem_m: float,
        tempo_reacao_s: float = None,
        condicao: str = 'normal'
    ) -> Dict[str, Any]:
        """
        Calcula distância total de parada (reação + frenagem)
        
        Distância Total = Distância de Reação + Distância de Frenagem
        """
        
        # Calcula distância de reação
        reacao = self.calcular_distancia_reacao(velocidade_kmh, tempo_reacao_s, condicao)
        
        distancia_total = reacao['distancia_reacao_m'] + distancia_frenagem_m
        
        return {
            'distancia_total_m': round(distancia_total, 2),
            'distancia_reacao_m': reacao['distancia_reacao_m'],
            'distancia_frenagem_m': distancia_frenagem_m,
            'tempo_reacao_s': reacao['tempo_reacao_s'],
            'velocidade_kmh': velocidade_kmh,
            'condicao': condicao,
            'percentual_reacao': round((reacao['distancia_reacao_m'] / distancia_total) * 100, 1),
            'percentual_frenagem': round((distancia_frenagem_m / distancia_total) * 100, 1)
        }
    
    def interpretar_distancia_reacao(self, resultado: Dict[str, Any]) -> str:
        """Interpretação da distância de reação"""
        
        texto = f"""DISTÂNCIA PERCORRIDA DURANTE TEMPO DE REAÇÃO

Parâmetros:
- Velocidade: {resultado['velocidade_kmh']:.2f} km/h ({resultado['velocidade_ms']:.2f} m/s)
- Tempo de reação: {resultado['tempo_reacao_s']:.2f} segundos
- Condição: {resultado['condicao'].title()}

Fórmula: {resultado['formula']}

RESULTADO:
Distância de reação: {resultado['distancia_reacao_m']:.2f} metros

INTERPRETAÇÃO:
Durante o tempo de reação, o motorista ainda NÃO pisou no freio.
O veículo continua em velocidade constante neste período.
Esta distância SOMA à distância de frenagem para calcular parada total.

Fundamentação:
"""
        for fund in resultado['fundamentacao']:
            texto += f"{fund}\n"
        
        return texto
    
    def interpretar_parada_total(self, resultado: Dict[str, Any]) -> str:
        """Interpretação da distância total de parada"""
        
        texto = f"""DISTÂNCIA TOTAL DE PARADA

Velocidade: {resultado['velocidade_kmh']:.2f} km/h
Condição do motorista: {resultado['condicao'].title()}

COMPOSIÇÃO:
1. Distância de reação:  {resultado['distancia_reacao_m']:>7.2f} m ({resultado['percentual_reacao']:.1f}%)
2. Distância de frenagem: {resultado['distancia_frenagem_m']:>7.2f} m ({resultado['percentual_frenagem']:.1f}%)
   ─────────────────────────────────────
   TOTAL:                   {resultado['distancia_total_m']:>7.2f} m

INTERPRETAÇÃO:
Esta é a distância necessária para parar COMPLETAMENTE o veículo,
desde o momento em que o motorista percebe o perigo até a parada total.
"""
        return texto