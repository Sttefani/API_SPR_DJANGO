from django.db import models
from django.utils import timezone
from django.conf import settings

class LaudoReferencia(models.Model):
    """PDFs de laudos antigos para usar como referência"""
    titulo = models.CharField(max_length=200)
    tipo_exame = models.CharField(max_length=100)
    arquivo_pdf = models.FileField(upload_to='laudos_referencia/')
    texto_extraido = models.TextField(blank=True)
    processado = models.BooleanField(default=False)
    pasta_origem = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Laudo de Referência"
        verbose_name_plural = "Laudos de Referência"
    
    def __str__(self):
        return f"{self.titulo} ({self.tipo_exame})"


class TemplateLaudo(models.Model):
    """Template de laudo pericial com placeholders para preenchimento automático"""
    
    TIPOS_LAUDO = [
        ('quimico_preliminar_thc', 'Químico Preliminar - THC'),
        ('quimico_definitivo_thc', 'Químico Definitivo - THC'),
    ]
    
    tipo = models.CharField(max_length=50, choices=TIPOS_LAUDO, unique=True)
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    template_texto = models.TextField(
        help_text="Use {{variavel}} para placeholders. Ex: {{nome_perito}}, {{data_requisicao}}"
    )
    campos_obrigatorios = models.JSONField(
        default=list,
        help_text="Lista de campos que devem ser preenchidos pelo usuário"
    )
    campos_com_validacao = models.JSONField(
        default=dict,
        help_text='Ex: {"resultado": ["POSITIVO", "NEGATIVO"]}'
    )
    campos_automaticos = models.JSONField(
        default=list,
        help_text='Ex: ["ano_atual", "data_laudo_extenso"]'
    )
    exemplo_dados = models.JSONField(
        default=dict,
        help_text="Exemplo de como preencher os dados"
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ia_template_laudo'
        verbose_name = 'Template de Laudo'
        verbose_name_plural = 'Templates de Laudos'
    
    def __str__(self):
        return f"{self.nome} ({self.tipo})"
    
    def _gerar_campos_automaticos(self, dados: dict) -> dict:
        agora = timezone.now()
        numeros_extenso = {1: 'um', 2: 'dois', 3: 'três', 4: 'quatro', 5: 'cinco', 6: 'seis', 7: 'sete', 8: 'oito', 9: 'nove', 10: 'dez', 11: 'onze', 12: 'doze', 13: 'treze', 14: 'quatorze', 15: 'quinze', 16: 'dezesseis', 17: 'dezessete', 18: 'dezoito', 19: 'dezenove', 20: 'vinte', 21: 'vinte e um', 22: 'vinte e dois', 23: 'vinte e três', 24: 'vinte e quatro', 25: 'vinte e cinco', 26: 'vinte e seis', 27: 'vinte e sete', 28: 'vinte e oito', 29: 'vinte e nove', 30: 'trinta', 31: 'trinta e um'}
        meses_extenso = {1: 'janeiro', 2: 'fevereiro', 3: 'março', 4: 'abril', 5: 'maio', 6: 'junho', 7: 'julho', 8: 'agosto', 9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'}
        
        # ✅ CALCULAR NÚMERO DE PÁGINAS AUTOMATICAMENTE
        # Estimativa: 1 página A4 = ~3000 caracteres (fonte 12, margens padrão)
        num_chars = len(self.template_texto)
        num_paginas = max(1, (num_chars // 3000) + 1)
        numero_paginas_formatado = str(num_paginas).zfill(2)  # Ex: "02"
        
        campos_auto = {
            'ano_atual': str(agora.year),
            'ano_numero': str(agora.year),
            'ano_extenso': self._numero_ano_extenso(agora.year),
            'dia_numero': f"{agora.day:02d}",
            'dia_extenso': numeros_extenso.get(agora.day, str(agora.day)),
            'mes_numero': f"{agora.month:02d}",
            'mes_extenso': meses_extenso[agora.month],
            'data_laudo_extenso': f"{agora.day} de {meses_extenso[agora.month]} de {agora.year}",
            'numero_paginas': numero_paginas_formatado,  # ✅ NOVO CAMPO AUTOMÁTICO
        }
        return {**campos_auto, **dados}
    
    def _numero_ano_extenso(self, ano: int) -> str:
        milhares = ano // 1000
        centenas = (ano % 1000) // 100
        dezenas_unidades = ano % 100
        texto = ""
        if milhares == 2: texto = "dois mil"
        elif milhares == 1: texto = "mil"
        if centenas > 0:
            centenas_extenso = {1: 'cento', 2: 'duzentos', 3: 'trezentos', 4: 'quatrocentos', 5: 'quinhentos', 6: 'seiscentos', 7: 'setecentos', 8: 'oitocentos', 9: 'novecentos'}
            texto += " e " + centenas_extenso[centenas]
        if dezenas_unidades > 0:
            numeros = {1: 'um', 2: 'dois', 3: 'três', 4: 'quatro', 5: 'cinco', 6: 'seis', 7: 'sete', 8: 'oito', 9: 'nove', 10: 'dez', 11: 'onze', 12: 'doze', 13: 'treze', 14: 'quatorze', 15: 'quinze', 16: 'dezesseis', 17: 'dezessete', 18: 'dezoito', 19: 'dezenove', 20: 'vinte', 30: 'trinta', 40: 'quarenta', 50: 'cinquenta', 60: 'sessenta', 70: 'setenta', 80: 'oitenta', 90: 'noventa'}
            if dezenas_unidades <= 20:
                texto += " e " + numeros[dezenas_unidades]
            else:
                dezena = (dezenas_unidades // 10) * 10
                unidade = dezenas_unidades % 10
                texto += " e " + numeros[dezena]
                if unidade > 0: texto += " e " + numeros[unidade]
        return texto
    
    def validar_dados(self, dados: dict) -> tuple:
        faltantes = []
        invalidos = []
        for campo in self.campos_obrigatorios:
            if campo in self.campos_automaticos: continue
            if campo not in dados or not dados[campo]: faltantes.append(campo)
        for campo, valores_permitidos in self.campos_com_validacao.items():
            if campo in dados and dados[campo]:
                if dados[campo] not in valores_permitidos:
                    invalidos.append({'campo': campo, 'valor_fornecido': dados[campo], 'valores_permitidos': valores_permitidos})
        return (len(faltantes) == 0 and len(invalidos) == 0, faltantes, invalidos)
    
    def preencher(self, dados: dict) -> str:
        dados_completos = self._gerar_campos_automaticos(dados)
        valido, faltantes, invalidos = self.validar_dados(dados_completos)
        if not valido:
            erros = []
            if faltantes: erros.append(f"Campos obrigatórios faltantes: {', '.join(faltantes)}")
            if invalidos:
                for inv in invalidos: erros.append(f"Campo '{inv['campo']}' tem valor inválido '{inv['valor_fornecido']}'. Valores permitidos: {inv['valores_permitidos']}")
            raise ValueError('\n'.join(erros))
        try:
            laudo_preenchido = self.template_texto.format(**dados_completos)
            return laudo_preenchido
        except KeyError as e:
            raise ValueError(f"Campo não encontrado no template: {e}")


class LaudoGerado(models.Model):
    """Registro de laudos gerados pelo sistema"""
    
    template = models.ForeignKey(TemplateLaudo, on_delete=models.PROTECT)
    dados_preenchimento = models.JSONField()
    laudo_texto = models.TextField()
    resultado = models.CharField(
        max_length=20, 
        blank=True,
        help_text="Ex: POSITIVO, NEGATIVO"
    )
    pdf_arquivo = models.FileField(upload_to='laudos/pdf/', null=True, blank=True)
    gerado_em = models.DateTimeField(auto_now_add=True)
    gerado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        db_table = 'ia_laudo_gerado'
        verbose_name = 'Laudo Gerado'
        verbose_name_plural = 'Laudos Gerados'
        ordering = ['-gerado_em']
    
    def __str__(self):
        return f"Laudo {self.template.tipo} - {self.gerado_em.strftime('%d/%m/%Y %H:%M')}"