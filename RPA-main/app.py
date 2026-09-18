"""Inicialização simples: python app.py --host 127.0.0.1 --port 5000."""
from __future__ import annotations

import argparse

from techsolutions.config import load_settings
from techsolutions.web import create_app


def main():
    settings = load_settings()
    parser = argparse.ArgumentParser(description="Sistema local TechSolutions")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", default=settings.port, type=int)
    arguments = parser.parse_args()
    application = create_app(settings)
    print(f"TechSolutions: http://{arguments.host}:{arguments.port}")
    print("Senha administrativa: configuração ADMIN_PASSWORD ou data/local_admin_password.txt.")
    application.run(host=arguments.host, port=arguments.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
