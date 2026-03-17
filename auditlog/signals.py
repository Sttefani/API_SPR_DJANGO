"""
# SPR-CRIMINALÍSTICA - Sistema de Organização Pericial
# Desenvolvido por: Perito Criminal Sttefani Ribeiro
# Versão 1.0 - 2025

Signals que escutam post_save e post_delete dos módulos auditados
sem modificar nenhum app existente.
"""

from .middleware import get_current_user

# Apps que serão auditados
AUDITED_APPS = {
    'usuarios',
    'ocorrencias',
    'movimentacoes',
    'ordens_servico',
    'procedimentos',
    'procedimentos_cadastrados',
    'exames',
    'classificacoes',
    'cidades',
    'cargos',
    'autoridades',
    'unidades_demandantes',
    'tipos_documento',
    'servicos_periciais',
    'IA',
}

# Models internos que não devem gerar log
EXCLUDED_MODELS = {'AuditLog'}


def _registrar_log(sender, instance, acao):
    if sender.__name__ in EXCLUDED_MODELS:
        return
    if sender._meta.app_label not in AUDITED_APPS:
        return

    from .models import AuditLog

    try:
        repr_str = str(instance)[:250]
    except Exception:
        repr_str = f"ID: {instance.pk}"

    AuditLog.objects.create(
        usuario=get_current_user(),
        acao=acao,
        app_label=sender._meta.app_label,
        modelo=sender._meta.verbose_name.title() if sender._meta.verbose_name else sender.__name__,
        objeto_id=str(instance.pk) if instance.pk else '?',
        objeto_repr=repr_str,
    )


def handle_save(sender, instance, created, **kwargs):
    acao = 'criou' if created else 'editou'
    _registrar_log(sender, instance, acao)


def handle_delete(sender, instance, **kwargs):
    _registrar_log(sender, instance, 'deletou')
