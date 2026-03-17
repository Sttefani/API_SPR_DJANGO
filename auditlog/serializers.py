"""
# SPR-CRIMINALÍSTICA - Sistema de Organização Pericial
# Desenvolvido por: Perito Criminal Sttefani Ribeiro
# Versão 1.0 - 2025
"""

from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    usuario_nome = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'usuario',
            'usuario_nome',
            'acao',
            'app_label',
            'modelo',
            'objeto_id',
            'objeto_repr',
            'timestamp',
        ]

    def get_usuario_nome(self, obj):
        if not obj.usuario:
            return 'Sistema'
        return obj.usuario.get_full_name() or obj.usuario.username
