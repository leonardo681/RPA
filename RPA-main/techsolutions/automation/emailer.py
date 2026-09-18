"""Envio Gmail: aceitação SMTP não equivale a leitura ou recebimento."""

from __future__ import annotations

import smtplib
import socket
import ssl
import hashlib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from techsolutions.services.validation import validate_email


class DeliveryError(RuntimeError):
    def __init__(self, message, *, uncertain=False):
        super().__init__(message)
        self.uncertain = uncertain


def send_email(settings, item):
    """Recebe somente um item já relacionado, revisado e reservado pelo lote."""
    recipient = validate_email(item["recipient"])
    if not settings.smtp_user or not settings.smtp_password:
        raise DeliveryError("Credenciais Gmail ausentes. Configure SMTP_USER e SMTP_PASSWORD.")
    sender = validate_email(settings.smtp_from or settings.smtp_user)
    if settings.smtp_host != "smtp.gmail.com" or int(settings.smtp_port) not in (465, 587):
        raise DeliveryError("Configure smtp.gmail.com na porta 465 (SSL) ou 587 (STARTTLS).")
    pdf = Path(item["pdf_path"])
    if not pdf.is_file():
        raise DeliveryError(f"PDF inexistente: {pdf.name}")
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = item["subject"]
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=sender.rsplit("@", 1)[-1])
    message.set_content(item["message"])
    contents = pdf.read_bytes()
    if hashlib.sha256(contents).hexdigest() != item["pdf_sha256"]:
        raise DeliveryError("O PDF mudou após a revisão; gere e revise o lote novamente.")
    message.add_attachment(contents, maintype="application", subtype="pdf", filename=pdf.name)
    context = ssl.create_default_context()
    client = None
    sending = False
    try:
        if int(settings.smtp_port) == 465:
            client = smtplib.SMTP_SSL(settings.smtp_host, 465, timeout=30, context=context)
        else:
            client = smtplib.SMTP(settings.smtp_host, 587, timeout=30)
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
        client.login(settings.smtp_user, settings.smtp_password)
        sending = True
        refused = client.send_message(message, from_addr=sender, to_addrs=[recipient])
        if refused:
            raise DeliveryError("O servidor SMTP rejeitou o destinatário.")
        return {
            "status": "Aceito pelo SMTP",
            "evidence": f"SMTP aceitou a mensagem {message['Message-ID']}; recebimento não confirmado.",
        }
    except smtplib.SMTPAuthenticationError as exc:
        raise DeliveryError("Credenciais rejeitadas pelo Gmail. Verifique a senha de app.") from exc
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError) as exc:
        raise DeliveryError(f"Envio rejeitado pelo servidor SMTP ({type(exc).__name__}).") from exc
    except (socket.timeout, TimeoutError, OSError, smtplib.SMTPServerDisconnected) as exc:
        raise DeliveryError(
            "Conexão SMTP interrompida" + (" durante a transmissão; confira manualmente a pasta Enviados." if sending else "; nenhuma mensagem transmitida."),
            uncertain=sending,
        ) from exc
    except smtplib.SMTPException as exc:
        raise DeliveryError(f"Falha SMTP ({type(exc).__name__}).", uncertain=sending) from exc
    finally:
        if client is not None:
            try:
                client.quit()
            except Exception:
                # A resposta de sucesso ao DATA já é evidência, mesmo com falha no QUIT.
                try:
                    client.close()
                except Exception:
                    pass
