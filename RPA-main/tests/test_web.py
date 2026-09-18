"""Fluxos HTTP reais com SQLite temporário, sem acessar credenciais locais."""
from __future__ import annotations

import re
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from techsolutions.config import Settings
from techsolutions.web import create_app


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        folder = Path(self.temp.name)
        self.settings = Settings(
            base_dir=Path(__file__).resolve().parents[1],
            data_dir=folder, database_path=folder / "test.sqlite3", pdf_dir=folder / "pdfs",
            report_path=folder / "faturas_relatorio.xlsx", public_base_url="http://127.0.0.1:5000",
            admin_password="senha-apenas-teste", secret_key="chave-apenas-teste",
        )
        self.settings.pdf_dir.mkdir()
        self.app = create_app(self.settings)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        self.repo = self.app.extensions["repository"]

    def tearDown(self):
        self.temp.cleanup()

    def csrf(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(match)
        return match.group(1)

    def login(self):
        token = self.csrf("/login")
        result = self.client.post("/login", data={"password": self.settings.admin_password, "csrf_token": token})
        self.assertEqual(result.status_code, 302)

    def new_client(self):
        token = self.csrf("/clientes/novo")
        result = self.client.post("/clientes/novo", data={
            "csrf_token": token, "nome": "Cliente de Teste", "email": "pessoa@example.com",
            "telefone": "11999998888", "endereco": "Rua Exemplo, 100",
        })
        self.assertIn('data-status="success"', result.get_data(as_text=True))
        return self.repo.list_clients()[0]["id"]

    def test_authenticated_pages_and_csrf(self):
        self.assertEqual(self.client.get("/clientes").status_code, 302)
        self.assertEqual(self.client.get("/faturas/1/pdf").status_code, 302)
        self.assertEqual(self.client.post("/login", data={"password": "senha-apenas-teste"}).status_code, 400)
        self.login()
        for path in ("/", "/clientes", "/clientes/novo", "/faturas", "/faturas/nova"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.post("/clientes/novo", data={"csrf_token": "inválido"}).status_code, 400)

    def test_form_saves_and_reexecution_reports_duplicate(self):
        self.login()
        client_id = self.new_client()
        token = self.csrf("/clientes/novo")
        result = self.client.post("/clientes/novo", data={
            "csrf_token": token, "nome": "Outro Nome", "email": "PESSOA@EXAMPLE.COM",
            "telefone": "11999998888", "endereco": "Outro endereço",
        })
        self.assertIn('data-status="duplicate"', result.get_data(as_text=True))
        self.assertEqual(len(self.repo.list_clients()), 1)
        self.assertEqual(self.repo.get_client(client_id)["nome"], "Cliente de Teste")
        token = self.csrf(f"/clientes/{client_id}/editar")
        result = self.client.post(f"/clientes/{client_id}/editar", data={
            "csrf_token": token, "nome": "Cliente Editado", "email": "pessoa@example.com",
            "telefone": "11999998888", "endereco": "Rua Atualizada, 101",
        })
        self.assertIn('data-status="success"', result.get_data(as_text=True))
        self.assertEqual(self.repo.get_client(client_id)["nome"], "Cliente Editado")

    def test_invoice_pdf_public_token_and_manual_payment(self):
        self.login()
        client_id = self.new_client()
        token = self.csrf("/faturas/nova")
        due = (date.today() + timedelta(days=7)).isoformat()
        result = self.client.post("/faturas/nova", data={
            "csrf_token": token, "cliente_id": str(client_id), "valor": "123,45", "data_vencimento": due,
        })
        self.assertEqual(result.status_code, 302)
        invoice = self.repo.list_invoices()[0]
        self.assertEqual(invoice["valor_centavos"], 12345)
        self.assertEqual(invoice["cliente_id"], client_id)
        detail = self.client.get(f"/faturas/{invoice['id']}")
        self.assertEqual(detail.status_code, 200)
        pdf = self.client.get(f"/faturas/{invoice['id']}/pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.data.startswith(b"%PDF"))
        first_document = pdf.data
        pdf.close()
        same_pdf = self.client.get(f"/faturas/{invoice['id']}/pdf")
        self.assertEqual(same_pdf.data, first_document, "A consulta não deve alterar um PDF já revisado.")
        same_pdf.close()
        client_data = self.repo.get_client(client_id)
        client_data["endereco"] = "Endereço atualizado após a geração"
        self.repo.save_client(client_data, id=client_id)
        updated_pdf = self.client.get(f"/faturas/{invoice['id']}/pdf")
        self.assertEqual(updated_pdf.status_code, 200)
        self.assertNotEqual(updated_pdf.data, first_document, "Um PDF desatualizado deve ser regenerado.")
        updated_pdf.close()
        self.repo.record_notification(invoice["id"], "email", "Simulado", simulated=True)
        self.assertEqual(self.repo.get_invoice(invoice["id"])["status"], "Pendente")
        token = self.csrf(f"/faturas/{invoice['id']}")
        response = self.client.post(f"/faturas/{invoice['id']}/pagar", data={"csrf_token": token})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.repo.get_invoice(invoice["id"])["status"], "Paga")
        self.assertEqual(len(self.repo.notifications(invoice["id"])), 1)
        anonymous = self.app.test_client()
        public = anonymous.get(f"/f/{invoice['token']}")
        self.assertEqual(public.status_code, 200)
        self.assertIn("SEM VALIDADE PARA PAGAMENTO", public.get_data(as_text=True))
        self.assertEqual(anonymous.get(f"/f/{invoice['id']}").status_code, 404)
        self.assertEqual(anonymous.get("/f/" + "a" * 43).status_code, 404)
        self.assertEqual(anonymous.get(f"/faturas/{invoice['id']}/pdf").status_code, 302)

    def test_nonexistent_records_and_external_redirect(self):
        token = self.csrf("/login")
        result = self.client.post("/login?next=https://example.org", data={
            "csrf_token": token, "password": self.settings.admin_password,
        })
        self.assertEqual(result.headers["Location"], "/")
        self.assertEqual(self.client.get("/clientes/99999/editar").status_code, 404)
        self.assertEqual(self.client.get("/faturas/99999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
