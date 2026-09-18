"""Validação do tkinter sem abrir navegadores ou enviar mensagens."""

from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import time
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import patch

from techsolutions.config import Settings
from techsolutions.gui.app import DesktopApp


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        folder = Path(self.temp.name)
        settings = Settings(
            base_dir=folder, data_dir=folder, database_path=folder / "database.sqlite3",
            pdf_dir=folder / "pdfs", report_path=folder / "report.xlsx",
            public_base_url="http://127.0.0.1:5000", admin_password="test-only",
            secret_key="test-only-secret", demo_mode=False,
        )
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.temp.cleanup()
            self.skipTest(f"tkinter não disponível neste ambiente: {exc}")
        self.root.withdraw()
        self.app = DesktopApp(self.root, settings)

    def tearDown(self):
        self.app.stop_event.set()
        if self.app.worker is not None:
            self.app.worker.join(timeout=2)
        self.root.destroy()
        self.temp.cleanup()

    def pump_until(self, predicate, timeout=4):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.root.update()
            if predicate():
                return
            time.sleep(0.01)
        self.fail("A interface não processou o evento dentro do tempo limite.")

    def test_demo_is_default_even_when_settings_say_real(self):
        self.assertTrue(self.app.demo_var.get())
        settings, options = self.app._snapshot()
        self.assertTrue(options["demo"])
        self.assertEqual(settings.web_url, "http://127.0.0.1:5000")

    def test_worker_keeps_event_loop_responsive_and_cancels_safely(self):
        started = threading.Event()
        heartbeat = []
        rendered_threads = []
        original_append = self.app._append_log

        def record_render(message):
            rendered_threads.append(threading.get_ident())
            original_append(message)

        def operation(settings, options):
            self.app._log("Resultado anterior à interrupção foi preservado.")
            self.app._progress(1, 3)
            started.set()
            self.app.stop_event.wait(3)
            return {"sucessos": 1, "ignorados": 2}

        with patch.object(self.app, "_append_log", side_effect=record_render):
            self.app._start_task("Teste de responsividade", operation)
            self.root.after(0, lambda: heartbeat.append(True))
            self.pump_until(lambda: started.is_set() and bool(heartbeat) and self.app.progress_var.get() > 0)
            self.assertTrue(self.app.worker.is_alive())
            self.assertIn("disabled", self.app.action_buttons[0].state())
            self.app._request_stop()
            self.pump_until(lambda: "interrompido em ponto seguro" in self.app.status_var.get())
        self.assertTrue(all(thread_id == threading.get_ident() for thread_id in rendered_threads))
        self.assertIn("Sucessos: 1", self.app.summary_var.get())
        self.assertIn("Ignorados: 2", self.app.summary_var.get())
        self.assertIn("preservado", self.app.log_text.get("1.0", "end"))

    def test_real_review_requires_explicit_authorized_contact_confirmation(self):
        batch = [{
            "invoice_id": 1, "client_id": 5, "name": "Cliente fictício",
            "recipient": "teste@example.com", "original_recipient": "cliente@example.com",
            "test_override": True, "value_cents": 12550, "due_date": "2026-12-31",
            "pdf_path": "fatura_000001_cliente_000005.pdf", "link": "http://127.0.0.1/f/token",
            "message": "Mensagem de teste, sem envio externo.",
        }]
        observed = []

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        def inspect_dialog():
            dialog = next(child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel))
            widgets = list(descendants(dialog))
            approve = next(widget for widget in widgets if isinstance(widget, ttk.Button) and widget.cget("text") == "Confirmar envio real deste lote")
            checkbox = next(widget for widget in widgets if isinstance(widget, ttk.Checkbutton))
            observed.append("disabled" in approve.state())
            checkbox.invoke()
            observed.append("disabled" not in approve.state())
            approve.invoke()

        self.root.after(50, inspect_dialog)
        approved = self.app._review_dialog("email", batch, demo=False)
        self.assertEqual(observed, [True, True])
        self.assertTrue(approved)


if __name__ == "__main__":
    unittest.main()
