# ordens_servico/models.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from ocorrencias.models import Ocorrencia
from usuarios.models import AuditModel
from unidades_demandantes.models import UnidadeDemandante
from autoridades.models import Autoridade
from procedimentos_cadastrados.models import ProcedimentoCadastrado
from tipos_documento.models import TipoDocumento


class OrdemServico(AuditModel):
    """
    Representa uma Ordem de Serviço, um documento formal com dados
    espelhados da ocorrência e seus próprios campos.
    """
    class Status(models.TextChoices):
        AGUARDANDO_CIENCIA = 'AGUARDANDO_CIENCIA', 'Aguardando Ciência'
        ABERTA = 'ABERTA', 'Aberta'
        EM_ANDAMENTO = 'EM_ANDAMENTO', 'Em Andamento'
        VENCIDA = 'VENCIDA', 'Vencida'
        CONCLUIDA = 'CONCLUIDA', 'Concluída'

    # --- Relação Principal ---
    ocorrencia = models.ForeignKey(
        Ocorrencia,
        on_delete=models.CASCADE,
        related_name='ordens_servico'
    )
    
    
    # --- Dados da Própria OS ---
    numero_os = models.CharField(
        max_length=20,
        unique=True,
        editable=False
    )
    
    prazo_dias = models.PositiveIntegerField(
        verbose_name="Prazo para Conclusão (em dias)"
    )
    
    texto_padrao = models.TextField(
        editable=False,
        default="O DIRETOR, NO USO DE SUAS ATRIBUIÇÕES LEGAIS, EMITE A PRESENTE ORDEM DE SERVIÇO, DETERMINANDO A REALIZAÇÃO DOS EXAMES E CONFECÇÃO DO LAUDO PERICIAL."
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AGUARDANDO_CIENCIA
    )
    
    data_conclusao = models.DateTimeField(null=True, blank=True)
    
    # --- OBSERVAÇÕES E JUSTIFICATIVAS ---
    observacoes_administrativo = models.TextField(
        blank=True,
        verbose_name="Observações do Administrativo",
        help_text="Observações internas sobre esta OS (não aparecem no PDF oficial)"
    )
    
    justificativa_atraso = models.TextField(
        blank=True,
        verbose_name="Justificativa de Atraso",
        help_text="Justificativa do perito em caso de atraso na entrega"
    )
    
    # --- HIERARQUIA DE COMANDO ---
    ordenada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='os_ordenadas',
        verbose_name="Ordenada por (Diretor/Chefe)"
    )
    
    # --- REITERAÇÃO ---
    os_original = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='reiteracoes',
        verbose_name="OS Original"
    )
    
    numero_reiteracao = models.PositiveIntegerField(
        default=0,
        verbose_name="Número da Reiteração",
        help_text="0 = Original, 1 = 1ª Reiteração, etc."
    )
    
    # --- DADOS ESPELHADOS DA OCORRÊNCIA (Snapshot no momento da criação) ---
    unidade_demandante = models.ForeignKey(
        UnidadeDemandante,
        on_delete=models.PROTECT,
        null=True
    )
    
    autoridade_demandante = models.ForeignKey(
        Autoridade,
        on_delete=models.PROTECT,
        null=True
    )
    
    procedimento = models.ForeignKey(
        ProcedimentoCadastrado,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    
    # --- DADOS ESPECÍFICOS DA OS ---
    tipo_documento_referencia = models.ForeignKey(
        TipoDocumento,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Documento de Referência"
    )
    
    numero_documento_referencia = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Nº do Documento de Referência"
    )
    
    processo_sei_referencia = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Processo SEI de Referência"
    )
    
    processo_judicial_referencia = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Processo Judicial de Referência"
    )

    # --- DADOS DE CIÊNCIA E VISUALIZAÇÃO (Assinatura do Perito) ---
    data_primeira_visualizacao = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Primeira Visualização",
        help_text="Quando o perito visualizou a OS pela primeira vez (mesmo sem dar ciência)"
    )
    
    ciente_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='os_cientes',
        verbose_name="Perito Ciente"
    )
    
    data_ciencia = models.DateTimeField(null=True, blank=True)
    ip_ciencia = models.GenericIPAddressField(null=True, blank=True)
    
    # ✅ NOVO CAMPO: Quem concluiu a OS
    concluida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordens_concluidas',
        verbose_name='Concluída por',
        help_text='Usuário que deu baixa/concluiu esta OS'
    )
    
    # ========================================
    # PROPRIEDADES CALCULADAS
    # ========================================
    
    @property
    def data_vencimento(self):
        """
        Calcula a data de vencimento baseada na ciência + prazo.
        Se ainda não teve ciência, retorna None.
        """
        if self.data_ciencia:
            return self.data_ciencia + timedelta(days=self.prazo_dias)
        return None
    
    @property
    def dias_desde_emissao(self):
        """Quantos dias se passaram desde que a OS foi emitida"""
        delta = timezone.now() - self.created_at
        return delta.days
    
    @property
    def dias_restantes(self):
        """
        Calcula quantos dias faltam para o vencimento.
        Retorna None se não houver ciência ainda.
        Retorna número negativo se já venceu.
        """
        if not self.data_vencimento:
            return None
        
        if self.status == self.Status.CONCLUIDA:
            return None
        
        delta = self.data_vencimento - timezone.now()
        return delta.days
    
    @property
    def esta_vencida(self):
        """Verifica se o prazo venceu"""
        if self.status == self.Status.CONCLUIDA:
            return False
        
        dias = self.dias_restantes
        if dias is None:
            return False
        
        return dias < 0
    
    @property
    def urgencia(self):
        """
        Retorna o nível de urgência para exibição de flags:
        - 'verde': 5+ dias restantes
        - 'amarelo': 3-4 dias restantes
        - 'laranja': 1-2 dias restantes
        - 'vermelho': Vencida ou 0 dias
        - None: Aguardando ciência
        """
        if self.status == self.Status.CONCLUIDA:
            return 'concluida'
        
        dias = self.dias_restantes
        if dias is None:
            return None  # Aguardando ciência
        
        if dias < 0:
            return 'vermelho'  # Vencida
        elif dias == 0:
            return 'vermelho'  # Vence hoje
        elif dias <= 2:
            return 'laranja'   # 1-2 dias
        elif dias <= 4:
            return 'amarelo'   # 3-4 dias
        else:
            return 'verde'     # 5+ dias
    
    @property
    def concluida_com_atraso(self):  # ← ADICIONAR AQUI
        """
        Verifica se a OS foi concluída após o prazo de vencimento.
        """
        if self.status != self.Status.CONCLUIDA or not self.data_conclusao:
            return None
        
        if not self.data_vencimento:
            return None
        
        return self.data_conclusao > self.data_vencimento
    
    @property
    def percentual_prazo_consumido(self):
        """
        Retorna 0-100% do prazo já consumido.
        Útil para barras de progresso visuais.
        """
        if not self.data_ciencia or self.status == self.Status.CONCLUIDA:
            return 0
        
        total_segundos = timedelta(days=self.prazo_dias).total_seconds()
        decorrido = (timezone.now() - self.data_ciencia).total_seconds()
        
        if total_segundos == 0:
            return 0
        
        percentual = (decorrido / total_segundos) * 100
        return min(int(percentual), 100)
    
    @property
    def prazo_acumulado_total(self):
        """
        Retorna o prazo total acumulado considerando a original + todas reiterações.
        Usado apenas para exibição visual.
        """
        if self.numero_reiteracao == 0:
            # É a original, soma ela + todas as reiterações
            total = self.prazo_dias
            for reit in self.reiteracoes.filter(deleted_at__isnull=True):
                total += reit.prazo_dias
            return total
        else:
            # É uma reiteração, busca a original e soma tudo
            original = self.os_original or self
            return original.prazo_acumulado_total
    
    @property
    def historico_completo(self):
        """
        Retorna todas as OS relacionadas (original + reiterações) ordenadas.
        """
        if self.numero_reiteracao == 0:
            # É a original
            todas = [self] + list(self.reiteracoes.filter(
                deleted_at__isnull=True).order_by('numero_reiteracao'))
        else:
            # É uma reiteração, busca a original
            original = self.os_original
            todas = [original] + list(original.reiteracoes.filter(
                deleted_at__isnull=True).order_by('numero_reiteracao'))
        
        return todas
    
    # ========================================
    # MÉTODOS
    # ========================================
    
    def ocultar_detalhes_ate_ciencia(self):
        return self.status == self.Status.AGUARDANDO_CIENCIA
    
    def registrar_visualizacao(self):
        """
        Registra a primeira vez que o perito visualizou a OS.
        Chamado automaticamente quando o perito abre o PDF ou detalhes.
        """
        if not self.data_primeira_visualizacao:
            self.data_primeira_visualizacao = timezone.now()
            self.save(update_fields=['data_primeira_visualizacao'])
    
    def tomar_ciencia(self, user, ip_address):
        """
        Registra a ciência do perito na OS com assinatura digital.
        """
        if not self.ciente_por:
            self.ciente_por = user
            self.data_ciencia = timezone.now()
            self.ip_ciencia = ip_address
            self.status = self.Status.ABERTA
            
            # Registra visualização se ainda não foi registrada
            if not self.data_primeira_visualizacao:
                self.data_primeira_visualizacao = self.data_ciencia
            
            self.save()
    
    def iniciar_trabalho(self, user):
        """
        Marca a OS como EM_ANDAMENTO quando o perito começa a trabalhar.
        """
        if self.status == self.Status.ABERTA:
            self.status = self.Status.EM_ANDAMENTO
            self.updated_by = user
            self.save()
    
    def justificar_atraso(self, justificativa, user):
        """
        Permite que o perito justifique o atraso na entrega.
        """
        self.justificativa_atraso = justificativa
        self.updated_by = user
        self.save()
    
    def reiterar(self, prazo_dias, ordenada_por, user, observacoes=''):
        """
        Cria uma OS de reiteração com prazo menor.
        Só permite reiterar a OS mais recente da cadeia.
        """
        from django.core.exceptions import ValidationError
        
        # Determina qual é a OS original
        original = self if self.numero_reiteracao == 0 else self.os_original
        
        # ✅ VALIDAÇÃO: Verifica se esta é a última OS da cadeia
        ultima_reiteracao = OrdemServico.objects.filter(
            os_original=original,
            deleted_at__isnull=True
        ).order_by('-numero_reiteracao').first()
        
        # Se existem reiterações, só pode reiterar a mais recente
        if ultima_reiteracao and ultima_reiteracao.id != self.id:
            raise ValidationError(
                f'Não é possível reiterar esta OS. '
                f'Você deve reiterar a OS mais recente: {ultima_reiteracao.numero_os} '
                f'({ultima_reiteracao.numero_reiteracao}ª Reiteração)'
            )
        
        # Cria a nova reiteração
        nova_os = OrdemServico.objects.create(
            ocorrencia=self.ocorrencia,
            prazo_dias=prazo_dias,
            ordenada_por=ordenada_por or self.ordenada_por,
            observacoes_administrativo=observacoes,
            unidade_demandante=self.unidade_demandante,
            autoridade_demandante=self.autoridade_demandante,
            procedimento=self.procedimento,
            tipo_documento_referencia=self.tipo_documento_referencia,
            numero_documento_referencia=self.numero_documento_referencia,
            processo_sei_referencia=self.processo_sei_referencia,
            processo_judicial_referencia=self.processo_judicial_referencia,
            os_original=original,
            numero_reiteracao=self.numero_reiteracao + 1,  # ✅ Incrementa corretamente
            created_by=user
        )
        return nova_os
        
    def concluir(self, user):
        """
        Marca a OS como concluída.
        Só pode ser feito pelo ADMINISTRATIVO.
        """
        self.status = self.Status.CONCLUIDA
        self.data_conclusao = timezone.now()
        self.concluida_por = user  # ✅ SALVA QUEM CONCLUIU
        self.updated_by = user
        self.save()
    
    def atualizar_status(self):
        """
        Atualiza automaticamente o status baseado no prazo.
        Deve ser chamado periodicamente (cronjob ou ao acessar).
        """
        if self.status == self.Status.CONCLUIDA:
            return
        
        if self.esta_vencida and self.status != self.Status.VENCIDA:
            self.status = self.Status.VENCIDA
            self.save(update_fields=['status'])

    def save(self, *args, **kwargs):
        # Gera o número da OS na primeira criação
        if not self.pk:
            ano = timezone.now().year
            ultimo_os = OrdemServico.objects.filter(
                numero_os__endswith=f"/{ano}"
            ).order_by('id').last()
            
            novo_numero = (
                int(ultimo_os.numero_os.split('/')[0]) + 1) if ultimo_os else 1
            self.numero_os = f"{novo_numero:04d}/{ano}"

        super(OrdemServico, self).save(*args, **kwargs)

    def __str__(self):
        if self.numero_reiteracao > 0:
            return f"OS {self.numero_os} ({self.numero_reiteracao}ª Reiteração)"
        return f"OS {self.numero_os}"

    class Meta:
        verbose_name = "Ordem de Serviço"
        verbose_name_plural = "Ordens de Serviço"
        ordering = ['-created_at']