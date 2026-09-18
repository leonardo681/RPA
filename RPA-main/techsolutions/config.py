"""Configuração local. Segredos nunca são incluídos no código."""
from dataclasses import dataclass
from pathlib import Path
import os
import secrets

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    data_dir: Path
    database_path: Path
    pdf_dir: Path
    report_path: Path
    public_base_url: str
    admin_password: str
    secret_key: str
    web_url: str = "http://127.0.0.1:5000"
    host: str = "127.0.0.1"
    port: int = 5000
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    test_email: str = ""
    test_phone: str = ""
    whatsapp_send_image: Path = ROOT / "assets/whatsapp_send.png"
    whatsapp_confidence: float = 0.90
    browser: str = "chrome"
    browser_driver: str = ""
    browser_binary: str = ""
    browser_profile: Path = ROOT / "data/browser"
    browser_headless: bool = False
    wait_timeout: int = 40
    demo_mode: bool = True


def _local_secret(folder, filename):
    path = folder / filename
    try:
        # O_EXCL evita sobrescrever chave já criada por outra instância.
        with path.open("x", encoding="utf-8") as stream:
            stream.write(secrets.token_urlsafe(32))
    except FileExistsError:
        pass
    return path.read_text(encoding="utf-8").strip()


def load_settings(data_dir=None):
    load_dotenv(ROOT / ".env", override=False)
    folder = Path(data_dir or os.getenv("TECH_DATA_DIR", "data"))
    if not folder.is_absolute():
        folder = ROOT / folder
    folder.mkdir(parents=True, exist_ok=True)
    pdf_dir = folder / "pdfs"
    pdf_dir.mkdir(exist_ok=True)
    image = Path(os.getenv("WHATSAPP_SEND_IMAGE", "assets/whatsapp_send.png"))
    return Settings(
        base_dir=ROOT, data_dir=folder, database_path=folder / "techsolutions.sqlite3",
        pdf_dir=pdf_dir, report_path=folder / "faturas_relatorio.xlsx",
        admin_password=os.getenv("ADMIN_PASSWORD") or _local_secret(folder, "local_admin_password.txt"),
        secret_key=os.getenv("SECRET_KEY") or _local_secret(folder, ".secret_key"),
        host=os.getenv("WEB_HOST", "127.0.0.1"), port=int(os.getenv("WEB_PORT", "5000")),
        web_url=os.getenv("WEB_URL", "http://127.0.0.1:5000").rstrip("/"),
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:5000").rstrip("/"),
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.getenv("SMTP_PORT", "465")),
        smtp_user=os.getenv("SMTP_USER", ""), smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=os.getenv("SMTP_FROM", ""), test_email=os.getenv("TEST_EMAIL", ""),
        test_phone=os.getenv("TEST_PHONE", ""), browser=os.getenv("BROWSER", "chrome"),
        browser_driver=os.getenv("BROWSER_DRIVER", ""), browser_binary=os.getenv("BROWSER_BINARY", ""),
        browser_profile=folder / "browser", whatsapp_send_image=image if image.is_absolute() else ROOT / image,
        whatsapp_confidence=float(os.getenv("WHATSAPP_CONFIDENCE", "0.90")),
        wait_timeout=int(os.getenv("WAIT_TIMEOUT", "40")),
    )
