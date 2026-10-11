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
    # Printed on commercial documents; set the real company data in .env.
    company_name: str = "LocaControl"
    company_document: str = ""
    company_address: str = ""
    company_contact: str = ""
