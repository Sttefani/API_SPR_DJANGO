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
            "id",
            "ocorrencia",
            "assunto",
            "descricao",
            "ip_registro",
            "visualizado_admin",  # NOVO CAMPO
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
        ]
        read_only_fields = fields


class CriarMovimentacaoSerializer(serializers.Serializer):
    """
    Serializer de AÇÃO para registrar uma nova movimentação com assinatura,
    seguindo o padrão já existente no app de ocorrências.
    """

    assunto = serializers.CharField(max_length=255, label="Assunto")
    descricao = serializers.CharField(
        style={"base_template": "textarea.html"}, label="Descrição"
    )

    # Campos de assinatura (idênticos ao ReabrirOcorrenciaSerializer)
    username = serializers.CharField(
        max_length=150,
        label="Email de Confirmação",
        help_text="Confirme seu email de login para assinar a movimentação.",
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        label="Senha de Confirmação",
    )

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user
        username_input = attrs.get("username")
        password = attrs.get("password")

        print(f"🔍 DEBUG - Validando movimentação")
        print(f"👤 Usuário logado: {user.nome_completo} (ID: {user.id})")

        # ====== VALIDAÇÃO DE PERMISSÃO DE EDIÇÃO ======
        movimentacao = self.context.get("movimentacao")
        print(f"📝 Movimentação no contexto: {movimentacao}")

        if movimentacao:  # Se está editando
            print(f"✏️ MODO EDIÇÃO DETECTADO!")
            print(
                f"👤 Criado por: {movimentacao.created_by.nome_completo if movimentacao.created_by else 'Ninguém'} (ID: {movimentacao.created_by.id if movimentacao.created_by else 'N/A'})"
            )
            print(f"🔐 É super admin? {user.is_superuser}")

            # Super Admin pode editar qualquer movimentação
            if not user.is_superuser:
                # Outros usuários só podem editar suas próprias movimentações
                if movimentacao.created_by and movimentacao.created_by.id != user.id:
                    print(f"❌ BLOQUEANDO EDIÇÃO!")
                    raise serializers.ValidationError(
                        {
                            "non_field_errors": [
                                f"Você não pode editar uma movimentação criada por {movimentacao.created_by.nome_completo}. "
                                "Apenas o autor original ou um Super Administrador pode editá-la."
                            ]
                        }
                    )
                else:
                    print(f"✅ Permitindo edição (é o autor)")
            else:
                print(f"✅ Permitindo edição (é super admin)")
        else:
            print(f"➕ MODO CRIAÇÃO - sem validação de autor")
        # =============================================

        # Valida o email
        if username_input != user.email:
            print(f"❌ Email incorreto!")
            raise serializers.ValidationError(
                {
                    "username": "O email de confirmação deve ser o mesmo do seu email de login."
                }
            )

        # Valida a senha
        authenticated_user = authenticate(
            request=request, email=username_input, password=password
        )
        if not authenticated_user or authenticated_user.id != user.id:
            print(f"❌ Senha incorreta!")
            raise serializers.ValidationError({"password": "Senha incorreta."})

        print(f"✅ Validação completa - PASSOU!")
        return attrs

    def create(self, validated_data):
        ocorrencia = self.context["ocorrencia"]
        request = self.context["request"]
        user = request.user

        # Remove os campos de assinatura que não são do modelo
        validated_data.pop("username")
        validated_data.pop("password")

        ip_address = request.META.get("REMOTE_ADDR", "127.0.0.1")

        movimentacao = Movimentacao.objects.create(
            ocorrencia=ocorrencia,
            created_by=user,
            ip_registro=ip_address,
            visualizado_admin=False,  # NOVO: sempre começa como não visualizado
            **validated_data,
        )
        return movimentacao
