import io
from django.http import FileResponse
from django.utils import timezone
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

def gerar_pdf_ordem_servico(ordem_servico, request):
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
    story.append(Paragraph("ORDEM DE SERVIÇO", styles['Titulo']))
    add_linha("Número da OS", ordem_servico.numero_os)
    add_linha("Ocorrência", ordem_servico.ocorrencia.numero_ocorrencia)
    add_linha("Status", ordem_servico.get_status_display())
    add_linha("Emitida em", ordem_servico.created_at.strftime('%d/%m/%Y às %H:%M'))
    if ordem_servico.created_by: 
        add_linha("Emitida por", ordem_servico.created_by.nome_completo)

    story.append(Paragraph("1. DADOS DA ORDEM DE SERVIÇO", styles['Subtitulo']))
    add_linha("Prazo para Conclusão", f"{ordem_servico.prazo_dias} dias")
    if ordem_servico.data_conclusao:
        add_linha("Data de Conclusão", ordem_servico.data_conclusao.strftime('%d/%m/%Y às %H:%M'))

    # Dados de Ciência
    story.append(Paragraph("2. DADOS DE CIÊNCIA", styles['Subtitulo']))
    if ordem_servico.ciente_por:
        add_linha("Perito Ciente", ordem_servico.ciente_por.nome_completo)
        add_linha("Data da Ciência", ordem_servico.data_ciencia.strftime('%d/%m/%Y às %H:%M:%S'))
        if ordem_servico.ip_ciencia:
            add_linha("IP da Ciência", ordem_servico.ip_ciencia)
    else:
        add_paragrafo("Aguardando ciência do perito.")

    # Dados da Ocorrência relacionada
    story.append(Paragraph("3. DADOS DA OCORRÊNCIA", styles['Subtitulo']))
    if ordem_servico.ocorrencia:
        if hasattr(ordem_servico.ocorrencia, 'status'):
            add_linha("Status da Ocorrência", ordem_servico.ocorrencia.get_status_display())
        if ordem_servico.ocorrencia.perito_atribuido:
            add_linha("Perito Atribuído", ordem_servico.ocorrencia.perito_atribuido.nome_completo)

    # Dados Espelhados (Snapshot da ocorrência)
    story.append(Paragraph("4. DADOS DEMANDANTES", styles['Subtitulo']))
    if ordem_servico.unidade_demandante:
        add_linha("Unidade Demandante", ordem_servico.unidade_demandante.nome)
    if ordem_servico.autoridade_demandante:
        add_linha("Autoridade Demandante", f"{ordem_servico.autoridade_demandante.nome} ({ordem_servico.autoridade_demandante.cargo.nome})" if ordem_servico.autoridade_demandante.cargo else ordem_servico.autoridade_demandante.nome)
    if ordem_servico.procedimento:
        add_linha("Procedimento", ordem_servico.procedimento.nome)

    # Documentos de Referência
    story.append(Paragraph("5. DOCUMENTOS DE REFERÊNCIA", styles['Subtitulo']))
    if ordem_servico.tipo_documento_referencia:
        add_linha("Tipo de Documento", ordem_servico.tipo_documento_referencia.nome)
    if ordem_servico.numero_documento_referencia:
        add_linha("Número do Documento", ordem_servico.numero_documento_referencia)
    if ordem_servico.processo_sei_referencia:
        add_linha("Processo SEI", ordem_servico.processo_sei_referencia)
    if ordem_servico.processo_judicial_referencia:
        add_linha("Processo Judicial", ordem_servico.processo_judicial_referencia)

    # Texto Padrão
    story.append(Paragraph("6. DETERMINAÇÃO", styles['Subtitulo']))
    add_paragrafo(ordem_servico.texto_padrao)

    # Dados de Auditoria
    story.append(Paragraph("7. DADOS DE AUDITORIA", styles['Subtitulo']))
    add_linha("Data de Criação", ordem_servico.created_at.strftime('%d/%m/%Y às %H:%M:%S'))
    if ordem_servico.created_by:
        add_linha("Criado por", ordem_servico.created_by.nome_completo)
    if ordem_servico.updated_at:
        add_linha("Última Atualização", ordem_servico.updated_at.strftime('%d/%m/%Y às %H:%M:%S'))
    if ordem_servico.updated_by:
        add_linha("Atualizado por", ordem_servico.updated_by.nome_completo)
    if hasattr(ordem_servico, 'deleted_at') and ordem_servico.deleted_at:
        add_linha("Data de Exclusão", ordem_servico.deleted_at.strftime('%d/%m/%Y às %H:%M:%S'))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"OS-{ordem_servico.numero_os.replace('/', '_')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def gerar_pdf_listagem_ordens_servico(ocorrencia, request):
    """Gera PDF com todas as ordens de serviço de uma ocorrência"""
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
    styles.add(ParagraphStyle(name='OrdemItem', parent=styles['Normal'], leading=14, spaceAfter=4, leftIndent=20))

    story = []
    
    def add_linha(chave, valor):
        if valor not in [None, '']:
            p_text = f"<b>{chave}:</b> {str(valor)}"
            story.append(Paragraph(p_text, styles['NormalCompacto']))

    def add_paragrafo(texto):
        if texto:
            story.append(Paragraph(texto, styles['NormalCompacto']))

    # --- MONTAGEM DO PDF ---
    story.append(Paragraph("RELATÓRIO DE ORDENS DE SERVIÇO", styles['Titulo']))
    
    # Dados da Ocorrência
    story.append(Paragraph("DADOS DA OCORRÊNCIA", styles['Subtitulo']))
    add_linha("Número da Ocorrência", ocorrencia.numero_ocorrencia)
    if hasattr(ocorrencia, 'status'):
        add_linha("Status", ocorrencia.get_status_display())
    if ocorrencia.servico_pericial:
        add_linha("Serviço Pericial", ocorrencia.servico_pericial.nome)
    if ocorrencia.perito_atribuido:
        add_linha("Perito Atribuído", ocorrencia.perito_atribuido.nome_completo)

    # Lista de Ordens de Serviço
    ordens_servico = ocorrencia.ordens_servico.filter(deleted_at__isnull=True).order_by('created_at')
    
    story.append(Paragraph("ORDENS DE SERVIÇO EMITIDAS", styles['Subtitulo']))
    
    if ordens_servico.exists():
        for i, os in enumerate(ordens_servico, 1):
            story.append(Paragraph(f"<b>{i}. Ordem de Serviço {os.numero_os}</b>", styles['Subtitulo']))
            
            # Dados da OS
            data_emissao_os = os.created_at.strftime('%d/%m/%Y às %H:%M:%S')
            emissor = os.created_by.nome_completo if os.created_by else "Sistema"
            story.append(Paragraph(f"<b>Data de Emissão:</b> {data_emissao_os}", styles['OrdemItem']))
            story.append(Paragraph(f"<b>Emitida por:</b> {emissor}", styles['OrdemItem']))
            story.append(Paragraph(f"<b>Status:</b> {os.get_status_display()}", styles['OrdemItem']))
            story.append(Paragraph(f"<b>Prazo:</b> {os.prazo_dias} dias", styles['OrdemItem']))
            
            if os.ciente_por:
                story.append(Paragraph(f"<b>Ciência:</b> {os.ciente_por.nome_completo} em {os.data_ciencia.strftime('%d/%m/%Y às %H:%M')}", styles['OrdemItem']))
            else:
                story.append(Paragraph("<b>Ciência:</b> Aguardando", styles['OrdemItem']))
            
            if os.data_conclusao:
                story.append(Paragraph(f"<b>Conclusão:</b> {os.data_conclusao.strftime('%d/%m/%Y às %H:%M')}", styles['OrdemItem']))
            
            # Documentos de referência
            if os.numero_documento_referencia or os.processo_sei_referencia or os.processo_judicial_referencia:
                story.append(Paragraph("<b>Referências:</b>", styles['OrdemItem']))
                if os.numero_documento_referencia:
                    tipo_doc = os.tipo_documento_referencia.nome if os.tipo_documento_referencia else "Documento"
                    story.append(Paragraph(f"• {tipo_doc}: {os.numero_documento_referencia}", styles['OrdemItem']))
                if os.processo_sei_referencia:
                    story.append(Paragraph(f"• Processo SEI: {os.processo_sei_referencia}", styles['OrdemItem']))
                if os.processo_judicial_referencia:
                    story.append(Paragraph(f"• Processo Judicial: {os.processo_judicial_referencia}", styles['OrdemItem']))
            
            story.append(Spacer(1, 0.3*cm))
    else:
        add_paragrafo("Nenhuma ordem de serviço emitida para esta ocorrência.")

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"ORDENS-{ocorrencia.numero_ocorrencia.replace('/', '_')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def gerar_pdf_oficial_ordem_servico(ordem_servico, request):
    """
    Gera PDF oficial da Ordem de Serviço para impressão/assinatura
    Formato mais formal, como documento oficial
    """
    buffer = io.BytesIO()
    
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.line(doc.leftMargin, doc.bottomMargin - 0.5*cm, doc.width + doc.leftMargin, doc.bottomMargin - 0.5*cm)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1*cm, f"Ordem de Serviço {ordem_servico.numero_os}")
        canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 1*cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=3*cm)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TituloOficial', fontSize=16, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=20))
    styles.add(ParagraphStyle(name='NumeroOS', fontSize=12, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=15))
    styles.add(ParagraphStyle(name='CampoOficial', fontSize=10, fontName='Helvetica', leading=16, spaceAfter=8))
    styles.add(ParagraphStyle(name='TextoPadrao', fontSize=10, fontName='Helvetica', leading=16, spaceAfter=12, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='Assinatura', fontSize=10, fontName='Helvetica', leading=16, spaceAfter=8, alignment=TA_CENTER))

    story = []

    # Cabeçalho oficial
    story.append(Paragraph("POLÍCIA CIVIL DO ESTADO DE RORAIMA", styles['TituloOficial']))
    story.append(Paragraph("INSTITUTO DE CRIMINALÍSTICA", styles['TituloOficial']))
    story.append(Paragraph("ORDEM DE SERVIÇO", styles['TituloOficial']))
    story.append(Paragraph(f"Nº {ordem_servico.numero_os}", styles['NumeroOS']))
    story.append(Paragraph(f"Ocorrência: {ordem_servico.ocorrencia.numero_ocorrencia}", styles['NumeroOS']))
    
    story.append(Spacer(1, 1*cm))

    # Dados principais
    if ordem_servico.unidade_demandante:
        story.append(Paragraph(f"<b>UNIDADE DEMANDANTE:</b> {ordem_servico.unidade_demandante.nome}", styles['CampoOficial']))
    
    if ordem_servico.autoridade_demandante:
        autoridade_texto = f"{ordem_servico.autoridade_demandante.nome}"
        if ordem_servico.autoridade_demandante.cargo:
            autoridade_texto += f" - {ordem_servico.autoridade_demandante.cargo.nome}"
        story.append(Paragraph(f"<b>AUTORIDADE DEMANDANTE:</b> {autoridade_texto}", styles['CampoOficial']))
    
    if ordem_servico.ocorrencia.perito_atribuido:
        story.append(Paragraph(f"<b>PERITO DESIGNADO:</b> {ordem_servico.ocorrencia.perito_atribuido.nome_completo}", styles['CampoOficial']))
    
    story.append(Paragraph(f"<b>PRAZO PARA CONCLUSÃO:</b> {ordem_servico.prazo_dias} dias", styles['CampoOficial']))

    # Documentos de referência
    if (ordem_servico.tipo_documento_referencia or 
        ordem_servico.numero_documento_referencia or 
        ordem_servico.processo_sei_referencia or 
        ordem_servico.processo_judicial_referencia):
        
        story.append(Spacer(1, 0.5*cm))
        story.append(Paragraph("<b>DOCUMENTOS DE REFERÊNCIA:</b>", styles['CampoOficial']))
        
        if ordem_servico.numero_documento_referencia:
            tipo_doc = ordem_servico.tipo_documento_referencia.nome if ordem_servico.tipo_documento_referencia else "Documento"
            story.append(Paragraph(f"• {tipo_doc}: {ordem_servico.numero_documento_referencia}", styles['CampoOficial']))
        
        if ordem_servico.processo_sei_referencia:
            story.append(Paragraph(f"• Processo SEI: {ordem_servico.processo_sei_referencia}", styles['CampoOficial']))
        
        if ordem_servico.processo_judicial_referencia:
            story.append(Paragraph(f"• Processo Judicial: {ordem_servico.processo_judicial_referencia}", styles['CampoOficial']))

    # Texto padrão
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(ordem_servico.texto_padrao, styles['TextoPadrao']))

    # Dados de emissão
    story.append(Spacer(1, 1.5*cm))
    data_emissao = ordem_servico.created_at.strftime('%d de %B de %Y')
    story.append(Paragraph(f"Emitida em {data_emissao}", styles['CampoOficial']))

    # Espaço para assinaturas
    story.append(Spacer(1, 2*cm))
    
    story.append(Paragraph("_" * 50, styles['Assinatura']))
    emissor = ordem_servico.created_by.nome_completo if ordem_servico.created_by else "Sistema"
    story.append(Paragraph(f"{emissor}", styles['Assinatura']))
    story.append(Paragraph("Diretor/Autoridade Competente", styles['Assinatura']))

    # Espaço para ciência do perito
    if ordem_servico.ocorrencia.perito_atribuido:
        story.append(Spacer(1, 1.5*cm))
        story.append(Paragraph("CIÊNCIA DO PERITO:", styles['CampoOficial']))
        
        if ordem_servico.ciente_por:
            story.append(Paragraph(f"Registrada em {ordem_servico.data_ciencia.strftime('%d/%m/%Y às %H:%M')}", styles['CampoOficial']))
        else:
            story.append(Spacer(1, 1*cm))
            story.append(Paragraph("_" * 50, styles['Assinatura']))
            story.append(Paragraph(f"{ordem_servico.ocorrencia.perito_atribuido.nome_completo}", styles['Assinatura']))
            story.append(Paragraph("Perito Designado", styles['Assinatura']))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"OS_OFICIAL-{ordem_servico.numero_os.replace('/', '_')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)s