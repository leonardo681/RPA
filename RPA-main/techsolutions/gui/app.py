"""Controle desktop. Somente a thread principal acessa componentes tkinter."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any, Callable
from urllib.parse import urlsplit
import webbrowser

from techsolutions.automation import import_clients, prepare_batch, run_batch
from techsolutions.config import load_settings
from techsolutions.reports.excel import export_report
from techsolutions.reports.pdf import generate_all_pdfs
from techsolutions.services.billing import Repository


SUMMARY_KEYS = ("sucessos", "falhas", "ignorados", "simulados")


class DesktopApp:
    """Executa tarefas em uma thread e entrega eventos à janela por uma fila."""

    def __init__(self, root: tk.Tk, settings=None) -> None:
        self.root = root
        self.settings = settings or load_settings()
        self.events: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.server = None
        self.server_thread: threading.Thread | None = None
        self.closing = False
        self.action_buttons: list[ttk.Button] = []
        self.config_widgets: list[Any] = []

        self.file_var = tk.StringVar()
        self.url_var = tk.StringVar(value=self.settings.web_url)
        self.test_email_var = tk.StringVar(value=self.settings.test_email or "")
        self.test_phone_var = tk.StringVar(value=self.settings.test_phone or "")
        # A configuração do ambiente nunca ativa envios reais automaticamente.
        self.demo_var = tk.BooleanVar(value=True)
        self.retry_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Pronto. Modo demonstrativo: nenhum envio real.")
        self.summary_var = tk.StringVar(value="Sucessos: 0  |  Falhas: 0  |  Ignorados: 0  |  Simulados: 0")
        self.progress_var = tk.DoubleVar(value=0)

        self.root.title("TechSolutions • Central de cobrança")
        self.root.geometry("1110x840")
        self.root.minsize(860, 700)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()
        self.root.after(100, self._drain_events)
        self._append_log("Modo demonstrativo ativo. PDFs são faturas demonstrativas, sem validade para pagamento.")
        self._append_log("No envio real, revise os destinatários de cada lote e use somente contatos autorizados.")

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"), foreground="#17354a")
        style.configure("Subtitle.TLabel", foreground="#466078")
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="TechSolutions Ltda", style="Title.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Central de automação de clientes e cobranças", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 12))

        config = ttk.LabelFrame(outer, text="Arquivos e conexão", padding=10)
        config.pack(fill="x")
        config.columnconfigure(1, weight=1)
        ttk.Label(config, text="Planilha de clientes:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        file_entry = ttk.Entry(config, textvariable=self.file_var)
        file_entry.grid(row=0, column=1, sticky="ew", pady=4)
        self._button(config, "Selecionar Excel/CSV", self._select_file).grid(row=0, column=2, padx=(8, 0))
        ttk.Label(config, text="Endereço do sistema:").grid(row=1, column=0, sticky="w", padx=(0, 8))
        url_entry = ttk.Entry(config, textvariable=self.url_var)
        url_entry.grid(row=1, column=1, sticky="ew", pady=4)
        self._button(config, "Iniciar e abrir sistema web", lambda: self._start_task("Iniciar sistema web", self._start_server)).grid(row=1, column=2, padx=(8, 0))
        ttk.Label(config, text="O servidor usa WEB_HOST/WEB_PORT do .env. O endereço acima é usado pelo navegador e pelo RPA.", wraplength=820).grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))

        delivery = ttk.LabelFrame(outer, text="Modo de envio e destinatários de teste", padding=10)
        delivery.pack(fill="x", pady=10)
        delivery.columnconfigure(1, weight=1)
        delivery.columnconfigure(3, weight=1)
        demo_check = ttk.Checkbutton(delivery, text="Modo demonstrativo (simular, sem enviar)", variable=self.demo_var, command=self._mode_changed)
        demo_check.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 7))
        retry_check = ttk.Checkbutton(delivery, text="Reprocessar falhas anteriores neste lote", variable=self.retry_var)
        retry_check.grid(row=0, column=2, columnspan=2, sticky="w", pady=(0, 7))
        ttk.Label(delivery, text="E-mail de teste:").grid(row=1, column=0, sticky="w", padx=(0, 8))
        email_entry = ttk.Entry(delivery, textvariable=self.test_email_var)
        email_entry.grid(row=1, column=1, sticky="ew", padx=(0, 14))
        ttk.Label(delivery, text="Telefone de teste:").grid(row=1, column=2, sticky="w", padx=(0, 8))
        phone_entry = ttk.Entry(delivery, textvariable=self.test_phone_var)
        phone_entry.grid(row=1, column=3, sticky="ew")
        ttk.Label(delivery, text="Campos preenchidos redirecionam o canal ao contato de teste. Vazios usam o cliente da fatura.\nResultados incertos exigem conferência manual; a opção acima reprocessa somente falhas.", wraplength=960).grid(row=2, column=0, columnspan=4, sticky="w", pady=(7, 0))
        self.config_widgets.extend([file_entry, url_entry, email_entry, phone_entry, demo_check, retry_check])

        actions = ttk.LabelFrame(outer, text="Executar etapas", padding=10)
        actions.pack(fill="x")
        for column in range(3):
            actions.columnconfigure(column, weight=1)
        buttons = [
            ("1. Importar clientes via RPA", "Importar clientes", self._import),
            ("2. Gerar PDFs", "Gerar PDFs", self._pdfs),
            ("3. Exportar relatório Excel", "Exportar relatório", self._export),
            ("4. Enviar WhatsApp", "WhatsApp", lambda settings, opts: self._send(settings, opts, "whatsapp")),
            ("5. Enviar e-mails", "E-mails", lambda settings, opts: self._send(settings, opts, "email")),
            ("Executar fluxo completo", "Fluxo completo", self._full_flow),
        ]
        for index, (label, task, operation) in enumerate(buttons):
            self._button(actions, label, lambda name=task, work=operation: self._start_task(name, work)).grid(row=index // 3, column=index % 3, sticky="ew", padx=4, pady=5)

        helper = ttk.Frame(outer)
        helper.pack(fill="x", pady=(10, 3))
        self.cancel_button = ttk.Button(helper, text="Solicitar interrupção segura", command=self._request_stop, state="disabled")
        self.cancel_button.pack(side="left")
        ttk.Button(helper, text="Abrir pasta de resultados", command=lambda: self._open_folder(self.settings.data_dir)).pack(side="left", padx=8)
        ttk.Button(helper, text="Localizar senha de acesso web", command=self._show_password_location).pack(side="left")
        ttk.Label(outer, textvariable=self.status_var, wraplength=1030).pack(anchor="w", pady=(6, 3))
        ttk.Progressbar(outer, variable=self.progress_var, maximum=100).pack(fill="x", pady=3)
        ttk.Label(outer, textvariable=self.summary_var).pack(anchor="w", pady=(3, 8))
        self.log_text = ScrolledText(outer, height=13, wrap="word", font=("Consolas", 10), state="disabled", background="#f5f8fc")
        self.log_text.pack(fill="both", expand=True)

    def _button(self, parent, label: str, command: Callable) -> ttk.Button:
        button = ttk.Button(parent, text=label, command=command)
        self.action_buttons.append(button)
        return button

    def _select_file(self) -> None:
        path = filedialog.askopenfilename(parent=self.root, title="Selecionar clientes", filetypes=[("Excel ou CSV", "*.xlsx *.csv"), ("Excel", "*.xlsx"), ("CSV", "*.csv")])
        if path:
            self.file_var.set(path)

    def _mode_changed(self) -> None:
        if self.demo_var.get():
            self.status_var.set("Modo demonstrativo. As tentativas serão registradas como Simulado.")
        else:
            self.status_var.set("Envio real selecionado. Cada lote exige revisão e confirmação dos contatos autorizados.")

    def _snapshot(self):
        web_url = self.url_var.get().strip().rstrip("/")
        parsed = urlsplit(web_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Informe um endereço http:// ou https:// válido, sem credenciais na URL.")
        settings = replace(self.settings, web_url=web_url, test_email=self.test_email_var.get().strip(), test_phone=self.test_phone_var.get().strip())
        options = {"file": self.file_var.get().strip(), "demo": self.demo_var.get(), "retry_failed": self.retry_var.get()}
        return settings, options

    def _start_task(self, name: str, operation: Callable) -> None:
        if self.worker and self.worker.is_alive():
            return
        try:
            settings, options = self._snapshot()
        except ValueError as exc:
            messagebox.showerror("Configuração inválida", str(exc), parent=self.root)
            return
        self.stop_event.clear()
        self.progress_var.set(0)
        self._set_summary({})
        self.status_var.set(f"Em execução: {name}")
        self._set_busy(True)
        self._append_log(f"Iniciando: {name}. Modo: {'demonstrativo' if options['demo'] else 'real, sujeito à revisão do lote'}.")

        def work():
            try:
                summary = operation(settings, options) or {}
                self.events.put(("finished", (name, summary, None)))
            except Exception as exc:
                self.events.put(("log", f"Falha: {type(exc).__name__}: {exc}"))
                self.events.put(("finished", (name, {"falhas": 1}, str(exc))))

        self.worker = threading.Thread(target=work, name="techsolutions-operation", daemon=True)
        self.worker.start()

    def _set_busy(self, busy: bool) -> None:
        for widget in self.action_buttons + self.config_widgets:
            widget.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")

    def _log(self, message: Any) -> None:
        self.events.put(("log", str(message)))

    def _progress(self, done: int, total: int) -> None:
        self.events.put(("progress", (done, total)))

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{datetime.now():%H:%M:%S}] {message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_summary(self, summary: dict) -> None:
        self.summary_var.set("  |  ".join(f"{key.capitalize()}: {int(summary.get(key, 0))}" for key in SUMMARY_KEYS))

    def _drain_events(self) -> None:
        # Agendar antes de abrir um modal mantém a fila ativa durante wait_window.
        self.root.after(100, self._drain_events)
        for _ in range(100):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._append_log(value)
            elif kind == "progress":
                done, total = value
                self.progress_var.set(100 * done / total if total else 0)
            elif kind == "request":
                request, payload, event, answer = value
                if self.stop_event.is_set():
                    answer["value"] = False
                elif request == "review":
                    answer["value"] = self._review_dialog(**payload)
                elif request == "login":
                    answer["value"] = messagebox.askyesno("WhatsApp Web: continuar aguardando", payload, parent=self.root)
                event.set()
            elif kind == "finished":
                name, summary, error = value
                self._set_busy(False)
                self._set_summary(summary)
                stopped = self.stop_event.is_set()
                state = "interrompido em ponto seguro" if stopped else ("concluído com erro" if error else "concluído")
                self.status_var.set(f"{name}: {state}. Consulte o resumo e os logs.")
                if not error and not stopped:
                    self.progress_var.set(100)
                self._append_log(f"{name}: {state}. " + "; ".join(f"{key}={summary.get(key, 0)}" for key in SUMMARY_KEYS))
                if error and not self.closing:
                    messagebox.showerror("Operação não concluída", error, parent=self.root)

    def _ask_ui(self, request: str, payload: Any) -> bool:
        event = threading.Event()
        answer: dict[str, Any] = {}
        self.events.put(("request", (request, payload, event, answer)))
        while not event.wait(0.1):
            if self.stop_event.is_set():
                return False
        return bool(answer.get("value", False))

    def _review_dialog(self, channel: str, batch: list[dict], demo: bool) -> bool:
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Revisar lote • {channel} • {'SIMULAÇÃO' if demo else 'ENVIO REAL'}")
        dialog.geometry("930x700")
        dialog.minsize(760, 520)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=15)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"{'Simular' if demo else 'Enviar'} {len(batch)} cobrança(s) por {channel}", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Confira a fatura, o destinatário efetivo e o documento de cada registro.", wraplength=860).pack(anchor="w", pady=7)
        text = ScrolledText(frame, wrap="word", font=("Consolas", 10))
        text.pack(fill="both", expand=True)
        for item in batch:
            cents = int(item["value_cents"])
            value = f"{cents // 100:,}".replace(",", ".") + f",{cents % 100:02d}"
            lines = [
                f"FATURA {item['invoice_id']} | Cliente {item['client_id']} | {item['name']}",
                f"Destinatário efetivo: {item['recipient']}",
                f"Destinatário cadastrado: {item.get('original_recipient', item['recipient'])}",
                f"Redirecionamento para teste: {'SIM' if item.get('test_override') else 'não'}",
                f"Valor: R$ {value} | Vencimento: {item['due_date']}",
                f"PDF: {item['pdf_path']}",
                f"Link: {item['link']}",
                f"Mensagem:\n{item['message']}",
                f"Conferência do documento: {item.get('validation_error') or 'documento associado e conferido'}",
                "─" * 65,
            ]
            text.insert("end", "\n".join(lines) + "\n\n")
        text.configure(state="disabled")
        acknowledged = tk.BooleanVar(value=False)
        response = {"approved": False}
        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=(12, 0))

        def finish(approved: bool) -> None:
            response["approved"] = approved
            dialog.destroy()

        approve = ttk.Button(controls, text="Simular lote" if demo else "Confirmar envio real deste lote", command=lambda: finish(True))
        approve.pack(side="right")
        ttk.Button(controls, text="Cancelar lote", command=lambda: finish(False)).pack(side="right", padx=8)
        if not demo:
            approve.configure(state="disabled")
            ttk.Checkbutton(frame, text="Revisei os documentos e confirmo que todos os destinatários autorizaram estes testes.", variable=acknowledged, command=lambda: approve.configure(state="normal" if acknowledged.get() else "disabled")).pack(anchor="w", pady=(12, 0))
            ttk.Label(frame, text="Aceitação SMTP e evidência de envio no WhatsApp não confirmam pagamento nem leitura.", wraplength=870).pack(anchor="w", pady=(6, 0))
        dialog.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        self.root.wait_window(dialog)
        return response["approved"]

    def _repository(self, settings):
        repo = Repository(settings)
        repo.init_db()
        return repo

    def _start_server(self, settings, options) -> dict:
        if self.stop_event.is_set():
            return {}
        if self.server is None:
            from werkzeug.serving import make_server
            from techsolutions.web import create_app

            try:
                self.server = make_server(settings.host, settings.port, create_app(settings), threaded=True)
            except SystemExit as exc:
                raise RuntimeError(f"Não foi possível iniciar o servidor em {settings.host}:{settings.port}. Confira se outro servidor já usa essa porta; nesse caso abra o endereço existente no navegador ou configure outra WEB_PORT.") from exc
            self.server_thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.25}, name="techsolutions-web", daemon=True)
            self.server_thread.start()
            self._log(f"Servidor iniciado em {settings.host}:{settings.port}.")
        else:
            self._log("O servidor iniciado por esta janela já está ativo.")
        self._log(f"Abrindo {settings.web_url}. Senha local em {settings.data_dir / 'local_admin_password.txt'} (quando ADMIN_PASSWORD não está configurada).")
        webbrowser.open(settings.web_url)
        return {"sucessos": 1}

    def _import(self, settings, options) -> dict:
        if not options["file"]:
            raise ValueError("Selecione clientes_exemplo.xlsx, clientes_exemplo.csv ou outra planilha de clientes.")
        path = Path(options["file"])
        if not path.is_file():
            raise ValueError(f"Arquivo não encontrado: {path}")
        return import_clients(settings, path, web_url=settings.web_url, stop_event=self.stop_event, log=self._log, progress=self._progress)

    def _pdfs(self, settings, options) -> dict:
        return generate_all_pdfs(settings, self._repository(settings), stop_event=self.stop_event, log=self._log, progress=self._progress)

    def _export(self, settings, options) -> dict:
        path = export_report(settings, self._repository(settings))
        self._log(f"Relatório atualizado: {path}. O histórico de notificações foi consultado no banco.")
        self._progress(1, 1)
        return {"sucessos": 1}

    def _send(self, settings, options, channel: str, refresh: bool = True) -> dict:
        repo = self._repository(settings)
        if self.stop_event.is_set():
            return {}
        if refresh:
            report = export_report(settings, repo)
            self._log(f"Relatório regenerado antes da leitura do lote: {report}")
        batch = prepare_batch(settings, repo, channel, retry_failed=options["retry_failed"])
        if not batch:
            self._log(f"{channel}: nenhuma cobrança elegível e pendente para este canal. Falhas somente entram com reprocessamento explícito.")
            return {"ignorados": 0}
        if not self._ask_ui("review", {"channel": channel, "batch": batch, "demo": options["demo"]}):
            self._log(f"Lote {channel} cancelado antes dos envios.")
            return {"ignorados": len(batch)}
        if self.stop_event.is_set():
            return {"ignorados": len(batch)}
        return run_batch(settings, repo, channel, demo=options["demo"], retry_failed=options["retry_failed"], approved_batch=batch, stop_event=self.stop_event, log=self._log, progress=self._progress, wait_for_login=lambda message: self._ask_ui("login", message))

    def _full_flow(self, settings, options) -> dict:
        totals = {key: 0 for key in SUMMARY_KEYS}

        def collect(summary):
            for key in SUMMARY_KEYS:
                totals[key] += int((summary or {}).get(key, 0))

        if options["file"]:
            self._log("Etapa 1: importar clientes pelo formulário web.")
            collect(self._import(settings, options))
        else:
            self._log("Nenhuma planilha de clientes selecionada. O fluxo usará os clientes cadastrados.")
        if self.stop_event.is_set():
            return totals
        repo = self._repository(settings)
        if not repo.list_invoices():
            self._log("AÇÃO NECESSÁRIA: não há faturas. Abra o sistema web, cadastre faturas selecionando os clientes e execute novamente. Clientes importados não geram dívidas automaticamente.")
            self.events.put(("log", "Para os dados fictícios da apresentação, a carga inicial está documentada no README."))
            return totals
        self._log("Etapa 2: gerar PDFs individuais.")
        collect(self._pdfs(settings, options))
        if self.stop_event.is_set():
            return totals
        self._log("Etapa 3: exportar relatório de cobrança.")
        collect(self._export(settings, options))
        for channel in ("whatsapp", "email"):
            if self.stop_event.is_set():
                break
            self._log(f"Etapa de notificações: ler o relatório e revisar o lote {channel}.")
            collect(self._send(settings, options, channel, refresh=False))
        return totals

    def _request_stop(self) -> None:
        self.stop_event.set()
        self.cancel_button.configure(state="disabled")
        self.status_var.set("Interrupção solicitada. Aguardando a conclusão e gravação da tentativa em andamento.")
        self._append_log("Interrupção segura solicitada. Os resultados já gravados serão preservados.")

    def _show_password_location(self) -> None:
        messagebox.showinfo("Acesso ao sistema web", "Se ADMIN_PASSWORD foi configurada no .env, use essa senha.\n\nCaso contrário, a primeira inicialização gera a senha local em:\n" + str(self.settings.data_dir / "local_admin_password.txt") + "\n\nAbra esse arquivo localmente para consultar a senha. Não compartilhe a senha na apresentação.", parent=self.root)

    def _open_folder(self, path: Path) -> None:
        if not path.exists():
            messagebox.showinfo("Resultados", "A pasta será criada ao inicializar o banco ou gerar os documentos.", parent=self.root)
            return
        webbrowser.open(path.resolve().as_uri())

    def _on_close(self) -> None:
        if self.closing:
            return
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Encerrar com segurança", "Solicitar interrupção e fechar quando a tentativa em andamento tiver sido registrada?", parent=self.root):
                return
            self._request_stop()
        self.closing = True
        self._close_when_idle()

    def _close_when_idle(self) -> None:
        if self.worker and self.worker.is_alive():
            self.root.after(150, self._close_when_idle)
            return
        if self.server is not None:
            server = self.server
            self.server = None
            shutdown = threading.Thread(target=lambda: (server.shutdown(), server.server_close()), daemon=True)
            shutdown.start()

            def wait_shutdown():
                if shutdown.is_alive():
                    self.root.after(100, wait_shutdown)
                else:
                    self.root.destroy()

            wait_shutdown()
        else:
            self.root.destroy()


def main() -> None:
    root = tk.Tk()
    try:
        DesktopApp(root)
    except Exception as exc:
        messagebox.showerror("Falha ao iniciar TechSolutions", f"{type(exc).__name__}: {exc}", parent=root)
        root.destroy()
        raise
    root.mainloop()


if __name__ == "__main__":
    main()
