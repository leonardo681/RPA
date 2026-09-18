"""Faturas demonstrativas com QR de acesso e Code128 não bancário."""
from datetime import date
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
from xml.sax.saxutils import escape

import qrcode
from reportlab.graphics.barcode import code128
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether

from techsolutions.services.validation import format_brl


def invoice_link(settings, invoice):
    base = settings.public_base_url.rstrip("/")
    url = urlsplit(base)
    if url.scheme not in ("http", "https") or not url.hostname or url.query or url.fragment or url.username:
        raise ValueError("PUBLIC_BASE_URL deve ser uma URL HTTP(S) sem credenciais, consulta ou fragmento.")
    return f"{base}/f/{invoice['token']}"


def _fingerprint(settings, invoice):
    keys = ("id", "cliente_id", "nome", "email", "telefone", "endereco", "valor_centavos", "data_vencimento", "data_emissao", "token")
    fields = {key: invoice[key] for key in keys}
    fields["link"] = invoice_link(settings, invoice)
    return sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def pdf_path(settings, invoice):
    return settings.pdf_dir / f"fatura_{invoice['id']:06d}_cliente_{invoice['cliente_id']:06d}.pdf"


def validate_pdf(settings, repo, invoice):
    path = pdf_path(settings, invoice).resolve()
    registered = repo.pdf_record(invoice["id"])
    if Path(invoice["caminho_pdf"]).resolve() != path or not registered or Path(registered["caminho"]).resolve() != path:
        raise ValueError("PDF não associado à fatura. Gere os PDFs novamente.")
    if not path.is_file():
        raise ValueError("PDF inexistente. Gere os PDFs novamente.")
    if registered["fingerprint"] != _fingerprint(settings, invoice):
        raise ValueError("Dados da fatura ou cliente mudaram. Gere o PDF e exporte novamente.")
    if sha256(path.read_bytes()).hexdigest() != registered["sha256"]:
        raise ValueError("PDF modificado ou trocado após a geração. Gere novamente.")
    return path


def generate_pdf(settings, repo, invoice_id):
    invoice = repo.get_invoice(invoice_id)
    path = pdf_path(settings, invoice)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.stem + f".{uuid4().hex}.tmp.pdf")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("Brand", fontName="Helvetica-Bold", fontSize=24, leading=29, textColor=colors.HexColor("#163b61")))
    styles.add(ParagraphStyle("Muted", fontSize=9, leading=13, textColor=colors.HexColor("#536779")))
    styles.add(ParagraphStyle("Notice", fontName="Helvetica-Bold", fontSize=11, leading=16, alignment=TA_CENTER, textColor=colors.HexColor("#8b350c")))
    styles.add(ParagraphStyle("Value", fontName="Helvetica-Bold", fontSize=22, leading=28, textColor=colors.HexColor("#163b61")))
    para = lambda value, style="Normal": Paragraph(escape(str(value)), styles[style])
    story = [Table([[para("TS", "Brand"), [para("TechSolutions Ltda", "Brand"), para("Tecnologia que simplifica. | Empresa fictícia", "Muted")]]], colWidths=[20*mm, 154*mm]), Spacer(1, 10*mm),
             para("FATURA DEMONSTRATIVA — SEM VALIDADE PARA PAGAMENTO", "Notice"), Spacer(1, 8*mm),
             para(f"Fatura nº {invoice['id']:06d}", "Heading1"),
             para(f"Emissão: {invoice['data_emissao'][:10]}  |  Vencimento: {date.fromisoformat(invoice['data_vencimento']).strftime('%d/%m/%Y')}", "Muted"), Spacer(1, 7*mm),
             para("DADOS DO CLIENTE", "Heading3"), para(invoice["nome"], "Heading2"), para(invoice["endereco"]),
             para(f"E-mail: {invoice['email']}"), para(f"Telefone: +{invoice['telefone']}"), Spacer(1, 8*mm)]
    summary = Table([[para("Serviços de tecnologia — cobrança de demonstração"), para(f"R$ {format_brl(invoice['valor_centavos'])}", "Value")]], colWidths=[110*mm, 64*mm])
    summary.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,-1),colors.HexColor("#edf4fa")),("BOX",(0,0),(-1,-1),0.5,colors.HexColor("#d4e2ed")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),14),("BOTTOMPADDING",(0,0),(-1,-1),14)]))
    story += [summary, Spacer(1, 8*mm)]
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4)
    qr.add_data(invoice_link(settings, invoice))
    qr.make(fit=True)
    buffer = BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
    buffer.seek(0)
    barcode_id = f"TS-FAT-{invoice['id']:06d}-CLI-{invoice['cliente_id']:06d}"
    barcode = code128.Code128(barcode_id, barHeight=18*mm, barWidth=0.29*mm, humanReadable=True)
    codes = Table([[Image(buffer, width=48*mm, height=48*mm), [para("CONSULTE SUA FATURA", "Heading3"), para("Leia o QR Code para abrir a página desta fatura. O link permite acesso a quem o possui; compartilhe somente com o destinatário.", "Muted"), Spacer(1, 4*mm), barcode, Spacer(1, 4*mm), para("Código interno de identificação. Não é linha digitável bancária.", "Muted")]]], colWidths=[54*mm, 120*mm])
    codes.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story += [KeepTogether(codes), Spacer(1, 7*mm), para("INSTRUÇÕES DE DEMONSTRAÇÃO", "Heading3"),
              para("Este documento não é boleto registrado nem PIX. O QR Code contém uma URL de consulta, sem ordem de pagamento. Não efetue pagamentos com este documento.", "Muted"), Spacer(1, 3*mm),
              para("A situação financeira é atualizada apenas pelo registro manual de pagamento no sistema. Envio de mensagem ou leitura do QR Code não comprova pagamento.", "Muted")]

    def footer(canvas, doc):
        canvas.setTitle(f"Fatura TechSolutions {invoice['id']:06d}")
        canvas.setAuthor("TechSolutions Ltda — demonstração acadêmica")
        canvas.setSubject(f"TechSolutions;fatura={invoice['id']};cliente={invoice['cliente_id']}")
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#536779"))
        canvas.drawString(18*mm, 13*mm, "TechSolutions Ltda | Documento acadêmico demonstrativo")
        canvas.drawRightString(A4[0]-18*mm, 13*mm, f"Página {doc.page}")

    try:
        doc = SimpleDocTemplate(str(temp), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=22*mm)
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        temp.replace(path)
        repo.register_pdf(invoice_id, path.resolve(), sha256(path.read_bytes()).hexdigest(), _fingerprint(settings, invoice))
    finally:
        temp.unlink(missing_ok=True)
    return path


def generate_all_pdfs(settings, repo, stop_event=None, log=print, progress=lambda done,total:None):
    invoices = repo.list_invoices()
    result = {"sucessos": 0, "falhas": 0, "ignorados": 0}
    for index, invoice in enumerate(invoices):
        if stop_event is not None and stop_event.is_set():
            result["ignorados"] += len(invoices)-index
            break
        try:
            path = generate_pdf(settings, repo, invoice["id"])
            log(f"PDF gerado: {path.name}")
            result["sucessos"] += 1
        except Exception as exc:
            log(f"Falha PDF fatura {invoice['id']}: {exc}")
            result["falhas"] += 1
        progress(index+1, len(invoices))
    return result
