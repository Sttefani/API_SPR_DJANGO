import io
from django.http import FileResponse
from django.utils import timezone
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

# ✅ DICIONÁRIO DE MESES EM PORTUGUÊS
MESES_PT = {
    1: 'janeiro', 2: 'fevereiro', 3: 'março', 4: 'abril',
    5: 'maio', 6: 'junho', 7: 'julho', 8: 'agosto',
    9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'
}

def formatar_data_portugues(data):
    """Formata data em português: 10 de outubro de 2025"""
    dia = data.day
    mes = MESES_PT[data.month]
    ano = data.year
    return f"{dia} de {mes} de {ano}"


# ✅ NOVA FUNÇÃO: GERAR BADGE DE STATUS
def gerar_badge_status(status, get_status_display):
    """
    Cria um badge colorido para o status da OS.
    Retorna uma Table do ReportLab com fundo colorido.
    """
    # Mapeamento de cores por status
    cores_status = {
        'CONCLUIDA': colors.HexColor('#10b981'),      # Verde
        'EM_ANDAMENTO': colors.HexColor('#3b82f6'),   # Azul
        'ABERTA': colors.HexColor('#f59e0b'),         # Amarelo/Laranja
        'AGUARDANDO_CIENCIA': colors.HexColor('#eab308'),  # Amarelo
    }
    
    # Detecta se está vencida (status genérico)
    texto_status = get_status_display
    cor_fundo = cores_status.get(status, colors.HexColor('#6b7280'))  # Cinza padrão
    
    # Badge em formato de tabela
    badge_data = [[texto_status]]
    badge_table = Table(badge_data, colWidths=[4*cm])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cor_fundo),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ROUNDEDCORNERS', [5, 5, 5, 5]),
    ]))
    
    return badge_table


# ✅ NOVA FUNÇÃO: SEÇÃO DE TRAMITAÇÃO
def adicionar_secao_tramitacao(story, ordem_servico, styles):
    """
    Adiciona a seção de tramitação com timeline completa:
    - Emissão
    - Ciência
    - Conclusão (se houver)
    """
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("📅 TRAMITAÇÃO", styles['Subtitulo']))
    
    # Dados de emissão
    data_emissao = ordem_servico.created_at.strftime('%d/%m/%Y às %H:%M')
    emissor = ordem_servico.created_by.nome_completo if ordem_servico.created_by else "Sistema"
    
    story.append(Paragraph(
        f"<b>• Emitida em:</b> {data_emissao}",
        styles['NormalCompacto']
    ))
    story.append(Paragraph(
        f"  <b>Por:</b> {emissor}",
        styles['NormalCompacto']
    ))
    story.append(Spacer(1, 0.2*cm))
    
    # Dados de ciência
    if ordem_servico.ciente_por:
        data_ciencia = ordem_servico.data_ciencia.strftime('%d/%m/%Y às %H:%M')
        perito_ciente = ordem_servico.ciente_por.nome_completo
        
        story.append(Paragraph(
            f"<b>• Ciência em:</b> {data_ciencia}",
            styles['NormalCompacto']
        ))
        story.append(Paragraph(
            f"  <b>Por:</b> {perito_ciente}",
            styles['NormalCompacto']
        ))
        story.append(Spacer(1, 0.2*cm))
    else:
        story.append(Paragraph(
            "<b>• Ciência:</b> Aguardando",
            styles['NormalCompacto']
        ))
        story.append(Spacer(1, 0.2*cm))
    
    # Dados de conclusão
    if ordem_servico.data_conclusao:
        data_conclusao = ordem_servico.data_conclusao.strftime('%d/%m/%Y às %H:%M')
        
        # ✅ USA O CAMPO ESPECÍFICO concluida_por
        concluido_por = "Sistema"
        if ordem_servico.concluida_por:
            concluido_por = ordem_servico.concluida_por.nome_completo
        
        story.append(Paragraph(
            f"<b>• Concluída em:</b> {data_conclusao}",
            styles['NormalCompacto']
        ))
        story.append(Paragraph(
            f"  <b>Por:</b> {concluido_por}",
            styles['NormalCompacto']
        ))
    
    story.append(Spacer(1, 0.3*cm))


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
    
    # ✅ BADGE DE STATUS
    story.append(Spacer(1, 0.3*cm))
    badge = gerar_badge_status(ordem_servico.status, ordem_servico.get_status_display())
    story.append(badge)
    
    # ✅ SEÇÃO DE TRAMITAÇÃO
    adicionar_secao_tramitacao(story, ordem_servico, styles)

    # Dados gerais
    story.append(Paragraph("1. DADOS DA ORDEM DE SERVIÇO", styles['Subtitulo']))
    add_linha("Prazo para Conclusão", f"{ordem_servico.prazo_dias} dias")

    # Dados da Ocorrência relacionada
    story.append(Paragraph("2. DADOS DA OCORRÊNCIA", styles['Subtitulo']))
    if ordem_servico.ocorrencia:
        if hasattr(ordem_servico.ocorrencia, 'status'):
            add_linha("Status da Ocorrência", ordem_servico.ocorrencia.get_status_display())
        if ordem_servico.ocorrencia.perito_atribuido:
            add_linha("Perito Atribuído", ordem_servico.ocorrencia.perito_atribuido.nome_completo)

    # Dados Espelhados (Snapshot da ocorrência)
    story.append(Paragraph("3. DADOS DEMANDANTES", styles['Subtitulo']))
    if ordem_servico.unidade_demandante:
        add_linha("Unidade Demandante", ordem_servico.unidade_demandante.nome)
    if ordem_servico.autoridade_demandante:
        add_linha("Autoridade Demandante", f"{ordem_servico.autoridade_demandante.nome} ({ordem_servico.autoridade_demandante.cargo.nome})" if ordem_servico.autoridade_demandante.cargo else ordem_servico.autoridade_demandante.nome)
    if ordem_servico.procedimento:
        add_linha("Procedimento", str(ordem_servico.procedimento))

    # Documentos de Referência
    story.append(Paragraph("4. DOCUMENTOS DE REFERÊNCIA", styles['Subtitulo']))
    if ordem_servico.tipo_documento_referencia:
        add_linha("Tipo de Documento", ordem_servico.tipo_documento_referencia.nome)
    if ordem_servico.numero_documento_referencia:
        add_linha("Número do Documento", ordem_servico.numero_documento_referencia)
    if ordem_servico.processo_sei_referencia:
        add_linha("Processo SEI", ordem_servico.processo_sei_referencia)
    if ordem_servico.processo_judicial_referencia:
        add_linha("Processo Judicial", ordem_servico.processo_judicial_referencia)

    # Texto Padrão
    story.append(Paragraph("5. DETERMINAÇÃO", styles['Subtitulo']))
    add_paragrafo(ordem_servico.texto_padrao)

    # Dados de Auditoria
    story.append(Paragraph("6. DADOS DE AUDITORIA", styles['Subtitulo']))
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
            
            # Badge de status
            badge = gerar_badge_status(os.status, os.get_status_display())
            story.append(badge)
            story.append(Spacer(1, 0.2*cm))
            
            # Dados da OS
            data_emissao_os = os.created_at.strftime('%d/%m/%Y às %H:%M:%S')
            emissor = os.created_by.nome_completo if os.created_by else "Sistema"
            story.append(Paragraph(f"<b>Data de Emissão:</b> {data_emissao_os}", styles['OrdemItem']))
            story.append(Paragraph(f"<b>Emitida por:</b> {emissor}", styles['OrdemItem']))
            story.append(Paragraph(f"<b>Prazo:</b> {os.prazo_dias} dias", styles['OrdemItem']))
            
            if os.ciente_por:
                story.append(Paragraph(f"<b>Ciência:</b> {os.ciente_por.nome_completo} em {os.data_ciencia.strftime('%d/%m/%Y às %H:%M')}", styles['OrdemItem']))
            else:
                story.append(Paragraph("<b>Ciência:</b> Aguardando", styles['OrdemItem']))
            
            if os.data_conclusao:
                concluido_por = os.concluida_por.nome_completo if os.concluida_por else "Sistema"
                story.append(Paragraph(f"<b>Conclusão:</b> {os.data_conclusao.strftime('%d/%m/%Y às %H:%M')} por {concluido_por}", styles['OrdemItem']))
            
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

    # MARGENS REDUZIDAS
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5*cm, leftMargin=1.5*cm, topMargin=1.2*cm, bottomMargin=2.5*cm)
    
    styles = getSampleStyleSheet()
    # ESTILOS COMPACTADOS
    styles.add(ParagraphStyle(name='TituloOficial', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=8))
    styles.add(ParagraphStyle(name='NumeroOS', fontSize=11, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=8))
    styles.add(ParagraphStyle(name='CampoOficial', fontSize=9, fontName='Helvetica', leading=12, spaceAfter=4))
    styles.add(ParagraphStyle(name='TextoPadrao', fontSize=9, fontName='Helvetica', leading=12, spaceAfter=6, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='Assinatura', fontSize=9, fontName='Helvetica', leading=12, spaceAfter=4, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name='Subtitulo', fontSize=10, fontName='Helvetica-Bold', spaceAfter=4))
    styles.add(ParagraphStyle(name='NormalCompacto', fontSize=9, leading=12, spaceAfter=2))

    story = []

    # Cabeçalho oficial
    story.append(Paragraph("POLÍCIA CIVIL DO ESTADO DE RORAIMA", styles['TituloOficial']))
    story.append(Paragraph("INSTITUTO DE CRIMINALÍSTICA", styles['TituloOficial']))
    story.append(Paragraph("ORDEM DE SERVIÇO", styles['TituloOficial']))
    story.append(Paragraph(f"Nº {ordem_servico.numero_os}", styles['NumeroOS']))
    story.append(Paragraph(f"Ocorrência: {ordem_servico.ocorrencia.numero_ocorrencia}", styles['NumeroOS']))
    
    # ✅ BADGE DE STATUS
    story.append(Spacer(1, 0.2*cm))
    badge = gerar_badge_status(ordem_servico.status, ordem_servico.get_status_display())
    story.append(badge)
    
    # ✅ SEÇÃO DE TRAMITAÇÃO
    adicionar_secao_tramitacao(story, ordem_servico, styles)

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
        
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph("<b>DOCUMENTOS DE REFERÊNCIA:</b>", styles['CampoOficial']))
        
        if ordem_servico.numero_documento_referencia:
            tipo_doc = ordem_servico.tipo_documento_referencia.nome if ordem_servico.tipo_documento_referencia else "Documento"
            story.append(Paragraph(f"• {tipo_doc}: {ordem_servico.numero_documento_referencia}", styles['CampoOficial']))
        
        if ordem_servico.processo_sei_referencia:
            story.append(Paragraph(f"• Processo SEI: {ordem_servico.processo_sei_referencia}", styles['CampoOficial']))
        
        if ordem_servico.processo_judicial_referencia:
            story.append(Paragraph(f"• Processo Judicial: {ordem_servico.processo_judicial_referencia}", styles['CampoOficial']))

    # Texto padrão
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(ordem_servico.texto_padrao, styles['TextoPadrao']))

    # ✅ DADOS DE EMISSÃO EM PORTUGUÊS
    story.append(Spacer(1, 0.5*cm))
    data_emissao = formatar_data_portugues(ordem_servico.created_at)
    story.append(Paragraph(f"Emitida em {data_emissao}", styles['CampoOficial']))

    # Espaço para assinaturas
    story.append(Spacer(1, 1*cm))

    story.append(Paragraph("_" * 50, styles['Assinatura']))

    # Usa "ordenada_por" (quem ordenou = diretor/perito)
    if ordem_servico.ordenada_por:
        diretor = ordem_servico.ordenada_por.nome_completo
        
        # Pega o cargo do perito se tiver
        cargo_info = ""
        if hasattr(ordem_servico.ordenada_por, 'cargo') and ordem_servico.ordenada_por.cargo:
            cargo_info = f"<br/>{ordem_servico.ordenada_por.cargo.nome}"
        
        story.append(Paragraph(f"{diretor}{cargo_info}", styles['Assinatura']))
    else:
        story.append(Paragraph("Diretor não informado", styles['Assinatura']))

    story.append(Paragraph("Diretor/Autoridade Competente", styles['Assinatura']))

    # Espaço para ciência do perito
    if ordem_servico.ocorrencia.perito_atribuido:
        story.append(Spacer(1, 0.8*cm))
        story.append(Paragraph("CIÊNCIA DO PERITO:", styles['CampoOficial']))
        
        if ordem_servico.ciente_por:
            story.append(Paragraph(f"Registrada em {ordem_servico.data_ciencia.strftime('%d/%m/%Y às %H:%M')}", styles['CampoOficial']))
        else:
            story.append(Spacer(1, 0.6*cm))
            story.append(Paragraph("_" * 50, styles['Assinatura']))
            story.append(Paragraph(f"{ordem_servico.ocorrencia.perito_atribuido.nome_completo}", styles['Assinatura']))
            story.append(Paragraph("Perito Designado", styles['Assinatura']))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"OS_OFICIAL-{ordem_servico.numero_os.replace('/', '_')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)

def gerar_pdf_relatorios_gerenciais(dados_relatorio, filtros_aplicados):
    """
    Gera PDF dos relatórios gerenciais de Ordens de Serviço.
    
    Args:
        dados_relatorio: Dict com os dados do relatório
        filtros_aplicados: Dict com os filtros que foram aplicados
    """
    buffer = io.BytesIO()
    
    data_emissao = timezone.now().strftime('%d/%m/%Y às %H:%M:%S')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.line(doc.leftMargin, doc.bottomMargin - 0.5*cm, doc.width + doc.leftMargin, doc.bottomMargin - 0.5*cm)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1*cm, f"Relatório Gerencial - Ordens de Serviço")
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Emitido em: {data_emissao}")
        canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 1.5*cm, f"Página {doc.page}")
        canvas.restoreState()

    # Documento em paisagem para caber mais informações
    from reportlab.lib.pagesizes import landscape
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(A4), 
        rightMargin=1*cm, 
        leftMargin=1*cm, 
        topMargin=1.5*cm, 
        bottomMargin=2.5*cm
    )
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TituloRelatorio', fontSize=16, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=12, textColor=colors.HexColor('#DAA520')))
    styles.add(ParagraphStyle(name='SubtituloRelatorio', fontSize=12, fontName='Helvetica-Bold', spaceBefore=10, spaceAfter=6, textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='NormalCompacto', fontSize=9, leading=12, spaceAfter=2))
    
    story = []
    
    # Título
    story.append(Paragraph("RELATÓRIO GERENCIAL - ORDENS DE SERVIÇO", styles['TituloRelatorio']))
    story.append(Spacer(1, 0.3*cm))
    
    # Filtros aplicados
    if filtros_aplicados:
        story.append(Paragraph("FILTROS APLICADOS:", styles['SubtituloRelatorio']))
        filtros_texto = []
        if filtros_aplicados.get('data_inicio'):
            filtros_texto.append(f"Data Início: {filtros_aplicados['data_inicio']}")
        if filtros_aplicados.get('data_fim'):
            filtros_texto.append(f"Data Fim: {filtros_aplicados['data_fim']}")
        if filtros_aplicados.get('perito_nome'):
            filtros_texto.append(f"Perito: {filtros_aplicados['perito_nome']}")
        if filtros_aplicados.get('unidade_nome'):
            filtros_texto.append(f"Unidade: {filtros_aplicados['unidade_nome']}")
        if filtros_aplicados.get('servico_nome'):
            filtros_texto.append(f"Serviço: {filtros_aplicados['servico_nome']}")
        if filtros_aplicados.get('status'):
            filtros_texto.append(f"Status: {filtros_aplicados['status']}")
        
        if filtros_texto:
            story.append(Paragraph(" | ".join(filtros_texto), styles['NormalCompacto']))
        else:
            story.append(Paragraph("Todos os registros (sem filtros)", styles['NormalCompacto']))
        
        story.append(Spacer(1, 0.5*cm))
    
    # 1. RESUMO GERAL
    resumo = dados_relatorio['resumo_geral']
    story.append(Paragraph("1. RESUMO GERAL", styles['SubtituloRelatorio']))
    
    resumo_data = [
        ['Indicador', 'Quantidade', '%'],
        ['Total Emitidas', str(resumo['total_emitidas']), '100%'],
        ['Aguardando Ciência', str(resumo['aguardando_ciencia']), f"{round(resumo['aguardando_ciencia']/resumo['total_emitidas']*100 if resumo['total_emitidas'] > 0 else 0, 1)}%"],
        ['Abertas', str(resumo['abertas']), f"{round(resumo['abertas']/resumo['total_emitidas']*100 if resumo['total_emitidas'] > 0 else 0, 1)}%"],
        ['Em Andamento', str(resumo['em_andamento']), f"{round(resumo['em_andamento']/resumo['total_emitidas']*100 if resumo['total_emitidas'] > 0 else 0, 1)}%"],
        ['Vencidas', str(resumo['vencidas']), f"{round(resumo['vencidas']/resumo['total_emitidas']*100 if resumo['total_emitidas'] > 0 else 0, 1)}%"],
        ['Concluídas', str(resumo['concluidas']), f"{round(resumo['concluidas']/resumo['total_emitidas']*100 if resumo['total_emitidas'] > 0 else 0, 1)}%"],
    ]
    
    resumo_table = Table(resumo_data, colWidths=[14*cm, 4*cm, 3*cm])
    resumo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DAA520')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    story.append(resumo_table)
    story.append(Spacer(1, 0.8*cm))
    
    # 2. TAXA DE CUMPRIMENTO
    taxa = dados_relatorio['taxa_cumprimento']
    story.append(Paragraph("2. TAXA DE CUMPRIMENTO DE PRAZOS", styles['SubtituloRelatorio']))
    
    taxa_data = [
        ['Indicador', 'Quantidade', 'Percentual'],
        ['Cumpridas no Prazo ✓', str(taxa['cumpridas_no_prazo']), f"{taxa['percentual_no_prazo']}%"],
        ['Cumpridas com Atraso ⚠', str(taxa['cumpridas_com_atraso']), f"{taxa['percentual_com_atraso']}%"],
        ['Total Concluídas', str(taxa['total_concluidas']), '100%'],
    ]
    
    taxa_table = Table(taxa_data, colWidths=[14*cm, 4*cm, 3*cm])
    taxa_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DAA520')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#d4edda')),
        ('BACKGROUND', (0, 2), (0, 2), colors.HexColor('#f8d7da')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    story.append(taxa_table)
    story.append(Spacer(1, 0.8*cm))
    
    # 3. PRAZOS MÉDIOS
    prazos = dados_relatorio['prazos']
    story.append(Paragraph("3. ESTATÍSTICAS DE PRAZOS", styles['SubtituloRelatorio']))
    
    prazos_data = [
        ['Indicador', 'Valor'],
        ['Tempo Médio de Conclusão', f"{prazos['tempo_medio_conclusao_dias']} dias"],
        ['Prazo Médio Concedido', f"{prazos['prazo_medio_concedido']} dias"],
    ]
    
    prazos_table = Table(prazos_data, colWidths=[14*cm, 7*cm])
    prazos_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DAA520')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    story.append(prazos_table)
    story.append(Spacer(1, 0.8*cm))
    
    # 4. PRODUÇÃO POR PERITO (TOP 20)
    if dados_relatorio['producao_por_perito']:
        story.append(Paragraph("4. PRODUÇÃO POR PERITO (TOP 20)", styles['SubtituloRelatorio']))
        
        perito_data = [['Perito', 'Total', 'Concl.', 'No Prazo', 'Atraso', 'Taxa %', 'Andamento', 'Vencidas']]
        
        for item in dados_relatorio['producao_por_perito'][:20]:
            perito_data.append([
                item['perito'][:40],
                str(item['total_emitidas']),
                str(item['concluidas']),
                str(item['cumpridas_no_prazo']),
                str(item['cumpridas_com_atraso']),
                f"{item['taxa_cumprimento_prazo']}%",
                str(item['em_andamento']),
                str(item['vencidas'])
            ])
        
        perito_table = Table(perito_data, colWidths=[10*cm, 2*cm, 2*cm, 2*cm, 2*cm, 2*cm, 2.5*cm, 2*cm])
        perito_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DAA520')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        
        story.append(perito_table)
    
    # Gerar PDF
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    buffer.seek(0)
    filename = f"Relatorio_OS_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)