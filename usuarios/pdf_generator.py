# usuarios/pdf_generator.py

import io
from django.http import FileResponse
from django.utils import timezone
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm

# IMPORT ADICIONADO PARA GARANTIR O ACESSO AOS CHOICES DE STATUS E PERFIL
from .models import User


def gerar_pdf_usuario(usuario, request):
    buffer = io.BytesIO()

    usuario_emissor = request.user.nome_completo if request.user.is_authenticated else "Sistema"
    data_emissao = timezone.now().strftime('%d/%m/%Y às %H:%M:%S')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.line(doc.leftMargin, doc.bottomMargin - 0.5 * cm, doc.width + doc.leftMargin, doc.bottomMargin - 0.5 * cm)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1 * cm, f"Relatório emitido por: {usuario_emissor}")
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1.5 * cm, f"Data da Emissão: {data_emissao}")
        canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 1.5 * cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1.5 * cm,
                            bottomMargin=2.5 * cm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Titulo', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name='Subtitulo', fontSize=12, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=2,
                              textColor=colors.HexColor('#2c3e50')))
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
    story.append(Paragraph("RELATÓRIO DE USUÁRIO", styles['Titulo']))
    add_linha("ID do Usuário", f"#{usuario.id}")
    add_linha("Nome Completo", usuario.nome_completo)
    add_linha("Email", usuario.email)
    add_linha("Status", usuario.get_status_display())
    if usuario.perfil:
        add_linha("Perfil", usuario.get_perfil_display())

    story.append(Paragraph("1. DADOS PESSOAIS", styles['Subtitulo']))
    add_linha("CPF", usuario.cpf)
    if usuario.data_nascimento:
        add_linha("Data de Nascimento", usuario.data_nascimento.strftime('%d/%m/%Y'))
    if usuario.telefone_celular:
        add_linha("Telefone Celular", usuario.telefone_celular)

    story.append(Paragraph("2. DADOS PROFISSIONAIS", styles['Subtitulo']))
    if usuario.perfil:
        add_linha("Perfil", usuario.get_perfil_display())
    add_linha("Status no Sistema", usuario.get_status_display())
    if usuario.is_staff:
        add_linha("Acesso Administrativo", "Sim")
    if usuario.is_superuser:
        add_linha("Super Usuário", "Sim")

    story.append(Paragraph("3. SERVIÇOS PERICIAIS", styles['Subtitulo']))
    servicos = usuario.servicos_periciais.all()
    if servicos:
        for servico in servicos:
            add_linha("Serviço", f"{servico.sigla} - {servico.nome}")
    else:
        add_paragrafo("Nenhum serviço pericial atribuído.")

    story.append(Paragraph("4. DADOS DE AUDITORIA", styles['Subtitulo']))
    add_linha("Data de Criação", usuario.created_at.strftime('%d/%m/%Y às %H:%M:%S'))
    if usuario.created_by:
        add_linha("Criado por", usuario.created_by.nome_completo)
    if usuario.updated_at:
        add_linha("Última Atualização", usuario.updated_at.strftime('%d/%m/%Y às %H:%M:%S'))
    if usuario.updated_by:
        add_linha("Atualizado por", usuario.updated_by.nome_completo)
    if hasattr(usuario, 'deleted_at') and usuario.deleted_at:
        add_linha("Data de Exclusão", usuario.deleted_at.strftime('%d/%m/%Y às %H:%M:%S'))
        if usuario.deleted_by:
            add_linha("Excluído por", usuario.deleted_by.nome_completo)

    doc.build(story, onFirstPage=footer, onLaterPages=footer)

    buffer.seek(0)
    filename = f"USUARIO-{usuario.id}-{usuario.nome_completo.replace(' ', '_')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def gerar_pdf_listagem_usuarios(request):
    """Gera PDF com listagem de usuários"""
    buffer = io.BytesIO()

    usuario_emissor = request.user.nome_completo if request.user.is_authenticated else "Sistema"
    data_emissao = timezone.now().strftime('%d/%m/%Y às %H:%M:%S')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.line(doc.leftMargin, doc.bottomMargin - 0.5 * cm, doc.width + doc.leftMargin, doc.bottomMargin - 0.5 * cm)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1 * cm, f"Relatório emitido por: {usuario_emissor}")
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1.5 * cm, f"Data da Emissão: {data_emissao}")
        canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 1.5 * cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1.5 * cm,
                            bottomMargin=2.5 * cm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Titulo', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name='Subtitulo', fontSize=12, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=2,
                              textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='NormalCompacto', parent=styles['Normal'], leading=14, spaceAfter=2))
    styles.add(ParagraphStyle(name='UsuarioItem', parent=styles['Normal'], leading=14, spaceAfter=4, leftIndent=20))

    story = []

    def add_linha(chave, valor):
        if valor not in [None, '']:
            p_text = f"<b>{chave}:</b> {str(valor)}"
            story.append(Paragraph(p_text, styles['NormalCompacto']))

    # --- MONTAGEM DO PDF ---
    story.append(Paragraph("RELATÓRIO DE USUÁRIOS", styles['Titulo']))

    usuarios = User.objects.filter(is_superuser=False, deleted_at__isnull=True).order_by('nome_completo')

    story.append(Paragraph("USUÁRIOS CADASTRADOS", styles['Subtitulo']))
    add_linha("Total de Usuários", usuarios.count())

    story.append(Paragraph("ESTATÍSTICAS POR STATUS", styles['Subtitulo']))
    for status_code, status_display in User.Status.choices:
        count = usuarios.filter(status=status_code).count()
        add_linha(status_display, count)

    story.append(Paragraph("ESTATÍSTICAS POR PERFIL", styles['Subtitulo']))
    for perfil_code, perfil_display in User.Perfil.choices:
        count = usuarios.filter(perfil=perfil_code).count()
        if count > 0:
            add_linha(perfil_display, count)

    story.append(Spacer(1, 0.5 * cm))

    if usuarios.exists():
        story.append(Paragraph("DETALHAMENTO DOS USUÁRIOS", styles['Subtitulo']))

        for i, user in enumerate(usuarios, 1):
            story.append(Paragraph(f"<b>{i}. {user.nome_completo}</b>", styles['Subtitulo']))

            story.append(Paragraph(f"<b>Email:</b> {user.email}", styles['UsuarioItem']))
            story.append(Paragraph(f"<b>CPF:</b> {user.cpf}", styles['UsuarioItem']))
            story.append(Paragraph(f"<b>Status:</b> {user.get_status_display()}", styles['UsuarioItem']))
            if user.perfil:
                story.append(Paragraph(f"<b>Perfil:</b> {user.get_perfil_display()}", styles['UsuarioItem']))
            if user.telefone_celular:
                story.append(Paragraph(f"<b>Telefone:</b> {user.telefone_celular}", styles['UsuarioItem']))
            data_cadastro = user.created_at.strftime('%d/%m/%Y')
            story.append(Paragraph(f"<b>Cadastrado em:</b> {data_cadastro}", styles['UsuarioItem']))
            servicos = user.servicos_periciais.all()
            if servicos:
                servicos_nomes = [f"{s.sigla}" for s in servicos]
                story.append(Paragraph(f"<b>Serviços:</b> {', '.join(servicos_nomes)}", styles['UsuarioItem']))
            story.append(Spacer(1, 0.3 * cm))
    else:
        story.append(Paragraph("Nenhum usuário encontrado.", styles['NormalCompacto']))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)

    buffer.seek(0)
    filename = f"USUARIOS-{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)


def gerar_pdf_usuarios_por_perfil(perfil, request):
    """Gera PDF com usuários filtrados por perfil"""
    buffer = io.BytesIO()

    usuario_emissor = request.user.nome_completo if request.user.is_authenticated else "Sistema"
    data_emissao = timezone.now().strftime('%d/%m/%Y às %H:%M:%S')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.line(doc.leftMargin, doc.bottomMargin - 0.5 * cm, doc.width + doc.leftMargin, doc.bottomMargin - 0.5 * cm)
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1 * cm, f"Relatório emitido por: {usuario_emissor}")
        canvas.drawString(doc.leftMargin, doc.bottomMargin - 1.5 * cm, f"Data da Emissão: {data_emissao}")
        canvas.drawRightString(doc.width + doc.leftMargin, doc.bottomMargin - 1.5 * cm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1.5 * cm,
                            bottomMargin=2.5 * cm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Titulo', fontSize=14, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=10))
    styles.add(ParagraphStyle(name='Subtitulo', fontSize=12, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=2,
                              textColor=colors.HexColor('#2c3e50')))
    styles.add(ParagraphStyle(name='NormalCompacto', parent=styles['Normal'], leading=14, spaceAfter=2))
    styles.add(ParagraphStyle(name='UsuarioItem', parent=styles['Normal'], leading=14, spaceAfter=4, leftIndent=20))

    story = []

    def add_linha(chave, valor):
        if valor not in [None, '']:
            p_text = f"<b>{chave}:</b> {str(valor)}"
            story.append(Paragraph(p_text, styles['NormalCompacto']))

    perfil_display = dict(User.Perfil.choices).get(perfil, perfil)

    # --- MONTAGEM DO PDF ---
    story.append(Paragraph(f"USUÁRIOS - {perfil_display.upper()}", styles['Titulo']))

    usuarios = User.objects.filter(
        perfil=perfil,
        is_superuser=False,
        deleted_at__isnull=True
    ).order_by('nome_completo')

    add_linha("Perfil", perfil_display)
    add_linha("Total de Usuários", usuarios.count())

    story.append(Paragraph("ESTATÍSTICAS POR STATUS", styles['Subtitulo']))
    for status_code, status_display in User.Status.choices:
        count = usuarios.filter(status=status_code).count()
        if count > 0:
            add_linha(status_display, count)

    story.append(Spacer(1, 0.5 * cm))

    if usuarios.exists():
        story.append(Paragraph("USUÁRIOS ENCONTRADOS", styles['Subtitulo']))

        for i, user in enumerate(usuarios, 1):
            story.append(Paragraph(f"<b>{i}. {user.nome_completo}</b>", styles['Subtitulo']))

            story.append(Paragraph(f"<b>Email:</b> {user.email}", styles['UsuarioItem']))
            story.append(Paragraph(f"<b>CPF:</b> {user.cpf}", styles['UsuarioItem']))
            story.append(Paragraph(f"<b>Status:</b> {user.get_status_display()}", styles['UsuarioItem']))
            if user.telefone_celular:
                story.append(Paragraph(f"<b>Telefone:</b> {user.telefone_celular}", styles['UsuarioItem']))
            data_cadastro = user.created_at.strftime('%d/%m/%Y')
            story.append(Paragraph(f"<b>Cadastrado em:</b> {data_cadastro}", styles['UsuarioItem']))
            servicos = user.servicos_periciais.all()
            if servicos:
                servicos_nomes = [f"{s.sigla} - {s.nome}" for s in servicos]
                story.append(Paragraph(f"<b>Serviços:</b>", styles['UsuarioItem']))
                for servico_nome in servicos_nomes:
                    story.append(Paragraph(f"• {servico_nome}", styles['UsuarioItem']))
            story.append(Spacer(1, 0.3 * cm))
    else:
        story.append(Paragraph(f"Nenhum usuário encontrado para o perfil {perfil_display}.", styles['NormalCompacto']))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)

    buffer.seek(0)
    filename = f"USUARIOS_{perfil}-{timezone.now().strftime('%Y%m%d_%H%M')}.pdf"
    return FileResponse(buffer, as_attachment=True, filename=filename)