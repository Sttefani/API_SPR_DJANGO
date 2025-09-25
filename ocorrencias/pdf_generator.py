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