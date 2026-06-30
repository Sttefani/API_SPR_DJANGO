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

import datetime
import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from usuarios.models import User
from unidades_demandantes.models import UnidadeDemandante
from servicos_periciais.models import ServicoPericial
from .models import Vestigio, VestigioMovimentacao, DNA, FichaVestigioRegistro


# ---------------------------------------------------------------------------
# Helpers de criação
# ---------------------------------------------------------------------------

def _criar_unidade(sigla='DPC', nome='Delegacia de Polícia Civil'):
    return UnidadeDemandante.objects.create(sigla=sigla, nome=nome)


def _criar_servico(sigla='SETEC', nome='Seção Técnica'):
    return ServicoPericial.objects.create(sigla=sigla, nome=nome)


def _criar_usuario(email, senha='Teste@1234', perfil=User.Perfil.PERITO, unidade=None):
    # CPF fictício único por chamada (sem validação de dígito verificador)
    cpf = str(uuid.uuid4().int)[:11]
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


def _criar_dna(perito, situacao=DNA.Situacao.APENADO, nome='FULANO DE TAL'):
    """Cria um DNA diretamente via ORM (banco nacional de perfis genéticos)."""
    agora = timezone.now()
    return DNA.objects.create(
        nome=nome, nascimento=agora, naturalidade='MANAUS',
        mae='MARIA DE TAL', cpf='11122233344', rg='1234567',
        gemeo=DNA.SimNao.NAO, transfusao=DNA.SimNao.NAO, transplante=DNA.SimNao.NAO,
        processado_banco_perfis_genetico=DNA.SimNao.NAO,
        data_da_coleta=agora, finalidade_coleta=DNA.FinalidadeColeta.LEI,
        situacao=situacao, perito=perito, created_by=perito,
    )


# ---------------------------------------------------------------------------
# Base comum para todos os testes
# ---------------------------------------------------------------------------

class CustodiaBaseTest(APITestCase):

    def setUp(self):
        self.client = APIClient()
        self.unidade = _criar_unidade()
        self.servico = _criar_servico()
        # Custódia central do IC — destino fixo dos vestígios de usuário EXTERNO
        self.custodia_ic = _criar_servico('CUST', 'CUSTÓDIA ICPDA')

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
            'descricao':             'Material de teste',
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

    def test_externo_pode_criar_vestigio(self):
        """
        EXTERNO pode cadastrar vestígios da própria unidade (sessão 16).
        O backend força unidade_demandante = unidade do usuário externo.
        """
        r = self._criar_vestigio_via_api(self.externo)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['status'], 'INICIAL')

    def test_custodiante_pode_criar_vestigio(self):
        r = self._criar_vestigio_via_api(self.custodiante)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_duplicata_lacre_mesmo_servico(self):
        """Dois vestígios com o mesmo lacre no mesmo serviço pericial são bloqueados."""
        dados = {
            'lacre':                 'DUP-001',
            'descricao':             'Material X',
            'unidade_demandante_id': self.unidade.pk,
            'servico_pericial_id':   self.servico.pk,
        }
        self.autenticar(self.perito)
        r1 = self.client.post('/api/custodia/vestigios/', dados)
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        r2 = self.client.post('/api/custodia/vestigios/', dados)
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mesmo_lacre_servicos_diferentes_ok(self):
        """Mesmo lacre em serviços diferentes é permitido (unicidade é por serviço)."""
        outro_servico = _criar_servico('BIO', 'Biologia')
        base = {
            'lacre':                 'DUP-002',
            'descricao':             'Material Y',
            'unidade_demandante_id': self.unidade.pk,
        }
        self.autenticar(self.perito)
        r1 = self.client.post('/api/custodia/vestigios/', {**base, 'servico_pericial_id': self.servico.pk})
        r2 = self.client.post('/api/custodia/vestigios/', {**base, 'servico_pericial_id': outro_servico.pk})
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)

    def test_lacre_obrigatorio(self):
        """Lacre é obrigatório no cadastro (regra do administrador)."""
        self.autenticar(self.perito)
        r = self.client.post('/api/custodia/vestigios/', {
            'descricao':             'Sem lacre',
            'unidade_demandante_id': self.unidade.pk,
            'servico_pericial_id':   self.servico.pk,
        })
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_descricao_obrigatoria(self):
        """Descrição é obrigatória no cadastro (regra do administrador)."""
        self.autenticar(self.perito)
        r = self.client.post('/api/custodia/vestigios/', {
            'lacre':                 'LAC-DESC',
            'unidade_demandante_id': self.unidade.pk,
            'servico_pericial_id':   self.servico.pk,
        })
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unidade_obrigatoria(self):
        """Unidade demandante é obrigatória no cadastro."""
        self.autenticar(self.perito)
        r = self.client.post('/api/custodia/vestigios/', {
            'lacre':               'LAC-UNI',
            'descricao':           'Sem unidade',
            'servico_pericial_id': self.servico.pk,
        })
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cria_contraprova_grava_vinculo(self):
        """Criar um vestígio como contraprova grava o FK vestigio_contra_prova
        e ele aparece na lista de contraprovas do original."""
        original = _criar_vestigio(self.unidade, self.servico, self.perito, lacre='ORIG-CP')
        self.autenticar(self.perito)
        r = self.client.post('/api/custodia/vestigios/', {
            'lacre':                    'CONTRAPROVA-1',
            'descricao':                'Contraprova de teste',
            'unidade_demandante_id':    self.unidade.pk,
            'servico_pericial_id':      self.servico.pk,
            'vestigio_contra_prova_id': original.pk,
        })
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        cp = Vestigio.objects.get(pk=r.data['id'])
        self.assertEqual(cp.vestigio_contra_prova_id, original.pk)
        r2 = self.client.get(f'/api/custodia/vestigios/{original.pk}/contra-provas/')
        self.assertIn(cp.pk, [v['id'] for v in r2.data])


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

    def test_externo_nao_move_vestigio_alheio(self):
        """
        EXTERNO só pode movimentar vestígios que ele mesmo cadastrou (sessão 18,
        regra 21). Aqui o vestígio foi criado pelo perito, então o envio pelo
        externo é barrado na validação (400, não 403 — ele alcança o create mas
        falha a regra de propriedade).
        """
        r = self._criar_movimentacao_via_api(self.vestigio_id, self.externo)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

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

    def test_admin_lotado_no_servico_aceita(self):
        """ADMINISTRATIVO aceita SOMENTE se lotado no serviço de destino."""
        self.admin.servicos_periciais.add(self.servico)
        r = self._aceitar_movimentacao(self.mov_id, self.admin)
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_admin_sem_lotacao_nao_aceita(self):
        """ADMINISTRATIVO sem lotação no serviço de destino NÃO aceita (sem override)."""
        r = self._aceitar_movimentacao(self.mov_id, self.admin)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

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
        """Reabrir é exclusivo de SUPER_ADMIN (sessão 18, regra 2b)."""
        self.autenticar(self.super_admin)
        r = self.client.post(f'/api/custodia/vestigios/{self.vestigio_id}/reabrir/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['status'], 'ANDAMENTO')

    def test_admin_nao_pode_reabrir(self):
        """ADMINISTRATIVO pode finalizar, mas NÃO pode reabrir (regra 2b)."""
        self.autenticar(self.admin)
        r = self.client.post(f'/api/custodia/vestigios/{self.vestigio_id}/reabrir/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


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


# ---------------------------------------------------------------------------
# 9. Movimentação ENTRE SERVIÇOS distintos — cadeia de custódia (Lei 13.964)
# ---------------------------------------------------------------------------

class MovimentacaoEntreServicosTest(CustodiaBaseTest):
    """
    Regressão do bug que travava a movimentação em produção.

    A suíte anterior usava UM ÚNICO serviço pericial em tudo, então o serviço de
    destino da movimentação sempre coincidia com o serviço atual do vestígio —
    mascarando o bug. Aqui o vestígio nasce no serviço BAL e é passado adiante
    para BIO e depois para PLT.

    Regra (analogia do "passe de bola"): o perito lotado no serviço de DESTINO
    precisa VER a transferência pendente para poder aceitá-la (receber a posse).
    Antes da correção, a visibilidade da listagem usava o serviço ATUAL do
    vestígio, tornando o passe invisível ao destino — o recebedor nunca via a
    movimentação e jamais conseguia aceitar. Só o detentor atual pode repassar.
    """

    def setUp(self):
        super().setUp()
        # Três serviços periciais distintos
        self.bal = self.servico                            # origem  (SETEC)
        self.bio = _criar_servico('BIO', 'Biologia')       # destino 1
        self.plt = _criar_servico('PLT', 'Papiloscopia')   # destino 2

        # Perito A (origem) já existe na base; B e C sem unidade → visibilidade
        # puramente por serviço pericial (isola o critério sob teste).
        self.perito_a = self.perito
        self.perito_a.servicos_periciais.add(self.bal)

        self.perito_b = _criar_usuario('peritoB@test.com', perfil=User.Perfil.PERITO)
        self.perito_b.servicos_periciais.add(self.bio)

        self.perito_c = _criar_usuario('peritoC@test.com', perfil=User.Perfil.PERITO)
        self.perito_c.servicos_periciais.add(self.plt)

        # A registra o vestígio no serviço de origem (BAL)
        self.vestigio = _criar_vestigio(self.unidade, self.bal, self.perito_a, lacre='BAL-BIO-001')

    # -- helpers -----------------------------------------------------------------

    def _transferir(self, servico, usuario):
        """Cria movimentação interna para um serviço pericial específico."""
        self.autenticar(usuario)
        return self.client.post('/api/custodia/movimentacoes/', {
            'vestigio_id':         self.vestigio.pk,
            'servico_pericial_id': servico.pk,
            'descricao':           f'Transferência para {servico.sigla}',
        })

    def _ids_movimentacoes(self, usuario, params=''):
        self.autenticar(usuario)
        r = self.client.get(f'/api/custodia/movimentacoes/{params}')
        results = r.data.get('results', r.data)
        return [m['id'] for m in results], results

    # -- testes ------------------------------------------------------------------

    def test_destino_ve_transferencia_pendente(self):
        """Perito do serviço de destino VÊ a transferência pendente (o passe chega)."""
        r_mov = self._transferir(self.bio, self.perito_a)
        self.assertEqual(r_mov.status_code, status.HTTP_201_CREATED)
        mov_id = r_mov.data['id']

        ids, _ = self._ids_movimentacoes(self.perito_b)
        self.assertIn(mov_id, ids,
                      'O perito do serviço de destino (BIO) precisa ver a transferência pendente.')

    def test_destino_ve_na_aba_aguardando_meu_aceite(self):
        mov_id = self._transferir(self.bio, self.perito_a).data['id']
        ids, _ = self._ids_movimentacoes(self.perito_b, '?aguardando_meu_aceite=true')
        self.assertIn(mov_id, ids)

    def test_servico_alheio_nao_ve_transferencia(self):
        """Perito de serviço não envolvido NÃO vê a transferência (sem vazamento)."""
        mov_id = self._transferir(self.bio, self.perito_a).data['id']
        ids, _ = self._ids_movimentacoes(self.perito_c)
        self.assertNotIn(mov_id, ids)

    def test_emissor_continua_vendo_o_que_enviou(self):
        """O emissor (A) continua vendo a movimentação que registrou."""
        mov_id = self._transferir(self.bio, self.perito_a).data['id']
        ids, _ = self._ids_movimentacoes(self.perito_a)
        self.assertIn(mov_id, ids)

    def test_pode_aceitar_true_para_destino(self):
        mov_id = self._transferir(self.bio, self.perito_a).data['id']
        _, results = self._ids_movimentacoes(self.perito_b)
        mov = next(m for m in results if m['id'] == mov_id)
        self.assertTrue(mov['pode_aceitar'])

    def test_servico_alheio_nao_pode_aceitar(self):
        """
        Serviço alheio (C) nem enxerga a movimentação → 404 (resposta opaca).

        Como C não está no escopo de visibilidade, o get_object() do DRF nega
        com 404 antes de chegar à checagem de autorização. Para cadeia de
        custódia isso é o ideal: não vaza sequer a existência do registro.
        """
        mov_id = self._transferir(self.bio, self.perito_a).data['id']
        self.autenticar(self.perito_c)
        r = self.client.post(f'/api/custodia/movimentacoes/{mov_id}/aceitar/')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_emissor_nao_pode_aceitar_o_proprio_passe(self):
        """
        O emissor (A) VÊ a movimentação (created_by) mas NÃO pode aceitá-la —
        ele não está no serviço de destino. Aqui a negação é 403: A enxerga o
        registro, mas a autorização de aceite recai apenas sobre o destino.
        """
        mov_id = self._transferir(self.bio, self.perito_a).data['id']
        self.autenticar(self.perito_a)
        r = self.client.post(f'/api/custodia/movimentacoes/{mov_id}/aceitar/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_destino_aceita_e_recebe_a_posse(self):
        """B aceita → vira user_destino do vestígio e o serviço passa a ser BIO."""
        mov_id = self._transferir(self.bio, self.perito_a).data['id']

        self.autenticar(self.perito_b)
        r_aceite = self.client.post(f'/api/custodia/movimentacoes/{mov_id}/aceitar/')
        self.assertEqual(r_aceite.status_code, status.HTTP_200_OK)
        self.assertTrue(r_aceite.data['aceito'])

        self.vestigio.refresh_from_db()
        self.assertEqual(self.vestigio.user_destino_id, self.perito_b.pk)
        self.assertEqual(self.vestigio.servico_pericial_id, self.bio.pk)

    def test_destino_ve_vestigio_apos_aceitar(self):
        """Depois de aceitar, B passa a ver o vestígio na sua listagem."""
        mov_id = self._transferir(self.bio, self.perito_a).data['id']
        self.autenticar(self.perito_b)
        self.client.post(f'/api/custodia/movimentacoes/{mov_id}/aceitar/')

        r = self.client.get('/api/custodia/vestigios/')
        ids = [v['id'] for v in r.data.get('results', r.data)]
        self.assertIn(self.vestigio.pk, ids)

    def test_fluxo_completo_passe_e_repasse(self):
        """
        Cadeia completa: A(BAL) → B(BIO) aceita → B repassa → C(PLT) aceita.

        Garante que, após receber a posse, o detentor consegue passar adiante e
        que somente o detentor atual pode fazê-lo.
        """
        # 1º passe: A → BIO, B aceita
        mov1 = self._transferir(self.bio, self.perito_a).data['id']
        self.autenticar(self.perito_b)
        self.client.post(f'/api/custodia/movimentacoes/{mov1}/aceitar/')

        # 2º passe: B (detentor) → PLT
        r_mov2 = self._transferir(self.plt, self.perito_b)
        self.assertEqual(r_mov2.status_code, status.HTTP_201_CREATED)
        mov2 = r_mov2.data['id']

        # C (PLT) vê o passe pendente na sua caixa de entrada e aceita
        ids_c, _ = self._ids_movimentacoes(self.perito_c, '?aguardando_meu_aceite=true')
        self.assertIn(mov2, ids_c)

        self.autenticar(self.perito_c)
        r_aceite2 = self.client.post(f'/api/custodia/movimentacoes/{mov2}/aceitar/')
        self.assertEqual(r_aceite2.status_code, status.HTTP_200_OK)

        self.vestigio.refresh_from_db()
        self.assertEqual(self.vestigio.user_destino_id, self.perito_c.pk)
        self.assertEqual(self.vestigio.servico_pericial_id, self.plt.pk)

    def test_nao_detentor_nao_pode_repassar(self):
        """
        Após B receber a posse, A (que apenas criou e já passou) não pode mais
        registrar nova movimentação — só o detentor atual toca na bola.
        """
        mov1 = self._transferir(self.bio, self.perito_a).data['id']
        self.autenticar(self.perito_b)
        self.client.post(f'/api/custodia/movimentacoes/{mov1}/aceitar/')

        # A tenta repassar para PLT, mas não detém mais a posse
        r = self._transferir(self.plt, self.perito_a)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# 10. Widget de Resumo de Custódia (/api/custodia/resumo/)
# ---------------------------------------------------------------------------

class ResumoCustodiaTest(CustodiaBaseTest):
    """
    Garante que o widget de resumo seja coerente com o que cada perfil vê:

    - PERITO sem unidade_demandante (situação normal — o campo é só de EXTERNO)
      precisa ver números reais do seu serviço, e não zeros.
    - O contador de "transferências pendentes" deve incluir os passes que estão
      CHEGANDO para o serviço do usuário, mesmo que o vestígio ainda esteja
      fisicamente no serviço de origem (movimentação ainda não aceita).
    """

    def setUp(self):
        super().setUp()
        self.bal = self.servico
        self.bio = _criar_servico('BIO', 'Biologia')

        # Perito A em BAL, sem unidade (como os peritos reais do sistema)
        self.perito_a = self.perito
        self.perito_a.unidade_demandante = None
        self.perito_a.save()
        self.perito_a.servicos_periciais.add(self.bal)

        # Perito B em BIO, sem unidade
        self.perito_b = _criar_usuario('peritoB_res@test.com', perfil=User.Perfil.PERITO)
        self.perito_b.servicos_periciais.add(self.bio)

        self.vestigio = _criar_vestigio(self.unidade, self.bal, self.perito_a, lacre='RES-001')

    def test_perito_sem_unidade_ve_numeros_reais(self):
        """Antes da correção, perito sem unidade recebia tudo zerado."""
        self.autenticar(self.perito_a)
        r = self.client.get('/api/custodia/resumo/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(r.data['vestigios']['total'], 1)

    def test_contador_pendentes_inclui_passe_chegando(self):
        """
        Transferência pendente A(BAL) → BIO deve contar para o perito de BIO,
        mesmo o vestígio ainda estando em BAL (não aceito).
        """
        self.autenticar(self.perito_a)
        self.client.post('/api/custodia/movimentacoes/', {
            'vestigio_id':         self.vestigio.pk,
            'servico_pericial_id': self.bio.pk,
            'descricao':           'Para BIO',
        })

        self.autenticar(self.perito_b)
        r = self.client.get('/api/custodia/resumo/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(r.data['transferencias_pendentes'], 1)


# ---------------------------------------------------------------------------
# 11. Regra de DNA para EXTERNO (banco nacional de perfis genéticos)
# ---------------------------------------------------------------------------

class DNARegraExternoTest(CustodiaBaseTest):
    """
    EXTERNO pode VER e BUSCAR perfis APENADOS e NÃO APENADOS (consulta plena ao
    banco nacional — Lei 12.654/2012), mas só pode CRIAR perfis NÃO APENADOS.
    O backend força situacao=NAO_APENADO na criação por usuário externo; a
    leitura/busca não tem restrição por situação.
    """

    _PAYLOAD_BASE = {
        'nascimento':   '1990-01-01T00:00:00Z',
        'naturalidade': 'MANAUS',
        'mae':          'MARIA',
        'gemeo':        'NO',
        'transfusao':   'NO',
        'transplante':  'NO',
        'processado_banco_perfis_genetico': 'NO',
        'data_da_coleta': '2024-01-01T00:00:00Z',
        'finalidade_coleta': 'LEI',
    }

    def _payload(self, **extra):
        return {**self._PAYLOAD_BASE, **extra}

    def test_externo_ve_dna_apenado(self):
        """EXTERNO consegue ABRIR um perfil apenado."""
        dna = _criar_dna(self.perito, situacao=DNA.Situacao.APENADO)
        self.autenticar(self.externo)
        r = self.client.get(f'/api/custodia/dnas/{dna.pk}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['situacao'], 'APENADO')

    def test_externo_busca_dna_apenado(self):
        """EXTERNO consegue FILTRAR/buscar perfis apenados."""
        dna = _criar_dna(self.perito, situacao=DNA.Situacao.APENADO)
        self.autenticar(self.externo)
        r = self.client.get('/api/custodia/dnas/?situacao=APENADO')
        ids = [d['id'] for d in r.data.get('results', r.data)]
        self.assertIn(dna.pk, ids)

    def test_externo_cria_forcado_para_nao_apenado(self):
        """EXTERNO tenta criar como APENADO → backend sobrescreve para NAO_APENADO."""
        self.autenticar(self.externo)
        payload = self._payload(
            nome='CICRANO', cpf='55566677788', rg='7654321', situacao='APENADO',
        )
        r = self.client.post('/api/custodia/dnas/', payload)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['situacao'], 'NAO_APENADO')

    def test_perito_cria_apenado_sem_restricao(self):
        """PERITO pode registrar APENADO normalmente."""
        self.autenticar(self.perito)
        payload = self._payload(
            nome='BELTRANO', cpf='99988877766', rg='1112223', situacao='APENADO',
        )
        r = self.client.post('/api/custodia/dnas/', payload)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['situacao'], 'APENADO')

    def test_externo_nao_pode_editar_dna(self):
        """EXTERNO não pode editar perfis existentes."""
        dna = _criar_dna(self.perito, situacao=DNA.Situacao.NAO_APENADO)
        self.autenticar(self.externo)
        r = self.client.patch(f'/api/custodia/dnas/{dna.pk}/', {'notas': 'alteração'})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# 12. Filtro "Vestígios comigo" (visão CRM da mesa do perito)
# ---------------------------------------------------------------------------

class VestigiosComigoTest(CustodiaBaseTest):
    """
    ?comigo=true → vestígios sob a guarda física atual do perito: recebidos por
    ele (user_destino), SEM transferência pendente de saída e não finalizados.
    Some da lista assim que ele repassa o vestígio adiante (entra em trânsito).
    """

    def setUp(self):
        super().setUp()
        self.bio = _criar_servico('BIO', 'Biologia')
        self.perito.servicos_periciais.add(self.servico)  # perito lotado em SETEC

    def _comigo_ids(self, usuario):
        self.autenticar(usuario)
        r = self.client.get('/api/custodia/vestigios/?comigo=true')
        return [v['id'] for v in r.data.get('results', r.data)]

    def test_vestigio_aceito_aparece_em_comigo(self):
        vid = self._criar_vestigio_via_api(self.perito).data['id']
        mov = self._criar_movimentacao_via_api(vid, self.perito)   # destino = SETEC
        self._aceitar_movimentacao(mov.data['id'], self.perito)    # perito recebe
        self.assertIn(vid, self._comigo_ids(self.perito))

    def test_vestigio_em_transito_some_de_comigo(self):
        vid = self._criar_vestigio_via_api(self.perito).data['id']
        mov = self._criar_movimentacao_via_api(vid, self.perito)
        self._aceitar_movimentacao(mov.data['id'], self.perito)

        # Perito repassa adiante → entra em trânsito (movimentação pendente)
        self.autenticar(self.perito)
        self.client.post('/api/custodia/movimentacoes/', {
            'vestigio_id':         vid,
            'servico_pericial_id': self.bio.pk,
            'descricao':           'Para BIO',
        })
        self.assertNotIn(vid, self._comigo_ids(self.perito))

    def test_vestigio_finalizado_nao_aparece_em_comigo(self):
        vid = self._criar_vestigio_via_api(self.perito).data['id']
        mov = self._criar_movimentacao_via_api(vid, self.perito)
        self._aceitar_movimentacao(mov.data['id'], self.perito)
        self._finalizar_vestigio(vid, self.custodiante)
        self.assertNotIn(vid, self._comigo_ids(self.perito))


# ---------------------------------------------------------------------------
# 13. FAV (PDF) — smoke + integridade de conteúdo (hash)
# ---------------------------------------------------------------------------

class FichaVestigioPdfTest(CustodiaBaseTest):
    """
    Exercita o gerador da Ficha de Acompanhamento (FAV): deve emitir o PDF,
    gravar o FichaVestigioRegistro com o digest de conteúdo (SHA-256) e o
    endpoint público de validação deve devolver o hash e indicar que o conteúdo
    atual ainda confere com o emitido.
    """

    def test_ficha_pdf_gera_e_grava_hash(self):
        vid = self._criar_vestigio_via_api(self.perito).data['id']
        self.autenticar(self.perito)
        r = self.client.get(f'/api/custodia/vestigios/{vid}/ficha-pdf/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r['Content-Type'], 'application/pdf')

        reg = FichaVestigioRegistro.objects.filter(vestigio_id=vid).first()
        self.assertIsNotNone(reg)
        self.assertEqual(len(reg.conteudo_hash), 64)  # SHA-256 hex

    def test_validar_ficha_retorna_hash_e_confere(self):
        vid = self._criar_vestigio_via_api(self.perito).data['id']
        self.autenticar(self.perito)
        self.client.get(f'/api/custodia/vestigios/{vid}/ficha-pdf/')
        reg = FichaVestigioRegistro.objects.filter(vestigio_id=vid).first()

        r = self.client.get(f'/api/custodia/vestigios/validar-ficha/?protocolo={reg.protocolo}')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['valido'])
        self.assertIsNotNone(r.data['conteudo_hash'])
        self.assertTrue(r.data['conteudo_atual_confere'])

    def test_validar_ficha_detecta_alteracao_posterior(self):
        """Após nova movimentação, o conteúdo muda → conteudo_atual_confere = False."""
        vid = self._criar_vestigio_via_api(self.perito).data['id']
        self.autenticar(self.perito)
        self.client.get(f'/api/custodia/vestigios/{vid}/ficha-pdf/')
        reg = FichaVestigioRegistro.objects.filter(vestigio_id=vid).first()

        # Movimenta o vestígio depois da emissão da ficha
        self._criar_movimentacao_via_api(vid, self.perito)

        r = self.client.get(f'/api/custodia/vestigios/validar-ficha/?protocolo={reg.protocolo}')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data['conteudo_atual_confere'])


# ---------------------------------------------------------------------------
# 14. Análise Gerencial (analytics) — visibilidade por perfil + filtros
# ---------------------------------------------------------------------------

class AnalyticsVisibilidadeTest(CustodiaBaseTest):
    """
    - CUSTODIANTE / ADMINISTRATIVO / SUPER_ADMIN → todos os dados (global).
    - PERITO / OPERACIONAL → apenas o(s) serviço(s) em que estão lotados.
    - Filtro explícito por serviço restringe os dados para todos.
    """

    def setUp(self):
        super().setUp()
        self.servico_b = _criar_servico('BIO', 'Biologia')
        _criar_vestigio(self.unidade, self.servico,   self.perito, lacre='SETEC-1')
        _criar_vestigio(self.unidade, self.servico_b, self.admin,  lacre='BIO-1')
        self.perito.servicos_periciais.add(self.servico)  # lotado só em SETEC

    def _total(self, usuario, params=''):
        self.autenticar(usuario)
        r = self.client.get(f'/api/custodia/analytics/{params}')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        return r.data['resumo']['total_vestigios']

    def test_custodiante_ve_todos(self):
        self.assertGreaterEqual(self._total(self.custodiante), 2)

    def test_admin_ve_todos(self):
        self.assertGreaterEqual(self._total(self.admin), 2)

    def test_perito_ve_apenas_servico_lotado(self):
        self.assertEqual(self._total(self.perito), 1)  # só SETEC-1

    def test_externo_nao_acessa_analytics(self):
        self.autenticar(self.externo)
        r = self.client.get('/api/custodia/analytics/')
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_filtro_servico_restringe_para_quem_ve_tudo(self):
        total = self._total(self.custodiante, f'?servico_pericial_id={self.servico_b.pk}')
        self.assertEqual(total, 1)  # só BIO-1


# ---------------------------------------------------------------------------
# 15. Auto-preenchimento de ocorrencia/ano_ocorrencia a partir do vínculo
# ---------------------------------------------------------------------------

class SincronizarOcorrenciaPrincipalTest(CustodiaBaseTest):
    """
    Os campos texto ocorrencia/ano_ocorrencia saíram do formulário de cadastro,
    mas continuam alimentando a FAV/listagens — então são preenchidos
    automaticamente a partir da PRIMEIRA ocorrência vinculada (fonte única).
    """

    def _sincronizar_com_oc(self, vestigio, numero, data_fato):
        fake_oc = MagicMock(numero_ocorrencia=numero, data_fato=data_fato)
        qs = MagicMock()
        qs.order_by.return_value.first.return_value = fake_oc
        with patch.object(Vestigio, 'ocorrencias_vinculadas', qs):
            vestigio.sincronizar_ocorrencia_principal()
        vestigio.refresh_from_db()

    def test_ano_vem_do_numero_da_ocorrencia(self):
        """O ano vem dos 2 primeiros dígitos do número (2026), não do data_fato (2025)."""
        v = _criar_vestigio(self.unidade, self.servico, self.perito, lacre='SYNC-FILL')
        self._sincronizar_com_oc(v, '2612300045/SETEC', datetime.date(2025, 12, 28))
        self.assertEqual(v.ocorrencia, '2612300045/SETEC')
        self.assertEqual(v.ano_ocorrencia, 2026)

    def test_ano_fallback_data_fato_quando_numero_atipico(self):
        """Número fora do padrão AAMM… → ano cai para o data_fato (dados legados)."""
        v = _criar_vestigio(self.unidade, self.servico, self.perito, lacre='SYNC-LEG')
        self._sincronizar_com_oc(v, 'LEGADO-XYZ', datetime.date(2019, 3, 1))
        self.assertEqual(v.ano_ocorrencia, 2019)

    def test_limpa_quando_sem_vinculo(self):
        v = _criar_vestigio(self.unidade, self.servico, self.perito, lacre='SYNC-CLEAR')
        v.ocorrencia = 'ANTIGO/2020'
        v.ano_ocorrencia = 2020
        v.save()
        v.sincronizar_ocorrencia_principal()  # nenhuma ocorrência vinculada
        v.refresh_from_db()
        self.assertIsNone(v.ocorrencia)
        self.assertIsNone(v.ano_ocorrencia)


# ---------------------------------------------------------------------------
# 16. Edição de vestígio — restrita à lotação no serviço de cadastro
# ---------------------------------------------------------------------------

class EdicaoVestigioTest(CustodiaBaseTest):
    """
    Editar um vestígio antes da 1ª movimentação só pode ser feito por quem está
    lotado no serviço pericial onde foi cadastrado (cadeia de custódia).
    ADMINISTRATIVO/CUSTODIANTE sem lotação NÃO editam; SUPER_ADMIN é break-glass.
    """

    def setUp(self):
        super().setUp()
        self.vest = _criar_vestigio(self.unidade, self.servico, self.perito, lacre='EDIT-1')

    def _editar(self, usuario, dados=None):
        self.autenticar(usuario)
        return self.client.patch(
            f'/api/custodia/vestigios/{self.vest.pk}/',
            dados or {'descricao': 'Nova descrição'},
        )

    def test_perito_lotado_no_servico_edita(self):
        self.perito.servicos_periciais.add(self.servico)
        self.assertEqual(self._editar(self.perito).status_code, status.HTTP_200_OK)

    def test_perito_de_outro_servico_nao_edita(self):
        """
        Perito de outro serviço nem ENXERGA o vestígio (filtro de visibilidade) →
        404 (resposta opaca). Já o ADMINISTRATIVO vê tudo, então é barrado na
        edição com 400 (ver test_administrativo_sem_lotacao_nao_edita).
        """
        outro = _criar_usuario('peritoX@test.com', perfil=User.Perfil.PERITO)
        outro.servicos_periciais.add(_criar_servico('BIO', 'Biologia'))
        self.assertEqual(self._editar(outro).status_code, status.HTTP_404_NOT_FOUND)

    def test_administrativo_sem_lotacao_nao_edita(self):
        """ADMINISTRATIVO de outro serviço NÃO edita (era o comportamento relatado)."""
        self.assertEqual(self._editar(self.admin).status_code, status.HTTP_400_BAD_REQUEST)

    def test_administrativo_lotado_edita(self):
        self.admin.servicos_periciais.add(self.servico)
        self.assertEqual(self._editar(self.admin).status_code, status.HTTP_200_OK)

    def test_custodiante_sem_lotacao_nao_edita(self):
        self.assertEqual(self._editar(self.custodiante).status_code, status.HTTP_400_BAD_REQUEST)

    def test_super_admin_edita_qualquer(self):
        self.assertEqual(self._editar(self.super_admin).status_code, status.HTTP_200_OK)

    def test_pode_editar_reflete_lotacao(self):
        self.autenticar(self.admin)  # sem lotação
        r = self.client.get(f'/api/custodia/vestigios/{self.vest.pk}/')
        self.assertFalse(r.data['pode_editar'])
        self.admin.servicos_periciais.add(self.servico)
        r2 = self.client.get(f'/api/custodia/vestigios/{self.vest.pk}/')
        self.assertTrue(r2.data['pode_editar'])


# ---------------------------------------------------------------------------
# 17. Edição de movimentação — permitida só até antes do aceite
# ---------------------------------------------------------------------------

class EdicaoMovimentacaoTest(CustodiaBaseTest):
    """
    A movimentação pode ser editada enquanto NÃO for aceita, apenas por quem está
    lotado no serviço de ORIGEM (quem enviou o passe). SUPER_ADMIN é break-glass;
    ADMINISTRATIVO NÃO tem override. Após o aceite torna-se imutável para todos.
    """

    def setUp(self):
        super().setUp()
        # Perito lotado no serviço de origem (onde o vestígio foi cadastrado) — é
        # quem pode editar a movimentação pendente, conforme a regra de lotação.
        self.perito.servicos_periciais.add(self.servico)
        r_vest = self._criar_vestigio_via_api()
        self.vest_id = r_vest.data['id']
        r_mov = self._criar_movimentacao_via_api(self.vest_id, usuario=self.perito)
        self.mov_id = r_mov.data['id']

    def _patch(self, usuario, dados):
        self.autenticar(usuario)
        return self.client.patch(f'/api/custodia/movimentacoes/{self.mov_id}/', dados)

    def test_lotado_na_origem_edita_movimentacao_pendente(self):
        # 'lacre-novo-1' minúsculo deve ser gravado em CAIXA ALTA (save() do modelo)
        r = self._patch(self.perito, {'lacre': 'lacre-novo-1', 'descricao': 'Corrigido'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        mov = VestigioMovimentacao.objects.get(pk=self.mov_id)
        self.assertEqual(mov.lacre, 'LACRE-NOVO-1')
        self.assertEqual(mov.descricao, 'Corrigido')

    def test_admin_sem_lotacao_nao_edita(self):
        """ADMINISTRATIVO vê tudo, mas sem lotação na origem é barrado (400)."""
        r = self._patch(self.admin, {'descricao': 'tentativa admin'})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_perito_de_outro_servico_nao_edita(self):
        """Perito de outro serviço nem enxerga a movimentação → 404 (opaco)."""
        outro = _criar_usuario('peritoMov@test.com', perfil=User.Perfil.PERITO)
        outro.servicos_periciais.add(_criar_servico('BIO', 'Biologia'))
        r = self._patch(outro, {'descricao': 'tentativa'})
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_super_admin_edita(self):
        r = self._patch(self.super_admin, {'descricao': 'break-glass'})
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_nao_edita_apos_aceite(self):
        self._aceitar_movimentacao(self.mov_id, usuario=self.custodiante)
        r = self._patch(self.perito, {'descricao': 'Tentativa pós-aceite'})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pode_editar_true_antes_false_depois(self):
        self.autenticar(self.perito)
        movs = self.client.get(f'/api/custodia/vestigios/{self.vest_id}/movimentacoes/').data
        self.assertTrue(movs[0]['pode_editar'])
        self._aceitar_movimentacao(self.mov_id, usuario=self.custodiante)
        self.autenticar(self.perito)
        movs2 = self.client.get(f'/api/custodia/vestigios/{self.vest_id}/movimentacoes/').data
        self.assertFalse(movs2[0]['pode_editar'])

    def test_externo_nao_edita_movimentacao(self):
        """EXTERNO é bloqueado no update pelo PodeCustodiar (403/404), nunca 200."""
        self.autenticar(self.externo)
        r = self.client.patch(
            f'/api/custodia/movimentacoes/{self.mov_id}/', {'descricao': 'tentativa'}
        )
        self.assertIn(r.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))


# ---------------------------------------------------------------------------
# 17b. Lacre efetivo — toda movimentação referencia um lacre (mudando ou não)
# ---------------------------------------------------------------------------

class LacreEfetivoMovimentacaoTest(CustodiaBaseTest):
    """
    Na listagem/timeline, TODA movimentação referencia um lacre: a que troca
    mostra o novo; a que não troca herda o lacre vigente (lacre_mantido=True).
    Espelha o rastreio de lacre da FAV.
    """

    def setUp(self):
        super().setUp()
        self.perito.servicos_periciais.add(self.servico)
        self.vest = _criar_vestigio(self.unidade, self.servico, self.perito, lacre='INIT-1')

    def test_segunda_movimentacao_herda_lacre_vigente(self):
        import datetime
        from django.utils import timezone

        m1 = VestigioMovimentacao.objects.create(vestigio=self.vest, lacre='a44444', created_by=self.perito)
        m2 = VestigioMovimentacao.objects.create(vestigio=self.vest, lacre='', created_by=self.perito)
        # ordem cronológica determinística (m1 antes de m2)
        t0 = timezone.now()
        VestigioMovimentacao.objects.filter(pk=m1.pk).update(created_at=t0)
        VestigioMovimentacao.objects.filter(pk=m2.pk).update(created_at=t0 + datetime.timedelta(seconds=5))

        self.autenticar(self.perito)
        movs = self.client.get(f'/api/custodia/vestigios/{self.vest.pk}/movimentacoes/').data
        by_id = {m['id']: m for m in movs}

        # 1ª trocou o lacre → mostra o novo (em CAIXA ALTA), não é "mantido"
        self.assertEqual(by_id[m1.id]['lacre_efetivo'], 'A44444')
        self.assertFalse(by_id[m1.id]['lacre_mantido'])
        # 2ª não trocou → herda 'A44444' e marca como mantido
        self.assertEqual(by_id[m2.id]['lacre_efetivo'], 'A44444')
        self.assertTrue(by_id[m2.id]['lacre_mantido'])

    def test_movimentacao_sem_troca_herda_lacre_inicial_do_vestigio(self):
        """Sem nenhuma troca anterior, herda o lacre inicial do próprio vestígio."""
        m = VestigioMovimentacao.objects.create(vestigio=self.vest, lacre='', created_by=self.perito)
        self.autenticar(self.perito)
        movs = self.client.get(f'/api/custodia/vestigios/{self.vest.pk}/movimentacoes/').data
        d = next(x for x in movs if x['id'] == m.id)
        self.assertEqual(d['lacre_efetivo'], 'INIT-1')
        self.assertTrue(d['lacre_mantido'])


# ---------------------------------------------------------------------------
# 18. Serviço de origem — imutável; localização atual dinâmica
# ---------------------------------------------------------------------------

class OrigemServicoTest(CustodiaBaseTest):
    """
    O serviço de ORIGEM (cadastro) é imutável e sempre preservado.
    `servico_pericial` reflete a LOCALIZAÇÃO atual e muda no aceite de
    movimentação interna — sem nunca apagar a origem.
    """

    def setUp(self):
        super().setUp()
        self.servico_y = _criar_servico('BIO', 'Biologia')
        r = self._criar_vestigio_via_api()   # cadastrado em self.servico (origem)
        self.vest_id = r.data['id']

    def _mover_para_y_e_aceitar(self):
        self.autenticar(self.perito)
        r_mov = self.client.post('/api/custodia/movimentacoes/', {
            'vestigio_id':         self.vest_id,
            'servico_pericial_id': self.servico_y.id,
            'descricao':           'Transferência para BIO',
        })
        self.assertEqual(r_mov.status_code, status.HTTP_201_CREATED)
        self._aceitar_movimentacao(r_mov.data['id'], usuario=self.custodiante)

    def test_origem_gravada_no_cadastro(self):
        v = Vestigio.objects.get(pk=self.vest_id)
        self.assertEqual(v.servico_pericial_origem_id, self.servico.id)

    def test_origem_preservada_apos_movimentacao(self):
        self._mover_para_y_e_aceitar()
        v = Vestigio.objects.get(pk=self.vest_id)
        self.assertEqual(v.servico_pericial_id, self.servico_y.id)         # localização mudou
        self.assertEqual(v.servico_pericial_origem_id, self.servico.id)    # origem preservada

    def test_detalhe_expoe_origem_e_localizacao(self):
        self._mover_para_y_e_aceitar()
        self.autenticar(self.custodiante)  # enxerga tudo
        r = self.client.get(f'/api/custodia/vestigios/{self.vest_id}/')
        self.assertEqual(r.data['servico_pericial_origem']['id'], self.servico.id)
        self.assertEqual(r.data['localizacao_atual']['sigla'], self.servico_y.sigla)
        self.assertEqual(r.data['localizacao_atual']['tipo'], 'servico')

    def test_aceite_nao_altera_origem_de_outro_aceite(self):
        """Após dois saltos (X→Y→X de novo não; só Y), origem continua X."""
        self._mover_para_y_e_aceitar()
        v = Vestigio.objects.get(pk=self.vest_id)
        self.assertEqual(v.servico_pericial_origem_id, self.servico.id)

    def test_registrado_por_servico_exposto(self):
        """O serviço do registrante (created_by) é buscado do banco e exposto."""
        self.perito.servicos_periciais.add(self.servico)
        self.autenticar(self.perito)
        r = self.client.get(f'/api/custodia/vestigios/{self.vest_id}/')
        self.assertIn(self.servico.sigla, r.data['registrado_por_servico'])

    def test_origem_inferida_do_registrante_quando_historico(self):
        """Histórico sem origem explícita → infere do serviço do registrante
        (inferido=True), em vez de 'Não registrada'."""
        self.perito.servicos_periciais.add(self.servico)
        v = Vestigio.objects.get(pk=self.vest_id)
        v.servico_pericial_origem = None            # simula dado histórico (origem perdida)
        v.save(update_fields=['servico_pericial_origem'])
        self.autenticar(self.perito)
        r = self.client.get(f'/api/custodia/vestigios/{self.vest_id}/')
        self.assertTrue(r.data['servico_origem_inferido'])
        self.assertIn(self.servico.sigla, r.data['servico_origem_nome'])

    def test_origem_nao_registrada_sem_servico_do_registrante(self):
        """Sem origem explícita e sem serviço no registrante → 'Não registrada'."""
        self.perito.servicos_periciais.clear()
        v = Vestigio.objects.get(pk=self.vest_id)
        v.servico_pericial_origem = None
        v.save(update_fields=['servico_pericial_origem'])
        self.autenticar(self.perito)
        r = self.client.get(f'/api/custodia/vestigios/{self.vest_id}/')
        self.assertFalse(r.data['servico_origem_inferido'])
        self.assertIn('Não registrada', r.data['servico_origem_nome'])


# ---------------------------------------------------------------------------
# 19. EXTERNO — destino fixo na custódia central do IC
# ---------------------------------------------------------------------------

class ExternoDestinoCustodiaTest(CustodiaBaseTest):
    """
    EXTERNO: o destino do cadastro é SEMPRE a custódia central do IC (sigla CUST),
    forçado pelo backend mesmo que o front envie outro serviço. A ORIGEM do vestígio
    é a UNIDADE do externo — a custódia é destino, não origem.
    """

    def _criar_como_externo(self, lacre, servico_id=None, unidade_id=None):
        self.autenticar(self.externo)
        return self.client.post('/api/custodia/vestigios/', {
            'lacre':                 lacre,
            'descricao':             'Material externo',
            'unidade_demandante_id': unidade_id or self.unidade.pk,
            'servico_pericial_id':   servico_id or self.servico.pk,  # tentativa de outro destino
        })

    def test_destino_forcado_para_custodia_ic(self):
        r = self._criar_como_externo('EXT-CUST-1')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        v = Vestigio.objects.get(pk=r.data['id'])
        self.assertEqual(v.servico_pericial_id, self.custodia_ic.id)   # forçado p/ CUST
        self.assertNotEqual(v.servico_pericial_id, self.servico.id)    # ignorou o enviado

    def test_origem_servico_nao_carimbada(self):
        r = self._criar_como_externo('EXT-CUST-2')
        v = Vestigio.objects.get(pk=r.data['id'])
        self.assertIsNone(v.servico_pericial_origem_id)   # custódia é destino, não origem

    def test_origem_display_aponta_para_externa(self):
        r = self._criar_como_externo('EXT-CUST-3')
        v = Vestigio.objects.get(pk=r.data['id'])
        texto, inferido = v.origem_display()
        self.assertIn('externa', texto.lower())
        self.assertFalse(inferido)

    def test_unidade_forcada_para_a_do_externo(self):
        outra = _criar_unidade('XYZ', 'Outra Unidade')
        r = self._criar_como_externo('EXT-CUST-4', unidade_id=outra.pk)
        v = Vestigio.objects.get(pk=r.data['id'])
        self.assertEqual(v.unidade_demandante_id, self.externo.unidade_demandante_id)

    def test_perito_continua_com_origem_servico(self):
        """Garante que a trava do EXTERNO não afeta o perito (origem = serviço)."""
        r = self._criar_vestigio_via_api(self.perito, lacre='PER-CUST-1')
        v = Vestigio.objects.get(pk=r.data['id'])
        self.assertEqual(v.servico_pericial_origem_id, self.servico.id)


# ---------------------------------------------------------------------------
# 20. EXTERNO — visibilidade de movimentações restrita aos seus vestígios
# ---------------------------------------------------------------------------

class ExternoVisibilidadeMovimentacaoTest(CustodiaBaseTest):
    """
    EXTERNO só enxerga movimentações de vestígios que ele pode ver (cadastrados
    por ele OU da unidade dele). NÃO vê movimentações de vestígios de OUTRAS
    unidades — nem quando o destino do passe é a unidade do externo.
    """

    def setUp(self):
        super().setUp()
        self.outra_unidade = _criar_unidade('OUTRA', 'Outra Unidade')

    def test_ve_movimentacao_do_proprio_vestigio(self):
        vest = _criar_vestigio(self.unidade, self.servico, self.externo, lacre='EXT-MOV-1')
        mov = VestigioMovimentacao.objects.create(
            vestigio=vest, servico_pericial=self.servico, created_by=self.externo
        )
        self.autenticar(self.externo)
        r = self.client.get('/api/custodia/movimentacoes/')
        ids = [m['id'] for m in r.data['results']]
        self.assertIn(mov.id, ids)

    def test_nao_ve_movimentacao_de_outra_unidade(self):
        """Vazamento corrigido: mov de vestígio de outra unidade, destino = unidade do externo."""
        vest_outro = _criar_vestigio(self.outra_unidade, self.servico, self.perito, lacre='OUTRO-MOV-1')
        mov_outro = VestigioMovimentacao.objects.create(
            vestigio=vest_outro, unidade_demandante=self.unidade, created_by=self.perito
        )
        self.autenticar(self.externo)
        r = self.client.get('/api/custodia/movimentacoes/')
        ids = [m['id'] for m in r.data['results']]
        self.assertNotIn(mov_outro.id, ids)
