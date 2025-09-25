import io
from django.http import FileResponse
from django.utils import timezone
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

def gerar_pdf_movimentacao(movimentacao, request):
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
    story.append(Paragraph("RELATÓRIO DE MOVIMENTAÇÃO", styles['Titulo']))
    add_linha("ID da Movimentação", f"#{movimentacao.id}")
    add_linha("Assunto", movimentacao.assunto)
    add_linha("Registrado em", movimentacao.created_at.strftime('%d/%m/%Y às %H:%M:%S'))
    if movimentacao.created_by: 
        add_linha("Registrado por", movimentacao.created_by.nome_completo)

    # Dados da Ocorrência relacionada
    story.append(Paragraph("1. OCORRÊNCIA RELACIONADA", styles['Subtitulo']))
    if movimentacao.ocorrencia:
        add_linha("Número da Ocorrência", movimentacao.ocorrencia.numero_ocorrencia)
        if hasattr(movimentacao.ocorrencia, 'status'):
            add_linha("Status da Ocorrência", movimentacao.ocorrencia.get_status_display())
        if movimentacao.ocorrencia.servico_pericial:
            add_linha("Serviço Pericial", movimentacao.ocorrencia.servico_pericial.nome)
        if movimentacao.ocorrencia.perito_atribuido:
            add_linha("Perito Atribuído", movimentacao.ocorrencia.perito_atribuido.nome_completo)

    # Detalhes da Movimentação
    story.append(Paragraph("2. DETALHES DA MOVIMENTAÇÃO", styles['Subtitulo']))
    add_linha("Assunto", movimentacao.assunto)
    if movimentacao.ip_registro:
        add_linha("IP de Registro", movimentacao.ip_registro)
    
    story.append(Paragraph("3. DESCRIÇÃO", styles['Subtitulo']))
    add_paragrafo(movimentacao.descricao or "Não informado.")

    # Dados de Auditoria
    story.append(Paragraph("4. DADOS DE AUDITORIA", styles['Subtitulo']))
    add_linha("Data de Criação", movimentacao.created_at.strftime('%d/%m/%Y às %H:%M:%S'))
    if movimentacao.created_by:
        add_linha("Criado por", movimentacao.created_by.nome_completo)
    if movimentacao.updated_at:
        add_linha("Última Atualização", movimentacao.updated_at.strftime('%d/%m/%Y às %H:%M:%S'))
    if movimentacao.updated_by:
        add_linha("Atualizado por", movimentacao.updated_by.nome_completo)
    if hasattr(movimentacao, 'deleted_at') and movimentacao.deleted_at:
        add_linha("Data de Exclusão", movimentacao.deleted_at.strftime('%d/%m/%Y às %H:%M:%S'))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"MOV-{movimentacao.id}-{movimentacao.created_at.strftime('%Y%m%d_%H%M')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def gerar_pdf_historico_movimentacoes(ocorrencia, request):
    """Gera PDF com todas as movimentações de uma ocorrência"""
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
    styles.add(ParagraphStyle(name='MovimentacaoItem', parent=styles['Normal'], leading=14, spaceAfter=4, leftIndent=20))

    story = []
    
    def add_linha(chave, valor):
        if valor not in [None, '']:
            p_text = f"<b>{chave}:</b> {str(valor)}"
            story.append(Paragraph(p_text, styles['NormalCompacto']))

    def add_paragrafo(texto):
        if texto:
            story.append(Paragraph(texto, styles['NormalCompacto']))

    # --- MONTAGEM DO PDF ---
    story.append(Paragraph("HISTÓRICO DE MOVIMENTAÇÕES", styles['Titulo']))
    
    # Dados da Ocorrência
    story.append(Paragraph("DADOS DA OCORRÊNCIA", styles['Subtitulo']))
    add_linha("Número da Ocorrência", ocorrencia.numero_ocorrencia)
    if hasattr(ocorrencia, 'status'):
        add_linha("Status", ocorrencia.get_status_display())
    if ocorrencia.servico_pericial:
        add_linha("Serviço Pericial", ocorrencia.servico_pericial.nome)
    if ocorrencia.perito_atribuido:
        add_linha("Perito Atribuído", ocorrencia.perito_atribuido.nome_completo)

    # Lista de Movimentações
    movimentacoes = ocorrencia.movimentacoes.filter(deleted_at__isnull=True).order_by('created_at')
    
    story.append(Paragraph("HISTÓRICO DE MOVIMENTAÇÕES", styles['Subtitulo']))
    
    if movimentacoes.exists():
        for i, mov in enumerate(movimentacoes, 1):
            story.append(Paragraph(f"<b>{i}. {mov.assunto}</b>", styles['Subtitulo']))
            
            # Dados da movimentação
            data_hora = mov.created_at.strftime('%d/%m/%Y às %H:%M:%S')
            autor = mov.created_by.nome_completo if mov.created_by else "Sistema"
            story.append(Paragraph(f"<b>Data/Hora:</b> {data_hora}", styles['MovimentacaoItem']))
            story.append(Paragraph(f"<b>Autor:</b> {autor}", styles['MovimentacaoItem']))
            
            if mov.ip_registro:
                story.append(Paragraph(f"<b>IP:</b> {mov.ip_registro}", styles['MovimentacaoItem']))
            
            if mov.descricao:
                story.append(Paragraph(f"<b>Descrição:</b>", styles['MovimentacaoItem']))
                story.append(Paragraph(mov.descricao, styles['MovimentacaoItem']))
            
            story.append(Spacer(1, 0.3*cm))
    else:
        add_paragrafo("Nenhuma movimentação registrada para esta ocorrência.")

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"HISTORICO-{ocorrencia.numero_ocorrencia.replace('/', '_')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)