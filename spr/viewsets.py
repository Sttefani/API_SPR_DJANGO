from rest_framework import viewsets

class LimpaFormularioViewSetMixin:
    """
    Um 'mixin' que corrige o problema do formulário pré-preenchido
    na interface de teste do DRF.
    """
    def get_renderer_context(self):
        context = super().get_renderer_context()
        if self.action == 'list':
            # Força o formulário de criação a ser instanciado sem dados iniciais.
            # Usamos get_serializer_class para garantir que pegamos o serializer correto
            # (ex: OcorrenciaDetailSerializer) e não o de lista.
            serializer_class = self.get_serializer_class()
            # Precisamos de um contexto para o serializer aninhado de usuário
            context_extra = {'request': self.request}
            context['post_form'] = serializer_class(context=context_extra)
        return context

class CustomModelViewSet(LimpaFormularioViewSetMixin, viewsets.ModelViewSet):
    """
    Nossa ModelViewSet customizada que já vem com a correção do formulário.
    Use esta classe como base para todas as suas ViewSets de CRUD.
    """
    pass