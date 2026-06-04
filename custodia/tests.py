# custodia/tests.py
"""
Testes automatizados do módulo Custódia de Vestígios.

Fluxo principal testado:
  Criação → Movimentação → Aceite → Finalização com assinatura digital

Restrições de perfil:
  EXTERNO        → não pode criar movimentação, não pode finalizar
  CUSTODIANTE    → pode aceitar e finalizar, não pode criar vestígio
  PERITO         → pode criar, movimentar; não pode finalizar
  ADMINISTRATIVO → pode tudo exceto deletar (só SUPER_ADMIN deleta)
  SUPER_ADMIN    → poder total, único que pode DELETE
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from usuarios.models import User
from unidades_demandantes.models import UnidadeDemandante
from servicos_periciais.models import ServicoPericial
from .models import Vestigio, VestigioMovimentacao


# ---------------------------------------------------------------------------
# Helpers de criação
# ---------------------------------------------------------------------------

def _criar_unidade(sigla='DPC', nome='Delegacia de Polícia Civil'):
    return UnidadeDemandante.objects.create(sigla=sigla, nome=nome)


def _criar_servico(sigla='SETEC', nome='Seção Técnica'):
    return ServicoPericial.objects.create(sigla=sigla, nome=nome)


_cpf_counter = 0

def _criar_usuario(email, senha='Teste@1234', perfil=User.Perfil.PERITO, unidade=None):
    global _cpf_counter
    _cpf_counter += 1
    # CPF fictício único por usuário de teste (sem validação de dígito)
    cpf = f'{_cpf_counter:011d}'
    u = User.objects.create_user(
        email=email,
        password=senha,
        nome_completo=f'Usuário {perfil}',
        cpf=cpf,
        perfil=perfil,
    )
    if unidade:
        u.unidade_demandante = unidade
        u.save()
    return u


def _criar_vestigio(unidade, servico, criado_por, lacre='LAC-001'):
    return Vestigio.objects.create(
        lacre=lacre,
        unidade_demandante=unidade,
        servico_pericial=servico,
        created_by=criado_por,
    )


# ---------------------------------------------------------------------------
# Base comum para todos os testes
# ---------------------------------------------------------------------------

class CustodiaBaseTest(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.unidade = _criar_unidade()
        self.servico = _criar_servico()

        # Usuários com perfis distintos
        self.perito       = _criar_usuario('perito@test.com',       perfil=User.Perfil.PERITO,          unidade=self.unidade)
        self.operacional  = _criar_usuario('oper@test.com',          perfil=User.Perfil.OPERACIONAL,     unidade=self.unidade)
        self.admin        = _criar_usuario('admin@test.com',         perfil=User.Perfil.ADMINISTRATIVO)
        self.custodiante  = _criar_usuario('cust@test.com',          perfil=User.Perfil.CUSTODIANTE)
        self.externo      = _criar_usuario('ext@test.com',           perfil=User.Perfil.EXTERNO,         unidade=self.unidade)
        self.super_admin  = _criar_usuario('super@test.com',         perfil=User.Perfil.SUPER_ADMIN)
        self.super_admin.is_superuser = True
        self.super_admin.save()

        self.senha_padrao = 'Teste@1234'

    def autenticar(self, usuario):
        self.client.force_authenticate(user=usuario)

    def _criar_vestigio_via_api(self, usuario=None, lacre='LAC-001'):
        self.autenticar(usuario or self.perito)
        return self.client.post('/api/custodia/vestigios/', {
            'lacre':                lacre,
            'unidade_demandante_id': self.unidade.pk,
            'servico_pericial_id':   self.servico.pk,
        })

    def _criar_movimentacao_via_api(self, vestigio_id, usuario=None):
        self.autenticar(usuario or self.perito)
        return self.client.post('/api/custodia/movimentacoes/', {
            'vestigio_id':           vestigio_id,
            'unidade_demandante_id': self.unidade.pk,
            'servico_pericial_id':   self.servico.pk,
            'descricao':             'Transferência de teste',
        })

    def _aceitar_movimentacao(self, mov_id, usuario=None):
        self.autenticar(usuario or self.custodiante)
        return self.client.post(f'/api/custodia/movimentacoes/{mov_id}/aceitar/')

    def _finalizar_vestigio(self, vestigio_id, usuario=None, motivo='Motivo de finalização para teste.'):
        u = usuario or self.custodiante
        self.autenticar(u)
        return self.client.post(f'/api/custodia/vestigios/{vestigio_id}/finalizar/', {
            'saiu_da_custodia':  False,
            'motivo_finalizacao': motivo,
            'assinatura_email':   u.email,
            'assinatura_senha':   self.senha_padrao,
        })


# ---------------------------------------------------------------------------
# 1. Criação de vestígio
# ---------------------------------------------------------------------------

class VestgioCriacaoTest(CustodiaBaseTest):

    def test_perito_cria_vestigio(self):
        r = self._criar_vestigio_via_api()
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'INICIAL')
        self.assertEqual(r.data['lacre'], 'LAC-001')

    def test_operacional_cria_vestigio(self):
        r = self._criar_vestigio_via_api(self.operacional)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_externo_nao_pode_criar_vestigio(self):
        r = self._criar_vestigio_via_api(self.externo)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_custodiante_nao_pode_criar_vestigio(self):
        r = self._criar_vestigio_via_api(self.custodiante)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicata_mesmo_lacre_ocorrencia_ano_servico(self):
        """Dois vestígios com mesmo lacre+ocorrência+ano+serviço devem ser bloqueados."""
        dados = {
            'lacre':                'DUP-001',
            'ocorrencia':           '1234/2026',
            'ano_ocorrencia':       2026,
            'unidade_demandante_id': self.unidade.pk,
            'servico_pericial_id':   self.servico.pk,
        }
        self.autenticar(self.perito)
        r1 = self.client.post('/api/custodia/vestigios/', dados)
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        r2 = self.client.post('/api/custodia/vestigios/', dados)
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sem_lacre_mesmo_servico_nao_bloqueia(self):
        """Vestígios sem lacre não disparam validação de duplicata."""
        dados = {
            'unidade_demandante_id': self.unidade.pk,
            'servico_pericial_id':   self.servico.pk,
        }
        self.autenticar(self.perito)
        r1 = self.client.post('/api/custodia/vestigios/', dados)
        r2 = self.client.post('/api/custodia/vestigios/', dados)
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# 2. Movimentação
# ---------------------------------------------------------------------------

class MovimentacaoTest(CustodiaBaseTest):

    def setUp(self):
        super().setUp()
        self.autenticar(self.perito)
        r = self._criar_vestigio_via_api()
        self.vestigio_id = r.data['id']

    def test_movimentacao_muda_status_para_andamento(self):
        r = self._criar_movimentacao_via_api(self.vestigio_id)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

        self.autenticar(self.perito)
        v = self.client.get(f'/api/custodia/vestigios/{self.vestigio_id}/')
        self.assertEqual(v.data['status'], 'ANDAMENTO')

    def test_externo_nao_pode_criar_movimentacao(self):
        r = self._criar_movimentacao_via_api(self.vestigio_id, self.externo)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_nova_movimentacao_sem_aceitar_anterior_bloqueada(self):
        """Não pode haver nova movimentação enquanto a anterior não foi aceita."""
        self._criar_movimentacao_via_api(self.vestigio_id)
        r2 = self._criar_movimentacao_via_api(self.vestigio_id)
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_vestigio_finalizado_nao_aceita_movimentacao(self):
        """Vestígio FINALIZADO não pode ter novas movimentações."""
        r_mov = self._criar_movimentacao_via_api(self.vestigio_id)
        self._aceitar_movimentacao(r_mov.data['id'])
        self._finalizar_vestigio(self.vestigio_id)

        r3 = self._criar_movimentacao_via_api(self.vestigio_id)
        self.assertEqual(r3.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# 3. Aceite de movimentação
# ---------------------------------------------------------------------------

class AceiteMovimentacaoTest(CustodiaBaseTest):

    def setUp(self):
        super().setUp()
        r_vest = self._criar_vestigio_via_api()
        self.vestigio_id = r_vest.data['id']
        r_mov = self._criar_movimentacao_via_api(self.vestigio_id)
        self.mov_id = r_mov.data['id']

    def test_custodiante_aceita_movimentacao(self):
        r = self._aceitar_movimentacao(self.mov_id)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['aceito'])

    def test_admin_aceita_movimentacao(self):
        r = self._aceitar_movimentacao(self.mov_id, self.admin)
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_perito_mesmo_servico_aceita(self):
        """Perito do mesmo serviço pode aceitar."""
        self.perito.servicos_periciais.add(self.servico)
        r = self._aceitar_movimentacao(self.mov_id, self.perito)
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_aceite_duplo_bloqueado(self):
        self._aceitar_movimentacao(self.mov_id)
        r2 = self._aceitar_movimentacao(self.mov_id)
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_destino_atualizado_apos_aceite(self):
        """Após aceitar, user_destino do vestígio deve ser quem aceitou."""
        self._aceitar_movimentacao(self.mov_id, self.custodiante)
        self.autenticar(self.perito)
        v = self.client.get(f'/api/custodia/vestigios/{self.vestigio_id}/')
        self.assertEqual(v.data['user_destino']['id'], self.custodiante.pk)


# ---------------------------------------------------------------------------
# 4. Finalização com assinatura digital
# ---------------------------------------------------------------------------

class FinalizacaoTest(CustodiaBaseTest):

    def setUp(self):
        super().setUp()
        r_vest = self._criar_vestigio_via_api()
        self.vestigio_id = r_vest.data['id']
        r_mov  = self._criar_movimentacao_via_api(self.vestigio_id)
        self._aceitar_movimentacao(r_mov.data['id'])

    def test_custodiante_finaliza_com_assinatura(self):
        r = self._finalizar_vestigio(self.vestigio_id)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'FINALIZADO')
        self.assertIsNotNone(r.data['motivo_finalizacao'])

    def test_perito_nao_pode_finalizar(self):
        r = self._finalizar_vestigio(self.vestigio_id, self.perito)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_externo_nao_pode_finalizar(self):
        r = self._finalizar_vestigio(self.vestigio_id, self.externo)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_assinatura_email_errado_rejeitado(self):
        """Email de assinatura diferente do usuário autenticado deve ser rejeitado."""
        self.autenticar(self.custodiante)
        r = self.client.post(f'/api/custodia/vestigios/{self.vestigio_id}/finalizar/', {
            'saiu_da_custodia':  False,
            'motivo_finalizacao': 'Teste',
            'assinatura_email':   'errado@test.com',
            'assinatura_senha':   self.senha_padrao,
        })
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assinatura_senha_errada_rejeitada(self):
        self.autenticar(self.custodiante)
        r = self.client.post(f'/api/custodia/vestigios/{self.vestigio_id}/finalizar/', {
            'saiu_da_custodia':  False,
            'motivo_finalizacao': 'Teste',
            'assinatura_email':   self.custodiante.email,
            'assinatura_senha':   'SenhaErrada!',
        })
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_finalizar_sem_movimentacao_bloqueado(self):
        """Não pode finalizar vestígio sem nenhuma movimentação aceita."""
        r_vest = self._criar_vestigio_via_api(lacre='SEM-MOV')
        r = self._finalizar_vestigio(r_vest.data['id'])
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_motivo_finalizacao_salvo(self):
        """motivo_finalizacao é gravado para não-repúdio."""
        motivo = 'Laudo entregue ao delegado responsável pelo caso.'
        r = self._finalizar_vestigio(self.vestigio_id, motivo=motivo)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['motivo_finalizacao'], motivo)

    def test_vestigio_finalizado_nao_pode_ser_editado(self):
        """Vestígio FINALIZADO deve ser imutável via PATCH."""
        self._finalizar_vestigio(self.vestigio_id)
        self.autenticar(self.admin)
        r = self.client.patch(f'/api/custodia/vestigios/{self.vestigio_id}/', {'descricao': 'Alteração indevida'})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# 5. Reabertura
# ---------------------------------------------------------------------------

class ReaberturaTest(CustodiaBaseTest):

    def setUp(self):
        super().setUp()
        r_vest = self._criar_vestigio_via_api()
        self.vestigio_id = r_vest.data['id']
        r_mov  = self._criar_movimentacao_via_api(self.vestigio_id)
        self._aceitar_movimentacao(r_mov.data['id'])
        self._finalizar_vestigio(self.vestigio_id)

    def test_reabrir_volta_para_andamento(self):
        self.autenticar(self.admin)
        r = self.client.post(f'/api/custodia/vestigios/{self.vestigio_id}/reabrir/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'ANDAMENTO')


# ---------------------------------------------------------------------------
# 6. salvarOcorrência imutável
# ---------------------------------------------------------------------------

class SalvarOcorrenciaTest(CustodiaBaseTest):

    def test_salvar_ocorrencia_uma_vez(self):
        r = self._criar_vestigio_via_api()
        vid = r.data['id']
        self.autenticar(self.perito)
        r2 = self.client.patch(f'/api/custodia/vestigios/{vid}/salvar-ocorrencia/', {'ocorrencia': '1234/TEST'})
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data['ocorrencia'], '1234/TEST')

    def test_alterar_ocorrencia_ja_preenchida_bloqueado(self):
        r = self._criar_vestigio_via_api()
        vid = r.data['id']
        self.autenticar(self.perito)
        self.client.patch(f'/api/custodia/vestigios/{vid}/salvar-ocorrencia/', {'ocorrencia': 'PRIMEIRA'})
        r3 = self.client.patch(f'/api/custodia/vestigios/{vid}/salvar-ocorrencia/', {'ocorrencia': 'ALTERADA'})
        self.assertEqual(r3.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# 7. Deleção — somente SUPER_ADMIN
# ---------------------------------------------------------------------------

class DeletePermissaoTest(CustodiaBaseTest):

    def test_perito_nao_pode_deletar(self):
        r_vest = self._criar_vestigio_via_api()
        self.autenticar(self.perito)
        r = self.client.delete(f'/api/custodia/vestigios/{r_vest.data["id"]}/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_nao_pode_deletar(self):
        r_vest = self._criar_vestigio_via_api()
        self.autenticar(self.admin)
        r = self.client.delete(f'/api/custodia/vestigios/{r_vest.data["id"]}/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_super_admin_pode_deletar(self):
        r_vest = self._criar_vestigio_via_api()
        self.autenticar(self.super_admin)
        r = self.client.delete(f'/api/custodia/vestigios/{r_vest.data["id"]}/')
        self.assertIn(r.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])


# ---------------------------------------------------------------------------
# 8. Visibilidade por perfil (filtro de queryset)
# ---------------------------------------------------------------------------

class VisibilidadePerfilTest(CustodiaBaseTest):

    def setUp(self):
        super().setUp()
        # Vestígio da unidade do perito
        self.vest_propia = _criar_vestigio(self.unidade, self.servico, self.perito, lacre='PROPRIA')

        # Vestígio de outra unidade (não deve aparecer para EXTERNO)
        outra = _criar_unidade('OUTRA', 'Outra Unidade')
        outro_perito = _criar_usuario('outro@test.com', perfil=User.Perfil.PERITO, unidade=outra)
        self.vest_alheia = _criar_vestigio(outra, self.servico, outro_perito, lacre='ALHEIA')

    def test_perito_ve_vestigio_da_propria_unidade(self):
        self.autenticar(self.perito)
        r = self.client.get('/api/custodia/vestigios/')
        ids = [v['id'] for v in r.data.get('results', r.data)]
        self.assertIn(self.vest_propia.pk, ids)

    def test_perito_nao_ve_vestigio_de_outra_unidade(self):
        self.autenticar(self.perito)
        r = self.client.get('/api/custodia/vestigios/')
        ids = [v['id'] for v in r.data.get('results', r.data)]
        self.assertNotIn(self.vest_alheia.pk, ids)

    def test_admin_ve_todos_os_vestigios(self):
        self.autenticar(self.admin)
        r = self.client.get('/api/custodia/vestigios/')
        ids = [v['id'] for v in r.data.get('results', r.data)]
        self.assertIn(self.vest_propia.pk, ids)
        self.assertIn(self.vest_alheia.pk, ids)

    def test_externo_ve_apenas_unidade_propria(self):
        self.autenticar(self.externo)
        r = self.client.get('/api/custodia/vestigios/')
        ids = [v['id'] for v in r.data.get('results', r.data)]
        self.assertIn(self.vest_propia.pk, ids)
        self.assertNotIn(self.vest_alheia.pk, ids)
