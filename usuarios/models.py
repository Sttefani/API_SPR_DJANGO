# usuarios/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

# --- Gerenciador para Soft Delete ---
# Este gerenciador garante que, por padrão, as buscas com .objects não retornem
# os objetos que foram "deletados suavemente".
class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)

# --- Modelo Base de Auditoria e Soft Delete ---
# Este é o modelo que todos os outros herdarão.
# Ele já implementa a auditoria e o soft delete que você pediu.
class AuditModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    created_by = models.ForeignKey('usuarios.User', related_name='%(class)s_created_by', on_delete=models.SET_NULL, null=True, blank=True)
    updated_by = models.ForeignKey('usuarios.User', related_name='%(class)s_updated_by', on_delete=models.SET_NULL, null=True, blank=True)
    deleted_by = models.ForeignKey('usuarios.User', related_name='%(class)s_deleted_by', on_delete=models.SET_NULL, null=True, blank=True)

    # Gerenciadores
    objects = SoftDeleteManager()  # Apenas objetos não deletados
    all_objects = models.Manager() # Todos os objetos, incluindo os deletados

    class Meta:
        abstract = True # Garante que este modelo não crie uma tabela no banco, servindo apenas para herança.

    def soft_delete(self, user):
        from django.utils import timezone
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save()


    def restore(self):
        self.deleted_at = None
        self.deleted_by = None
        self.save()


# --- Gerenciador de Usuário Personalizado ---
# Precisamos customizar o gerenciador para que o Django saiba como criar
# usuários e superusuários com o nosso modelo personalizado.
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('O Email é um campo obrigatório')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('status', 'ATIVO') # SuperAdmin já começa ativo
        extra_fields.setdefault('perfil', 'SUPER_ADMIN') # E com o perfil correto

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


# --- Nosso Modelo de Usuário Personalizado ---
# Ele herda do AbstractUser do Django (para ter todos os campos de autenticação)
# e do nosso AuditModel (para ter a auditoria e o soft delete).
class User(AbstractUser, AuditModel):
    # Enumerações para os campos de escolha (choices)
    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        ATIVO = 'ATIVO', 'Ativo'
        INATIVO = 'INATIVO', 'Inativo'

    class Perfil(models.TextChoices):
        PERITO = 'PERITO', 'Perito'
        ADMINISTRATIVO = 'ADMINISTRATIVO', 'Administrativo'
        OPERACIONAL = 'OPERACIONAL', 'Operacional'
        SUPER_ADMIN = 'SUPER_ADMIN', 'Super Admin'

    # Remove o campo 'username' padrão, pois usaremos o email
    username = None

    # Campos personalizados
    email = models.EmailField('endereço de email', unique=True)
    nome_completo = models.CharField(max_length=255)
    data_nascimento = models.DateField(null=True, blank=True)
    cpf = models.CharField(max_length=14, unique=True) # Pode formatar para 111.222.333-44
    telefone_celular = models.CharField(max_length=15, unique=True, blank=True, null=True)

    # Campos de controle do sistema
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    perfil = models.CharField(max_length=15, choices=Perfil.choices, blank=True, null=True)
    # CAMPO ADICIONADO PARA A FUNCIONALIDADE DE RESET DE SENHA
    deve_alterar_senha = models.BooleanField(default=False)

    # Campo de relação (atrelamento) com os Serviços Periciais
    servicos_periciais = models.ManyToManyField(
        'servicos_periciais.ServicoPericial',
        blank=True,
        related_name='usuarios',
        verbose_name='Serviços Periciais'
    )

    # Configuração para login
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nome_completo', 'cpf']

    # Sobrescreve o is_active padrão do Django para usar o nosso campo 'status'
    @property
    def is_active(self):
        return self.status == self.Status.ATIVO

    @is_active.setter
    def is_active(self, value):
        self.status = self.Status.ATIVO if value else self.Status.INATIVO


    objects = UserManager() # Vincula nosso gerenciador personalizado

    def __str__(self):
        return self.nome_completo