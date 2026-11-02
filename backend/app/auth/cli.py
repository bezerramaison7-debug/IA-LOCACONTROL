"""Local operator commands. No passwords in arguments, environment or logs."""

import argparse
import getpass
import sys

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.schemas import UserCreate
from app.auth.service import IdentityService
from app.core.config import Settings, resource
from app.persistence.database import build_engine


def run_local(action: str, username: str, name: str, password: str, settings: Settings):
    payload = UserCreate(
        username=username, name=name, password=password, role_codes=["ADMINISTRADOR"]
    )
    engine = build_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            heads = set(MigrationContext.configure(connection).get_current_heads())
        expected = set(ScriptDirectory(str(resource("backend/migrations"))).get_heads())
        if heads != expected:
            raise HTTPException(409, "Aplique as migrations antes deste comando.")
        with Session(engine) as db:
            db.execute(text("BEGIN IMMEDIATE"))
            service = IdentityService(db, local=True)
            if action == "bootstrap":
                service.bootstrap(payload.username, payload.name, payload.password)
            elif action == "recover":
                user = db.scalar(select(User).where(User.username == payload.username))
                if not user:
                    raise HTTPException(404, "Usuário não encontrado.")
                service.reset_password(user, payload.password, "password.recovered_local")
            else:
                raise ValueError("Comando local inválido")
            db.commit()
    finally:
        engine.dispose()


def create_default(settings: Settings) -> bool:
    """Non-interactive first-run account; does nothing when any user already exists."""
    engine = build_engine(settings.database_url)
    try:
        with Session(engine) as db:
            db.execute(text("BEGIN IMMEDIATE"))
            created = IdentityService(db, local=True).bootstrap_default() is not None
            db.commit()
            return created
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Administração local segura do LocaControl")
    parser.add_argument("action", choices=["bootstrap", "recover", "default"])
    args = parser.parse_args()
    if args.action == "default":
        print("CREATED" if create_default(Settings()) else "EXISTS")
        return
    if not sys.stdin.isatty():
        parser.exit(2, "Execute em terminal interativo. Senhas não são aceitas por pipe.\n")
    try:
        username = input("Usuário (3–80 letras minúsculas, números, ponto, _ ou -): ")
        name = input("Nome completo: ") if args.action == "bootstrap" else "Operador local"
        if args.action == "recover":
            print("A recuperação invalida todas as sessões e exige nova troca no próximo acesso.")
            if input("Digite RECUPERAR para confirmar: ") != "RECUPERAR":
                parser.exit(1, "Operação cancelada.\n")
        password = getpass.getpass("Nova senha (12–128 caracteres): ")
        if password != getpass.getpass("Confirme a senha: "):
            parser.exit(2, "As senhas não conferem.\n")
        run_local(args.action, username, name, password, Settings())
        print("Operação concluída e auditada. Nenhuma senha foi exibida ou salva em texto simples.")
    except ValidationError:
        parser.exit(2, "Dados inválidos. Confira usuário, nome e tamanho da senha.\n")
    except HTTPException as error:
        parser.exit(1, str(error.detail) + "\n")
    except (EOFError, KeyboardInterrupt):
        parser.exit(1, "\nOperação cancelada.\n")


if __name__ == "__main__":
    main()
