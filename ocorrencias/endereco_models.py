# ocorrencias/endereco_models.py

from django.db import models
from django.conf import settings
from usuarios.models import AuditModel
import logging

# IMPORTS PARA GEOCODIFICAÇÃO
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

logger = logging.getLogger(__name__)


class TipoOcorrencia(models.TextChoices):
    """Tipo de ocorrência: Interna (laboratório) ou Externa (cena)"""

    INTERNA = "INTERNA", "Interna (Laboratório)"
    EXTERNA = "EXTERNA", "Externa (Cena de Crime)"


class ModoEntrada(models.TextChoices):
    """Como o usuário inseriu a localização"""

    ENDERECO_CONVENCIONAL = "ENDERECO_CONVENCIONAL", "Endereço Convencional"
    COORDENADAS_DIRETAS = "COORDENADAS_DIRETAS", "Coordenadas GPS Diretas"


class EnderecoOcorrencia(AuditModel):
    """
    Módulo separado para endereços de ocorrências.
    Não mexe no model Ocorrencia existente (segurança).
    """

    # Relação 1:1 com Ocorrência
    ocorrencia = models.OneToOneField(
        "Ocorrencia",
        on_delete=models.CASCADE,
        related_name="endereco",
        verbose_name="Ocorrência",
    )

    tipo = models.CharField(
        max_length=10,
        choices=TipoOcorrencia.choices,
        default=TipoOcorrencia.EXTERNA,
        verbose_name="Tipo de Ocorrência",
    )

    modo_entrada = models.CharField(
        max_length=25,
        choices=ModoEntrada.choices,
        default=ModoEntrada.ENDERECO_CONVENCIONAL,
        verbose_name="Modo de Entrada",
    )

    # Campos de endereço (opcionais)
    logradouro = models.CharField(max_length=255, blank=True, verbose_name="Logradouro")
    numero = models.CharField(max_length=20, blank=True, verbose_name="Número")
    complemento = models.CharField(
        max_length=100, blank=True, verbose_name="Complemento"
    )

    # =========================================================================
    # CAMPO BAIRRO - CORREÇÃO DO ERRO DE PRODUÇÃO
    # =========================================================================

    # 1. Este campo aponta para a coluna 'bairro' que JÁ EXISTE no banco e tem texto.
    # Usamos db_column='bairro' para o Django saber que é a mesma coluna.
    bairro_legado = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_column="bairro",
        verbose_name="Bairro (Texto Original)",
        help_text="Campo antigo (texto)",
    )

    # 2. Criamos um campo NOVO para a chave estrangeira
    bairro_novo = models.ForeignKey(
        "cidades.Bairro",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="enderecos",
        verbose_name="Bairro (Selecionado)",
    )
    # =========================================================================

    cep = models.CharField(max_length=10, blank=True, verbose_name="CEP")

    # Geolocalização
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True, verbose_name="Latitude"
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True, verbose_name="Longitude"
    )

    coordenadas_manuais = models.BooleanField(
        default=False, verbose_name="Coordenadas Inseridas Manualmente"
    )

    ponto_referencia = models.CharField(
        max_length=255, blank=True, verbose_name="Ponto de Referência"
    )

    # ==========================================
    # ✅ MÉTODO SAVE OTIMIZADO - SEM GEOCODIFICAÇÃO
    # ==========================================

    def save(self, *args, **kwargs):
        """
        ✅ SEGURO: Geocodificação REMOVIDA para não travar o save()

        Para geocodificar endereços, use:
        - Management command: python manage.py geocodificar_enderecos
        - Ou chame manualmente: endereco.geocodificar_async()
        """

        # Se usuário escolheu coordenadas diretas, marca como manual
        if self.modo_entrada == ModoEntrada.COORDENADAS_DIRETAS:
            self.coordenadas_manuais = True

        # Apenas salva - SEM chamar API externa
        super().save(*args, **kwargs)

    # ==========================================
    # ✅ MÉTODO DE GEOCODIFICAÇÃO SEPARADO E SEGURO
    # ==========================================

    def geocodificar_async(self):
        """
        ✅ SEGURO: Geocodifica SEM bloquear o save()

        Este método deve ser chamado separadamente via:
        - Management command (para processar vários endereços)
        - Endpoint específico (para processar um endereço)
        - Task assíncrona (Celery, se configurado)

        Returns:
            bool: True se encontrou coordenadas, False caso contrário
        """

        # Validações
        if self.tipo != TipoOcorrencia.EXTERNA:
            logger.warning(
                f"Endereço ID {self.id} não é externo. Geocodificação ignorada."
            )
            return False

        if self.coordenadas_manuais:
            logger.warning(
                f"Endereço ID {self.id} possui coordenadas manuais. Geocodificação ignorada."
            )
            return False

        if not self.logradouro:
            logger.warning(
                f"Endereço ID {self.id} não possui logradouro. Geocodificação impossível."
            )
            return False

        try:
            geolocator = Nominatim(user_agent="spr_roraima_pericia_v1", timeout=10)

            # Montar endereço completo
            partes_endereco = []

            if self.logradouro:
                partes_endereco.append(self.logradouro)

            if self.numero:
                partes_endereco.append(str(self.numero))

            # CORREÇÃO: Usa o novo campo FK se disponível, senão o legado (texto)
            if self.bairro_novo:
                partes_endereco.append(self.bairro_novo.nome)
            elif self.bairro_legado:
                partes_endereco.append(self.bairro_legado)

            if self.ocorrencia and self.ocorrencia.cidade:
                partes_endereco.append(self.ocorrencia.cidade.nome)

            partes_endereco.extend(["Roraima", "Brasil"])

            endereco_completo = ", ".join(partes_endereco)

            logger.info(f"📍 Geocodificando ID {self.id}: {endereco_completo}")

            location = geolocator.geocode(
                endereco_completo, exactly_one=True, timeout=10
            )

            if location:
                self.latitude = str(location.latitude)
                self.longitude = str(location.longitude)
                self.coordenadas_manuais = False
                self.save(
                    update_fields=[
                        "latitude",
                        "longitude",
                        "coordenadas_manuais",
                        "updated_at",
                    ]
                )
                logger.info(
                    f"✅ Coordenadas salvas para ID {self.id}: {self.latitude}, {self.longitude}"
                )
                return True
            else:
                logger.warning(
                    f"⚠️ Endereço não encontrado para ID {self.id}: {endereco_completo}"
                )
                return False

        except GeocoderTimedOut:
            logger.error(f"⏱️ Timeout ao geocodificar ID {self.id}")
            return False

        except GeocoderServiceError as e:
            logger.error(f"🌐 Erro de serviço ao geocodificar ID {self.id}: {e}")
            return False

        except Exception as e:
            logger.error(f"❌ Erro inesperado ao geocodificar ID {self.id}: {e}")
            return False

    # ==========================================
    # PROPERTIES E MÉTODOS ORIGINAIS
    # ==========================================

    @property
    def endereco_completo(self):
        """Retorna endereço formatado"""
        partes = []
        if self.logradouro:
            partes.append(self.logradouro)
        if self.numero:
            partes.append(f"nº {self.numero}")
        if self.complemento:
            partes.append(self.complemento)

        # CORREÇÃO: Usa o novo campo FK se disponível, senão o legado
        if self.bairro_novo:
            partes.append(f"Bairro: {self.bairro_novo.nome}")
        elif self.bairro_legado:
            partes.append(f"Bairro: {self.bairro_legado}")

        if self.cep:
            partes.append(f"CEP: {self.cep}")
        return ", ".join(partes) if partes else "Endereço não informado"

    @property
    def nome_bairro(self):
        """Retorna o nome do bairro (novo ou legado)"""
        if self.bairro_novo:
            return self.bairro_novo.nome
        return self.bairro_legado or ""

    @property
    def tem_coordenadas(self):
        return self.latitude is not None and self.longitude is not None

    def __str__(self):
        if self.tipo == TipoOcorrencia.INTERNA:
            return f"Endereço (Interna) - {self.ocorrencia.numero_ocorrencia}"
        return f"Endereço (Externa) - {self.endereco_completo[:50]}"

    class Meta:
        verbose_name = "Endereço de Ocorrência"
        verbose_name_plural = "Endereços de Ocorrências"
        ordering = ["-created_at"]
