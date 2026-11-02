from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOCACONTROL_",
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/locacontrol.db"
    # Local edition (ADR-023): no login, automatic session for this computer only, no portal.
    # The packaged edition turns it on; False keeps the login-based edition.
    local_mode: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    allowed_origins: list[str] = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:4173",
    ]
    cookie_secure: bool = False  # Enable behind HTTPS; local loopback uses HTTP.
    import_directory: Path = PROJECT_ROOT / "data" / "imports"
    session_hours: int = Field(default=8, ge=1, le=24)
    # Generated contract PDFs; back up together with the database and imports.
    document_directory: Path = PROJECT_ROOT / "data" / "documents"
    # An active contract is shown as "vencendo" this many days before its expected return.
    contract_due_soon_days: int = Field(default=3, ge=0, le=60)
    # "fake" is the simulation. A real adapter needs sandbox credentials supplied via .env.
    fiscal_provider: str = "fake"
    fiscal_directory: Path = PROJECT_ROOT / "data" / "fiscal"
    # Free text agreed with the accountant; the system does not infer the tax document type.
    fiscal_document_kind: str = ""
    # Default folder for backup sets; the administrator may choose another in the interface.
    backup_directory: Path = PROJECT_ROOT / "data" / "backups"
    # Background check for the daily automatic backup; tests turn it off.
    backup_scheduler: bool = True
    # Printed on commercial documents; set the real company data in .env.
    company_name: str = "LocaControl"
    company_document: str = ""
    company_address: str = ""
    company_contact: str = ""
