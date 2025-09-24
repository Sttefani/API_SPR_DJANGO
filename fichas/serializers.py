# fichas/serializers.py

from rest_framework import serializers
from .models import (
    FichaLocalCrime, Vitima, Vestigio, Lacre,
    FichaAcidenteTransito, Veiculo,
    FichaConstatacaoSubstancia, ItemSubstancia,
    FichaDocumentoscopia, ItemDocumentoscopia,
    FichaMaterialDiverso, ItemMaterial
)
from usuarios.models import User
from usuarios.serializers import UserNestedSerializer

# =============================================================================
# SERIALIZERS PARA SUB-ITENS (COMPONENTES)
# =============================================================================
class LacreSerializer(serializers.ModelSerializer):
    aplicado_por = UserNestedSerializer(read_only=True)
    class Meta:
        model = Lacre
        fields = ['id', 'numero', 'tipo', 'status', 'aplicado_por', 'data_aplicacao', 'data_rompimento', 'motivo_rompimento', 'observacoes']

class VestigioSerializer(serializers.ModelSerializer):
    lacres = LacreSerializer(many=True, read_only=True)
    coletado_por = UserNestedSerializer(read_only=True)
    class Meta:
        model = Vestigio
        fields = ['id', 'item_numero', 'descricao', 'local_coleta', 'estado_conservacao', 'coletado_por', 'fotografado', 'destino', 'observacoes', 'lacres']

class VitimaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vitima
        fields = ['id', 'nome', 'idade_aparente', 'sexo', 'posicao_encontrada', 'observacoes']

class VeiculoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Veiculo
        fields = ['id', 'placa', 'tipo_veiculo', 'marca', 'modelo', 'cor', 'ano_modelo', 'chassi', 'renavam']

class ItemSubstanciaSerializer(serializers.ModelSerializer):
    lacres = LacreSerializer(many=True, read_only=True)
    class Meta:
        model = ItemSubstancia
        fields = ['id', 'substancia', 'quantidade', 'massa_bruta', 'massa_retirada_exame', 'massa_retirada_contraprova', 'massa_liquida_devolvida', 'lacres']

class ItemDocumentoscopiaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemDocumentoscopia
        fields = ['id', 'descricao_material']

class ItemMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemMaterial
        fields = ['id', 'material', 'descricao', 'quantidade']


# =============================================================================
# SERIALIZERS PARA AS FICHAS PRINCIPAIS (FORMULÁRIOS)
# =============================================================================
class FichaLocalCrimeSerializer(serializers.ModelSerializer):
    vitimas = VitimaSerializer(many=True, read_only=True)
    vestigios = VestigioSerializer(many=True, read_only=True)
    
    # --- CORREÇÃO DE NOME AQUI ---
    auxiliar = UserNestedSerializer(read_only=True)
    auxiliar_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(perfil='OPERACIONAL'),
        source='auxiliar',
        write_only=True,
        required=False,
        allow_null=True,
        label="Auxiliar Operacional"
    )
    class Meta:
        model = FichaLocalCrime
        # Usa exclude para ser mais seguro
        exclude = ['created_at', 'updated_at', 'deleted_at', 'created_by', 'updated_by', 'deleted_by']
        read_only_fields = ['ocorrencia']


class FichaAcidenteTransitoSerializer(serializers.ModelSerializer):
    vitimas = VitimaSerializer(many=True, read_only=True)
    vestigios = VestigioSerializer(many=True, read_only=True)
    veiculos = VeiculoSerializer(many=True, read_only=True)
    
    # --- CORREÇÃO DE NOME AQUI ---
    auxiliar = UserNestedSerializer(read_only=True)
    auxiliar_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(perfil='OPERACIONAL'),
        source='auxiliar',
        write_only=True,
        required=False,
        allow_null=True,
        label="Auxiliar Operacional"
    )
    class Meta:
        model = FichaAcidenteTransito
        exclude = ['created_at', 'updated_at', 'deleted_at', 'created_by', 'updated_by', 'deleted_by']
        read_only_fields = ['ocorrencia']


class FichaConstatacaoSubstanciaSerializer(serializers.ModelSerializer):
    itens_substancia = ItemSubstanciaSerializer(many=True, read_only=True)
    lacres = LacreSerializer(many=True, read_only=True)
    class Meta:
        model = FichaConstatacaoSubstancia
        exclude = ['created_at', 'updated_at', 'deleted_at', 'created_by', 'updated_by', 'deleted_by']
        read_only_fields = ['ocorrencia']


class FichaDocumentoscopiaSerializer(serializers.ModelSerializer):
    itens_documentoscopia = ItemDocumentoscopiaSerializer(many=True, read_only=True)
    class Meta:
        model = FichaDocumentoscopia
        exclude = ['created_at', 'updated_at', 'deleted_at', 'created_by', 'updated_by', 'deleted_by']
        read_only_fields = ['ocorrencia']


class FichaMaterialDiversoSerializer(serializers.ModelSerializer):
    itens_material = ItemMaterialSerializer(many=True, read_only=True)
    class Meta:
        model = FichaMaterialDiverso
        exclude = ['created_at', 'updated_at', 'deleted_at', 'created_by', 'updated_by', 'deleted_by']
        read_only_fields = ['ocorrencia']