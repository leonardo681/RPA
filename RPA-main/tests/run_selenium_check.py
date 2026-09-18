"""Verificação optativa real do navegador, com servidor e SQLite isolados.

Uso: python tests/run_selenium_check.py [exemplos/clientes_exemplo.xlsx]
Exige Chrome ou Edge instalado. Não lê .env, não envia notificações.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from werkzeug.serving import make_server

from techsolutions.automation.importer import import_clients, read_clients
from techsolutions.config import Settings
from techsolutions.web import create_app


def main():
    parser = argparse.ArgumentParser(description="Validação Selenium de importação e duplicidades")
    parser.add_argument("file", nargs="?", type=Path, default=ROOT / "exemplos" / "clientes_exemplo.xlsx")
    parser.add_argument("--visible", action="store_true", help="Mostrar o navegador durante o teste")
    args = parser.parse_args()
    rows = read_clients(args.file)
    if len(rows) < 5:
        raise ValueError("O arquivo de validação deve conter pelo menos cinco clientes.")
    evidence_dir = ROOT / "data" / "validacao"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("SE_CACHE_PATH", str(ROOT / "data" / "selenium_cache"))
    with tempfile.TemporaryDirectory(prefix="techsolutions_selenium_") as temporary:
        folder = Path(temporary)
        settings = Settings(
            base_dir=ROOT, data_dir=folder, database_path=folder / "test.sqlite3",
            pdf_dir=folder / "pdfs", report_path=folder / "faturas_relatorio.xlsx",
            public_base_url="http://127.0.0.1:5000", admin_password="apenas-validacao-local",
            secret_key="chave-de-validacao-sem-dados-reais", browser_headless=not args.visible,
            browser=os.getenv("TEST_BROWSER", "chrome"),
            browser_driver=os.getenv("TEST_BROWSER_DRIVER", ""),
            browser_binary=os.getenv("TEST_BROWSER_BINARY", ""),
            browser_profile=folder / "browser", wait_timeout=20,
        )
        application = create_app(settings)
        server = make_server("127.0.0.1", 0, application, threaded=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        web_url = f"http://127.0.0.1:{server.server_port}"
        try:
            first = import_clients(settings, args.file, web_url=web_url)
            if first["sucessos"] != len(rows) or first["falhas"] != 0:
                raise AssertionError(f"Primeira importação não cadastrou todas as linhas: {first}")
            second = import_clients(settings, args.file, web_url=web_url)
            if second["ignorados"] != len(rows) or second["sucessos"] or second["falhas"]:
                raise AssertionError(f"Reexecução não preservou duplicidades: {second}")
            stored = application.extensions["repository"].list_clients()
            if len(stored) != len(rows):
                raise AssertionError("Contagem de clientes diverge após reexecução.")
            expected = {str(item["email"]).strip().lower() for item in rows}
            actual = {item["email"] for item in stored}
            if expected != actual:
                raise AssertionError("Clientes persistidos divergem da planilha.")
            evidence = {
                "arquivo": args.file.name, "headless": not args.visible,
                "primeira_importacao": first, "reexecucao": second,
                "clientes_no_banco": len(stored), "emails_correspondem": True,
                "observacao": "Selenium preencheu e submeteu os formulários Flask; nenhum envio real foi realizado.",
            }
            (evidence_dir / "selenium_resultado.json").write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (evidence_dir / "selenium_importacao_resultados.csv").write_bytes(
                (folder / "importacao_resultados.csv").read_bytes()
            )
            print(json.dumps(evidence, ensure_ascii=False, indent=2))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
