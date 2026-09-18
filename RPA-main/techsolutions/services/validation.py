from decimal import Decimal, InvalidOperation
import re
from email_validator import validate_email as check_email, EmailNotValidError

DDDS = {11,12,13,14,15,16,17,18,19,21,22,24,27,28,31,32,33,34,35,37,38,41,42,43,44,45,46,47,48,49,51,53,54,55,61,62,63,64,65,66,67,68,69,71,73,74,75,77,79,81,82,83,84,85,86,87,88,89,91,92,93,94,95,96,97,98,99}


def validate_email(value):
    try:
        return check_email(str(value).strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise ValueError("E-mail inválido.") from exc


def normalize_phone(value):
    text = str(value).strip()
    if re.search(r"[^\d\s+().-]", text):
        raise ValueError("Telefone contém caracteres inválidos.")
    number = re.sub(r"\D", "", text)
    if number.startswith("0055"):
        number = number[2:]
    if len(number) in (10, 11):
        number = "55" + number
    if len(number) not in (12, 13) or not number.startswith("55"):
        raise ValueError("Use telefone brasileiro com DDD e 8 ou 9 dígitos.")
    if int(number[2:4]) not in DDDS:
        raise ValueError("DDD brasileiro inválido.")
    subscriber = number[4:]
    if (len(subscriber) == 9 and subscriber[0] != "9") or (len(subscriber) == 8 and subscriber[0] not in "2345"):
        raise ValueError("Telefone fixo deve iniciar em 2–5; celular deve ter nove dígitos e iniciar em 9.")
    return number


def money_to_cents(value):
    text = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        amount = Decimal(text)
        if not amount.is_finite() or amount <= 0 or amount > Decimal("999999999.99"):
            raise ValueError("Valor deve ser positivo e de até R$ 999.999.999,99.")
        if amount != amount.quantize(Decimal("0.01")):
            raise ValueError("Informe no máximo duas casas decimais.")
        return int(amount * 100)
    except InvalidOperation as exc:
        raise ValueError("Valor monetário inválido.") from exc


def format_brl(cents):
    number = f"{Decimal(int(cents)) / 100:,.2f}"
    return number.replace(",", "_").replace(".", ",").replace("_", ".")


def validate_client(data):
    result = {key: str(data.get(key, "")).strip() for key in ("nome", "email", "telefone", "endereco")}
    if not 2 <= len(result["nome"]) <= 150:
        raise ValueError("Nome deve ter entre 2 e 150 caracteres.")
    if not 3 <= len(result["endereco"]) <= 300:
        raise ValueError("Endereço obrigatório, entre 3 e 300 caracteres.")
    result["email"] = validate_email(result["email"])
    result["telefone"] = normalize_phone(result["telefone"])
    return result
