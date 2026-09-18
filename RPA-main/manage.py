"""Comandos locais seguros. Envios reais estão disponíveis somente na GUI revisada."""
import argparse

from techsolutions.config import load_settings
from techsolutions.services.billing import Repository


def main():
    parser = argparse.ArgumentParser(description="TechSolutions — utilitários locais")
    parser.add_argument("command", choices=["init", "examples", "demo", "seed-invoices", "pdfs", "report", "simulate", "import-clients"])
    parser.add_argument("--file", help="Arquivo CSV/XLSX para import-clients")
    parser.add_argument("--data-dir", help="Banco separado para testes/apresentação")
    parser.add_argument("--channel", choices=["whatsapp", "email", "both"], default="both")
    args = parser.parse_args()
    settings = load_settings(args.data_dir)
    repo = Repository(settings)
    repo.init_db()
    from techsolutions.demo import create_examples, seed_demo
    from techsolutions.reports.pdf import generate_all_pdfs
    from techsolutions.reports.excel import export_report
    if args.command in ("init", "examples", "demo"):
        print("Exemplos:", create_examples(settings))
    if args.command in ("demo", "seed-invoices"):
        print("Faturas criadas:", seed_demo(repo, include_clients=args.command == "demo"))
    if args.command in ("demo", "pdfs"):
        print(generate_all_pdfs(settings, repo))
    if args.command in ("demo", "report"):
        print("Relatório:", export_report(settings, repo))
    if args.command == "simulate":
        from techsolutions.automation.batch import run_batch
        for channel in ("whatsapp", "email") if args.channel == "both" else (args.channel,):
            print(run_batch(settings, repo, channel, demo=True))
    if args.command == "import-clients":
        if not args.file:
            parser.error("import-clients exige --file")
        from techsolutions.automation.importer import import_clients
        print(import_clients(settings, args.file))
    if args.command == "init":
        print("Banco inicializado. Senha administrativa: arquivo", settings.data_dir / "local_admin_password.txt")


if __name__ == "__main__":
    main()
