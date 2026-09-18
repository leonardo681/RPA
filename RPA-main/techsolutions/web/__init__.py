"""Interface Flask da apresentação TechSolutions."""

from __future__ import annotations

import hmac
import secrets
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import (
    Flask, abort, flash, redirect, render_template, request, send_file,
    session, url_for,
)

from techsolutions.config import load_settings
from techsolutions.services.billing import DuplicateClientError, Repository
from techsolutions.services.validation import format_brl
from techsolutions.reports.pdf import generate_pdf, validate_pdf


def create_app(settings=None):
    """Cria uma aplicação isolada; recebe configurações próprias nos testes."""
    settings = settings or load_settings()
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.secret_key,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=str(settings.web_url).startswith("https://"),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        SETTINGS=settings,
    )
    repository = Repository(settings)
    repository.init_db()
    app.extensions["repository"] = repository
    app.jinja_env.filters["brl"] = format_brl

    def csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        return session["csrf_token"]

    @app.context_processor
    def template_context():
        return {"csrf_token": csrf_token, "company": "TechSolutions Ltda"}

    @app.before_request
    def validate_csrf():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            expected = session.get("csrf_token", "")
            actual = request.form.get("csrf_token", "")
            if not expected or not hmac.compare_digest(str(expected).encode(), actual.encode()):
                abort(400, description="Formulário expirado. Recarregue a página e tente novamente.")

    @app.after_request
    def privacy_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    def login_required(view):
        @wraps(view)
        def protected(*args, **kwargs):
            if not session.get("authenticated"):
                return redirect(url_for("login", next=request.full_path))
            return view(*args, **kwargs)
        return protected

    def find_invoice(invoice_id):
        try:
            invoice = repository.get_invoice(invoice_id)
        except ValueError:
            abort(404)
        if not invoice:
            abort(404)
        return invoice

    def find_public_invoice(token):
        # O identificador secreto é uma credencial de acesso somente à fatura.
        if len(token) < 24 or len(token) > 128:
            abort(404)
        try:
            return repository.invoice_by_token(token)
        except ValueError:
            abort(404)

    def pdf_for(invoice):
        pdf_root = Path(settings.pdf_dir).resolve()
        # Preserve o arquivo revisado enquanto seus dados e sua integridade
        # permanecerem válidos. Alterações do cliente exigem nova geração.
        try:
            existing = Path(validate_pdf(settings, repository, invoice)).resolve()
            if existing.is_relative_to(pdf_root) and existing.is_file():
                return existing
        except ValueError:
            pass
        generated = Path(generate_pdf(settings, repository, invoice["id"])).resolve()
        if not generated.is_relative_to(pdf_root) or not generated.is_file():
            abort(500, description="O PDF não está disponível no diretório de faturas.")
        return generated

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            supplied = request.form.get("password", "")
            if hmac.compare_digest(supplied.encode(), str(settings.admin_password).encode()):
                session.clear()
                session["authenticated"] = True
                destination = request.args.get("next", "")
                split = urlsplit(destination)
                if (not destination.startswith("/") or split.netloc or split.scheme
                        or destination.startswith("//") or "\\" in destination
                        or any(ord(character) < 32 for character in destination)):
                    destination = url_for("dashboard")
                return redirect(destination)
            error = "Senha incorreta. Consulte a configuração local da apresentação."
        return render_template("login.html", error=error)

    @app.post("/logout")
    @login_required
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/health")
    def health():
        return {"status": "ok", "application": "techsolutions"}

    @app.get("/")
    @login_required
    def dashboard():
        return render_template("dashboard.html", stats=repository.dashboard(),
                               invoices=list(reversed(repository.list_invoices()))[:8])

    @app.get("/clientes")
    @login_required
    def clients():
        return render_template("clients.html", clients=repository.list_clients())

    @app.route("/clients/new", methods=["GET", "POST"])
    @app.route("/clientes/novo", methods=["GET", "POST"])
    @login_required
    def client_new():
        return save_client_form()

    @app.route("/clientes/<int:client_id>/editar", methods=["GET", "POST"])
    @login_required
    def client_edit(client_id):
        try:
            client = repository.get_client(client_id)
        except ValueError:
            abort(404)
        if not client:
            abort(404)
        return save_client_form(client)

    def save_client_form(client=None):
        values = dict(client or {})
        result = None
        if request.method == "POST":
            values = {field: request.form.get(field, "").strip()
                      for field in ("nome", "email", "telefone", "endereco")}
            try:
                saved_id = repository.save_client(values, id=client["id"] if client else None)
                result = {"status": "success", "id": saved_id, "message": "Cliente salvo com sucesso."}
            except DuplicateClientError as exc:
                result = {"status": "duplicate", "id": "", "message": str(exc)}
            except ValueError as exc:
                result = {"status": "error", "id": "", "message": str(exc)}
        return render_template("client_form.html", values=values, editing=bool(client), result=result)

    @app.get("/faturas")
    @login_required
    def invoices():
        filters = {
            "client_id": request.args.get("cliente_id", type=int),
            "status": request.args.get("status") or None,
            "due_from": request.args.get("de") or None,
            "due_to": request.args.get("ate") or None,
        }
        try:
            items = repository.list_invoices(**filters)
        except ValueError as exc:
            flash(str(exc), "danger")
            items = []
        return render_template("invoices.html", invoices=items, clients=repository.list_clients())

    @app.route("/faturas/nova", methods=["GET", "POST"])
    @login_required
    def invoice_new():
        error = None
        if request.method == "POST":
            try:
                client_id = int(request.form.get("cliente_id", ""))
                invoice_id = repository.create_invoice(
                    client_id, request.form.get("valor", ""), request.form.get("data_vencimento", "")
                )
                flash("Fatura cadastrada. Gere o PDF para visualizar o documento demonstrativo.", "success")
                return redirect(url_for("invoice_detail", invoice_id=invoice_id))
            except (ValueError, TypeError) as exc:
                error = str(exc) or "Verifique os campos da fatura."
        return render_template("invoice_form.html", clients=repository.list_clients(), error=error)

    @app.get("/faturas/<int:invoice_id>")
    @login_required
    def invoice_detail(invoice_id):
        return render_template("invoice_detail.html", invoice=find_invoice(invoice_id),
                               notifications=repository.notifications(invoice_id),
                               public_base_url=settings.public_base_url.rstrip("/"))

    @app.post("/faturas/<int:invoice_id>/pagar")
    @login_required
    def invoice_pay(invoice_id):
        find_invoice(invoice_id)
        try:
            repository.mark_paid(invoice_id)
            flash("Pagamento registrado manualmente. Os históricos de envio foram preservados.", "success")
        except ValueError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("invoice_detail", invoice_id=invoice_id))

    @app.post("/faturas/<int:invoice_id>/gerar-pdf")
    @login_required
    def invoice_generate_pdf(invoice_id):
        find_invoice(invoice_id)
        generate_pdf(settings, repository, invoice_id)
        flash("PDF demonstrativo gerado.", "success")
        return redirect(url_for("invoice_detail", invoice_id=invoice_id))

    @app.post("/faturas/gerar-pdfs")
    @login_required
    def invoices_generate_pdfs():
        count = 0
        failures = 0
        for invoice in repository.list_invoices():
            try:
                generate_pdf(settings, repository, invoice["id"])
                count += 1
            except (OSError, ValueError):
                app.logger.exception("Falha ao gerar PDF da fatura %s", invoice["id"])
                failures += 1
        flash(f"PDFs gerados: {count}. Falhas: {failures}.", "warning" if failures else "success")
        return redirect(url_for("invoices"))

    @app.get("/faturas/<int:invoice_id>/pdf")
    @login_required
    def invoice_pdf(invoice_id):
        path = pdf_for(find_invoice(invoice_id))
        return send_file(path, mimetype="application/pdf", as_attachment=request.args.get("download") == "1", download_name=path.name)

    @app.get("/f/<token>")
    def public_invoice(token):
        return render_template("public_invoice.html", invoice=find_public_invoice(token))

    @app.get("/f/<token>/pdf")
    def public_invoice_pdf(token):
        path = pdf_for(find_public_invoice(token))
        return send_file(path, mimetype="application/pdf", as_attachment=request.args.get("download") == "1", download_name=path.name)

    @app.get("/logo.svg")
    def logo():
        return send_file(Path(settings.base_dir) / "assets" / "logo.svg", mimetype="image/svg+xml")

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(500)
    def error_page(error):
        return render_template("error.html", error=error), error.code

    return app
