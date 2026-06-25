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
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm


# ─── Paleta de Cores (Sóbria / Monocromática) ────────────────────────────────

PRETO          = colors.HexColor('#000000')
CINZA_ESCURO   = colors.HexColor('#1e293b')
CINZA_MEDIO    = colors.HexColor('#64748b')
CINZA_CLARO    = colors.HexColor('#f8fafc')
BORDAS         = colors.HexColor('#cbd5e1')
BRANCO         = colors.white

# Alerta de não-conformidade
ALERTA_FUNDO   = colors.HexColor('#7f1d1d')   # vermelho escuro (header do box)
ALERTA_CORPO   = colors.HexColor('#fee2e2')    # vermelho claro (corpo do box)
ALERTA_BORDA   = colors.HexColor('#dc2626')    # vermelho (bordas)
ALERTA_TEXTO   = colors.HexColor('#dc2626')    # vermelho (texto inline)


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


# ─── Alerta de Não-Conformidade ──────────────────────────────────────────────

def _box_nao_conforme(story, st, lacre=None):
    """
    Insere um bloco de alerta vermelho quando o vestígio não está em conformidade.
    Deve aparecer logo após o cabeçalho, antes de qualquer seção.
    """
    st_header = ParagraphStyle(
        'nc_header', parent=st['subtitulo'],
        fontSize=10, textColor=BRANCO,
        fontName='Helvetica-Bold', leading=14,
    )
    st_corpo = ParagraphStyle(
        'nc_corpo', parent=st['label'],
        fontSize=8, textColor=CINZA_ESCURO,
        fontName='Helvetica', leading=12,
    )

    lacre_info = f'Lacre registrado: <b>{lacre}</b>' if lacre else 'Vestígio recebido <b>sem lacre de identificação</b>.'

    header_cell = Paragraph(
        '⚠  VESTÍGIO NÃO CONFORME  ⚠',
        st_header,
    )
    corpo_cell = Paragraph(
        f'{lacre_info}<br/>'
        'Este vestígio foi registrado como <b>NÃO CONFORME</b> ao padrão de '
        'acondicionamento e identificação estabelecido pelo protocolo forense. '
        'A não-conformidade deve ser investigada e justificada pelo responsável '
        'pelo recebimento. '
        '<i>Art. 158-B, CPP — Lei n.º 13.964/2019 (Pacote Anticrime).</i>',
        st_corpo,
    )

    tbl = Table(
        [[header_cell], [corpo_cell]],
        colWidths=[17.4 * cm],
    )
    tbl.setStyle(TableStyle([
        # Header vermelha
        ('BACKGROUND',    (0, 0), (0, 0), ALERTA_FUNDO),
        ('TEXTCOLOR',     (0, 0), (0, 0), BRANCO),
        ('ALIGN',         (0, 0), (0, 0), 'CENTER'),
        ('TOPPADDING',    (0, 0), (0, 0), 7),
        ('BOTTOMPADDING', (0, 0), (0, 0), 7),
        # Corpo vermelho claro
        ('BACKGROUND',    (0, 1), (0, 1), ALERTA_CORPO),
        ('TOPPADDING',    (0, 1), (0, 1), 6),
        ('BOTTOMPADDING', (0, 1), (0, 1), 6),
        ('LEFTPADDING',   (0, 1), (0, 1), 8),
        ('RIGHTPADDING',  (0, 1), (0, 1), 8),
        # Borda externa vermelha
        ('BOX',           (0, 0), (-1, -1), 1.5, ALERTA_BORDA),
        ('LINEBELOW',     (0, 0), (0, 0), 0.5, ALERTA_BORDA),
    ]))

    story.append(Spacer(1, 0.3 * cm))
    story.append(tbl)
    story.append(Spacer(1, 0.3 * cm))


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
    w, h = canvas._pagesize  # funciona para portrait e landscape
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


# ─── Integridade de conteúdo (digest do snapshot) ─────────────────────────────

def _calcular_hash_conteudo(vestigio) -> str:
    """
    Digest SHA-256 determinístico do estado do vestígio + sua cadeia de
    movimentações no momento da emissão. Serve de prova de integridade do
    CONTEÚDO da ficha: qualquer adulteração posterior (data, lacre, status,
    responsável) altera o digest, que deixa de bater com o registro gravado.
    """
    import hashlib
    from custodia.models import VestigioMovimentacao

    partes = [
        f'V{vestigio.id}',
        f'lacre={vestigio.lacre or ""}',
        f'sei={vestigio.num_processo_sei or ""}',
        f'status={vestigio.status}',
        f'conf={int(vestigio.conformidade)}',
        f'bio={int(vestigio.biologico)}',
        f'saiu={int(vestigio.saiu_da_custodia)}',
        f'servico={vestigio.servico_pericial_id or ""}',
        f'unidade={vestigio.unidade_demandante_id or ""}',
        f'destino={vestigio.user_destino_id or ""}',
        f'motivo={(vestigio.motivo_finalizacao or "").strip()}',
    ]
    movs = VestigioMovimentacao.all_objects.filter(
        vestigio=vestigio
    ).order_by('created_at')
    for m in movs:
        partes.append(
            f'M{m.id}:srv={m.servico_pericial_id or ""}:und={m.unidade_demandante_id or ""}'
            f':dest={m.user_destino_id or ""}:ace={int(m.aceito)}'
            f':dha={m.data_hora_aceito.isoformat() if m.data_hora_aceito else ""}'
            f':lac={m.lacre or ""}:del={m.deleted_at.isoformat() if m.deleted_at else ""}'
        )
    snapshot = '|'.join(partes)
    return hashlib.sha256(snapshot.encode('utf-8')).hexdigest()


# ─── Gerador principal: Vestígio ──────────────────────────────────────────────

# Cores para badges de evento na cadeia de custódia (escala de cinza, sóbria)
_EV_CORES = {
    'REGISTRO':    (colors.HexColor('#1e293b'), colors.white),   # grafite escuro
    'TRANSFERÊNCIA': (colors.HexColor('#475569'), colors.white), # cinza médio
    'ACEITE':      (colors.HexColor('#0f2d1a'), colors.white),   # verde muito escuro
    'PENDENTE':    (colors.HexColor('#f8fafc'), colors.HexColor('#92400e')),  # fundo claro, texto âmbar
    'ANULADO':     (colors.HexColor('#f1f5f9'), colors.HexColor('#94a3b8')),  # fundo claro, texto apagado
    'FINALIZAÇÃO': (colors.HexColor('#0f172a'), colors.white),   # quase preto — evento mais grave
}


def _badge_evento(tipo: str) -> 'Table':
    """Retorna uma mini-tabela com fundo colorido e texto centrado — o badge de evento."""
    fundo, texto_cor = _EV_CORES.get(tipo, _EV_CORES['REGISTRO'])
    st = ParagraphStyle(
        f'badge_{tipo}', fontName='Helvetica-Bold', fontSize=6.5,
        textColor=texto_cor, alignment=1, leading=9,
    )
    tbl = Table([[Paragraph(tipo, st)]], colWidths=[2.4 * cm])
    borda = colors.HexColor('#334155') if texto_cor == colors.white else colors.HexColor('#cbd5e1')
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), fundo),
        ('BOX',           (0, 0), (-1, -1), 0.5, borda),
        ('TOPPADDING',    (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 2),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 2),
    ]))
    return tbl


def gerar_ficha_vestigio(vestigio, request):
    """
    Ficha de Acompanhamento do Vestígio — v2.
    Suporta estados INICIAL, ANDAMENTO e FINALIZADO.
    A seção de finalização só aparece quando o vestígio foi efetivamente finalizado.
    """
    import hashlib
    from django.http import FileResponse
    from custodia.models import VestigioMovimentacao, Vestigio as _Vestigio, FichaVestigioRegistro

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.2 * cm, bottomMargin=4.5 * cm,
        title=f'Ficha de Acompanhamento — Vestígio #{vestigio.id}',
    )

    st   = _estilos()
    base = getSampleStyleSheet()
    story = []

    # Protocolo único de autenticidade (mesmo modelo da certidão de ausência)
    now_fav = timezone.now()
    protocolo_raw = f"FAV{vestigio.id}{now_fav.isoformat()}{request.user.id}"
    protocolo_fav = hashlib.sha256(protocolo_raw.encode()).hexdigest()[:16].upper()
    protocolo_fmt = f"{protocolo_fav[:4]}-{protocolo_fav[4:8]}-{protocolo_fav[8:12]}-{protocolo_fav[12:16]}"

    host = request.build_absolute_uri('/')
    url_validacao = f"{host.rstrip('/')}/api/custodia/vestigios/validar-ficha/?protocolo={protocolo_fav}"

    # Digest de integridade do conteúdo (snapshot do vestígio + cadeia)
    conteudo_hash = _calcular_hash_conteudo(vestigio)
    conteudo_hash_fmt = conteudo_hash[:32].upper()  # 32 chars legíveis no documento

    # Grava o registro para validação posterior via QR code
    FichaVestigioRegistro.objects.create(
        protocolo        = protocolo_fav,
        vestigio         = vestigio,
        vestigio_lacre   = vestigio.lacre or '',
        conteudo_hash    = conteudo_hash,
        emitido_por      = request.user,
        emitido_por_nome = getattr(request.user, 'nome_completo', None) or str(request.user),
        emitido_em       = now_fav,
    )

    # Estilos complementares
    st_dado_label = ParagraphStyle(
        'dado_label_v', parent=base['Normal'],
        fontName='Helvetica-Bold', fontSize=8.5, textColor=CINZA_ESCURO,
    )
    st_dado_valor = ParagraphStyle(
        'dado_valor_v', parent=base['Normal'],
        fontName='Helvetica', fontSize=9, textColor=PRETO, leading=12,
    )
    st_corpo_v = ParagraphStyle(
        'corpo_v', parent=base['Normal'],
        fontName='Helvetica', fontSize=9, textColor=PRETO,
        leading=14, alignment=4,
    )
    st_cab_col = ParagraphStyle(
        'cab_col', parent=base['Normal'],
        fontName='Helvetica-Bold', fontSize=7, textColor=PRETO,
    )
    st_cel = ParagraphStyle(
        'cel', parent=base['Normal'],
        fontName='Helvetica', fontSize=8, textColor=PRETO, leading=11,
    )
    st_cel_bold = ParagraphStyle(
        'cel_bold', parent=base['Normal'],
        fontName='Helvetica-Bold', fontSize=8, textColor=PRETO, leading=11,
    )
    st_cel_apagado = ParagraphStyle(
        'cel_ap', parent=base['Normal'],
        fontName='Helvetica-Oblique', fontSize=8,
        textColor=colors.HexColor('#94a3b8'), leading=11,
    )

    # ── Cabeçalho ────────────────────────────────────────────────────────────────
    _construir_cabecalho(
        story, st,
        'FICHA DE ACOMPANHAMENTO DO VESTÍGIO',
        'Cadeia de Custódia — Arts. 158-A a 158-F do Código de Processo Penal',
    )

    # ── Alerta de não-conformidade (imediatamente após o cabeçalho) ───────────────
    if not vestigio.conformidade:
        _box_nao_conforme(story, st, lacre=vestigio.lacre)

    # ── Seção 1: Identificação ────────────────────────────────────────────────────
    _adicionar_secao(story, st, '1. IDENTIFICAÇÃO DO VESTÍGIO')

    # Estilo de valor em alerta (vermelho bold) — para o campo conformidade quando NÃO
    st_dado_valor_alerta = ParagraphStyle(
        'dado_valor_v_alerta', parent=st_dado_valor,
        fontName='Helvetica-Bold', textColor=ALERTA_TEXTO,
    )

    def _linha(label, valor, alerta=False):
        st_v = st_dado_valor_alerta if alerta else st_dado_valor
        return [Paragraph(label, st_dado_label), Paragraph(_vazio(valor), st_v)]

    ident_pares = [
        _linha('Nº Registro', f'#{vestigio.id}'),
        _linha('Lacre', vestigio.lacre or 'SEM LACRE — Não conforme', alerta=not vestigio.conformidade and not vestigio.lacre),
        _linha('Nº Processo SEI', vestigio.num_processo_sei),
        _linha('Ocorrência / Ano', f"{vestigio.ocorrencia or '—'}{f' / {vestigio.ano_ocorrencia}' if vestigio.ano_ocorrencia else ''}"),
        _linha('Material Biológico', 'SIM' if vestigio.biologico else 'NÃO'),
        _linha('Em Conformidade', 'SIM' if vestigio.conformidade else 'NÃO — Vestígio não conforme', alerta=not vestigio.conformidade),
        _linha('Serviço Pericial', str(vestigio.servico_pericial) if vestigio.servico_pericial else '—'),
        _linha('Unidade Demandante', str(vestigio.unidade_demandante) if vestigio.unidade_demandante else '—'),
        _linha('Autoridade requisitante', str(vestigio.autoridade) if vestigio.autoridade else '—'),
        _linha('Registrado por', vestigio.get_responsavel()),
        _linha('Data / Hora Registro', _formatar_dt(vestigio.created_at)),
        _linha('', ''),  # padding de grade
    ]

    grid_rows = []
    for i in range(0, len(ident_pares), 2):
        esq = ident_pares[i]
        dir_ = ident_pares[i + 1] if i + 1 < len(ident_pares) else ['', '']
        grid_rows.append([esq[0], esq[1], dir_[0], dir_[1]])

    ident_tbl = Table(grid_rows, colWidths=[3.5 * cm, 5.2 * cm, 3.5 * cm, 5.2 * cm])
    ident_tbl.setStyle(TableStyle([
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('LINEBELOW',     (0, 0), (-1, -1), 0.5, BORDAS),
    ]))
    story.append(ident_tbl)

    # ── Seção 2: Situação Atual ──────────────────────────────────────────────────
    # Determina o custodiante atual
    finalizado = vestigio.status == _Vestigio.Status.FINALIZADO

    if vestigio.user_destino:
        custodiante_txt = vestigio.user_destino.nome_completo
        if hasattr(vestigio.user_destino, 'servicos_periciais'):
            servs = vestigio.user_destino.servicos_periciais.all()
            if servs.exists():
                custodiante_txt += f' ({servs.first().sigla})'
    elif vestigio.servico_pericial:
        custodiante_txt = str(vestigio.servico_pericial)
    elif vestigio.unidade_demandante:
        custodiante_txt = str(vestigio.unidade_demandante)
    else:
        custodiante_txt = '—'

    _adicionar_secao(story, st, '2. SITUAÇÃO ATUAL')

    sit_linhas = [
        [Paragraph('Status', st_dado_label), Paragraph(f'<b>{vestigio.get_status_display().upper()}</b>', st_dado_valor)],
    ]

    if not finalizado:
        sit_linhas.append(
            [Paragraph('Com quem está', st_dado_label), Paragraph(custodiante_txt, st_dado_valor)]
        )
    else:
        situacao_fisica = 'Saiu fisicamente da Instituição' if vestigio.saiu_da_custodia else 'Permanece na custódia da Instituição'
        sit_linhas.append(
            [Paragraph('Situação física', st_dado_label), Paragraph(situacao_fisica, st_dado_valor)]
        )
        if vestigio.updated_by:
            sit_linhas.append([
                Paragraph('Finalizado por', st_dado_label),
                Paragraph(
                    f'{vestigio.updated_by.nome_completo} em {_formatar_dt(vestigio.updated_at)}',
                    st_dado_valor,
                ),
            ])

    # Contra-prova
    if vestigio.vestigio_contra_prova:
        sit_linhas.append([
            Paragraph('Vestígio original', st_dado_label),
            Paragraph(f'Lacre: {vestigio.vestigio_contra_prova.lacre or f"#{vestigio.vestigio_contra_prova.id}"}', st_dado_valor),
        ])

    sit_tbl = Table(sit_linhas, colWidths=[3.5 * cm, 13.9 * cm])
    sit_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), CINZA_CLARO),
        ('BOX',           (0, 0), (-1, -1), 1, BORDAS),
        ('LINEBELOW',     (0, 0), (-1, -2), 0.5, BORDAS),
        ('BACKGROUND',    (0, 0), (0, -1), colors.HexColor('#e2e8f0')),
        ('TOPPADDING',    (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(sit_tbl)

    # ── Seção 3: Motivo da Finalização (apenas quando finalizado) ────────────────
    num = 3
    if finalizado and vestigio.motivo_finalizacao:
        _adicionar_secao(story, st, f'{num}. MOTIVO DA FINALIZAÇÃO')
        motivo_tbl = Table(
            [[Paragraph(vestigio.motivo_finalizacao, st_corpo_v)]],
            colWidths=[17.4 * cm],
        )
        motivo_tbl.setStyle(TableStyle([
            ('BOX',           (0, 0), (-1, -1), 1, BORDAS),
            ('BACKGROUND',    (0, 0), (-1, -1), CINZA_CLARO),
            ('TOPPADDING',    (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ]))
        story.append(motivo_tbl)
        num += 1

    # ── Seção: Material e Descrição ──────────────────────────────────────────────
    procedimentos = vestigio.procedimentos.select_related('tipo_procedimento').all()
    if vestigio.descricao or procedimentos.exists():
        _adicionar_secao(story, st, f'{num}. MATERIAL PERICIAL')

        if vestigio.descricao:
            desc_tbl = Table(
                [[Paragraph('Descrição:', st_dado_label), Paragraph(vestigio.descricao, st_corpo_v)]],
                colWidths=[2.5 * cm, 14.9 * cm],
            )
            desc_tbl.setStyle(TableStyle([
                ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING',    (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING',   (0, 0), (-1, -1), 0),
                ('LINEBELOW',     (0, 0), (-1, -1), 0.5, BORDAS),
            ]))
            story.append(desc_tbl)

        if procedimentos.exists():
            story.append(Spacer(1, 0.2 * cm))
            proc_cab = [Paragraph(c, st_cab_col) for c in ['Procedimento', 'Número', 'Ano']]
            proc_rows = [proc_cab]
            for p in procedimentos:
                sigla = p.tipo_procedimento.sigla if hasattr(p, 'tipo_procedimento') and p.tipo_procedimento else '—'
                proc_rows.append([
                    Paragraph(sigla, st_cel),
                    Paragraph(str(p.numero) if p.numero else '—', st_cel),
                    Paragraph(str(p.ano) if p.ano else '—', st_cel),
                ])
            proc_tbl = Table(proc_rows, colWidths=[10.0 * cm, 4.0 * cm, 3.4 * cm], repeatRows=1)
            proc_tbl.setStyle(TableStyle([
                ('LINEBELOW',     (0, 0), (-1, 0), 1, PRETO),
                ('LINEBELOW',     (0, 1), (-1, -1), 0.5, BORDAS),
                ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BRANCO, CINZA_CLARO]),
                ('TOPPADDING',    (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING',   (0, 0), (-1, -1), 2),
            ]))
            story.append(proc_tbl)

        num += 1

    # ── Seção: Ocorrências Vinculadas ────────────────────────────────────────────
    ocorrencias = vestigio.ocorrencias_vinculadas.select_related(
        'servico_pericial', 'unidade_demandante',
        'procedimento_cadastrado__tipo_procedimento',
    ).all()

    if ocorrencias.exists():
        _adicionar_secao(story, st, f'{num}. OCORRÊNCIAS VINCULADAS')
        oc_cab_row = [Paragraph(c, st_cab_col) for c in ['Nº Ocorrência', 'Status', 'Serviço', 'Unidade', 'Procedimento']]
        oc_rows = [oc_cab_row]
        for oc in ocorrencias:
            proc_txt = '—'
            if oc.procedimento_cadastrado:
                p = oc.procedimento_cadastrado
                proc_txt = f"{p.tipo_procedimento.sigla} {p.numero}/{p.ano}"
            oc_rows.append([
                Paragraph(oc.numero_ocorrencia, st_cel_bold),
                Paragraph(oc.get_status_display(), st_cel),
                Paragraph(oc.servico_pericial.sigla if oc.servico_pericial else '—', st_cel),
                Paragraph(oc.unidade_demandante.sigla if oc.unidade_demandante else '—', st_cel),
                Paragraph(proc_txt, st_cel),
            ])
        oc_tbl = Table(oc_rows, colWidths=[3.8 * cm, 3.0 * cm, 2.5 * cm, 3.0 * cm, 5.1 * cm], repeatRows=1)
        oc_tbl.setStyle(TableStyle([
            ('LINEBELOW',     (0, 0), (-1, 0), 1.2, PRETO),
            ('LINEBELOW',     (0, 1), (-1, -1), 0.5, BORDAS),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BRANCO, CINZA_CLARO]),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 2),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(oc_tbl)
        num += 1

    # ── Seção final: Cadeia de Custódia ──────────────────────────────────────────
    movimentacoes = VestigioMovimentacao.all_objects.filter(
        vestigio=vestigio,
    ).select_related(
        'unidade_demandante', 'servico_pericial', 'autoridade',
        'user_destino', 'created_by', 'deleted_by',
    ).order_by('created_at')

    # Monta lista de eventos
    eventos = []

    # Evento 0 — REGISTRO INICIAL
    origem = str(vestigio.unidade_demandante) if vestigio.unidade_demandante else '—'
    lacre_inicial = vestigio.lacre or '—'
    # lacre_vigente rastreia o lacre conhecido ao longo da cadeia
    lacre_vigente = vestigio.lacre

    eventos.append({
        'tipo':          'REGISTRO',
        'data_hora':     _formatar_dt(vestigio.created_at),
        'realizado_por': vestigio.get_responsavel(),
        'de_para':       f'{origem}<br/><b>Lacre inicial:</b> {lacre_inicial}',
        'observacoes':   'Entrada inicial no sistema.',
    })

    for mov in movimentacoes:
        anulado = mov.deleted_at is not None

        # Destino da movimentação
        if mov.unidade_demandante:
            destino_str = str(mov.unidade_demandante)
        elif mov.servico_pericial:
            destino_str = str(mov.servico_pericial)
        else:
            destino_str = '—'

        if anulado:
            anulador = str(mov.deleted_by) if mov.deleted_by else '—'
            eventos.append({
                'tipo':          'ANULADO',
                'data_hora':     _formatar_dt(mov.deleted_at),
                'realizado_por': anulador,
                'de_para':       f'→ {destino_str}',
                'observacoes':   f'Movimentação anulada. {_vazio(mov.descricao)}',
            })
        else:
            # ── Rastreio de lacre ──────────────────────────────────────────
            # Quando a movimentação informa um lacre:
            #   - igual ao vigente: confirma sem indicar troca
            #   - diferente:        exibe "anterior → novo" (troca detectada)
            # Quando a movimentação NÃO informa lacre:
            #   - lacre vigente conhecido: herda/mantém ("Lacre mantido: X")
            #   - nenhum lacre jamais registrado: inconformidade persistente
            if mov.lacre:
                if lacre_vigente and mov.lacre != lacre_vigente:
                    lacre_linha = (
                        f'<br/><b>Lacre:</b> {lacre_vigente} → <b>{mov.lacre}</b>'
                    )
                else:
                    lacre_linha = f'<br/><b>Lacre:</b> {mov.lacre}'
                lacre_vigente = mov.lacre
            elif lacre_vigente:
                lacre_linha = f'<br/><b>Lacre mantido:</b> {lacre_vigente}'
            else:
                lacre_linha = (
                    '<br/><font color="#b91c1c"><i>Sem lacre registrado</i></font>'
                )

            # Observações: descrição + SEI + autoridade (lacre saiu daqui)
            obs_transf = _vazio(mov.descricao)
            if mov.num_processo_sei:
                obs_transf = f'SEI: {mov.num_processo_sei} | {obs_transf}'
            if mov.autoridade:
                obs_transf += f' | Autoridade: {mov.autoridade.nome}'

            eventos.append({
                'tipo':          'TRANSFERÊNCIA',
                'data_hora':     _formatar_dt(mov.created_at),
                'realizado_por': mov.get_responsavel(),
                'de_para':       f'→ {destino_str}{lacre_linha}',
                'observacoes':   obs_transf,
            })

            if mov.aceito:
                # De/Para do ACEITE confirma o lacre — herda lacre_vigente se
                # a movimentação não informou número próprio (lacre mantido)
                quem_aceitou = str(mov.user_destino) if mov.user_destino else '—'
                _lacre_aceite = mov.lacre or lacre_vigente
                if _lacre_aceite:
                    aceite_lacre = f'<br/><b>Lacre confirmado:</b> {_lacre_aceite}'
                else:
                    aceite_lacre = (
                        '<br/><font color="#b91c1c"><i>Sem lacre registrado</i></font>'
                    )
                eventos.append({
                    'tipo':          'ACEITE',
                    'data_hora':     _formatar_dt(mov.data_hora_aceito),
                    'realizado_por': quem_aceitou,
                    'de_para':       f'{destino_str}{aceite_lacre}',
                    'observacoes':   'Recebimento confirmado — custódia transferida',
                })
            else:
                destinatario = str(mov.user_destino) if mov.user_destino else '—'
                eventos.append({
                    'tipo':          'PENDENTE',
                    'data_hora':     '—',
                    'realizado_por': destinatario,
                    'de_para':       f'→ {destino_str}',
                    'observacoes':   'Aguardando confirmação de recebimento',
                })

    # Evento de FINALIZAÇÃO — somente se o vestígio foi finalizado
    if finalizado:
        finalizador = str(vestigio.updated_by) if vestigio.updated_by else vestigio.get_responsavel()
        sit_fisica = 'Saiu fisicamente da Instituição' if vestigio.saiu_da_custodia else 'Permanece na Instituição'
        eventos.append({
            'tipo':          'FINALIZAÇÃO',
            'data_hora':     _formatar_dt(vestigio.updated_at),
            'realizado_por': finalizador,
            'de_para':       sit_fisica,
            'observacoes':   vestigio.motivo_finalizacao or '—',
        })

    total_ev = len(eventos)
    _adicionar_secao(story, st, f'{num}. CADEIA DE CUSTÓDIA  —  {total_ev} evento(s)')

    # Cabeçalho da tabela
    cab_row = [
        Paragraph('Evento',        st_cab_col),
        Paragraph('Data / Hora',   st_cab_col),
        Paragraph('Realizado por', st_cab_col),
        Paragraph('De / Para',     st_cab_col),
        Paragraph('Observações',   st_cab_col),
    ]
    # Larguras: badge(2.4) + data(2.8) + responsável(3.8) + de_para(4.0) + obs(4.4) = 17.4
    col_w = [2.4 * cm, 2.8 * cm, 3.8 * cm, 4.0 * cm, 4.4 * cm]

    cadeia_rows = [cab_row]
    estilos_linhas = []  # acumula estilos específicos por linha

    for idx, ev in enumerate(eventos, 1):
        anulado_ev = ev['tipo'] == 'ANULADO'
        pendente_ev = ev['tipo'] == 'PENDENTE'
        st_txt = st_cel_apagado if anulado_ev else st_cel
        st_bold_txt = st_cel_apagado if anulado_ev else st_cel_bold

        cadeia_rows.append([
            _badge_evento(ev['tipo']),
            Paragraph(ev['data_hora'],     st_bold_txt if not anulado_ev else st_txt),
            Paragraph(ev['realizado_por'], st_bold_txt),
            Paragraph(ev['de_para'],       st_txt),
            Paragraph(ev['observacoes'],   st_txt),
        ])

        # Fundo levemente diferenciado para ACEITE e FINALIZAÇÃO
        if ev['tipo'] == 'ACEITE':
            estilos_linhas.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#f0fdf4')))
        elif ev['tipo'] == 'FINALIZAÇÃO':
            estilos_linhas.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#f8fafc')))
            estilos_linhas.append(('LINEABOVE',  (0, idx), (-1, idx), 1.2, PRETO))
        elif ev['tipo'] == 'PENDENTE':
            estilos_linhas.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#fffbeb')))

    cadeia_tbl = Table(cadeia_rows, colWidths=col_w, repeatRows=1)
    base_style = [
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 3),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
        ('LINEBELOW',     (0, 0), (-1, 0), 1.5, PRETO),   # linha abaixo do cabeçalho
        ('LINEBELOW',     (0, 1), (-1, -1), 0.4, BORDAS), # separadores leves
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BRANCO, CINZA_CLARO]),
    ] + estilos_linhas

    cadeia_tbl.setStyle(TableStyle(base_style))
    story.append(cadeia_tbl)

    # ── Seção: Elos da Cadeia de Custódia (Art. 158-B do CPP) ────────────────────
    # Amarra a ficha ao vocabulário legal das 10 etapas, indicando onde cada elo
    # é evidenciado pelo sistema (os 3 primeiros ocorrem na cena do crime).
    num += 1
    _adicionar_secao(story, st, f'{num}. ELOS DA CADEIA DE CUSTÓDIA (ART. 158-B, CPP)')
    elos_cab = [Paragraph(c, st_cab_col) for c in ['Elo legal', 'Etapa', 'Onde é evidenciado nesta ficha']]
    elos_dados = [
        ('I — Reconhecimento',   'Cena',     'Etapa de campo (anterior ao sistema laboratorial)'),
        ('II — Isolamento',      'Cena',     'Etapa de campo (anterior ao sistema laboratorial)'),
        ('III — Fixação',        'Cena',     'Etapa de campo (anterior ao sistema laboratorial)'),
        ('IV — Coleta',          'Entrada',  'Registro inicial do vestígio'),
        ('V — Acondicionamento', 'Entrada',  'Registro inicial — lacre de entrada'),
        ('VI — Transporte',      'Trânsito', 'Eventos de TRANSFERÊNCIA da cadeia'),
        ('VII — Recebimento',    'Custódia', 'Eventos de ACEITE da cadeia'),
        ('VIII — Processamento', 'Exame',    'Seção Material Pericial / procedimentos'),
        ('IX — Armazenamento',   'Guarda',   'Seção Situação Atual (detentor vigente)'),
        ('X — Descarte',         'Saída',    'Finalização (quando o vestígio sai da custódia)'),
    ]
    elos_rows = [elos_cab]
    for elo, etapa, onde in elos_dados:
        elos_rows.append([
            Paragraph(elo, st_cel_bold),
            Paragraph(etapa, st_cel),
            Paragraph(onde, st_cel),
        ])
    elos_tbl = Table(elos_rows, colWidths=[4.6 * cm, 2.6 * cm, 10.2 * cm], repeatRows=1)
    elos_tbl.setStyle(TableStyle([
        ('LINEBELOW',     (0, 0), (-1, 0), 1.2, PRETO),
        ('LINEBELOW',     (0, 1), (-1, -1), 0.4, BORDAS),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BRANCO, CINZA_CLARO]),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 3),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(elos_tbl)

    # ── Seção: Autenticação do Documento ─────────────────────────────────────────
    # Assinatura eletrônica do emissor + protocolo + digest de integridade do
    # conteúdo (não-repúdio de quem emitiu e prova de que o conteúdo não foi alterado).
    num += 1
    _adicionar_secao(story, st, f'{num}. AUTENTICAÇÃO DO DOCUMENTO')

    try:
        perfil_emissor = request.user.get_perfil_display()
    except Exception:
        perfil_emissor = getattr(request.user, 'perfil', '') or ''
    cpf_emissor = getattr(request.user, 'cpf', '') or '—'
    nome_emissor = getattr(request.user, 'nome_completo', None) or str(request.user)

    auth_linhas = [
        [Paragraph('Emitido por', st_dado_label),
         Paragraph(f'{nome_emissor}{f" — {perfil_emissor}" if perfil_emissor else ""}', st_dado_valor)],
        [Paragraph('CPF do emissor', st_dado_label), Paragraph(cpf_emissor, st_dado_valor)],
        [Paragraph('Data / Hora da emissão', st_dado_label), Paragraph(_formatar_dt(now_fav), st_dado_valor)],
        [Paragraph('Protocolo', st_dado_label), Paragraph(protocolo_fmt, st_dado_valor)],
        [Paragraph('Hash de integridade (SHA-256)', st_dado_label),
         Paragraph(f'<font face="Courier">{conteudo_hash_fmt}</font>', st_dado_valor)],
    ]
    auth_tbl = Table(auth_linhas, colWidths=[4.4 * cm, 13.0 * cm])
    auth_tbl.setStyle(TableStyle([
        ('BOX',           (0, 0), (-1, -1), 1, BORDAS),
        ('LINEBELOW',     (0, 0), (-1, -2), 0.5, BORDAS),
        ('BACKGROUND',    (0, 0), (0, -1), colors.HexColor('#e2e8f0')),
        ('BACKGROUND',    (1, 0), (-1, -1), CINZA_CLARO),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(auth_tbl)

    st_nota_auth = ParagraphStyle(
        'nota_auth', parent=base['Normal'], fontName='Helvetica-Oblique',
        fontSize=7.5, textColor=CINZA_MEDIO, leading=10,
    )
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph(
        'Documento gerado eletronicamente pelo SPR-Criminalística. A autenticidade e a integridade do '
        'conteúdo podem ser verificadas pelo QR Code do rodapé ou pelo protocolo acima — o hash recomputado '
        'na validação deve coincidir com o registrado. Validade conforme MP nº 2.200-2/2001 (ICP-Brasil) e '
        'Arts. 158-A a 158-F do Código de Processo Penal.',
        st_nota_auth,
    ))

    def rodape_cb_vestigio(canvas, doc_):
        _gerar_rodape(canvas, doc_, request, url_validacao, f'Vestígio #{vestigio.id} | Prot.: {protocolo_fmt}')

    doc.build(story, onFirstPage=rodape_cb_vestigio, onLaterPages=rodape_cb_vestigio)
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


# ═══════════════════════════════════════════════════════════════════════════════
# Certidão / Comprovante de Ausência de Registro de Perfil Genético
#
# Dois modos conforme o perfil de quem emite:
#
#   EXTERNO (delegado/promotor/juiz com acesso direto):
#     → "Comprovante de Consulta" — emitido pelo Sistema, sem assinatura pessoal.
#       O usuário consultou por conta própria e o sistema registra o resultado.
#
#   PERITO / OPERACIONAL / ADMINISTRATIVO / CUSTODIANTE / SUPER_ADMIN:
#     → "Certidão" formal — assinatura eletrônica do perito responsável.
#       Emitida a pedido de uma autoridade, tem peso probatório maior.
# ═══════════════════════════════════════════════════════════════════════════════

def gerar_certidao_ausencia_dna(request, nome: str, cpf: str, rg: str = ''):
    """
    Gera documento de ausência de registro de DNA.

    Dois modos conforme o perfil do usuário autenticado:
      - EXTERNO: "Comprovante de Consulta" emitido pelo sistema (sem assinatura pessoal).
      - PERITO/ADMIN/etc: "Certidão" formal com assinatura eletrônica do perito.
    """
    import hashlib
    from django.http import FileResponse
    from usuarios.models import User as _User

    now = timezone.now()
    user = request.user
    is_externo = getattr(user, 'perfil', None) == _User.Perfil.EXTERNO

    # Protocolo único: hash dos parâmetros + usuário + timestamp
    protocolo_raw = f"{nome.upper()}{cpf}{rg.upper()}{now.isoformat()}{user.id}"
    protocolo     = hashlib.sha256(protocolo_raw.encode()).hexdigest()[:16].upper()
    protocolo_fmt = f"{protocolo[:4]}-{protocolo[4:8]}-{protocolo[8:12]}-{protocolo[12:16]}"

    host          = request.build_absolute_uri('/')
    url_validacao = f"{host.rstrip('/')}/api/custodia/dnas/validar-certidao/?protocolo={protocolo}"
    emissao_fmt   = now.strftime('%d/%m/%Y  %H:%M')

    # Grava o registro para validação posterior via QR code
    from custodia.models import CertidaoRegistro as _CertReg
    _CertReg.objects.create(
        protocolo       = protocolo,
        tipo            = _CertReg.Tipo.COMPROVANTE if is_externo else _CertReg.Tipo.CERTIDAO,
        nome_consultado = nome,
        cpf_consultado  = cpf,
        rg_consultado   = rg,
        emitido_por     = user,
        emitido_por_nome= getattr(user, 'nome_completo', None) or str(user),
        emitido_em      = now,
    )

    # Metadados do emissor
    emissor_nome   = getattr(user, 'nome_completo', None) or str(user)
    emissor_cpf    = getattr(user, 'cpf', None)
    emissor_email  = getattr(user, 'email', '') or '—'
    emissor_perfil = getattr(user, 'get_perfil_display', lambda: 'Usuário')()
    unidade_obj    = getattr(user, 'unidade_demandante', None)
    unidade_nome   = str(unidade_obj) if unidade_obj else None

    # Títulos e textos variam conforme o modo
    if is_externo:
        titulo_doc  = 'COMPROVANTE DE CONSULTA AO BANCO DE PERFIS GENÉTICOS'
        sub_legal   = 'Resultado de consulta registrada — Lei nº 12.654/2012 e Decreto nº 7.950/2013'
        nome_arquivo_prefix = 'comprovante_consulta_dna'
        tag_rodape  = f'Comprovante {protocolo_fmt}'
    else:
        titulo_doc  = 'CERTIDÃO DE AUSÊNCIA DE REGISTRO DE PERFIL GENÉTICO'
        sub_legal   = 'Banco de Perfis Genéticos — Lei nº 12.654/2012 e Decreto nº 7.950/2013'
        nome_arquivo_prefix = 'certidao_ausencia_dna'
        tag_rodape  = f'Certidão {protocolo_fmt}'

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.2 * cm, bottomMargin=4.5 * cm,
        title=titulo_doc,
    )

    st   = _estilos()
    base = getSampleStyleSheet()

    st['corpo'] = ParagraphStyle(
        'corpo', parent=base['Normal'],
        fontName='Helvetica', fontSize=10,
        textColor=PRETO, leading=16, alignment=4, spaceAfter=8,
    )
    st['dado_label'] = ParagraphStyle(
        'dado_label', parent=base['Normal'],
        fontName='Helvetica-Bold', fontSize=9, textColor=CINZA_ESCURO,
    )
    st['dado_valor'] = ParagraphStyle(
        'dado_valor', parent=base['Normal'],
        fontName='Helvetica', fontSize=10, textColor=PRETO,
    )
    st['rodape_legal'] = ParagraphStyle(
        'rodape_legal', parent=base['Normal'],
        fontName='Helvetica-Oblique', fontSize=8,
        textColor=CINZA_MEDIO, leading=11, alignment=4,
    )
    st['protocolo'] = ParagraphStyle(
        'protocolo', parent=base['Normal'],
        fontName='Helvetica-Bold', fontSize=9,
        textColor=CINZA_ESCURO, alignment=TA_CENTER,
    )
    selo_label = ParagraphStyle(
        'selo_label', parent=base['Normal'],
        fontName='Helvetica-Bold', fontSize=8, textColor=CINZA_ESCURO, leading=11,
    )
    selo_valor = ParagraphStyle(
        'selo_valor', parent=base['Normal'],
        fontName='Helvetica', fontSize=8, textColor=PRETO, leading=12,
    )
    nota_mp = ParagraphStyle(
        'nota_mp', parent=base['Normal'],
        fontName='Helvetica-Oblique', fontSize=7.5, textColor=CINZA_MEDIO, leading=10,
    )

    story = []

    # ── Cabeçalho ────────────────────────────────────────────────────────────
    _construir_cabecalho(story, st, titulo_doc, sub_legal)

    # ── Faixa de protocolo ───────────────────────────────────────────────────
    protocolo_row = Table(
        [[
            Paragraph(f'Protocolo: <b>{protocolo_fmt}</b>', st['protocolo']),
            Paragraph(f'Emissão: <b>{emissao_fmt}</b>',     st['protocolo']),
        ]],
        colWidths=[8.7 * cm, 8.7 * cm],
    )
    protocolo_row.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), CINZA_CLARO),
        ('BOX',           (0, 0), (-1, -1), 1, BORDAS),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(protocolo_row)
    story.append(Spacer(1, 0.4 * cm))

    # ── Corpo principal ──────────────────────────────────────────────────────
    if is_externo:
        story.append(Paragraph(
            f'O Sistema SPR-Criminalística do Instituto de Criminalística da Polícia Civil '
            f'do Estado de Roraima <b>DECLARA</b> que, em consulta realizada pelo(a) '
            f'usuário(a) <b>{emissor_nome}</b>'
            + (f' ({unidade_nome})' if unidade_nome else '')
            + f' em <b>{emissao_fmt}</b>, '
            f'<b>NÃO FOI ENCONTRADO</b> registro de coleta de material biológico '
            f'para a pessoa com os seguintes dados:',
            st['corpo'],
        ))
    else:
        story.append(Paragraph(
            f'O(A) Perito(a) Criminal infrascrito(a), no exercício de suas atribuições legais, '
            f'<b>CERTIFICA</b> que, em consulta ao Banco de Perfis Genéticos do Instituto de '
            f'Criminalística da Polícia Civil do Estado de Roraima — Sistema SPR-Criminalística, '
            f'realizada em <b>{emissao_fmt}</b>, <b>NÃO FOI ENCONTRADO</b> registro de coleta '
            f'de material biológico para a pessoa com os seguintes dados:',
            st['corpo'],
        ))

    story.append(Spacer(1, 0.2 * cm))

    # ── Quadro de dados da pessoa consultada ────────────────────────────────
    linhas_dados = []
    if nome:
        linhas_dados.append([Paragraph('Nome:', st['dado_label']), Paragraph(nome.upper(), st['dado_valor'])])
    if cpf:
        linhas_dados.append([Paragraph('CPF:',  st['dado_label']), Paragraph(cpf,          st['dado_valor'])])
    if rg:
        linhas_dados.append([Paragraph('RG:',   st['dado_label']), Paragraph(rg.upper(),   st['dado_valor'])])

    if linhas_dados:
        dados_tbl = Table(linhas_dados, colWidths=[3.0 * cm, 14.4 * cm])
        dados_tbl.setStyle(TableStyle([
            ('BOX',           (0, 0), (-1, -1), 1.5, PRETO),
            ('LINEBELOW',     (0, 0), (-1, -2), 0.5, BORDAS),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING',   (0, 0), (-1, -1), 12),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND',    (0, 0), (0, -1),  CINZA_CLARO),
        ]))
        story.append(dados_tbl)

    story.append(Spacer(1, 0.35 * cm))

    story.append(Paragraph(
        'A consulta abrangeu os campos de identificação do sistema de custódia de vestígios '
        'e perfis genéticos (nome, CPF, RG e código de barras), considerando '
        '<b>todos os registros ativos</b> no banco de dados do Instituto de Criminalística.',
        st['corpo'],
    ))

    story.append(Spacer(1, 0.2 * cm))

    # ── Base legal e validade ────────────────────────────────────────────────
    if is_externo:
        emitido_por_txt = 'Sistema SPR-Criminalística / Instituto de Criminalística — PCRR'
    else:
        emitido_por_txt = f'{emissor_nome} — Perito(a) Criminal / Instituto de Criminalística'

    base_legal_rows = [
        [Paragraph('Base Legal',  st['dado_label']),
         Paragraph('Lei nº 12.654/2012 | Decreto nº 7.950/2013 | Arts. 158-A a 158-F do CPP', st['dado_valor'])],
        [Paragraph('Validade',    st['dado_label']),
         Paragraph('30 (trinta) dias a contar da data de emissão', st['dado_valor'])],
        [Paragraph('Emitido por', st['dado_label']),
         Paragraph(emitido_por_txt, st['dado_valor'])],
    ]
    base_tbl = Table(base_legal_rows, colWidths=[3.0 * cm, 14.4 * cm])
    base_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), CINZA_CLARO),
        ('LINEBELOW',     (0, 0), (-1, -2), 0.5, BORDAS),
        ('BOX',           (0, 0), (-1, -1), 1, BORDAS),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (-1, -1), 12),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(base_tbl)
    story.append(Spacer(1, 0.5 * cm))

    # ── Bloco de identificação do emissor (visual diferente por modo) ────────
    AZUL_ESCURO       = colors.HexColor('#1e3a5f')
    CINZA_VERY_LIGHT  = colors.HexColor('#f1f5f9')
    AZUL_VERY_LIGHT   = colors.HexColor('#e8f0f8')
    VERDE_ESCURO      = colors.HexColor('#14532d')
    VERDE_VERY_LIGHT  = colors.HexColor('#f0fdf4')

    if is_externo:
        # Comprovante: o emissor é o sistema / a consulta foi feita pelo usuário externo
        cor_borda  = CINZA_ESCURO
        cor_fundo  = CINZA_VERY_LIGHT
        cor_labels = colors.HexColor('#e2e8f0')
        titulo_selo = '◆ REGISTRO DE CONSULTA'
        linhas_selo = [
            [Paragraph(titulo_selo, ParagraphStyle('st', parent=base['Normal'],
                       fontName='Helvetica-Bold', fontSize=8, textColor=CINZA_ESCURO)), Paragraph('')],
            [Paragraph('Consulta realizada por:', selo_label), Paragraph(emissor_nome, selo_valor)],
        ]
        if unidade_nome:
            linhas_selo.append([Paragraph('Órgão / Unidade:', selo_label), Paragraph(unidade_nome, selo_valor)])
        linhas_selo += [
            [Paragraph('Data/Hora da consulta:', selo_label),
             Paragraph(f'{emissao_fmt} (horário de Boa Vista — UTC-4)', selo_valor)],
            [Paragraph('Protocolo de registro:', selo_label),
             Paragraph(f'<b>{protocolo_fmt}</b>', selo_valor)],
            [Paragraph(''),
             Paragraph(
                 'Comprovante gerado automaticamente pelo Sistema SPR-Criminalística. '
                 'O resultado reflete o estado do banco de dados na data e hora da consulta.',
                 nota_mp,
             )],
        ]
    else:
        # Certidão: assinatura eletrônica pessoal do perito
        cor_borda  = AZUL_ESCURO
        cor_fundo  = AZUL_VERY_LIGHT
        cor_labels = colors.HexColor('#dbeafe')
        titulo_selo = '✦ ASSINATURA ELETRÔNICA'
        linhas_selo = [
            [Paragraph(titulo_selo, ParagraphStyle('st', parent=base['Normal'],
                       fontName='Helvetica-Bold', fontSize=8, textColor=AZUL_ESCURO)), Paragraph('')],
            [Paragraph('Responsável pela emissão:', selo_label), Paragraph(emissor_nome,   selo_valor)],
            [Paragraph('Perfil no sistema:',        selo_label), Paragraph(emissor_perfil, selo_valor)],
        ]
        if emissor_cpf:
            linhas_selo.append([Paragraph('CPF:', selo_label), Paragraph(emissor_cpf, selo_valor)])
        linhas_selo += [
            [Paragraph('E-mail institucional:', selo_label), Paragraph(emissor_email, selo_valor)],
            [Paragraph('Data/Hora da emissão:', selo_label),
             Paragraph(f'{emissao_fmt} (horário de Boa Vista — UTC-4)', selo_valor)],
            [Paragraph('Protocolo de autenticidade:', selo_label),
             Paragraph(f'<b>{protocolo_fmt}</b>', selo_valor)],
            [Paragraph(''),
             Paragraph(
                 'Documento gerado eletronicamente pelo Sistema SPR-Criminalística. '
                 'Dispensa assinatura manuscrita conforme MP nº 2.200-2/2001.',
                 nota_mp,
             )],
        ]

    selo_tbl = Table(linhas_selo, colWidths=[4.5 * cm, 12.9 * cm])
    selo_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), cor_fundo),
        ('BOX',           (0, 0), (-1, -1), 1.5, cor_borda),
        ('LINEBELOW',     (0, 0), (-1,  0), 1.5, cor_borda),
        ('LINEBELOW',     (0, 1), (-1, -2), 0.4, BORDAS),
        ('BACKGROUND',    (0, 1), (0, -2),  cor_labels),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('SPAN',          (0, 0), (1,  0)),
        ('ALIGN',         (0, 0), (1,  0), 'CENTER'),
        ('SPAN',          (0, -1), (1, -1)),
    ]))
    story.append(selo_tbl)
    story.append(Spacer(1, 0.3 * cm))

    # ── Nota final de autenticidade ───────────────────────────────────────────
    story.append(HRFlowable(width='100%', thickness=0.5, color=BORDAS))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(
        'A autenticidade deste documento pode ser verificada pelo QR Code no rodapé. '
        f'Chave: <b>{protocolo_fmt}</b>. '
        'Qualquer alteração no conteúdo invalida o protocolo e torna este documento sem efeito.',
        st['rodape_legal'],
    ))

    # ── Construção do PDF ─────────────────────────────────────────────────────
    def rodape_cb(canvas, doc_):
        _gerar_rodape(canvas, doc_, request, url_validacao, tag_rodape)

    doc.build(story, onFirstPage=rodape_cb, onLaterPages=rodape_cb)
    buffer.seek(0)
    nome_arquivo = f'{nome_arquivo_prefix}_{now.strftime("%Y%m%d_%H%M")}_{protocolo[:8]}.pdf'
    return FileResponse(buffer, as_attachment=False, filename=nome_arquivo, content_type='application/pdf')


# ═══════════════════════════════════════════════════════════════════════════════
# Relatório em Lote — Vestígios (formato paisagem)
# ═══════════════════════════════════════════════════════════════════════════════

def gerar_relatorio_vestigios(qs, request, filtros_desc: str = 'Todos os registros'):
    from django.http import FileResponse

    buffer = io.BytesIO()
    pg = landscape(A4)
    doc = SimpleDocTemplate(
        buffer, pagesize=pg,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.2 * cm, bottomMargin=3.8 * cm,
        title='Relatório de Vestígios — SPR-Criminalística',
    )

    st   = _estilos()
    base = getSampleStyleSheet()
    story = []

    st_cab_col = ParagraphStyle('rcab', parent=base['Normal'],
                                fontName='Helvetica-Bold', fontSize=7, textColor=PRETO)
    st_cel     = ParagraphStyle('rcel', parent=base['Normal'],
                                fontName='Helvetica', fontSize=7.5, textColor=PRETO, leading=10)
    st_cel_b   = ParagraphStyle('rcelb', parent=base['Normal'],
                                fontName='Helvetica-Bold', fontSize=7.5, textColor=PRETO, leading=10)
    st_filtros  = ParagraphStyle('rfilt', parent=base['Normal'],
                                fontName='Helvetica-Oblique', fontSize=8,
                                textColor=CINZA_MEDIO, leading=11)

    _construir_cabecalho(story, st, 'RELATÓRIO DE VESTÍGIOS',
                         'Custódia de Vestígios — Sistema SPR-Criminalística')

    # ── Bloco de filtros + total ──────────────────────────────────────────────
    total = qs.count()
    story.append(Paragraph(f'<b>Filtros aplicados:</b> {filtros_desc}', st_filtros))
    story.append(Paragraph(f'<b>Total de registros:</b> {total}', st_filtros))
    story.append(Spacer(1, 0.3 * cm))

    if total == 0:
        story.append(Paragraph('Nenhum registro encontrado para os filtros informados.', st_filtros))
    else:
        # ── Tabela ───────────────────────────────────────────────────────────
        # Larguras: 1.0 + 3.5 + 4.0 + 3.0 + 2.5 + 1.2 + 3.5 + 4.5 + 3.5 = 26.7cm
        col_w = [1.0, 3.5, 4.0, 3.0, 2.5, 1.2, 3.5, 4.5, 3.5]
        col_w = [c * cm for c in col_w]

        cabecalho = [Paragraph(t, st_cab_col) for t in [
            '#', 'Lacre', 'Processo SEI', 'Ocorrência', 'Status',
            'Bio', 'Serviço', 'Unidade', 'Registrado em',
        ]]
        rows = [cabecalho]

        _status_label = {'INICIAL': 'Inicial', 'ANDAMENTO': 'Andamento', 'FINALIZADO': 'Finalizado'}
        for v in qs.select_related('servico_pericial', 'unidade_demandante', 'created_by'):
            ocorrencia_txt = v.ocorrencia or '—'
            if v.ano_ocorrencia:
                ocorrencia_txt += f'/{v.ano_ocorrencia}'
            rows.append([
                Paragraph(str(v.id), st_cel),
                Paragraph(v.lacre or '—', st_cel_b),
                Paragraph(v.num_processo_sei or '—', st_cel),
                Paragraph(ocorrencia_txt, st_cel),
                Paragraph(_status_label.get(v.status, v.status), st_cel_b),
                Paragraph('S' if v.biologico else 'N', st_cel),
                Paragraph(v.servico_pericial.sigla if v.servico_pericial else '—', st_cel),
                Paragraph(str(v.unidade_demandante) if v.unidade_demandante else '—', st_cel),
                Paragraph(_formatar_dt(v.created_at)[:10], st_cel),
            ])

        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            ('LINEBELOW',     (0, 0), (-1, 0), 1.5, PRETO),
            ('LINEBELOW',     (0, 1), (-1, -1), 0.4, BORDAS),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BRANCO, CINZA_CLARO]),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING',   (0, 0), (-1, -1), 3),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(tbl)

    emissor = request.user.nome_completo if hasattr(request.user, 'nome_completo') else str(request.user)
    url_val = f"{request.build_absolute_uri('/').rstrip('/')}/#/gabinete-virtual/custodia/vestigios"
    tag = f'Relatório Vestígios — {timezone.now().strftime("%d/%m/%Y %H:%M")}'

    def rodape_cb(canvas, doc_):
        _gerar_rodape(canvas, doc_, request, url_val, tag)

    doc.build(story, onFirstPage=rodape_cb, onLaterPages=rodape_cb)
    buffer.seek(0)
    nome = f'relatorio_vestigios_{timezone.now().strftime("%Y%m%d_%H%M")}.pdf'
    return FileResponse(buffer, as_attachment=False, filename=nome, content_type='application/pdf')


# ═══════════════════════════════════════════════════════════════════════════════
# Relatório em Lote — DNAs (formato paisagem)
# ═══════════════════════════════════════════════════════════════════════════════

def gerar_relatorio_dnas(qs, request, filtros_desc: str = 'Todos os registros'):
    from django.http import FileResponse

    buffer = io.BytesIO()
    pg = landscape(A4)
    doc = SimpleDocTemplate(
        buffer, pagesize=pg,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.2 * cm, bottomMargin=3.8 * cm,
        title='Relatório de Perfis Genéticos — SPR-Criminalística',
    )

    st   = _estilos()
    base = getSampleStyleSheet()
    story = []

    st_cab_col = ParagraphStyle('rcab2', parent=base['Normal'],
                                fontName='Helvetica-Bold', fontSize=7, textColor=PRETO)
    st_cel     = ParagraphStyle('rcel2', parent=base['Normal'],
                                fontName='Helvetica', fontSize=7.5, textColor=PRETO, leading=10)
    st_cel_b   = ParagraphStyle('rcelb2', parent=base['Normal'],
                                fontName='Helvetica-Bold', fontSize=7.5, textColor=PRETO, leading=10)
    st_filtros  = ParagraphStyle('rfilt2', parent=base['Normal'],
                                fontName='Helvetica-Oblique', fontSize=8,
                                textColor=CINZA_MEDIO, leading=11)

    _construir_cabecalho(story, st, 'RELATÓRIO DE PERFIS GENÉTICOS (DNA)',
                         'Banco Nacional de Perfis Genéticos — Lei nº 12.654/2012 e Decreto nº 7.950/2013')

    total = qs.count()
    story.append(Paragraph(f'<b>Filtros aplicados:</b> {filtros_desc}', st_filtros))
    story.append(Paragraph(f'<b>Total de registros:</b> {total}', st_filtros))
    story.append(Spacer(1, 0.3 * cm))

    if total == 0:
        story.append(Paragraph('Nenhum registro encontrado para os filtros informados.', st_filtros))
    else:
        # Larguras: 1.0 + 5.5 + 3.0 + 2.5 + 2.5 + 2.5 + 4.7 + 2.0 + 3.0 = 26.7cm
        col_w = [1.0, 5.5, 3.0, 2.5, 2.5, 2.5, 4.7, 2.0, 3.0]
        col_w = [c * cm for c in col_w]

        cabecalho = [Paragraph(t, st_cab_col) for t in [
            '#', 'Nome', 'CPF', 'Situação', 'Finalidade',
            'Data Coleta', 'Perito', 'Vestígio', 'Registrado em',
        ]]
        rows = [cabecalho]

        _sit_label  = {'APENADO': 'Apenado', 'NAO_APENADO': 'Não Apenado'}
        _fin_label  = {'LEI': 'Lei 12.654', 'DJ': 'Dec. Judicial'}
        for d in qs.select_related('perito', 'vestigio', 'created_by'):
            rows.append([
                Paragraph(str(d.id), st_cel),
                Paragraph(d.nome or '—', st_cel_b),
                Paragraph(d.cpf or '—', st_cel),
                Paragraph(_sit_label.get(d.situacao, d.situacao), st_cel),
                Paragraph(_fin_label.get(d.finalidade_coleta, d.finalidade_coleta), st_cel),
                Paragraph(_formatar_dt(d.data_da_coleta)[:10], st_cel),
                Paragraph(d.perito.nome_completo if d.perito else '—', st_cel),
                Paragraph(f'#{d.vestigio_id}' if d.vestigio_id else '—', st_cel),
                Paragraph(_formatar_dt(d.created_at)[:10], st_cel),
            ])

        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            ('LINEBELOW',     (0, 0), (-1, 0), 1.5, PRETO),
            ('LINEBELOW',     (0, 1), (-1, -1), 0.4, BORDAS),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [BRANCO, CINZA_CLARO]),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING',   (0, 0), (-1, -1), 3),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(tbl)

    url_val = f"{request.build_absolute_uri('/').rstrip('/')}/#/gabinete-virtual/custodia/dnas"
    tag = f'Relatório DNA — {timezone.now().strftime("%d/%m/%Y %H:%M")}'

    def rodape_cb(canvas, doc_):
        _gerar_rodape(canvas, doc_, request, url_val, tag)

    doc.build(story, onFirstPage=rodape_cb, onLaterPages=rodape_cb)
    buffer.seek(0)
    nome = f'relatorio_dnas_{timezone.now().strftime("%Y%m%d_%H%M")}.pdf'
    return FileResponse(buffer, as_attachment=False, filename=nome, content_type='application/pdf')