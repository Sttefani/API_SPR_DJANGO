"""
settings_test.py — Configurações exclusivas para testes automatizados.

Usa SQLite em memória para dispensar Docker/PostgreSQL durante os testes.

Uso:
    python manage.py test custodia --settings=spr.settings_test
    python manage.py test custodia --settings=spr.settings_test --verbosity=2
"""

from .settings import *  # herda toda a configuração de produção

# Banco de dados em memória — rápido, sem dependência de Docker
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Desabilita verificação de senha para agilizar criação de usuários nos testes
AUTH_PASSWORD_VALIDATORS = []

# Desabilita logs desnecessários durante testes
LOGGING = {}

# Senha padrão dos usuários de teste (igual ao usado nos tests.py)
TEST_DEFAULT_PASSWORD = 'Teste@1234'
