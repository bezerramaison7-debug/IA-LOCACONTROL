import os
import sys
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def program_root() -> Path:
    """Read-only program files: the project folder, or PyInstaller's bundle when frozen."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT = program_root()


def resource(relative: str) -> Path:
    """Shipped resource such as "backend/migrations", "backend/alembic.ini", "frontend/dist"."""
    return program_root() / relative


def data_root() -> Path:
    """Persistent data of this installation (database, files, backups, logs, lock, .env).

    LOCACONTROL_DATA_DIR comes from the process environment only, never from a .env file,
    because the .env itself lives in this folder.
    """
    if value := os.environ.get("LOCACONTROL_DATA_DIR"):
        return Path(value).resolve()
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "LocaControl"
    return program_root() / "data"


def env_file() -> Path:
    # Without a separate data folder the project's .env keeps working as before.
    root = data_root()
    return PROJECT_ROOT / ".env" if root == PROJECT_ROOT / "data" else root / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOCACONTROL_",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __init__(self, **values):
        values.setdefault("_env_file", env_file())
        super().__init__(**values)

    database_url: str = "sqlite:///./data/locacontrol.db"
    # Local edition (ADR-023): no login, automatic session for this computer only, no portal.
    # The packaged edition turns it on; False keeps the login-based edition.
    local_mode: bool = False
    # Network edition (P1-D, ADR-025): the main computer listens on the store network and paired
    # stations use the same API. Only with local_mode; False keeps the server on 127.0.0.1.
    network_mode: bool = False
    # Station addresses accepted besides the private ranges (10/8, 172.16/12, 192.168/16, fc00::/7
    # and link-local), e.g. ["100.64.0.0/10"] for an unusual store network.
    station_networks: list[str] = []
    # Names by which stations reach this server besides IP literals and this computer's name.
    station_hosts: list[str] = []
    # Station token rotation (A1): a new token after this long in use (and at every new session).
    station_token_rotate_seconds: int = Field(default=900, ge=1, le=86_400)
    # A retired token is still accepted this long (requests in flight, other tabs) before its
    # use counts as reuse of a copied credential.
    station_token_grace_seconds: int = Field(default=120, ge=1, le=3_600)
    # HTTPS for the stations (P1-E): the store network only reaches this port; plain HTTP stays on
    # 127.0.0.1 for this computer.
    https_port: int = Field(default=8443, ge=1, le=65_535)
    # Pairing code: 26 characters of a 32-symbol alphabet = 130 bits (13 = 65 bits minimum). The
    # code also authenticates the CA a station downloads, so it must resist an offline search.
    pairing_code_length: int = Field(default=26, ge=13, le=40)
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

    @model_validator(mode="after")
    def derive_data_paths(self):
        """Defaults follow the data folder; explicitly configured values always win."""
        root = data_root()
        if root == PROJECT_ROOT / "data":
            return self
        unset = set(type(self).model_fields) - self.model_fields_set
        if "database_url" in unset:
            self.database_url = f"sqlite:///{(root / 'locacontrol.db').as_posix()}"
        for field, folder in DATA_FOLDERS.items():
            if field in unset:
                setattr(self, field, root / folder)
        return self


DATA_FOLDERS = {
    "import_directory": "imports",
    "document_directory": "documents",
    "fiscal_directory": "fiscal",
    "backup_directory": "backups",
}
