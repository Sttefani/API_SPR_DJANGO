from rest_framework import serializers
from .models import LaudoGerado

class LaudoGeradoListSerializer(serializers.ModelSerializer):
    """Serializer para listar laudos gerados"""
    
    gerado_por_nome = serializers.SerializerMethodField()
    template_nome = serializers.CharField(source='template.nome', read_only=True)

    class Meta:
        model = LaudoGerado
        fields = ['id', 'template_nome', 'resultado', 'gerado_por_nome', 'gerado_em']

    def get_gerado_por_nome(self, obj):
        """
        Retorna o nome do usuário usando o modelo customizado
        que tem 'nome_completo' e 'email' ao invés de 'username'
        """
        if not obj.gerado_por:
            return 'Sistema'
        
        # 1. Tenta nome_completo (campo customizado)
        if obj.gerado_por.nome_completo:
            return obj.gerado_por.nome_completo
        
        # 2. Usa email como fallback
        if obj.gerado_por.email:
            return obj.gerado_por.email
        
        # 3. Último recurso
        return f'Usuário #{obj.gerado_por.id}'