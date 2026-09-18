"""A planilha é a entrada; o banco é a autoridade sobre vínculo e idempotência."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Event, Lock

from techsolutions.reports.excel import read_report, sync_report_row
from techsolutions.reports.pdf import invoice_link, validate_pdf
from techsolutions.services.validation import format_brl, normalize_phone, validate_email
from .emailer import DeliveryError, send_email
from .whatsapp import WhatsAppSender, validate_accessible_link

_ERROR_LOCK = Lock()


def _integer(value, label):
    try:
        number = Decimal(str(value).strip())
        if not number.is_finite() or number != number.to_integral_value() or number < 1:
            raise ValueError
        return int(number)
    except (ValueError, InvalidOperation) as exc:
        raise ValueError(f"{label} deve ser um inteiro positivo.") from exc


def _iso_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value).strip()[:10]).isoformat()


def _cents(value):
    try:
        text = str(value).strip().replace("R$", "").strip()
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        amount = Decimal(text) * 100
        if not amount.is_finite() or amount != amount.to_integral_value():
            raise ValueError
        return int(amount)
    except (ValueError, InvalidOperation) as exc:
        raise ValueError("Valor do relatório inválido ou com mais de duas casas decimais.") from exc


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError("O anexo não tem um cabeçalho PDF válido.")
        stream.seek(0)
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(item):
    content = {key: value for key, value in item.items() if key != "fingerprint"}
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _build_item(settings, repo, invoice, row, channel):
    invoice_id = int(invoice["id"])
    client_id = int(invoice["cliente_id"])
    reason = f"Relatório divergente da fatura {invoice_id}; exporte novamente. Campo: "
    if _integer(row["cliente_id"], "cliente_id") != client_id:
        raise ValueError(reason + "cliente_id")
    for field, column in (("nome", "nome"), ("email", "email"), ("telefone", "telefone")):
        if str(row[column]).strip() != str(invoice[field]).strip():
            raise ValueError(reason + column)
    if _cents(row["valor"]) != int(invoice["valor_centavos"]):
        raise ValueError(reason + "valor")
    due = _iso_date(invoice["data_vencimento"])
    if _iso_date(row["vencimento"]) != due:
        raise ValueError(reason + "vencimento")
    if str(row["status_fatura"]).strip() not in {str(invoice["status"]), str(invoice.get("situacao", invoice["status"]))}:
        raise ValueError(reason + "status_fatura")
    link = invoice_link(settings, invoice)
    if str(row["link_fatura"]).strip() != link:
        raise ValueError(reason + "link_fatura")
    canonical = Path(settings.pdf_dir).resolve() / f"fatura_{invoice_id:06d}_cliente_{client_id:06d}.pdf"
    saved_path = Path(str(invoice.get("caminho_pdf") or ""))
    row_path = Path(str(row.get("caminho_pdf") or ""))
    if not saved_path.is_absolute():
        saved_path = Path(settings.base_dir) / saved_path
    if not row_path.is_absolute():
        row_path = Path(settings.base_dir) / row_path
    if saved_path.resolve() != canonical or row_path.resolve() != canonical:
        raise ValueError(reason + "caminho_pdf (gere os PDFs antes da exportação)")
    original = validate_email(invoice["email"]) if channel == "email" else normalize_phone(invoice["telefone"])
    override = settings.test_email if channel == "email" else settings.test_phone
    recipient = (validate_email(override) if channel == "email" else normalize_phone(override)) if override else original
    due_br = date.fromisoformat(due).strftime("%d/%m/%Y")
    value = format_brl(int(invoice["valor_centavos"]))
    value = str(value).replace("R$", "").strip()
    subject = f"Fatura TechSolutions - Vencimento {due_br}"
    if channel == "whatsapp":
        message = (f"Olá, {invoice['nome']}! Aqui é da TechSolutions. Sua fatura nº {invoice_id}, "
                   f"no valor de R$ {value}, vence em {due_br}. Segue sua fatura com QR Code. "
                   "Caso já tenha efetuado o pagamento, desconsidere esta mensagem.\n\n"
                   f"{link}\n\nFATURA DEMONSTRATIVA — SEM VALIDADE PARA PAGAMENTO.")
    else:
        message = (f"Olá, {invoice['nome']}!\n\n"
                   f"Encaminhamos em anexo sua fatura TechSolutions nº {invoice_id}, "
                   f"no valor de R$ {value}, com vencimento em {due_br}.\n"
                   "Por gentileza, confira os dados. Caso já tenha efetuado o pagamento, "
                   "desconsidere esta mensagem e entre em contato para atualização do registro.\n\n"
                   "Esta é uma apresentação acadêmica: FATURA DEMONSTRATIVA — SEM VALIDADE PARA PAGAMENTO.\n"
                   "O QR Code permite consultar a fatura; não é um código PIX.\n\n"
                   "Atenciosamente,\nEquipe TechSolutions Ltda")
    validation_error = ""
    digest = ""
    try:
        validate_pdf(settings, repo, invoice)
        digest = _digest(canonical)
    except (OSError, ValueError) as exc:
        validation_error = f"PDF inexistente, desatualizado ou inválido: {canonical.name}. {exc}"
    item = {
        "invoice_id": invoice_id, "client_id": client_id, "name": invoice["nome"],
        "recipient": recipient, "original_recipient": original, "test_override": bool(override),
        "message": message, "subject": subject, "pdf_path": str(canonical), "link": link,
        "value_cents": int(invoice["valor_centavos"]), "due_date": due, "channel": channel,
        "pdf_sha256": digest, "validation_error": validation_error,
    }
    item["fingerprint"] = _fingerprint(item)
    return item


def prepare_batch(settings, repo, channel, retry_failed=False):
    """Lê o Excel para revisão; linhas adulteradas bloqueiam o lote antes do envio."""
    if channel not in {"whatsapp", "email"}:
        raise ValueError("Canal inválido; use whatsapp ou email.")
    rows = read_report(Path(settings.report_path))
    batch = []
    seen = set()
    for row in rows:
        invoice_id = _integer(row["fatura_id"], "fatura_id")
        if invoice_id in seen:
            raise ValueError(f"Fatura {invoice_id} repetida no relatório. Exporte novamente.")
        seen.add(invoice_id)
        invoice = repo.get_invoice(invoice_id)
        if not invoice:
            raise ValueError(f"Fatura {invoice_id} não existe no banco. Exporte novamente.")
        if invoice["status"] != "Pendente":
            continue
        state = repo.notification_state(invoice_id, channel)
        eligible = state.get("status", "Pendente") in {"Pendente", "Simulado"} or (retry_failed and state.get("status") == "Falha")
        if not eligible:
            continue
        if str(row.get(f"status_{channel}", "")).strip() != state.get("status", "Pendente"):
            raise ValueError(f"Status de {channel} da fatura {invoice_id} diverge do banco. Exporte novamente.")
        batch.append(_build_item(settings, repo, invoice, row, channel))
    return batch


def _error_csv(settings, invoice_id, channel, reason):
    path = Path(settings.data_dir) / "erros.csv"
    with _ERROR_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists() or not path.stat().st_size
        with path.open("a", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream, delimiter=";")
            if new:
                writer.writerow(["data_hora", "fatura", "canal", "motivo"])
            writer.writerow([datetime.now().astimezone().isoformat(timespec="seconds"), invoice_id, channel, reason])


def _fresh_item(settings, repo, item):
    """Relê a linha por identificador imediatamente antes de cada tentativa."""
    candidates = [row for row in read_report(Path(settings.report_path))
                  if _integer(row["fatura_id"], "fatura_id") == item["invoice_id"]]
    if len(candidates) != 1:
        raise ValueError("Fatura ausente ou repetida no relatório após a revisão.")
    invoice = repo.get_invoice(item["invoice_id"])
    if not invoice or invoice["status"] != "Pendente":
        raise ValueError("A fatura deixou de estar financeiramente elegível.")
    current = _build_item(settings, repo, invoice, candidates[0], item["channel"])
    if current["fingerprint"] != item["fingerprint"]:
        raise ValueError("Dados, destinatário ou anexo mudaram após a revisão. Revise um novo lote.")
    return current


def run_batch(settings, repo, channel, demo=True, retry_failed=False, approved_batch=None,
              stop_event=None, log=print, progress=lambda done, total: None,
              wait_for_login=None):
    """Revisa, reserva, tenta, confirma no banco e sincroniza Excel a cada registro.

    Se o programa terminar após reservar, Em processamento exige conferência
    manual. Falhas de resultado ambíguo nunca entram em reprocessamento automático.
    """
    stop = stop_event or Event()
    batch = prepare_batch(settings, repo, channel, retry_failed=retry_failed)
    if not demo:
        if approved_batch is None:
            raise ValueError("O envio real exige revisão e aprovação explícita do lote na interface.")
        current = [(item["invoice_id"], item["fingerprint"]) for item in batch]
        approved = [(item["invoice_id"], item["fingerprint"]) for item in approved_batch]
        if current != approved:
            raise ValueError("O lote mudou após a revisão. Exporte e revise novamente antes do envio real.")
    summary = {"sucessos": 0, "falhas": 0, "ignorados": max(0, len(read_report(Path(settings.report_path))) - len(batch)), "simulados": 0}
    progress(0, len(batch))
    sender = WhatsAppSender(settings, stop_event=stop, log=log, wait_for_login=wait_for_login) if channel == "whatsapp" and not demo else None
    try:
        for number, item in enumerate(batch, start=1):
            if stop.is_set():
                log("Interrupção segura: resultados concluídos preservados.")
                break
            invoice_id = item["invoice_id"]
            attempt = None
            status = "Falha"
            error = ""
            evidence = ""
            try:
                if not demo:
                    attempt = repo.claim_notification(invoice_id, channel, retry_failed=retry_failed)
                    if attempt is None:
                        summary["ignorados"] += 1
                        log(f"Fatura {invoice_id}: ignorada; já reservada, concluída ou inelegível.")
                        progress(number, len(batch))
                        continue
                    # Publica a reserva no Excel antes de qualquer ação externa.
                    sync_report_row(settings, repo, invoice_id)
                item = _fresh_item(settings, repo, item)
                if item["validation_error"]:
                    raise DeliveryError(item["validation_error"])
                log(f"{'SIMULAÇÃO' if demo else 'ENVIO REAL'} — {channel} — fatura {invoice_id} — destinatário {item['recipient']}")
                log(f"PDF: {item['pdf_path']}\nMensagem prevista:\n{item['message']}")
                if demo:
                    status = "Simulado"
                    evidence = "Prévia local; nenhum navegador de mensagem ou servidor SMTP foi acionado."
                    summary["simulados"] += 1
                    summary["sucessos"] += 1
                else:
                    if stop.is_set():
                        raise DeliveryError("Interrupção solicitada antes da transmissão.")
                    if channel == "whatsapp":
                        validate_accessible_link(item["link"])
                        result = sender.send(item)
                    else:
                        result = send_email(settings, item)
                    status = result["status"]
                    evidence = result.get("evidence", "")
                    summary["sucessos"] += 1
            except Exception as exc:
                status = "Não confirmado" if getattr(exc, "uncertain", False) else "Falha"
                error = str(exc) or type(exc).__name__
                summary["falhas"] += 1
                _error_csv(settings, invoice_id, channel, error)
                log(f"Fatura {invoice_id}: {status} — {error}")
            # A persistência está fora do try de envio. Se ela falhar, não avançamos
            # para outro destinatário nem convertimos uma aceitação em falha segura.
            if attempt is not None:
                repo.finish_notification(attempt, status, error=error, recipient=item["recipient"],
                                         message=item["message"], evidence=evidence)
            elif demo:
                repo.record_notification(invoice_id, channel, "Simulado", error=error,
                                         recipient=item["recipient"], message=item["message"],
                                         evidence=evidence or "Prévia inválida; nenhuma tentativa real foi realizada.", simulated=True)
            else:
                raise RuntimeError(f"Não foi possível reservar a tentativa da fatura {invoice_id}: {error}")
            try:
                sync_report_row(settings, repo, invoice_id)
            except Exception as exc:
                reason = f"Resultado salvo no banco, mas não foi possível atualizar o Excel: {exc}. Feche a planilha e exporte novamente."
                _error_csv(settings, invoice_id, channel, reason)
                raise RuntimeError(reason) from exc
            log(f"Fatura {invoice_id}: {status}. {evidence}")
            progress(number, len(batch))
    finally:
        if sender is not None:
            sender.close()
    return summary
