# ocorrencias/endereco_models.py

from django.db import models
from django.conf import settings
from usuarios.models import AuditModel

# ✅ IMPORTS PARA GEOCODIFICAÇÃO
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError


class TipoOcorrencia(models.TextChoices):
    """Tipo de ocorrência: Interna (laboratório) ou Externa (cena)"""
    INTERNA = 'INTERNA', 'Interna (Laboratório)'
    EXTERNA = 'EXTERNA', 'Externa (Cena de Crime)'


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
    
    # Campos de endereço
    logradouro = models.CharField(max_length=255, blank=True, verbose_name='Logradouro')
    numero = models.CharField(max_length=20, blank=True, verbose_name='Número')
    complemento = models.CharField(max_length=100, blank=True, verbose_name='Complemento')
    bairro = models.CharField(max_length=100, blank=True, verbose_name='Bairro')
    cep = models.CharField(max_length=10, blank=True, verbose_name='CEP')
    
    # Geolocalização (para BI futuro)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='Latitude')
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name='Longitude')
    
    ponto_referencia = models.CharField(max_length=255, blank=True, verbose_name='Ponto de Referência')
    
    # ==========================================
    # ✅ MÉTODOS DE GEOCODIFICAÇÃO
    # ==========================================
    
    def save(self, *args, **kwargs):
        """
        Sobrescreve o save para geocodificar automaticamente.
        SEGURO: Só tenta geocodificar se necessário.
        """
        # Verificar se precisa geocodificar
        precisa_geocodificar = (
            (not self.latitude or not self.longitude) and  # Não tem coordenadas
            self.tipo == TipoOcorrencia.EXTERNA and  # É externa
            self.logradouro and  # Tem logradouro
            self.ocorrencia and  # Tem ocorrência vinculada
            self.ocorrencia.cidade  # Tem cidade
        )
        
        if precisa_geocodificar:
            print(f"🔍 [ID:{self.ocorrencia.id}] Tentando geocodificar: {self.logradouro}")
            try:
                self.geocodificar()
            except Exception as e:
                print(f"❌ Erro ao geocodificar (não vai impedir o salvamento): {e}")
        
        # SEMPRE salva, mesmo se geocodificação falhar
        super().save(*args, **kwargs)
    
    def geocodificar(self):
        """
        Converte endereço em coordenadas usando Nominatim (OpenStreetMap).
        GRATUITO e SEM API KEY.
        
        Returns:
            bool: True se encontrou coordenadas, False se não encontrou
        """
        try:
            # Criar geolocalizador com timeout
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
            
            # Adicionar cidade da ocorrência
            if self.ocorrencia and self.ocorrencia.cidade:
                partes_endereco.append(self.ocorrencia.cidade.nome)
            
            # Adicionar estado e país para melhor precisão
            partes_endereco.extend(['Roraima', 'Brasil'])
            
            endereco_completo = ', '.join(partes_endereco)
            
            print(f"📍 Buscando: {endereco_completo}")
            
            # Buscar coordenadas no OpenStreetMap
            location = geolocator.geocode(
                endereco_completo,
                exactly_one=True,
                timeout=10
            )
            
            if location:
                # Encontrou! Salvar coordenadas
                self.latitude = str(location.latitude)
                self.longitude = str(location.longitude)
                print(f"✅ Coordenadas encontradas: {self.latitude}, {self.longitude}")
                return True
            
            else:
                print(f"⚠️  Endereço específico não encontrado no OpenStreetMap")
                
                # FALLBACK: Tentar busca mais genérica (só cidade)
                if self.ocorrencia and self.ocorrencia.cidade:
                    print(f"🔄 Tentando busca genérica: {self.ocorrencia.cidade.nome}, Roraima")
                    
                    location = geolocator.geocode(
                        f"{self.ocorrencia.cidade.nome}, Roraima, Brasil",
                        exactly_one=True,
                        timeout=10
                    )
                    
                    if location:
                        # Usar coordenadas da cidade como fallback
                        self.latitude = str(location.latitude)
                        self.longitude = str(location.longitude)
                        print(f"✅ Coordenadas genéricas (cidade) encontradas: {self.latitude}, {self.longitude}")
                        return True
                
                print(f"❌ Nenhuma coordenada encontrada")
                return False
        
        except GeocoderTimedOut:
            print(f"⏱️  Timeout ao geocodificar (servidor demorou muito)")
            return False
        
        except GeocoderServiceError as e:
            print(f"🌐 Erro de serviço ao geocodificar: {e}")
            return False
        
        except Exception as e:
            print(f"❌ Erro inesperado ao geocodificar: {e}")
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