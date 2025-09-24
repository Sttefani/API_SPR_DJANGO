# movimentacoes/serializers.py

from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Movimentacao
from usuarios.serializers import UserNestedSerializer


class MovimentacaoSerializer(serializers.ModelSerializer):
    """
    Serializer para EXIBIR os detalhes de uma movimentação.
    """
    created_by = UserNestedSerializer(read_only=True)
    updated_by = UserNestedSerializer(read_only=True)

    class Meta:
        model = Movimentacao
        fields = [
            'id', 'ocorrencia', 'assunto', 'descricao',
            'ip_registro', 'created_at', 'updated_at',
            'created_by', 'updated_by',
        ]
        read_only_fields = fields


class CriarMovimentacaoSerializer(serializers.Serializer):
    """
    Serializer de AÇÃO para registrar uma nova movimentação com assinatura,
    seguindo o padrão já existente no app de ocorrências.
    """
    assunto = serializers.CharField(max_length=255, label="Assunto")
    descricao = serializers.CharField(style={'base_template': 'textarea.html'}, label="Descrição")
    
    # Campos de assinatura (idênticos ao ReabrirOcorrenciaSerializer)
    username = serializers.CharField(
        max_length=150,
        label="Email de Confirmação",
        help_text="Confirme seu email de login para assinar a movimentação."
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        label="Senha de Confirmação"
    )

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user
        username_input = attrs.get('username')
        password = attrs.get('password')

        # Valida o email
        if username_input != user.email:
            raise serializers.ValidationError({
                'username': 'O email de confirmação deve ser o mesmo do seu email de login.'
            })

        # Valida a senha usando authenticate
        authenticated_user = authenticate(
            request=request,
            email=username_input,
            password=password
        )
        if not authenticated_user or authenticated_user.id != user.id:
            raise serializers.ValidationError({
                'password': 'Senha incorreta.'
            })
        
        return attrs

    def create(self, validated_data):
        ocorrencia = self.context['ocorrencia']
        request = self.context['request']
        user = request.user
        
        # Remove os campos de assinatura que não são do modelo
        validated_data.pop('username')
        validated_data.pop('password')
        
        ip_address = request.META.get('REMOTE_ADDR', '127.0.0.1')

        movimentacao = Movimentacao.objects.create(
            ocorrencia=ocorrencia,
            created_by=user,
            ip_registro=ip_address,
            **validated_data
        )
        return movimentacao