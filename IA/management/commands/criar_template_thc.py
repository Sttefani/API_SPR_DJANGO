from django.core.management.base import BaseCommand
from IA.models import TemplateLaudo

class Command(BaseCommand):
    help = 'Cria template padrão de laudo químico THC'

    def handle(self, *args, **options):
        
        # Template completo
        template_texto = """GOVERNO DO ESTADO DE RORAIMA
"Amazônia: Patrimônio dos Brasileiros"
SECRETARIA DE ESTADO DA SEGURANÇA PÚBLICA
POLÍCIA CIVIL
INSTITUTO DE CRIMINALÍSTICA

Laudo nº. {numero_laudo}/{ano_atual}/{servico_pericial}

LAUDO PRELIMINAR DE CONSTATAÇÃO EM SUBSTÂNCIA

Aos {dia_extenso} ({dia_numero}) dia do mês de {mes_extenso} ({mes_numero}) do ano {ano_extenso} ({ano_numero}), no Laboratório de Química Forense do Instituto de Criminalística de Roraima, em conformidade com a legislação e os dispositivos regulamentares vigentes, designado pelo Diretor {nome_diretor} do INSTITUTO DE CRIMINALÍSTICA DO ESTADO DE RORAIMA, o Perito Criminal de Polícia Civil {nome_perito} realizou Exame de Constatação em Substância, a fim de ser atendida solicitação {tipo_autoridade} {nome_autoridade}, contida na Requisição de Exame Pericial nº. {numero_requisicao}, datada de {data_requisicao}, referente ao {tipo_procedimento} nº. {numero_procedimento}, descrevendo com verdade e tudo quanto possa interessar à Justiça.

1 DO MATERIAL

{descricao_material}

Massa bruta total: {massa_bruta_total}

Lacre(s) de entrada: {lacres_entrada}

2 DOS EXAMES

O material enviado foi examinado macroscopicamente e descrito.

Amostras do material foram submetidas à pesquisa da substância psicotrópica DELTA-9-TETRA-HIDROCANNABINOL (THC), presente na espécie vegetal Cannabis sativa Linneu, através do Teste de Duquenois Levine.

3 DOS RESULTADOS

O exame realizado na amostra extraída do material descrito no item 1 resultou {resultado} para a substância psicotrópica TETRAHIDROCANNABINOL (THC), presente na espécie vegetal Cannabis sativa L., estando seu uso proscrito em todo Território Nacional por causar dependência física e/ou psíquica, de acordo com a Portaria nº 344, de 12 de maio de 1998, da Secretaria Nacional de Vigilância Sanitária do Ministério da Saúde.

Ressalta-se que, para bem e fielmente permitir a sistemática de análises, uma parte do material recebido ({peso_consumido}) foi consumido nos exames realizados, enquanto que outra parte ({peso_contraprova}) foi encaminhada para contraprova/definitivo sob lacre(s) {lacres_contraprova}, restando para ser devolvido o total de massa líquida de {massa_liquida_final}, sob lacre(s) de saída {lacres_saida}.

Nada mais havendo a relatar, o Perito encerra o presente Laudo, confeccionado em {numero_paginas} folha(s) numerada(s), que segue devidamente assinado.

Boa Vista-RR, {data_laudo_extenso}.


_________________________________
{nome_perito_assinatura}
Perito Criminal IC/RR
Matrícula: {matricula_perito}"""

        # Verifica se já existe
        if TemplateLaudo.objects.filter(tipo='quimico_preliminar_thc').exists():
            self.stdout.write(self.style.WARNING('Template já existe. Atualizando...'))
            template = TemplateLaudo.objects.get(tipo='quimico_preliminar_thc')
        else:
            self.stdout.write(self.style.SUCCESS('Criando novo template...'))
            template = TemplateLaudo(tipo='quimico_preliminar_thc')
        
        # Dados do template
        template.nome = 'Laudo Preliminar de Constatação - THC'
        template.descricao = 'Template padrão para exames químicos preliminares de THC (Cannabis sativa)'
        template.template_texto = template_texto
        
        template.campos_obrigatorios = [
            'numero_laudo',
            'servico_pericial',
            'nome_diretor',
            'nome_perito',
            'tipo_autoridade',
            'nome_autoridade',
            'numero_requisicao',
            'data_requisicao',
            'tipo_procedimento',
            'numero_procedimento',
            'descricao_material',
            'massa_bruta_total',
            'lacres_entrada',
            'resultado',
            'peso_consumido',
            'peso_contraprova',
            'lacres_contraprova',
            'massa_liquida_final',
            'lacres_saida',
            'numero_paginas',
            'nome_perito_assinatura',
            'matricula_perito'
        ]
        
        template.campos_com_validacao = {
            "resultado": ["POSITIVO", "NEGATIVO"],
            "tipo_procedimento": ["TCO", "TC","IP", "APF", "IP", "IPM", "BOC", "BO", "AAFFAI"],
            "tipo_autoridade": ["do Delegado", "da Delegada", "do Promotor", "da Promotora", "do Juiz", "da Juíza", "do PRF", "do PM"]
        }
        
        template.campos_automaticos = [
            'ano_atual',
            'ano_numero',
            'ano_extenso',
            'dia_numero',
            'dia_extenso',
            'mes_numero',
            'mes_extenso',
            'data_laudo_extenso'
        ]
        
        template.exemplo_dados = {
            'numero_laudo': '167',
            'servico_pericial': 'DPE/IC/PC/SESP/RR',
            'nome_diretor': 'Dr. João Silva',
            'nome_perito': 'Geovane Sales da Silva',
            'tipo_autoridade': 'do Delegado',
            'nome_autoridade': 'DOMINGOS SÁVIO MACENA CORREA',
            'numero_requisicao': '119/18-10DP',
            'data_requisicao': '16/02/2018',
            'tipo_procedimento': 'TCO',
            'numero_procedimento': '023/2018-1°DPD',
            'descricao_material': 'Um (01) invólucro plástico contendo substância vegetal desidratada, de coloração pardo-esverdeada, constituída por fragmentos de caules, folhas e frutos, aparentando ser maconha',
            'massa_bruta_total': '2,30g (dois gramas e trinta centigramas)',
            'lacres_entrada': '123456',
            'resultado': 'POSITIVO',
            'peso_consumido': '0,50g',
            'peso_contraprova': '1,50g',
            'lacres_contraprova': '123457',
            'massa_liquida_final': '0,30g',
            'lacres_saida': '123458',
            'numero_paginas': '02',
            'nome_perito_assinatura': 'Geovane Sales da Silva',
            'matricula_perito': '042000343'
        }
        
        template.ativo = True
        template.save()
        
        self.stdout.write(self.style.SUCCESS(f'✅ Template "{template.nome}" criado com sucesso!'))
        self.stdout.write(self.style.SUCCESS(f'📋 Total de campos obrigatórios: {len(template.campos_obrigatorios)}'))