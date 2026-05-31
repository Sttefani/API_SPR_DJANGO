# custodia/pdf_generator.py
#
# Gera a Ficha de Acompanhamento do Vestígio (cadeia de custódia) e DNA em PDF.
# Design Forense Sóbrio (Monocromático), com Logo da PC e QR Code ajustado.

import io
import os
import qrcode
import qrcode.image.pil

from django.conf import settings
from django.utils import timezone
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable,
)
from reportlab.platypus.flowables import Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm


# ─── Paleta de Cores (Sóbria / Monocromática) ────────────────────────────────

PRETO          = colors.HexColor('#000000')
CINZA_ESCURO   = colors.HexColor('#1e293b')
CINZA_MEDIO    = colors.HexColor('#64748b')
CINZA_CLARO    = colors.HexColor('#f8fafc')
BORDAS         = colors.HexColor('#cbd5e1')
BRANCO         = colors.white


# ─── Utilitários ─────────────────────────────────────────────────────────────

def _vazio(v):
    return '—' if (v is None or str(v).strip() == '') else str(v).strip()


def _formatar_dt(dt):
    if dt is None:
        return '—'
    if hasattr(dt, 'strftime'):
        from django.utils import timezone as tz
        try:
            import zoneinfo
            local = dt.astimezone(zoneinfo.ZoneInfo('America/Boa_Vista'))
        except Exception:
            local = dt
        return local.strftime('%d/%m/%Y  %H:%M')
    return str(dt)


def _gerar_qrcode(url: str) -> RLImage:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return RLImage(buf, width=2.0 * cm, height=2.0 * cm)


def _obter_logo_pc():
    """Tenta carregar o logo da Polícia Civil procurando em locais comuns."""
    locais_possiveis = [
        os.path.join(settings.BASE_DIR, 'assets', 'logo_pc.png'),
        os.path.join(settings.BASE_DIR, 'static', 'img', 'logo_pc.png'),
        os.path.join(settings.BASE_DIR, 'static', 'logo_pc.png'),
    ]
    
    for caminho in locais_possiveis:
        if os.path.exists(caminho):
            return RLImage(caminho, width=1.6 * cm, height=1.6 * cm)
            
    print("⚠️ AVISO: Logo não encontrado no servidor. Coloque 'logo_pc.png' na pasta 'assets' na raiz do projeto Django.")
    return '' 


# ─── Estilos (Hierarquia Visual Sóbria) ──────────────────────────────────────

def _estilos():
    base = getSampleStyleSheet()
    return {
        'titulo_org': ParagraphStyle(
            'titulo_org', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=10,
            textColor=PRETO, alignment=TA_CENTER, leading=14,
        ),
        'titulo_doc': ParagraphStyle(
            'titulo_doc', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=14,
            textColor=PRETO, alignment=TA_CENTER, spaceAfter=2,
        ),
        'subtitulo': ParagraphStyle(
            'subtitulo', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=10,
            textColor=PRETO, alignment=TA_LEFT,
        ),
        'label': ParagraphStyle(
            'label', parent=base['Normal'],
            fontName='Helvetica', fontSize=8,
            textColor=CINZA_MEDIO, leading=10,
        ),
        'valor': ParagraphStyle(
            'valor', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=9,
            textColor=PRETO, leading=12,
        ),
        'mov_data': ParagraphStyle(
            'mov_data', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=8,
            textColor=PRETO,
        ),
        'mov_texto': ParagraphStyle(
            'mov_texto', parent=base['Normal'],
            fontName='Helvetica', fontSize=8,
            textColor=PRETO, leading=11,
        ),
        'legal': ParagraphStyle(
            'legal', parent=base['Normal'],
            fontName='Helvetica', fontSize=7,
            textColor=CINZA_MEDIO, alignment=TA_CENTER, leading=10,
        ),
    }


# ─── Gerador de Cabeçalho e Seção Padronizados ───────────────────────────────

def _construir_cabecalho(story, st, titulo_principal, sub_legal):
    logo = _obter_logo_pc()
    texto_cabecalho = Paragraph(
        'POLÍCIA CIVIL DO ESTADO DE RORAIMA<br/>'
        '<font size="8" color="#000000">INSTITUTO DE CRIMINALÍSTICA — SISTEMA DE GESTÃO PERICIAL</font>',
        st['titulo_org']
    )
    
    if logo:
        header_data = [[logo, texto_cabecalho, '']]
        header_table = Table(header_data, colWidths=[2.5 * cm, 12.4 * cm, 2.5 * cm])
    else:
        header_data = [[texto_cabecalho]]
        header_table = Table(header_data, colWidths=[17.4 * cm])
        
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(header_table)
    
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(titulo_principal, st['titulo_doc']))
    story.append(Paragraph(sub_legal, st['legal']))
    story.append(Spacer(1, 0.6 * cm))


def _adicionar_secao(story, st, titulo):
    t = Table([[Paragraph(titulo.upper(), st['subtitulo'])]], colWidths=[17.4 * cm])
    t.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1.2, PRETO),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2 * cm))


# ─── Função Auxiliar do Rodapé com QR Code ───────────────────────────────────

def _gerar_rodape(canvas, doc, request, url_validacao, tag_documento):
    canvas.saveState()
    w, h = A4
    y_linha = 2.4 * cm 
    
    qr_x = w - 1.8 * cm - 2.0 * cm 
    qr_y = y_linha + 0.1 * cm 
    
    qr_img = _gerar_qrcode(url_validacao)
    qr_img.drawOn(canvas, qr_x, qr_y)

    canvas.setStrokeColor(PRETO)
    canvas.setLineWidth(1)
    canvas.line(1.8 * cm, y_linha, w - 1.8 * cm, y_linha)
    
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(CINZA_MEDIO)
    
    emissao = timezone.now().strftime('%d/%m/%Y %H:%M')
    emissor = request.user.nome_completo if hasattr(request.user, 'nome_completo') else '—'
    
    canvas.drawString(1.8 * cm, y_linha - 0.4 * cm, f'Emitido por: {emissor} | {emissao}')
    canvas.drawString(1.8 * cm, y_linha - 0.7 * cm, f'SPR-Criminalística — Autenticidade: {url_validacao}')
    canvas.drawRightString(w - 1.8 * cm, y_linha - 0.4 * cm, f'Página {doc.page} | {tag_documento}')
    canvas.restoreState()


# ─── Gerador principal: Vestígio ──────────────────────────────────────────────

def gerar_ficha_vestigio(vestigio, request):
    from django.http import FileResponse
    from custodia.models import VestigioMovimentacao

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.5 * cm, bottomMargin=5.0 * cm,
        title=f'Ficha de Custódia — Vestígio #{vestigio.id}',
    )

    st = _estilos()
    story = []
    
    host = request.build_absolute_uri('/')
    url_validacao = f"{host.rstrip('/')}/#/gabinete-virtual/custodia/vestigios/{vestigio.id}"

    _construir_cabecalho(
        story, st, 
        'FICHA DE ACOMPANHAMENTO DO VESTÍGIO', 
        'Cadeia de Custódia — Arts. 158-A a 158-F do Código de Processo Penal'
    )

    _adicionar_secao(story, st, '1. IDENTIFICAÇÃO DO VESTÍGIO')

    def campo(label, valor):
        return [Paragraph(label, st['label']), Paragraph(_vazio(valor), st['valor'])]

    ident_data = [
        campo('Nº Registro', f'#{vestigio.id}'),
        campo('Status', f'<b>{vestigio.get_status_display().upper()}</b>'),
        campo('Lacre',  vestigio.lacre),
        campo('Nº Processo SEI', vestigio.num_processo_sei),
        campo('Ocorrência', f"{vestigio.ocorrencia or '—'}{(' / ' + str(vestigio.ano_ocorrencia)) if vestigio.ano_ocorrencia else ''}"),
        campo('Material Biológico', 'SIM' if vestigio.biologico else 'NÃO'),
        campo('Serviço Pericial', str(vestigio.servico_pericial) if vestigio.servico_pericial else '—'),
        campo('Unidade Demandante', str(vestigio.unidade_demandante) if vestigio.unidade_demandante else '—'),
        campo('Autoridade', str(vestigio.autoridade) if vestigio.autoridade else '—'),
        campo('Em Conformidade', 'SIM' if vestigio.conformidade else 'NÃO'),
        campo('Registrado por', str(vestigio.created_by) if vestigio.created_by else '—'),
        campo('Data / Hora Registro', _formatar_dt(vestigio.created_at)),
    ]

    rows_2col = []
    for i in range(0, len(ident_data), 2):
        esq = ident_data[i]
        dir_ = ident_data[i + 1] if i + 1 < len(ident_data) else ['', '']
        rows_2col.append([esq[0], esq[1], dir_[0], dir_[1]])

    ident_table = Table(rows_2col, colWidths=[3.2 * cm, 5.5 * cm, 3.2 * cm, 5.5 * cm])
    ident_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, BORDAS),
    ]))
    story.append(ident_table)

    if vestigio.descricao:
        story.append(Spacer(1, 0.2 * cm))
        desc_table = Table(
            [[Paragraph('Descrição do Material', st['label']), Paragraph(vestigio.descricao, st['valor'])]],
            colWidths=[3.2 * cm, 14.2 * cm]
        )
        desc_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, BORDAS),
        ]))
        story.append(desc_table)

    movimentacoes = VestigioMovimentacao.all_objects.filter(
        vestigio=vestigio
    ).select_related(
        'unidade_demandante', 'servico_pericial', 'autoridade',
        'user_destino', 'created_by', 'deleted_by',
    ).order_by('created_at')

    total_mov = movimentacoes.count()
    _adicionar_secao(story, st, f'2. CADEIA DE CUSTÓDIA  —  {total_mov + 1} evento(s)')

    st_anulado = ParagraphStyle('anulado', fontName='Helvetica-Oblique', fontSize=8, textColor=CINZA_MEDIO)
    st_status = ParagraphStyle('st_st', fontName='Helvetica-Bold', fontSize=8, textColor=PRETO)
    
    cab = ['#', 'Data / Hora', 'Responsável', 'Destino / Serviço', 'Descrição', 'Situação']
    cab_row = [Paragraph(c, ParagraphStyle('ch', fontName='Helvetica-Bold', fontSize=7, textColor=PRETO)) for c in cab]
    mov_rows = [cab_row]
    
    origem_inicial = vestigio.unidade_demandante.sigla if vestigio.unidade_demandante else '—'
    
    mov_rows.append([
        Paragraph('0', st['mov_data']),
        Paragraph(_formatar_dt(vestigio.created_at), st['mov_data']),
        Paragraph(vestigio.get_responsavel(), st['mov_texto']),
        Paragraph(origem_inicial, st['mov_texto']),
        Paragraph(f'<b>REGISTRO INICIAL DO VESTÍGIO</b> | Lacre: {_vazio(vestigio.lacre)}', st['mov_texto']),
        Paragraph('Entrada', st_status),
    ])

    for idx, mov in enumerate(movimentacoes, 1):
        anulado = mov.deleted_at is not None
        txt  = st_anulado if anulado else st['mov_texto']
        bold = st_anulado if anulado else st['mov_data']

        destino = '—'
        if mov.unidade_demandante: destino = mov.unidade_demandante.sigla
        elif mov.servico_pericial: destino = mov.servico_pericial.sigla

        if anulado: status_par = Paragraph('Anulado', st_anulado)
        elif mov.aceito: status_par = Paragraph('Aceito', st_status)
        else: status_par = Paragraph('Pendente', st_status)

        desc = f"[ANULADO por {mov.deleted_by or '—'}] {_vazio(mov.descricao)}" if anulado else _vazio(mov.descricao)

        mov_rows.append([
            Paragraph(str(idx), bold),
            Paragraph(_formatar_dt(mov.created_at), bold),
            Paragraph(mov.get_responsavel(), txt),
            Paragraph(destino, txt),
            Paragraph(desc[:300], txt),
            status_par,
        ])

    mov_table = Table(
        mov_rows,
        colWidths=[0.6 * cm, 2.7 * cm, 3.8 * cm, 2.5 * cm, 5.8 * cm, 2.0 * cm],
        repeatRows=1,
    )
    mov_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, 0), 1.2, PRETO), 
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, BORDAS),      
        ('ROWBACKGROUNDS', (1, 1), (-1, -1), [BRANCO, CINZA_CLARO]), 
    ]))
    story.append(mov_table)

    def rodape_cb_vestigio(canvas, doc_):
        _gerar_rodape(canvas, doc_, request, url_validacao, f'Vestígio #{vestigio.id}')

    doc.build(story, onLaterPages=rodape_cb_vestigio, onFirstPage=rodape_cb_vestigio)
    buffer.seek(0)
    nome_arquivo = f'ficha_vestigio_{vestigio.id}_{timezone.now().strftime("%Y%m%d_%H%M")}.pdf'
    return FileResponse(buffer, as_attachment=False, filename=nome_arquivo, content_type='application/pdf')


# ═══════════════════════════════════════════════════════════════════════════════
# Ficha de Coleta de DNA / Perfil Genético
# ═══════════════════════════════════════════════════════════════════════════════

def _sim_nao(valor) -> str:
    return 'Sim' if valor == 'YES' else 'Não'

def _imagem_foto(dna, largura=3.5 * cm, altura=4.5 * cm):
    if not dna.foto: return None
    try:
        return RLImage(dna.foto.path, width=largura, height=altura)
    except Exception:
        return None

def gerar_ficha_dna(dna, request):
    from django.http import FileResponse

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.5 * cm, bottomMargin=5.0 * cm,
        title=f'Ficha de Coleta de DNA — {dna.nome}',
    )

    st = _estilos()
    story = []
    
    host = request.build_absolute_uri('/')
    url_validacao = f"{host.rstrip('/')}/#/gabinete-virtual/custodia/dna/{dna.id}"

    _construir_cabecalho(
        story, st, 
        'FICHA DE COLETA DE PERFIL GENÉTICO (DNA)', 
        'Banco Nacional de Perfis Genéticos — Lei nº 12.654/2012 e Decreto nº 7.950/2013'
    )

    # Função atualizada para calcular a largura das colunas dinamicamente
    def linhas_2col(pares, tem_foto=False):
        dados = [[Paragraph(lb, st['label']), Paragraph(_vazio(v), st['valor'])] for lb, v in pares]
        rows = []
        for i in range(0, len(dados), 2):
            esq = dados[i]
            dir_ = dados[i + 1] if i + 1 < len(dados) else ['', '']
            rows.append([esq[0], esq[1], dir_[0], dir_[1]])
            
        # Se tiver foto, a tabela fica mais estreita (13.6 cm no total)
        if tem_foto:
            col_widths = [2.4 * cm, 4.4 * cm, 2.4 * cm, 4.4 * cm]
        else:
            # Sem foto, ocupa a largura inteira (17.4 cm no total)
            col_widths = [3.2 * cm, 5.5 * cm, 3.2 * cm, 5.5 * cm]
            
        tbl = Table(rows, colWidths=col_widths)
        tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, BORDAS),
        ]))
        return tbl

    _adicionar_secao(story, st, '1. DADOS PESSOAIS E IDENTIFICAÇÃO')

    ident_pares = [
        ('Nome', dna.nome), ('CPF', dna.cpf),
        ('RG', dna.rg), ('Nascimento', _formatar_dt(dna.nascimento)[:10]),
        ('Mãe', dna.mae), ('Pai', dna.pai),
        ('Naturalidade', dna.naturalidade), ('UF', dna.uf),
        ('Estrangeiro', 'Sim' if dna.estrangeiro else 'Não'), ('País', dna.pais or 'BRASIL'),
    ]
    
    foto = _imagem_foto(dna)
    if foto is not None:
        # Avisa a função de que temos foto para reduzir a largura das colunas
        tabela_ident = linhas_2col(ident_pares, tem_foto=True)
        bloco = Table([[tabela_ident, foto]], colWidths=[13.6 * cm, 3.8 * cm])
        bloco.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (1, 0), (1, 0), 10),
        ]))
        story.append(bloco)
    else:
        # Desenha a tabela com a largura inteira
        tabela_ident = linhas_2col(ident_pares, tem_foto=False)
        story.append(tabela_ident)

    _adicionar_secao(story, st, '2. DADOS CLÍNICOS E SITUAÇÃO LEGAL')
    clinico_pares = [
        ('Situação', dna.get_situacao_display()),
        ('Processado no RNBG', _sim_nao(dna.processado_banco_perfis_genetico)),
        ('Histórico Médico', f"Gêmeo: {_sim_nao(dna.gemeo)} | Transfusão: {_sim_nao(dna.transfusao)} | Transplante: {_sim_nao(dna.transplante)}"),
        ('', ''),
    ]
    if dna.situacao == 'APENADO':
        clinico_pares += [('Unidade Prisional', dna.unidade_prisional), ('Tipo Penal', dna.tipo_penal)]
    story.append(linhas_2col(clinico_pares, tem_foto=False))

    _adicionar_secao(story, st, '3. DADOS DA COLETA E REFERÊNCIAS')
    coleta_pares = [
        ('Finalidade', dna.get_finalidade_coleta_display()), ('Data da coleta', _formatar_dt(dna.data_da_coleta)[:10]),
        ('Responsável', dna.responsavel_coleta), ('Perito Responsável', str(dna.perito) if dna.perito else '—'),
        ('Código de Barras', dna.codigo_barras), ('Lacres', dna.lacres),
        ('Nº Processo SEI', dna.num_processo_sei), ('Ocorrência Policial', dna.ocorrencia),
        ('Processo Judicial', dna.processo_judicial), ('Vestígio Vinculado', f'#{dna.vestigio.id}' if dna.vestigio else '—'),
        ('Testemunha 1', dna.testemunha), ('Testemunha 2', dna.testemunha2),
    ]
    story.append(linhas_2col(coleta_pares, tem_foto=False))

    if dna.notas:
        story.append(Spacer(1, 0.4 * cm))
        story.append(Paragraph('<b>Observações:</b>', st['label']))
        story.append(Paragraph(dna.notas, st['valor']))

    story.append(Spacer(1, 1.0 * cm))
    registrado_por = str(dna.created_by) if dna.created_by else '—'
    audit_txt = f"Registro de Sistema: Criado por {registrado_por} em {_formatar_dt(dna.created_at)}. Última atualização em {_formatar_dt(dna.updated_at)}."
    if dna.registrado_por_usuario_externo:
        audit_txt += " (Registrado via portal externo)."
    story.append(Paragraph(audit_txt, st['legal']))

    def rodape_cb_dna(canvas, doc_):
        _gerar_rodape(canvas, doc_, request, url_validacao, f'DNA #{dna.id}')

    doc.build(story, onLaterPages=rodape_cb_dna, onFirstPage=rodape_cb_dna)
    buffer.seek(0)
    nome_arquivo = f'ficha_dna_{dna.id}_{timezone.now().strftime("%Y%m%d_%H%M")}.pdf'
    return FileResponse(buffer, as_attachment=False, filename=nome_arquivo, content_type='application/pdf')