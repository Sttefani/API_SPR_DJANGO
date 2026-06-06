# protocolos/pdf_generator.py
#
# Gera o Protocolo de Entrega de Material Examinado em PDF.
# Design idêntico ao design forense sóbrio dos outros documentos do SPR.

import io
import os
import qrcode
import qrcode.image.pil

from django.conf import settings
from django.utils import timezone
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from reportlab.platypus.flowables import Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm


# ─── Paleta ───────────────────────────────────────────────────────────────────

PRETO        = colors.HexColor('#000000')
CINZA_ESCURO = colors.HexColor('#1e293b')
CINZA_MEDIO  = colors.HexColor('#64748b')
CINZA_CLARO  = colors.HexColor('#f8fafc')
BORDAS       = colors.HexColor('#cbd5e1')
BRANCO       = colors.white
VERDE_ESCURO = colors.HexColor('#14532d')
VERDE_CLARO  = colors.HexColor('#f0fdf4')
AMARELO_CLARO = colors.HexColor('#fefce8')
AMARELO_BORDA = colors.HexColor('#ca8a04')


# ─── Utilitários ──────────────────────────────────────────────────────────────

def _vazio(v):
    return '—' if (v is None or str(v).strip() == '') else str(v).strip()


def _formatar_dt(dt):
    if dt is None:
        return '—'
    if hasattr(dt, 'strftime'):
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
    return RLImage(buf, width=2.2 * cm, height=2.2 * cm)


def _obter_logo_pc():
    for caminho in [
        os.path.join(settings.BASE_DIR, 'assets', 'logo_pc.png'),
        os.path.join(settings.BASE_DIR, 'static', 'img', 'logo_pc.png'),
        os.path.join(settings.BASE_DIR, 'static', 'logo_pc.png'),
    ]:
        if os.path.exists(caminho):
            return RLImage(caminho, width=1.6 * cm, height=1.6 * cm)
    return ''


# ─── Estilos ──────────────────────────────────────────────────────────────────

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
            fontName='Helvetica-Bold', fontSize=13,
            textColor=PRETO, alignment=TA_CENTER, spaceAfter=2,
        ),
        'numero_proto': ParagraphStyle(
            'numero_proto', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=11,
            textColor=CINZA_ESCURO, alignment=TA_CENTER,
        ),
        'sec_header': ParagraphStyle(
            'sec_header', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=8,
            textColor=BRANCO, leading=11,
        ),
        'label': ParagraphStyle(
            'label', parent=base['Normal'],
            fontName='Helvetica', fontSize=7.5,
            textColor=CINZA_MEDIO, leading=10,
        ),
        'valor': ParagraphStyle(
            'valor', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=9,
            textColor=PRETO, leading=12,
        ),
        'valor_normal': ParagraphStyle(
            'valor_normal', parent=base['Normal'],
            fontName='Helvetica', fontSize=9,
            textColor=PRETO, leading=12,
        ),
        'assin_titulo': ParagraphStyle(
            'assin_titulo', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=8,
            textColor=CINZA_ESCURO,
        ),
        'assin_texto': ParagraphStyle(
            'assin_texto', parent=base['Normal'],
            fontName='Helvetica', fontSize=8,
            textColor=PRETO, leading=11,
        ),
        'assin_legal': ParagraphStyle(
            'assin_legal', parent=base['Normal'],
            fontName='Helvetica-Oblique', fontSize=7.5,
            textColor=CINZA_MEDIO, leading=10,
        ),
        'rodape': ParagraphStyle(
            'rodape', parent=base['Normal'],
            fontName='Helvetica', fontSize=7,
            textColor=CINZA_MEDIO, alignment=TA_CENTER, leading=9,
        ),
        'pendente': ParagraphStyle(
            'pendente', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=9,
            textColor=AMARELO_BORDA, alignment=TA_CENTER,
        ),
        'assinado': ParagraphStyle(
            'assinado', parent=base['Normal'],
            fontName='Helvetica-Bold', fontSize=9,
            textColor=VERDE_ESCURO, alignment=TA_CENTER,
        ),
    }


# ─── Bloco de seção com cabeçalho cinza escuro ────────────────────────────────

def _secao(st, titulo: str, linhas: list, largura: float) -> Table:
    """
    Monta uma tabela-seção: header cinza escuro + linhas de label/valor.
    `linhas` = lista de tuples (label, valor) ou (None, texto_inteiro).
    """
    header_row = [
        Paragraph(f'▌  {titulo}', st['sec_header']),
        '',
    ]

    data = [header_row]
    for label, valor in linhas:
        if label is None:
            data.append([Paragraph(valor, st['valor_normal']), ''])
        else:
            data.append([
                Paragraph(label, st['label']),
                Paragraph(_vazio(valor), st['valor']),
            ])

    col_w = [largura * 0.28, largura * 0.72]
    tbl = Table(data, colWidths=col_w)
    tbl.setStyle(TableStyle([
        # Header
        ('BACKGROUND',  (0, 0), (-1, 0), CINZA_ESCURO),
        ('SPAN',        (0, 0), (-1, 0)),
        ('TOPPADDING',  (0, 0), (-1, 0), 5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('LEFTPADDING', (0, 0), (-1, 0), 8),
        # Linhas de dados
        ('BACKGROUND',  (0, 1), (-1, -1), CINZA_CLARO),
        ('TOPPADDING',  (0, 1), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
        ('LEFTPADDING', (0, 1), (-1, -1), 8),
        ('RIGHTPADDING', (0, 1), (-1, -1), 8),
        # Bordas externas
        ('BOX',         (0, 0), (-1, -1), 0.5, BORDAS),
        ('LINEBELOW',   (0, 0), (-1, 0),  0.5, BORDAS),
        # Separadores internos
        ('LINEBELOW',   (0, 1), (-1, -2), 0.3, BORDAS),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return tbl


def _secao_texto(st, titulo: str, texto: str, largura: float) -> Table:
    """Seção com bloco de texto corrido (descrição, observações)."""
    data = [
        [Paragraph(f'▌  {titulo}', st['sec_header']), ''],
        [Paragraph(_vazio(texto), st['valor_normal']), ''],
    ]
    col_w = [largura, 0]
    tbl = Table(data, colWidths=[largura, 0.001])
    tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), CINZA_ESCURO),
        ('SPAN',          (0, 0), (-1, 0)),
        ('SPAN',          (0, 1), (-1, 1)),
        ('TOPPADDING',    (0, 0), (-1, 0), 5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('LEFTPADDING',   (0, 0), (-1, 0), 8),
        ('BACKGROUND',    (0, 1), (-1, 1), CINZA_CLARO),
        ('TOPPADDING',    (0, 1), (-1, 1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 6),
        ('LEFTPADDING',   (0, 1), (-1, 1), 8),
        ('RIGHTPADDING',  (0, 1), (-1, 1), 8),
        ('BOX',           (0, 0), (-1, -1), 0.5, BORDAS),
        ('LINEBELOW',     (0, 0), (-1, 0), 0.5, BORDAS),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
    ]))
    return tbl


# ─── Bloco de assinatura ──────────────────────────────────────────────────────

def _bloco_assinatura(st, protocolo, largura: float) -> Table:
    """
    Dois blocos lado a lado: Entregador (sempre assinado eletronicamente)
    e Recebedor (pendente / eletrônico / manual).
    """
    from .models import ProtocoloEntrega

    col_w = [(largura - 0.4 * cm) / 2, (largura - 0.4 * cm) / 2]

    # — Entregador —
    entrega_linhas = [
        Paragraph('RESPONSÁVEL PELA ENTREGA', st['assin_titulo']),
        Spacer(1, 3),
        Paragraph(protocolo.entregue_por_nome, st['assin_texto']),
        Paragraph(protocolo.entregue_por_cargo, st['assin_texto']),
        Paragraph(f'CPF: {_vazio(protocolo.entregue_por_cpf)}', st['assin_texto']),
        Spacer(1, 4),
        Paragraph(_formatar_dt(protocolo.entregue_em), st['assin_texto']),
        Spacer(1, 4),
        HRFlowable(width='100%', thickness=0.3, color=BORDAS),
        Spacer(1, 3),
        Paragraph(
            'Documento entregue eletronicamente via<br/>SPR-Criminalística — Lei nº 14.063/2020',
            st['assin_legal'],
        ),
    ]

    # — Recebedor —
    status = protocolo.status_recebimento
    receb_linhas = [
        Paragraph('RECEBEDOR', st['assin_titulo']),
        Spacer(1, 3),
        Paragraph(protocolo.recebido_por_nome, st['assin_texto']),
        Paragraph(protocolo.recebido_por_cargo, st['assin_texto']),
    ]
    if protocolo.recebido_por_cpf:
        receb_linhas.append(Paragraph(f'CPF: {protocolo.recebido_por_cpf}', st['assin_texto']))
    if protocolo.recebido_por_matricula:
        receb_linhas.append(Paragraph(f'Matrícula: {protocolo.recebido_por_matricula}', st['assin_texto']))

    receb_linhas += [Spacer(1, 4)]

    if status == ProtocoloEntrega.StatusRecebimento.PENDENTE:
        receb_linhas += [
            Paragraph('⏳  PENDENTE DE RECEBIMENTO', st['pendente']),
            Spacer(1, 4),
            HRFlowable(width='100%', thickness=0.3, color=BORDAS),
            Spacer(1, 3),
            Paragraph(
                'Assinatura eletrônica pendente ou assinatura<br/>manuscrita via impressão física.',
                st['assin_legal'],
            ),
        ]
    elif status == ProtocoloEntrega.StatusRecebimento.ASSINADO_ELETRONICAMENTE:
        receb_linhas += [
            Paragraph(_formatar_dt(protocolo.recebido_em), st['assin_texto']),
            Spacer(1, 4),
            HRFlowable(width='100%', thickness=0.3, color=BORDAS),
            Spacer(1, 3),
            Paragraph(
                '✔  Assinado eletronicamente via<br/>SPR-Criminalística — Lei nº 14.063/2020',
                st['assin_legal'],
            ),
        ]
    else:  # MANUAL
        receb_linhas += [
            Paragraph(_formatar_dt(protocolo.recebido_em), st['assin_texto']),
            Spacer(1, 4),
            HRFlowable(width='100%', thickness=0.3, color=BORDAS),
            Spacer(1, 3),
            Paragraph('✔  Assinatura manuscrita confirmada.', st['assin_legal']),
        ]

    # Montar células
    from reportlab.platypus import KeepTogether

    def _celula(linhas):
        inner = Table([[item] for item in linhas], colWidths=[col_w[0] - 1 * cm])
        inner.setStyle(TableStyle([
            ('TOPPADDING',    (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
        ]))
        return inner

    outer = Table(
        [[_celula(entrega_linhas), _celula(receb_linhas)]],
        colWidths=col_w,
        spaceAfter=0,
    )
    outer.setStyle(TableStyle([
        ('BOX',          (0, 0), (0, 0), 0.5, BORDAS),
        ('BOX',          (1, 0), (1, 0), 0.5, BORDAS),
        ('BACKGROUND',   (0, 0), (-1, -1), CINZA_CLARO),
        ('TOPPADDING',   (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 8),
        ('LEFTPADDING',  (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('LINEAFTER',    (0, 0), (0, -1), 0.5, BORDAS),
    ]))
    return outer


# ─── Função principal ─────────────────────────────────────────────────────────

def gerar_protocolo_pdf(protocolo, buffer=None):
    """
    Gera o PDF do Protocolo de Entrega e escreve em `buffer` (BytesIO).
    Retorna o buffer preenchido.
    """
    if buffer is None:
        buffer = io.BytesIO()

    largura_pag, altura_pag = A4
    margem_h = 1.5 * cm
    margem_v = 1.8 * cm
    largura = largura_pag - 2 * margem_h

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=margem_h,
        rightMargin=margem_h,
        topMargin=margem_v,
        bottomMargin=margem_v,
    )

    st = _estilos()
    story = []

    # ── Cabeçalho ──────────────────────────────────────────────────────────────
    from django.conf import settings as dj_settings
    base_url = getattr(dj_settings, 'SITE_URL', 'http://localhost:4200')
    validacao_url = f'{base_url}/api/protocolos/validar/?protocolo={protocolo.protocolo_hash}'
    qr = _gerar_qrcode(validacao_url)
    logo = _obter_logo_pc()

    cabecalho_txt = Paragraph(
        'POLÍCIA CIVIL DE RORAIMA<br/>'
        '<font size="9">Instituto de Criminalística — ICCRR</font>',
        st['titulo_org'],
    )
    titulo_txt = Paragraph(
        'PROTOCOLO DE ENTREGA DE MATERIAL EXAMINADO',
        st['titulo_doc'],
    )
    numero_txt = Paragraph(f'Nº {protocolo.numero}', st['numero_proto'])

    header_table = Table(
        [[logo, cabecalho_txt, qr]],
        colWidths=[2 * cm, largura - 4.2 * cm, 2.2 * cm],
    )
    header_table.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',        (0, 0), (0, 0),   'LEFT'),
        ('ALIGN',        (1, 0), (1, 0),   'CENTER'),
        ('ALIGN',        (2, 0), (2, 0),   'RIGHT'),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width=largura, thickness=1.5, color=CINZA_ESCURO))
    story.append(Spacer(1, 0.2 * cm))
    story.append(titulo_txt)
    story.append(numero_txt)
    story.append(Spacer(1, 0.25 * cm))
    story.append(HRFlowable(width=largura, thickness=0.5, color=BORDAS))
    story.append(Spacer(1, 0.3 * cm))

    # ── Seção 1: Dados do Vestígio ──────────────────────────────────────────────
    v = protocolo.vestigio
    tipo_label = protocolo.get_tipo_entrega_display()

    story.append(_secao(st, 'DADOS DO VESTÍGIO', [
        ('Lacre na Entrega',  protocolo.lacre_na_entrega or v.lacre),
        ('SEI / Processo',    v.num_processo_sei),
        ('Tipo de Entrega',   tipo_label),
        ('Status do Vestígio',v.get_status_display()),
    ], largura))
    story.append(Spacer(1, 0.25 * cm))

    # ── Seção 2: Descrição do Material ─────────────────────────────────────────
    story.append(_secao_texto(st, 'DESCRIÇÃO DO MATERIAL', protocolo.descricao_material, largura))
    story.append(Spacer(1, 0.25 * cm))

    # ── Seção 3: Vinculações ────────────────────────────────────────────────────
    vinc_linhas = [
        ('Ocorrência', getattr(protocolo.ocorrencia, 'numero_ocorrencia', str(protocolo.ocorrencia_id))),
    ]
    if protocolo.procedimento:
        vinc_linhas.append(('Procedimento', str(protocolo.procedimento)))
    story.append(_secao(st, 'VINCULAÇÕES', vinc_linhas, largura))
    story.append(Spacer(1, 0.25 * cm))

    # ── Seção 4: Destinatário ──────────────────────────────────────────────────
    aut = protocolo.autoridade
    und = protocolo.unidade_demandante
    story.append(_secao(st, 'DESTINATÁRIO', [
        ('Autoridade',         aut.nome),
        ('Cargo',              aut.cargo.nome if aut.cargo else '—'),
        ('Unidade Demandante', und.nome),
    ], largura))
    story.append(Spacer(1, 0.25 * cm))

    # ── Seção 5: Assinaturas ───────────────────────────────────────────────────
    # Título da seção
    story.append(Table(
        [[Paragraph('▌  ASSINATURAS', st['sec_header'])]],
        colWidths=[largura],
        style=TableStyle([
            ('BACKGROUND',    (0, 0), (-1, -1), CINZA_ESCURO),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('LINEBELOW',     (0, 0), (-1, -1), 0.5, BORDAS),
        ]),
    ))
    story.append(_bloco_assinatura(st, protocolo, largura))
    story.append(Spacer(1, 0.25 * cm))

    # ── Observações (se houver) ────────────────────────────────────────────────
    if protocolo.observacoes and protocolo.observacoes.strip():
        story.append(_secao_texto(st, 'OBSERVAÇÕES', protocolo.observacoes, largura))
        story.append(Spacer(1, 0.25 * cm))

    # ── Rodapé ────────────────────────────────────────────────────────────────
    try:
        import zoneinfo
        agora = timezone.now().astimezone(zoneinfo.ZoneInfo('America/Boa_Vista'))
    except Exception:
        agora = timezone.now()
    data_local = agora.strftime('%d/%m/%Y')

    story.append(HRFlowable(width=largura, thickness=0.5, color=BORDAS))
    story.append(Spacer(1, 0.15 * cm))
    story.append(Paragraph(
        f'Boa Vista — RR, {data_local}   |   '
        f'Hash de Autenticidade: <b>{protocolo.protocolo_hash}</b>',
        st['rodape'],
    ))
    story.append(Paragraph(
        f'Validar em: {validacao_url}',
        st['rodape'],
    ))

    doc.build(story)
    return buffer
