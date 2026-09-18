"""Importação comprovada pelo formulário HTML, sem escrever diretamente no banco."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from threading import Event
from urllib.parse import urlparse

import pandas as pd

from techsolutions.services.validation import normalize_phone, validate_email


def create_driver(settings, *, persistent=False):
    """Selenium Manager resolve o driver; configuração manual também é aceita."""
    from selenium import webdriver

    browser = str(settings.browser).lower()
    if browser not in {"chrome", "edge"}:
        raise ValueError("BROWSER deve ser chrome ou edge.")
    if browser == "edge":
        from selenium.webdriver.edge.service import Service
        options = webdriver.EdgeOptions()
        driver_class = webdriver.Edge
    else:
        from selenium.webdriver.chrome.service import Service
        options = webdriver.ChromeOptions()
        driver_class = webdriver.Chrome
    if settings.browser_binary:
        options.binary_location = str(settings.browser_binary)
    if getattr(settings, "browser_headless", False):
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")
    else:
        options.add_argument("--start-maximized")
    if persistent:
        profile = Path(settings.browser_profile).resolve()
        profile.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile}")
    service = Service(executable_path=str(settings.browser_driver)) if settings.browser_driver else Service()
    driver = driver_class(service=service, options=options)
    driver.set_page_load_timeout(max(30, int(settings.wait_timeout)))
    return driver


def read_clients(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Planilha de clientes inexistente: {path}")
    if path.suffix.lower() == ".xlsx":
        frame = pd.read_excel(path, dtype=str, keep_default_na=False, engine="openpyxl")
    elif path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, sep=None,
                            engine="python", encoding="utf-8-sig")
    else:
        raise ValueError("Selecione uma planilha .xlsx ou .csv UTF-8.")
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    required = {"nome", "email", "telefone", "endereco"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError("Colunas ausentes: " + ", ".join(sorted(missing)))
    if len(frame.columns) != len(set(frame.columns)):
        raise ValueError("A planilha contém nomes de colunas repetidos.")
    return frame.to_dict(orient="records")


def _write_import_log(path, number, status, email, detail):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or not path.stat().st_size
    with path.open("a", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, delimiter=";")
        if new:
            writer.writerow(["data_hora", "linha", "status", "email", "detalhe"])
        writer.writerow([datetime.now().astimezone().isoformat(timespec="seconds"),
                         number, status, email, detail])


def import_clients(settings, path, web_url=None, stop_event=None, log=print,
                   progress=lambda done, total: None):
    """Valida cada linha, digita os campos e verifica o marcador de resultado."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    rows = read_clients(path)
    stop = stop_event or Event()
    base = str(web_url or settings.web_url).rstrip("/")
    if urlparse(base).scheme not in {"http", "https"}:
        raise ValueError("O endereço do sistema deve começar com http:// ou https://.")
    summary = {"sucessos": 0, "falhas": 0, "ignorados": 0, "simulados": 0}
    progress(0, len(rows))
    if not rows or stop.is_set():
        return summary
    driver = create_driver(settings)
    wait = WebDriverWait(driver, max(5, int(settings.wait_timeout)))
    log_path = Path(settings.data_dir) / "importacao_resultados.csv"
    try:
        for index, raw in enumerate(rows, start=1):
            if stop.is_set():
                log("Importação interrompida entre registros; cadastros concluídos preservados.")
                break
            email = str(raw.get("email", "")).strip()
            try:
                values = {key: str(raw[key]).strip() for key in ("nome", "email", "telefone", "endereco")}
                if not values["nome"] or not values["endereco"]:
                    raise ValueError("Nome e endereço são obrigatórios.")
                values["email"] = validate_email(values["email"])
                values["telefone"] = normalize_phone(values["telefone"])
                driver.get(f"{base}/clientes/novo")
                if driver.find_elements(By.ID, "password"):
                    driver.find_element(By.ID, "password").send_keys(settings.admin_password)
                    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
                    wait.until(lambda browser: not browser.find_elements(By.ID, "password"))
                    driver.get(f"{base}/clientes/novo")
                wait.until(EC.visibility_of_element_located((By.ID, "nome")))
                for field, value in values.items():
                    element = driver.find_element(By.ID, field)
                    element.clear()
                    element.send_keys(value)
                driver.find_element(By.ID, "save-client").click()
                result = wait.until(EC.presence_of_element_located((By.ID, "rpa-result")))
                status = result.get_attribute("data-status")
                detail = result.text.strip() or "Resultado do formulário sem descrição."
                if status == "success":
                    summary["sucessos"] += 1
                    log(f"Linha {index + 1}: cadastrado {values['nome']}.")
                elif status == "duplicate":
                    summary["ignorados"] += 1
                    log(f"Linha {index + 1}: duplicidade de e-mail, cliente ignorado.")
                else:
                    raise ValueError(detail)
                _write_import_log(log_path, index + 1, status, email, detail)
            except Exception as exc:
                summary["falhas"] += 1
                detail = f"{type(exc).__name__}: {str(exc).split('Stacktrace:')[0].strip()}"
                _write_import_log(log_path, index + 1, "error", email, detail)
                log(f"Linha {index + 1}: falha — {detail}")
            progress(index, len(rows))
    finally:
        driver.quit()
    return summary
