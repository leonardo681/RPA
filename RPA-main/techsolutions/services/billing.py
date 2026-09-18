"""SQLite com valores em centavos e histórico imutável das tentativas."""
from contextlib import contextmanager
from datetime import date, datetime, timezone
import secrets
import sqlite3

from .validation import validate_client, money_to_cents


class DuplicateClientError(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


SCHEMA = """
CREATE TABLE IF NOT EXISTS clientes (
 id INTEGER PRIMARY KEY, nome TEXT NOT NULL, email TEXT NOT NULL COLLATE NOCASE UNIQUE,
 telefone TEXT NOT NULL, endereco TEXT NOT NULL, data_cadastro TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS faturas (
 id INTEGER PRIMARY KEY, cliente_id INTEGER NOT NULL REFERENCES clientes(id),
 valor_centavos INTEGER NOT NULL CHECK(valor_centavos>0), data_vencimento TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'Pendente' CHECK(status IN ('Pendente','Paga','Cancelada')),
 data_emissao TEXT NOT NULL, caminho_pdf TEXT NOT NULL DEFAULT '',
 token TEXT NOT NULL UNIQUE, data_pagamento TEXT, demo_key TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS notificacoes (
 id INTEGER PRIMARY KEY, fatura_id INTEGER NOT NULL REFERENCES faturas(id),
 cliente_id INTEGER NOT NULL REFERENCES clientes(id), canal TEXT NOT NULL CHECK(canal IN ('whatsapp','email')),
 status TEXT NOT NULL, data_hora TEXT NOT NULL, erro TEXT NOT NULL DEFAULT '',
 destinatario TEXT NOT NULL DEFAULT '', mensagem TEXT NOT NULL DEFAULT '',
 evidencia TEXT NOT NULL DEFAULT '', simulado INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_notificacoes_fatura_canal ON notificacoes(fatura_id,canal,id);
CREATE TABLE IF NOT EXISTS pdf_documentos (
 fatura_id INTEGER PRIMARY KEY REFERENCES faturas(id), caminho TEXT NOT NULL,
 sha256 TEXT NOT NULL, fingerprint TEXT NOT NULL, gerado_em TEXT NOT NULL
);
"""


class Repository:
    def __init__(self, settings):
        self.settings = settings

    @contextmanager
    def connection(self):
        con = sqlite3.connect(str(self.settings.database_path), timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def init_db(self):
        self.settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript(SCHEMA)

    def list_clients(self):
        with self.connection() as con:
            return [dict(r) for r in con.execute("SELECT * FROM clientes ORDER BY nome,id")]

    def get_client(self, client_id):
        with self.connection() as con:
            row = con.execute("SELECT * FROM clientes WHERE id=?", (client_id,)).fetchone()
            if row is None:
                raise ValueError("Cliente não encontrado.")
            return dict(row)

    def save_client(self, data, id=None):
        item = validate_client(data)
        try:
            with self.connection() as con:
                if id is None:
                    cur = con.execute("INSERT INTO clientes(nome,email,telefone,endereco,data_cadastro) VALUES(?,?,?,?,?)",
                                      (*item.values(), now()))
                    return cur.lastrowid
                cur = con.execute("UPDATE clientes SET nome=?,email=?,telefone=?,endereco=? WHERE id=?", (*item.values(), id))
                if cur.rowcount == 0:
                    raise ValueError("Cliente não encontrado.")
                return id
        except sqlite3.IntegrityError as exc:
            raise DuplicateClientError("E-mail já cadastrado. Duplicidade identificada pelo e-mail normalizado.") from exc

    def create_invoice(self, client_id, valor, data_vencimento, demo_key=None):
        cents = money_to_cents(valor)
        try:
            due = date.fromisoformat(str(data_vencimento)).isoformat()
        except (ValueError, TypeError) as exc:
            raise ValueError("Vencimento inválido; use AAAA-MM-DD.") from exc
        self.get_client(client_id)
        with self.connection() as con:
            cur = con.execute("INSERT INTO faturas(cliente_id,valor_centavos,data_vencimento,data_emissao,token,demo_key) VALUES(?,?,?,?,?,?)",
                              (client_id, cents, due, now(), secrets.token_urlsafe(32), demo_key))
            return cur.lastrowid

    def list_invoices(self, client_id=None, status=None, due_from=None, due_to=None):
        clauses, params = [], []
        if client_id:
            clauses.append("f.cliente_id=?")
            params.append(int(client_id))
        if status == "Vencida":
            clauses.append("f.status='Pendente' AND f.data_vencimento<?")
            params.append(date.today().isoformat())
        elif status:
            clauses.append("f.status=?")
            params.append(status)
        for field, operator in ((due_from, ">="), (due_to, "<=")):
            if field:
                clauses.append("f.data_vencimento" + operator + "?")
                params.append(date.fromisoformat(str(field)).isoformat())
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connection() as con:
            rows = con.execute("SELECT f.*,c.nome,c.email,c.telefone,c.endereco FROM faturas f JOIN clientes c ON c.id=f.cliente_id" + where + " ORDER BY f.id", params)
            return [self._invoice(row) for row in rows]

    @staticmethod
    def _invoice(row):
        result = dict(row)
        result["situacao"] = "Vencida" if result["status"] == "Pendente" and result["data_vencimento"] < date.today().isoformat() else result["status"]
        return result

    def get_invoice(self, invoice_id):
        with self.connection() as con:
            row = con.execute("SELECT f.*,c.nome,c.email,c.telefone,c.endereco FROM faturas f JOIN clientes c ON c.id=f.cliente_id WHERE f.id=?", (invoice_id,)).fetchone()
            if row is None:
                raise ValueError("Fatura não encontrada.")
            return self._invoice(row)

    def invoice_by_token(self, token):
        with self.connection() as con:
            row = con.execute("SELECT id FROM faturas WHERE token=?", (token,)).fetchone()
        if row is None:
            raise ValueError("Fatura não encontrada.")
        return self.get_invoice(row["id"])

    def set_pdf(self, invoice_id, path):
        with self.connection() as con:
            con.execute("UPDATE faturas SET caminho_pdf=? WHERE id=?", (str(path), invoice_id))

    def register_pdf(self, invoice_id, path, digest, fingerprint):
        with self.connection() as con:
            con.execute("UPDATE faturas SET caminho_pdf=? WHERE id=?", (str(path), invoice_id))
            con.execute("INSERT INTO pdf_documentos VALUES(?,?,?,?,?) ON CONFLICT(fatura_id) DO UPDATE SET caminho=excluded.caminho,sha256=excluded.sha256,fingerprint=excluded.fingerprint,gerado_em=excluded.gerado_em",
                        (invoice_id, str(path), digest, fingerprint, now()))

    def pdf_record(self, invoice_id):
        with self.connection() as con:
            row = con.execute("SELECT * FROM pdf_documentos WHERE fatura_id=?", (invoice_id,)).fetchone()
            return dict(row) if row else None

    def mark_paid(self, invoice_id):
        with self.connection() as con:
            cur = con.execute("UPDATE faturas SET status='Paga',data_pagamento=? WHERE id=? AND status='Pendente'", (now(), invoice_id))
            if cur.rowcount == 0:
                raise ValueError("Fatura inexistente ou já finalizada.")

    def dashboard(self):
        invoices = self.list_invoices()
        return {"total_clientes": len(self.list_clients()),
                "pendentes": sum(i["situacao"] == "Pendente" for i in invoices),
                "pagas": sum(i["status"] == "Paga" for i in invoices),
                "vencidas": sum(i["situacao"] == "Vencida" for i in invoices),
                "valor_aberto_centavos": sum(i["valor_centavos"] for i in invoices if i["status"] == "Pendente")}

    def notifications(self, invoice_id=None):
        with self.connection() as con:
            if invoice_id is None:
                rows = con.execute("SELECT * FROM notificacoes ORDER BY id DESC")
            else:
                rows = con.execute("SELECT * FROM notificacoes WHERE fatura_id=? ORDER BY id DESC", (invoice_id,))
            return [dict(row) for row in rows]

    @staticmethod
    def _state(con, invoice_id, channel):
        # Simulações não substituem nenhuma tentativa real já existente.
        real = con.execute("SELECT * FROM notificacoes WHERE fatura_id=? AND canal=? AND simulado=0 ORDER BY id DESC LIMIT 1", (invoice_id, channel)).fetchone()
        row = real or con.execute("SELECT * FROM notificacoes WHERE fatura_id=? AND canal=? ORDER BY id DESC LIMIT 1", (invoice_id, channel)).fetchone()
        if row is None:
            return {"status": "Pendente", "data_envio": "", "erro": ""}
        status = "Não confirmado" if row["status"] == "Em processamento" else row["status"]
        return {"status": status, "data_envio": row["data_hora"] if status in ("Enviado", "Aceito pelo SMTP") else "", "erro": row["erro"], "simulado": bool(row["simulado"])}

    def notification_state(self, invoice_id, channel):
        with self.connection() as con:
            return self._state(con, invoice_id, channel)

    def claim_notification(self, invoice_id, channel, retry_failed=False):
        if channel not in ("whatsapp", "email"):
            raise ValueError("Canal inválido.")
        with self.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            invoice = con.execute("SELECT * FROM faturas WHERE id=?", (invoice_id,)).fetchone()
            if not invoice or invoice["status"] != "Pendente":
                return None
            state = self._state(con, invoice_id, channel)["status"]
            if state not in ("Pendente", "Simulado") and not (retry_failed and state == "Falha"):
                return None
            cur = con.execute("INSERT INTO notificacoes(fatura_id,cliente_id,canal,status,data_hora) VALUES(?,?,?,'Em processamento',?)",
                              (invoice_id, invoice["cliente_id"], channel, now()))
            return cur.lastrowid

    def finish_notification(self, attempt_id, status, error="", recipient="", message="", evidence=""):
        if status not in ("Enviado", "Aceito pelo SMTP", "Falha", "Não confirmado"):
            raise ValueError("Estado final de tentativa inválido.")
        with self.connection() as con:
            cur = con.execute("UPDATE notificacoes SET status=?,data_hora=?,erro=?,destinatario=?,mensagem=?,evidencia=? WHERE id=? AND status='Em processamento'",
                              (status, now(), error, recipient, message, evidence, attempt_id))
            if cur.rowcount != 1:
                raise ValueError("Tentativa inexistente ou já concluída.")

    def record_notification(self, invoice_id, channel, status, error="", recipient="", message="", evidence="", simulated=False):
        if status == "Simulado":
            simulated = True
        invoice = self.get_invoice(invoice_id)
        with self.connection() as con:
            cur = con.execute("INSERT INTO notificacoes(fatura_id,cliente_id,canal,status,data_hora,erro,destinatario,mensagem,evidencia,simulado) VALUES(?,?,?,?,?,?,?,?,?,?)",
                              (invoice_id, invoice["cliente_id"], channel, status, now(), error, recipient, message, evidence, int(simulated)))
            return cur.lastrowid
