"""Dados fictícios e inicialização idempotente para apresentação."""
from datetime import date, timedelta
from decimal import Decimal
import csv

from openpyxl import Workbook
from techsolutions.services.billing import DuplicateClientError

CLIENTS = [
    {"nome": "Ana Lima (Fictícia)", "email": "ana.lima@example.com", "telefone": "5511990001001", "endereco": "Rua das Ideias, 101 — São Paulo/SP"},
    {"nome": "Bruno Costa (Fictício)", "email": "bruno.costa@example.com", "telefone": "5521990001002", "endereco": "Av. da Inovação, 202 — Rio de Janeiro/RJ"},
    {"nome": "Carla Souza (Fictícia)", "email": "carla.souza@example.com", "telefone": "5531990001003", "endereco": "Rua dos Projetos, 303 — Belo Horizonte/MG"},
    {"nome": "Diego Alves (Fictício)", "email": "diego.alves@example.com", "telefone": "5541990001004", "endereco": "Rua da Pesquisa, 404 — Curitiba/PR"},
    {"nome": "Elisa Rocha (Fictícia)", "email": "elisa.rocha@example.com", "telefone": "5548990001005", "endereco": "Av. do Conhecimento, 505 — Florianópolis/SC"},
]


def create_examples(settings):
    folder = settings.base_dir / "exemplos"
    folder.mkdir(exist_ok=True)
    columns = ["nome", "email", "telefone", "endereco"]
    with (folder / "clientes_exemplo.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter=";")
        writer.writeheader()
        writer.writerows(CLIENTS)
    book = Workbook()
    sheet = book.active
    sheet.title = "Clientes"
    sheet.append(columns)
    for client in CLIENTS:
        sheet.append([client[key] for key in columns])
    for row in sheet.iter_rows(min_row=2):
        row[2].number_format = "@"
    for column, width in {"A": 27, "B": 30, "C": 20, "D": 60}.items():
        sheet.column_dimensions[column].width = width
    sheet.freeze_panes = "A2"
    book.save(folder / "clientes_exemplo.xlsx")
    book.close()
    return folder


def seed_demo(repo, include_clients=False):
    """Faturas por email/ID, sem depender da ordem de linhas na planilha."""
    if include_clients:
        for item in CLIENTS:
            try:
                repo.save_client(item)
            except DuplicateClientError:
                pass
    clients = {item["email"]: item["id"] for item in repo.list_clients()}
    missing = [item["email"] for item in CLIENTS if item["email"] not in clients]
    if missing:
        raise ValueError("Importe os cinco clientes pelo formulário RPA primeiro. Faltam: " + ", ".join(missing))
    added = []
    for index, client in enumerate(CLIENTS):
        key = "demo-" + client["email"]
        with repo.connection() as con:
            exists = con.execute("SELECT id FROM faturas WHERE demo_key=?", (key,)).fetchone()
        if exists:
            continue
        due = date.today() + timedelta(days=(-8, -2, 7, 14, 21)[index])
        invoice_id = repo.create_invoice(clients[client["email"]], ("250.50", "480.00", "1299.90", "89.99", "750.25")[index], due.isoformat(), demo_key=key)
        if index == 4:
            repo.mark_paid(invoice_id)
        added.append(invoice_id)
    return added
