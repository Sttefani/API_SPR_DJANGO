# ocorrencias/endereco_models.py

from django.db import models
from django.conf import settings
from usuarios.models import AuditModel

# IMPORTS PARA GEOCODIFICAÇÃO
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


class TipoOcorrencia(models.TextChoices):
    """Tipo de ocorrência: Interna (laboratório) ou Externa (cena)"""
    INTERNA = 'INTERNA', 'Interna (Laboratório)'
    EXTERNA = 'EXTERNA', 'Externa (Cena de Crime)'


class ModoEntrada(models.TextChoices):
    """Como o usuário inseriu a localização"""
    ENDERECO_CONVENCIONAL = 'ENDERECO_CONVENCIONAL', 'Endereço Convencional'
    COORDENADAS_DIRETAS = 'COORDENADAS_DIRETAS', 'Coordenadas GPS Diretas'


class EnderecoOcorrencia(AuditModel):
    """
    Módulo separado para endereços de ocorrências.
    Não mexe no model Ocorrencia existente (segurança).
    """
    
    # Relação 1:1 com Ocorrência
    ocorrencia = models.OneToOneField(
        'Ocorrencia',
        on_delete=models.CASCADE,
        related_name='endereco',
        verbose_name='Ocorrência'
    )
    
    tipo = models.CharField(
        max_length=10,
        choices=TipoOcorrencia.choices,
        default=TipoOcorrencia.EXTERNA,
        verbose_name='Tipo de Ocorrência'
    )
    
    # ✅ NOVO: Modo de entrada da localização
    modo_entrada = models.CharField(
        max_length=25,
        choices=ModoEntrada.choices,
        default=ModoEntrada.ENDERECO_CONVENCIONAL,
        verbose_name='Modo de Entrada'
    )
    
    # Campos de endereço (agora opcionais)
    logradouro = models.CharField(max_length=255, blank=True, verbose_name='Logradouro')
    numero = models.CharField(max_length=20, blank=True, verbose_name='Número')
    complemento = models.CharField(max_length=100, blank=True, verbose_name='Complemento')
    bairro = models.CharField(max_length=100, blank=True, verbose_name='Bairro')
    cep = models.CharField(max_length=10, blank=True, verbose_name='CEP')
    
    # Geolocalização
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='Latitude')
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='Longitude')
    
    # ✅ NOVO: Flag para indicar origem das coordenadas
    coordenadas_manuais = models.BooleanField(
        default=False,
        verbose_name='Coordenadas Inseridas Manualmente'
    )
    
    ponto_referencia = models.CharField(max_length=255, blank=True, verbose_name='Ponto de Referência')
    
    # ==========================================
    # ✅ MÉTODO SAVE ATUALIZADO
    # ==========================================
    
    def save(self, *args, **kwargs):
        """
        ✅ NOVA LÓGICA:
        - Se modo_entrada = COORDENADAS_DIRETAS: NUNCA geocodifica
        - Se coordenadas_manuais = True: NUNCA sobrescreve
        - Só geocodifica se modo_entrada = ENDERECO_CONVENCIONAL e não tem coordenadas
        """
        
        # Se usuário escolheu coordenadas diretas, respeitar e não geocodificar
        if self.modo_entrada == ModoEntrada.COORDENADAS_DIRETAS:
            self.coordenadas_manuais = True
            super().save(*args, **kwargs)
            return
        
        # Se coordenadas foram inseridas manualmente, NUNCA sobrescrever
        if self.coordenadas_manuais:
            super().save(*args, **kwargs)
            return
        
        # Geocodificar apenas se:
        # 1. Modo endereço convencional
        # 2. Não tem coordenadas
        # 3. É externa
        # 4. Tem dados de endereço
        precisa_geocodificar = (
            self.modo_entrada == ModoEntrada.ENDERECO_CONVENCIONAL and
            (not self.latitude or not self.longitude) and
            not self.coordenadas_manuais and
            self.tipo == TipoOcorrencia.EXTERNA and
            self.logradouro and
            self.ocorrencia and
            self.ocorrencia.cidade
        )
        
        if precisa_geocodificar:
            print(f"🔍 [ID:{self.ocorrencia.id}] Tentando geocodificar: {self.logradouro}")
            try:
                self.geocodificar()
            except Exception as e:
                print(f"❌ Erro ao geocodificar: {e}")
        
        super().save(*args, **kwargs)
    
    def geocodificar(self):
        """
        ✅ MODIFICADO: Não usa mais fallback para centro da cidade
        Converte endereço em coordenadas usando Nominatim (OpenStreetMap).
        
        Returns:
            bool: True se encontrou coordenadas, False se não encontrou
        """
        try:
            geolocator = Nominatim(
                user_agent="spr_roraima_pericia_v1",
                timeout=10
            )
            
            # Montar endereço completo
            partes_endereco = []
            
            if self.logradouro:
                partes_endereco.append(self.logradouro)
            
            if self.numero:
                partes_endereco.append(str(self.numero))
            
            if self.bairro:
                partes_endereco.append(self.bairro)
            
            if self.ocorrencia and self.ocorrencia.cidade:
                partes_endereco.append(self.ocorrencia.cidade.nome)
            
            partes_endereco.extend(['Roraima', 'Brasil'])
            
            endereco_completo = ', '.join(partes_endereco)
            
            print(f"📍 Buscando: {endereco_completo}")
            
            location = geolocator.geocode(
                endereco_completo,
                exactly_one=True,
                timeout=10
            )
            
            if location:
                self.latitude = str(location.latitude)
                self.longitude = str(location.longitude)
                self.coordenadas_manuais = False  # Marcando como geocodificado automaticamente
                print(f"✅ Coordenadas encontradas: {self.latitude}, {self.longitude}")
                return True
            else:
                # ✅ REMOVIDO: Não usa mais fallback para centro da cidade
                print(f"⚠️  Endereço não encontrado. Coordenadas não serão preenchidas.")
                return False
        
        except GeocoderTimedOut:
            print(f"⏱️  Timeout ao geocodificar")
            return False
        
        except GeocoderServiceError as e:
            print(f"🌐 Erro de serviço: {e}")
            return False
        
        except Exception as e:
            print(f"❌ Erro inesperado: {e}")
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
        if self.bairro:
            partes.append(f"Bairro: {self.bairro}")
        if self.cep:
            partes.append(f"CEP: {self.cep}")
        return ", ".join(partes) if partes else "Endereço não informado"
    
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
        ordering = ['-created_at']