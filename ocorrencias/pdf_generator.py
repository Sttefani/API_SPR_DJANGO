import io
from django.http import FileResponse
from django.utils import timezone
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

def gerar_pdf_ocorrencia(ocorrencia, request):
    buffer = io.BytesIO()
    
    usuario_emissor = request.user.nome_completo if request.user.is_authenticated else "Sistema"
    data_emissao = timezone.now().strftime('%d/%m/%Y às %H:%M:%S')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.line(doc.leftMargin, doc.bottomMargin - 0.5*cm, doc.width + doc.leftMargin, doc.bottomMargin - 0.5*cm)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1*cm, f"Relatório emitido por: {usuario_emissor}")
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Data da Emissão: {data_emissao}")
        canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=2.5*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Titulo', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name='Subtitulo', fontSize=12, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=2, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='NormalCompacto', parent=styles['Normal'], leading=14, spaceAfter=2))

    story = []
    
    def add_linha(chave, valor):
        if valor not in [None, '']:
            p_text = f"<b>{chave}:</b> {str(valor)}"
            story.append(Paragraph(p_text, styles['NormalCompacto']))

    def add_paragrafo(texto):
        if texto:
            story.append(Paragraph(texto, styles['NormalCompacto']))

    # --- MONTAGEM DO PDF ---
    story.append(Paragraph("RELATÓRIO DE OCORRÊNCIA", styles['Titulo']))
    add_linha("Número da Ocorrência", ocorrencia.numero_ocorrencia)
    add_linha("Status", ocorrencia.get_status_display())
    add_linha("Registrado em", ocorrencia.created_at.strftime('%d/%m/%Y às %H:%M'))
    if ocorrencia.created_by: add_linha("Registrado por", ocorrencia.created_by.nome_completo)

    story.append(Paragraph("1. DADOS GERAIS DA SOLICITAÇÃO", styles['Subtitulo']))
    if ocorrencia.servico_pericial: add_linha("Serviço Pericial", ocorrencia.servico_pericial.nome)
    if ocorrencia.unidade_demandante: add_linha("Unidade Demandante", ocorrencia.unidade_demandante.nome)
    if ocorrencia.autoridade: add_linha("Autoridade Demandante", f"{ocorrencia.autoridade.nome} ({ocorrencia.autoridade.cargo.nome})")
    if ocorrencia.perito_atribuido: add_linha("Perito Atribuído", ocorrencia.perito_atribuido.nome_completo)

    story.append(Paragraph("2. DADOS DO FATO", styles['Subtitulo']))
    add_linha("Data do Fato", ocorrencia.data_fato.strftime('%d/%m/%Y'))
    if ocorrencia.hora_fato: add_linha("Hora do Fato", ocorrencia.hora_fato.strftime('%H:%M'))
    if ocorrencia.cidade: add_linha("Cidade", ocorrencia.cidade.nome)
    if ocorrencia.classificacao: add_linha("Classificação", f"{ocorrencia.classificacao.codigo} - {ocorrencia.classificacao.nome}")

    story.append(Paragraph("3. HISTÓRICO / OBSERVAÇÕES", styles['Subtitulo']))
    add_paragrafo(ocorrencia.historico or "Não informado.")

    # --- SEÇÃO DAS FICHAS ESPECÍFICAS ---
    story.append(Paragraph("4. DADOS ESPECÍFICOS DA PERÍCIA", styles['Subtitulo']))
    
    ficha_impressa = False
    try:
        ficha = ocorrencia.ficha_local_crime
        add_linha("Tipo de Ficha", "Local de Crime")
        add_linha("Endereço", ficha.endereco_completo)
        if ficha.auxiliar: add_linha("Auxiliar", ficha.auxiliar.nome_completo)
        ficha_impressa = True
    except AttributeError:
        pass # Ignora se a ficha não existir
    
    # Adicione aqui os 'try/except' para as outras fichas...

    if not ficha_impressa:
        add_paragrafo("Nenhuma ficha específica associada.")

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"OC-{ocorrencia.numero_ocorrencia.replace('/', '_')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def gerar_pdf_ocorrencias_por_perito(perito_id, request):
    """Gera PDF com ocorrências de um perito específico"""
    from ocorrencias.models import Ocorrencia
    from usuarios.models import User
    
    buffer = io.BytesIO()
    
    usuario_emissor = request.user.nome_completo if request.user.is_authenticated else "Sistema"
    data_emissao = timezone.now().strftime('%d/%m/%Y às %H:%M:%S')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.line(doc.leftMargin, doc.bottomMargin - 0.5*cm, doc.width + doc.leftMargin, doc.bottomMargin - 0.5*cm)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1*cm, f"Relatório emitido por: {usuario_emissor}")
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Data da Emissão: {data_emissao}")
        canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=2.5*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Titulo', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name='Subtitulo', fontSize=12, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=2, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='NormalCompacto', parent=styles['Normal'], leading=14, spaceAfter=2))
    styles.add(ParagraphStyle(name='OcorrenciaItem', parent=styles['Normal'], leading=14, spaceAfter=4, leftIndent=20))

    story = []
    
    def add_linha(chave, valor):
        if valor not in [None, '']:
            p_text = f"<b>{chave}:</b> {str(valor)}"
            story.append(Paragraph(p_text, styles['NormalCompacto']))

    try:
        perito = User.objects.get(pk=perito_id)
    except User.DoesNotExist:
        story.append(Paragraph("ERRO: Perito não encontrado", styles['Titulo']))
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename="erro.pdf")

    # --- MONTAGEM DO PDF ---
    story.append(Paragraph(f"OCORRÊNCIAS - {perito.nome_completo.upper()}", styles['Titulo']))
    
    # Informações do perito
    add_linha("Perito", perito.nome_completo)
    add_linha("Email", perito.email)
    if perito.servicos_periciais.exists():
        servicos = ', '.join([s.nome for s in perito.servicos_periciais.all()])
        add_linha("Serviços Periciais", servicos)

    # Busca ocorrências do perito
    ocorrencias = Ocorrencia.objects.filter(perito_atribuido=perito, deleted_at__isnull=True).order_by('-created_at')
    
    add_linha("Total de Ocorrências", ocorrencias.count())
    
    # Estatísticas por status
    story.append(Paragraph("ESTATÍSTICAS POR STATUS", styles['Subtitulo']))
    for status_code, status_display in Ocorrencia.Status.choices:
        count = ocorrencias.filter(status=status_code).count()
        if count > 0:
            add_linha(status_display, count)

    story.append(Spacer(1, 0.5*cm))
    
    if ocorrencias.exists():
        story.append(Paragraph("OCORRÊNCIAS ATRIBUÍDAS", styles['Subtitulo']))
        
        for i, oc in enumerate(ocorrencias, 1):
            story.append(Paragraph(f"<b>{i}. {oc.numero_ocorrencia}</b>", styles['Subtitulo']))
            
            story.append(Paragraph(f"<b>Status:</b> {oc.get_status_display()}", styles['OcorrenciaItem']))
            story.append(Paragraph(f"<b>Data do Fato:</b> {oc.data_fato.strftime('%d/%m/%Y')}", styles['OcorrenciaItem']))
            story.append(Paragraph(f"<b>Registrado em:</b> {oc.created_at.strftime('%d/%m/%Y')}", styles['OcorrenciaItem']))
            
            if oc.servico_pericial:
                story.append(Paragraph(f"<b>Serviço:</b> {oc.servico_pericial.nome}", styles['OcorrenciaItem']))
            if oc.cidade:
                story.append(Paragraph(f"<b>Cidade:</b> {oc.cidade.nome}", styles['OcorrenciaItem']))
            if oc.classificacao:
                story.append(Paragraph(f"<b>Classificação:</b> {oc.classificacao.nome}", styles['OcorrenciaItem']))
            
            story.append(Spacer(1, 0.3*cm))
    else:
        story.append(Paragraph("Nenhuma ocorrência encontrada para este perito.", styles['NormalCompacto']))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"OCORRENCIAS_PERITO-{perito.nome_completo.replace(' ', '_')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def gerar_pdf_ocorrencias_por_ano(ano, request):
    """Gera PDF com ocorrências de um ano específico"""
    from ocorrencias.models import Ocorrencia
    
    buffer = io.BytesIO()
    
    usuario_emissor = request.user.nome_completo if request.user.is_authenticated else "Sistema"
    data_emissao = timezone.now().strftime('%d/%m/%Y às %H:%M:%S')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.line(doc.leftMargin, doc.bottomMargin - 0.5*cm, doc.width + doc.leftMargin, doc.bottomMargin - 0.5*cm)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1*cm, f"Relatório emitido por: {usuario_emissor}")
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Data da Emissão: {data_emissao}")
        canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=2.5*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Titulo', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name='Subtitulo', fontSize=12, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=2, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='NormalCompacto', parent=styles['Normal'], leading=14, spaceAfter=2))
    styles.add(ParagraphStyle(name='OcorrenciaItem', parent=styles['Normal'], leading=14, spaceAfter=4, leftIndent=20))

    story = []
    
    def add_linha(chave, valor):
        if valor not in [None, '']:
            p_text = f"<b>{chave}:</b> {str(valor)}"
            story.append(Paragraph(p_text, styles['NormalCompacto']))

    # --- MONTAGEM DO PDF ---
    story.append(Paragraph(f"OCORRÊNCIAS - ANO {ano}", styles['Titulo']))
    
    # Busca ocorrências do ano
    ocorrencias = Ocorrencia.objects.filter(
        created_at__year=ano, 
        deleted_at__isnull=True
    ).order_by('-created_at')
    
    add_linha("Ano", ano)
    add_linha("Total de Ocorrências", ocorrencias.count())
    
    # Estatísticas por status
    story.append(Paragraph("ESTATÍSTICAS POR STATUS", styles['Subtitulo']))
    for status_code, status_display in Ocorrencia.Status.choices:
        count = ocorrencias.filter(status=status_code).count()
        if count > 0:
            add_linha(status_display, count)

    # Estatísticas por mês
    story.append(Paragraph("ESTATÍSTICAS POR MÊS", styles['Subtitulo']))
    meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
             'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
    
    for i in range(1, 13):
        count = ocorrencias.filter(created_at__month=i).count()
        if count > 0:
            add_linha(meses[i-1], count)

    story.append(Spacer(1, 0.5*cm))
    
    if ocorrencias.exists():
        story.append(Paragraph("OCORRÊNCIAS REGISTRADAS", styles['Subtitulo']))
        
        for i, oc in enumerate(ocorrencias, 1):
            story.append(Paragraph(f"<b>{i}. {oc.numero_ocorrencia}</b>", styles['Subtitulo']))
            
            story.append(Paragraph(f"<b>Status:</b> {oc.get_status_display()}", styles['OcorrenciaItem']))
            story.append(Paragraph(f"<b>Data do Fato:</b> {oc.data_fato.strftime('%d/%m/%Y')}", styles['OcorrenciaItem']))
            story.append(Paragraph(f"<b>Registrado em:</b> {oc.created_at.strftime('%d/%m/%Y')}", styles['OcorrenciaItem']))
            
            if oc.perito_atribuido:
                story.append(Paragraph(f"<b>Perito:</b> {oc.perito_atribuido.nome_completo}", styles['OcorrenciaItem']))
            if oc.servico_pericial:
                story.append(Paragraph(f"<b>Serviço:</b> {oc.servico_pericial.nome}", styles['OcorrenciaItem']))
            if oc.cidade:
                story.append(Paragraph(f"<b>Cidade:</b> {oc.cidade.nome}", styles['OcorrenciaItem']))
            
            story.append(Spacer(1, 0.3*cm))
    else:
        story.append(Paragraph(f"Nenhuma ocorrência encontrada para o ano {ano}.", styles['NormalCompacto']))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"OCORRENCIAS_{ano}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def gerar_pdf_ocorrencias_por_status(status, request):
    """Gera PDF com ocorrências de um status específico"""
    from ocorrencias.models import Ocorrencia
    
    buffer = io.BytesIO()
    
    usuario_emissor = request.user.nome_completo if request.user.is_authenticated else "Sistema"
    data_emissao = timezone.now().strftime('%d/%m/%Y às %H:%M:%S')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.line(doc.leftMargin, doc.bottomMargin - 0.5*cm, doc.width + doc.leftMargin, doc.bottomMargin - 0.5*cm)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1*cm, f"Relatório emitido por: {usuario_emissor}")
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Data da Emissão: {data_emissao}")
        canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=2.5*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Titulo', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name='Subtitulo', fontSize=12, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=2, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='NormalCompacto', parent=styles['Normal'], leading=14, spaceAfter=2))
    styles.add(ParagraphStyle(name='OcorrenciaItem', parent=styles['Normal'], leading=14, spaceAfter=4, leftIndent=20))

    story = []
    
    def add_linha(chave, valor):
        if valor not in [None, '']:
            p_text = f"<b>{chave}:</b> {str(valor)}"
            story.append(Paragraph(p_text, styles['NormalCompacto']))

    # Obter o nome do status para exibição
    status_display = dict(Ocorrencia.Status.choices).get(status, status)
    
    # --- MONTAGEM DO PDF ---
    story.append(Paragraph(f"OCORRÊNCIAS - {status_display.upper()}", styles['Titulo']))
    
    # Busca ocorrências por status
    ocorrencias = Ocorrencia.objects.filter(
        status=status,
        deleted_at__isnull=True
    ).order_by('-created_at')
    
    add_linha("Status", status_display)
    add_linha("Total de Ocorrências", ocorrencias.count())
    
    story.append(Spacer(1, 0.5*cm))
    
    if ocorrencias.exists():
        story.append(Paragraph("OCORRÊNCIAS ENCONTRADAS", styles['Subtitulo']))
        
        for i, oc in enumerate(ocorrencias, 1):
            story.append(Paragraph(f"<b>{i}. {oc.numero_ocorrencia}</b>", styles['Subtitulo']))
            
            story.append(Paragraph(f"<b>Data do Fato:</b> {oc.data_fato.strftime('%d/%m/%Y')}", styles['OcorrenciaItem']))
            story.append(Paragraph(f"<b>Registrado em:</b> {oc.created_at.strftime('%d/%m/%Y')}", styles['OcorrenciaItem']))
            
            if oc.perito_atribuido:
                story.append(Paragraph(f"<b>Perito:</b> {oc.perito_atribuido.nome_completo}", styles['OcorrenciaItem']))
            if oc.servico_pericial:
                story.append(Paragraph(f"<b>Serviço:</b> {oc.servico_pericial.nome}", styles['OcorrenciaItem']))
            if oc.unidade_demandante:
                story.append(Paragraph(f"<b>Unidade:</b> {oc.unidade_demandante.nome}", styles['OcorrenciaItem']))
            if oc.cidade:
                story.append(Paragraph(f"<b>Cidade:</b> {oc.cidade.nome}", styles['OcorrenciaItem']))
            
            story.append(Spacer(1, 0.3*cm))
    else:
        story.append(Paragraph(f"Nenhuma ocorrência encontrada com status {status_display}.", styles['NormalCompacto']))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"OCORRENCIAS_{status}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def gerar_pdf_ocorrencias_por_servico(servico_id, request):
    """Gera PDF com ocorrências de um serviço pericial específico"""
    from ocorrencias.models import Ocorrencia
    from servicos_periciais.models import ServicoPericial
    
    buffer = io.BytesIO()
    
    usuario_emissor = request.user.nome_completo if request.user.is_authenticated else "Sistema"
    data_emissao = timezone.now().strftime('%d/%m/%Y às %H:%M:%S')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.line(doc.leftMargin, doc.bottomMargin - 0.5*cm, doc.width + doc.leftMargin, doc.bottomMargin - 0.5*cm)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1*cm, f"Relatório emitido por: {usuario_emissor}")
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Data da Emissão: {data_emissao}")
        canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=2.5*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Titulo', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name='Subtitulo', fontSize=12, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=2, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='NormalCompacto', parent=styles['Normal'], leading=14, spaceAfter=2))
    styles.add(ParagraphStyle(name='OcorrenciaItem', parent=styles['Normal'], leading=14, spaceAfter=4, leftIndent=20))

    story = []
    
    def add_linha(chave, valor):
        if valor not in [None, '']:
            p_text = f"<b>{chave}:</b> {str(valor)}"
            story.append(Paragraph(p_text, styles['NormalCompacto']))

    try:
        servico = ServicoPericial.objects.get(pk=servico_id)
    except ServicoPericial.DoesNotExist:
        story.append(Paragraph("ERRO: Serviço Pericial não encontrado", styles['Titulo']))
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename="erro.pdf")

    # --- MONTAGEM DO PDF ---
    story.append(Paragraph(f"OCORRÊNCIAS - {servico.nome.upper()}", styles['Titulo']))
    
    # Informações do serviço
    add_linha("Serviço Pericial", servico.nome)
    add_linha("Sigla", servico.sigla)

    # Busca ocorrências do serviço
    ocorrencias = Ocorrencia.objects.filter(
        servico_pericial=servico,
        deleted_at__isnull=True
    ).order_by('-created_at')
    
    add_linha("Total de Ocorrências", ocorrencias.count())
    
    # Estatísticas por status
    story.append(Paragraph("ESTATÍSTICAS POR STATUS", styles['Subtitulo']))
    for status_code, status_display in Ocorrencia.Status.choices:
        count = ocorrencias.filter(status=status_code).count()
        if count > 0:
            add_linha(status_display, count)

    story.append(Spacer(1, 0.5*cm))
    
    if ocorrencias.exists():
        story.append(Paragraph("OCORRÊNCIAS DO SERVIÇO", styles['Subtitulo']))
        
        for i, oc in enumerate(ocorrencias, 1):
            story.append(Paragraph(f"<b>{i}. {oc.numero_ocorrencia}</b>", styles['Subtitulo']))
            
            story.append(Paragraph(f"<b>Status:</b> {oc.get_status_display()}", styles['OcorrenciaItem']))
            story.append(Paragraph(f"<b>Data do Fato:</b> {oc.data_fato.strftime('%d/%m/%Y')}", styles['OcorrenciaItem']))
            story.append(Paragraph(f"<b>Registrado em:</b> {oc.created_at.strftime('%d/%m/%Y')}", styles['OcorrenciaItem']))
            
            if oc.perito_atribuido:
                story.append(Paragraph(f"<b>Perito:</b> {oc.perito_atribuido.nome_completo}", styles['OcorrenciaItem']))
            if oc.unidade_demandante:
                story.append(Paragraph(f"<b>Unidade:</b> {oc.unidade_demandante.nome}", styles['OcorrenciaItem']))
            if oc.cidade:
                story.append(Paragraph(f"<b>Cidade:</b> {oc.cidade.nome}", styles['OcorrenciaItem']))
            if oc.classificacao:
                story.append(Paragraph(f"<b>Classificação:</b> {oc.classificacao.nome}", styles['OcorrenciaItem']))
            
            story.append(Spacer(1, 0.3*cm))
    else:
        story.append(Paragraph("Nenhuma ocorrência encontrada para este serviço.", styles['NormalCompacto']))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"OCORRENCIAS_{servico.sigla}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def gerar_pdf_ocorrencias_por_cidade(cidade_id, request):
    """Gera PDF com ocorrências de uma cidade específica"""
    from ocorrencias.models import Ocorrencia
    from cidades.models import Cidade
    
    buffer = io.BytesIO()
    
    usuario_emissor = request.user.nome_completo if request.user.is_authenticated else "Sistema"
    data_emissao = timezone.now().strftime('%d/%m/%Y às %H:%M:%S')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.line(doc.leftMargin, doc.bottomMargin - 0.5*cm, doc.width + doc.leftMargin, doc.bottomMargin - 0.5*cm)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1*cm, f"Relatório emitido por: {usuario_emissor}")
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Data da Emissão: {data_emissao}")
        canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=2.5*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Titulo', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name='Subtitulo', fontSize=12, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=2, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='NormalCompacto', parent=styles['Normal'], leading=14, spaceAfter=2))
    styles.add(ParagraphStyle(name='OcorrenciaItem', parent=styles['Normal'], leading=14, spaceAfter=4, leftIndent=20))

    story = []
    
    def add_linha(chave, valor):
        if valor not in [None, '']:
            p_text = f"<b>{chave}:</b> {str(valor)}"
            story.append(Paragraph(p_text, styles['NormalCompacto']))

    try:
        cidade = Cidade.objects.get(pk=cidade_id)
    except Cidade.DoesNotExist:
        story.append(Paragraph("ERRO: Cidade não encontrada", styles['Titulo']))
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename="erro.pdf")

    # --- MONTAGEM DO PDF ---
    story.append(Paragraph(f"OCORRÊNCIAS - {cidade.nome.upper()}", styles['Titulo']))
    
    # Informações da cidade
    add_linha("Cidade", cidade.nome)
    if hasattr(cidade, 'estado'):
        add_linha("Estado", cidade.estado)

    # Busca ocorrências da cidade
    ocorrencias = Ocorrencia.objects.filter(
        cidade=cidade,
        deleted_at__isnull=True
    ).order_by('-created_at')
    
    add_linha("Total de Ocorrências", ocorrencias.count())
    
    # Estatísticas por status
    story.append(Paragraph("ESTATÍSTICAS POR STATUS", styles['Subtitulo']))
    for status_code, status_display in Ocorrencia.Status.choices:
        count = ocorrencias.filter(status=status_code).count()
        if count > 0:
            add_linha(status_display, count)

    story.append(Spacer(1, 0.5*cm))
    
    if ocorrencias.exists():
        story.append(Paragraph("OCORRÊNCIAS NA CIDADE", styles['Subtitulo']))
        
        for i, oc in enumerate(ocorrencias, 1):
            story.append(Paragraph(f"<b>{i}. {oc.numero_ocorrencia}</b>", styles['Subtitulo']))
            
            story.append(Paragraph(f"<b>Status:</b> {oc.get_status_display()}", styles['OcorrenciaItem']))
            story.append(Paragraph(f"<b>Data do Fato:</b> {oc.data_fato.strftime('%d/%m/%Y')}", styles['OcorrenciaItem']))
            story.append(Paragraph(f"<b>Registrado em:</b> {oc.created_at.strftime('%d/%m/%Y')}", styles['OcorrenciaItem']))
            
            if oc.perito_atribuido:
                story.append(Paragraph(f"<b>Perito:</b> {oc.perito_atribuido.nome_completo}", styles['OcorrenciaItem']))
            if oc.servico_pericial:
                story.append(Paragraph(f"<b>Serviço:</b> {oc.servico_pericial.nome}", styles['OcorrenciaItem']))
            if oc.unidade_demandante:
                story.append(Paragraph(f"<b>Unidade:</b> {oc.unidade_demandante.nome}", styles['OcorrenciaItem']))
            if oc.classificacao:
                story.append(Paragraph(f"<b>Classificação:</b> {oc.classificacao.nome}", styles['OcorrenciaItem']))
            
            story.append(Spacer(1, 0.3*cm))
    else:
        story.append(Paragraph("Nenhuma ocorrência encontrada para esta cidade.", styles['NormalCompacto']))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"OCORRENCIAS_{cidade.nome.replace(' ', '_')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def gerar_pdf_relatorio_geral(request):
    """Gera PDF com todas as ocorrências (listagem geral)"""
    from ocorrencias.models import Ocorrencia
    
    buffer = io.BytesIO()
    
    usuario_emissor = request.user.nome_completo if request.user.is_authenticated else "Sistema"
    data_emissao = timezone.now().strftime('%d/%m/%Y às %H:%M:%S')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.line(doc.leftMargin, doc.bottomMargin - 0.5*cm, doc.width + doc.leftMargin, doc.bottomMargin - 0.5*cm)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1*cm, f"Relatório emitido por: {usuario_emissor}")
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Data da Emissão: {data_emissao}")
        canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.5*cm, bottomMargin=2.5*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Titulo', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name='Subtitulo', fontSize=12, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=2, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='NormalCompacto', parent=styles['Normal'], leading=14, spaceAfter=2))

    story = []
    
    def add_linha(chave, valor):
        if valor not in [None, '']:
            p_text = f"<b>{chave}:</b> {str(valor)}"
            story.append(Paragraph(p_text, styles['NormalCompacto']))

    # --- MONTAGEM DO PDF ---
    story.append(Paragraph("RELATÓRIO GERAL DE OCORRÊNCIAS", styles['Titulo']))
    
    # Busca todas as ocorrências
    ocorrencias = Ocorrencia.objects.filter(deleted_at__isnull=True)
    
    add_linha("Total de Ocorrências", ocorrencias.count())
    
    # Estatísticas por status
    story.append(Paragraph("ESTATÍSTICAS POR STATUS", styles['Subtitulo']))
    for status_code, status_display in Ocorrencia.Status.choices:
        count = ocorrencias.filter(status=status_code).count()
        if count > 0:
            add_linha(status_display, count)

    # Estatísticas por ano
    story.append(Paragraph("ESTATÍSTICAS POR ANO", styles['Subtitulo']))
    anos = ocorrencias.dates('created_at', 'year', order='DESC')
    for ano in anos:
        count = ocorrencias.filter(created_at__year=ano.year).count()
        add_linha(str(ano.year), count)

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"RELATORIO_GERAL-{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)