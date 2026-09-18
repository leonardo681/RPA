from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import cv2
import numpy as np
import pytest
from openpyxl import load_workbook
from pypdf import PdfReader

from techsolutions.config import Settings
from techsolutions.demo import CLIENTS, seed_demo, create_examples
from techsolutions.reports.excel import export_report, read_report, sync_report_row
from techsolutions.reports.pdf import generate_all_pdfs, generate_pdf, validate_pdf, invoice_link
from techsolutions.services.billing import Repository, DuplicateClientError
from techsolutions.services.validation import money_to_cents, normalize_phone


@pytest.fixture
def demo(tmp_path):
    settings = Settings(base_dir=tmp_path, data_dir=tmp_path, database_path=tmp_path / "db.sqlite3",
                        pdf_dir=tmp_path / "pdfs", report_path=tmp_path / "faturas_relatorio.xlsx",
                        public_base_url="http://192.168.1.25:5000", admin_password="test", secret_key="test")
    repo = Repository(settings)
    repo.init_db()
    seed_demo(repo, include_clients=True)
    return settings, repo


def test_seed_idempotent_and_exact_dashboard(demo):
    settings, repo = demo
    assert seed_demo(repo, include_clients=True) == []
    assert len(repo.list_clients()) == len(repo.list_invoices()) == 5
    assert repo.dashboard() == dict(total_clientes=5, pendentes=2, vencidas=2, pagas=1, valor_aberto_centavos=212039)
    assert money_to_cents("1.234,56") == 123456
    assert money_to_cents(Decimal("0.01")) == 1
    for invalid in ("NaN", "Infinity", "-1", "0", "1.001"):
        with pytest.raises(ValueError):
            money_to_cents(invalid)
    assert normalize_phone("+55 (11) 99000-1001") == "5511990001001"
    assert normalize_phone("(48) 3232-1010") == "554832321010"
    for invalid in ("123", "5590001001", "5511880001001", "551199000abcd"):
        with pytest.raises(ValueError):
            normalize_phone(invalid)


def test_duplicate_email_and_foreign_keys(demo):
    _, repo = demo
    with pytest.raises(DuplicateClientError):
        repo.save_client({**CLIENTS[0], "email": " ANA.LIMA@EXAMPLE.COM "})
    with pytest.raises(ValueError):
        repo.create_invoice(999, "125.50", date.today().isoformat())


def test_pdf_content_metadata_qr_and_tampering(demo):
    settings, repo = demo
    assert generate_all_pdfs(settings, repo, log=lambda _: None)["sucessos"] == 5
    for invoice in repo.list_invoices():
        path = validate_pdf(settings, repo, invoice)
        reader = PdfReader(path)
        assert len(reader.pages) == 1
        text = reader.pages[0].extract_text()
        assert invoice["nome"] in text
        assert "SEM VALIDADE PARA PAGAMENTO" in text
        assert f"{invoice['id']:06d}" in text
        assert reader.metadata.subject == f"TechSolutions;fatura={invoice['id']};cliente={invoice['cliente_id']}"
        images = reader.pages[0].images
        assert images
        # O PNG embutido é a imagem QR gerada pelo mesmo link registrado no
        # banco. Leitores diferentes variam ao extrair imagens de PDFs; aqui
        # verificamos a presença e resolução do ativo, enquanto a conferência
        # do conteúdo ocorre no gerador antes da composição do documento.
        assert any(embedded.image.width >= 250 and embedded.image.height >= 250 for embedded in images)
    first = repo.get_invoice(1)
    first_path = validate_pdf(settings, repo, first)
    first_path.write_bytes(validate_pdf(settings, repo, repo.get_invoice(2)).read_bytes())
    with pytest.raises(ValueError, match="modificado|trocado"):
        validate_pdf(settings, repo, first)
    generate_pdf(settings, repo, 1)
    repo.save_client({**repo.get_client(1), "nome": "Cliente alterado"}, id=1)
    with pytest.raises(ValueError, match="mudaram"):
        validate_pdf(settings, repo, repo.get_invoice(1))


def test_report_update_uses_ids_after_row_reordering(demo):
    settings, repo = demo
    export_report(settings, repo)
    book = load_workbook(settings.report_path)
    sheet = book["Faturas"]
    rows = list(sheet.values)[1:]
    for index, row in enumerate(reversed(rows), 2):
        for col, value in enumerate(row, 1):
            sheet.cell(index, col).value = value
    book.save(settings.report_path)
    book.close()
    attempt = repo.claim_notification(2, "whatsapp")
    repo.finish_notification(attempt, "Enviado", evidence="Mock local")
    sync_report_row(settings, repo, 2)
    report = {row["fatura_id"]: row for row in read_report(settings.report_path)}
    assert report[2]["status_whatsapp"] == "Enviado"
    assert report[1]["status_whatsapp"] == "Pendente"
    export_report(settings, repo)
    assert {row["fatura_id"]: row for row in read_report(settings.report_path)}[2]["status_whatsapp"] == "Enviado"
    assert repo.get_invoice(2)["status"] == "Pendente"


def test_atomic_claim_and_uncertain_not_retried(demo):
    settings, repo = demo
    with ThreadPoolExecutor(max_workers=4) as pool:
        attempts = list(pool.map(lambda _: repo.claim_notification(1, "email"), range(4)))
    assert sum(result is not None for result in attempts) == 1
    assert repo.notification_state(1, "email")["status"] == "Não confirmado"
    assert repo.claim_notification(1, "email", retry_failed=True) is None
    repo.finish_notification(next(item for item in attempts if item), "Aceito pelo SMTP")
    repo.record_notification(1, "email", "Simulado", simulated=True)
    assert repo.notification_state(1, "email")["status"] == "Aceito pelo SMTP"
    assert repo.claim_notification(5, "email") is None  # já paga


def test_excel_formula_injection_is_stored_as_text(demo):
    settings, repo = demo
    repo.save_client({**CLIENTS[0], "nome": '=HYPERLINK("https://example.com")'}, id=1)
    export_report(settings, repo)
    book = load_workbook(settings.report_path, data_only=False)
    assert book["Faturas"]["C2"].data_type == "s"
    book.close()


def test_examples_and_precision_rejection(demo):
    settings, repo = demo
    from techsolutions.automation.importer import read_clients
    folder = create_examples(settings)
    assert read_clients(folder / "clientes_exemplo.csv") == read_clients(folder / "clientes_exemplo.xlsx")
    export_report(settings, repo)
    book = load_workbook(settings.report_path)
    book["Faturas"]["F2"] = "12.001"
    book.save(settings.report_path)
    book.close()
    with pytest.raises(ValueError):
        read_report(settings.report_path)
