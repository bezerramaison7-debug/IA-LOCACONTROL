import hashlib
import json
import re
import time
from datetime import date, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException
from openpyxl.utils import get_column_letter
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth.catalog import permission_codes
from app.auth.service import IdentityService
from app.imports.models import ImportBatch, ImportOrigin
from app.imports.schemas import Mapping
from app.imports.workbook import checksum, read_workbook
from app.masters import schemas as s
from app.masters.models import Customer, Equipment, Price, Product, StockMovement
from app.masters.service import MasterService

SCHEMAS = {
    "customers": s.CustomerInput,
    "products": s.ProductInput,
    "equipment": s.EquipmentInput,
    "prices": s.PriceInput,
    "stock": s.MovementInput,
}
MODELS = {"customers": Customer, "products": Product, "equipment": Equipment}
LABELS = {
    "trade_name": "Nome fantasia",
    "state_registration": "Inscrição estadual",
    "phone": "Telefone",
    "mobile": "Celular",
    "email": "E-mail",
    "contact": "Contato",
    "notes": "Observações",
    "is_active": "Ativo (sim/não)",
    "description": "Descrição",
    "category": "Categoria",
    "asset_tag": "Patrimônio",
    "serial_number": "Número de série",
    "brand": "Marca",
    "model": "Modelo",
    "person_type": "Tipo de pessoa (PF/PJ)",
    "legal_name": "Nome / razão social",
    "document": "CPF/CNPJ",
    "code": "Código",
    "name": "Nome do produto",
    "unit": "Unidade",
    "individual_tracking": "Controle individual (sim/não)",
    "product_code": "Código do produto",
    "period": "Período (DIARIA/SEMANAL/QUINZENAL/MENSAL)",
    "amount": "Valor",
    "effective_date": "Data de vigência",
    "quantity": "Quantidade inicial disponível",
    "street": "Endereço",
    "city": "Cidade",
    "state": "UF",
    "postal_code": "CEP",
}
ADDRESS = {"street", "city", "state", "postal_code"}
BOOL = {"individual_tracking", "is_active"}
REQUIRED = {
    "customers": {"person_type", "legal_name", "document"},
    "products": {"code", "name", "unit"},
    "equipment": {"product_code", "code"},
    "prices": {"product_code", "period", "amount", "effective_date"},
    "stock": {"product_code", "quantity"},
}


def fields(entity):
    keys = set(SCHEMAS[entity].model_fields) - {
        "product_id",
        "addresses",
        "request_key",
        "reason",
        "from_status",
        "to_status",
    }
    if entity in {"equipment", "prices", "stock"}:
        keys.add("product_code")
    if entity == "customers":
        keys |= ADDRESS
    return [
        {
            "key": key,
            "label": LABELS.get(key, key.replace("_", " ")),
            "required": key in REQUIRED[entity],
        }
        for key in sorted(keys)
    ]


def batch_view(batch):
    return {
        key: getattr(batch, key)
        for key in (
            "id",
            "filename",
            "checksum",
            "created_at",
            "created_by",
            "status",
            "imported_at",
            "imported_by",
            "total_rows",
            "successful_rows",
            "ignored_rows",
            "warning_rows",
            "failed_rows",
            "mapping",
            "report",
        )
    }


class ImportService:
    def __init__(self, db, user, directory):
        self.db, self.user, self.directory = db, user, directory

    def batch(self, batch_id):
        batch = self.db.get(ImportBatch, batch_id)
        if not batch:
            raise HTTPException(404, "Importação não encontrada.")
        return batch

    def read(self, batch):
        path = self.directory / (batch.id + ".xlsx")
        if not path.is_file():
            raise HTTPException(409, "Arquivo original indisponível; envie novamente.")
        data = path.read_bytes()
        if checksum(data) != batch.checksum:
            raise HTTPException(409, "O original não corresponde ao checksum registrado.")
        return read_workbook(data)

    def process(self, batch, mapping: Mapping, *, dry_run=True):
        needed = {"imports.write", mapping.entity + ".write"}
        if mapping.entity == "stock":
            needed = {"imports.write", "stock.write"}
        if not needed <= set(permission_codes(self.user)):
            raise HTTPException(403, "Sem permissão para importar neste módulo.")
        allowed = {f["key"] for f in fields(mapping.entity)}
        if (
            not REQUIRED[mapping.entity] <= mapping.columns.keys()
            or not mapping.columns.keys() <= allowed
            or any(c < 1 or c > 200 for c in mapping.columns.values())
        ):
            raise HTTPException(422, "Mapeie os campos obrigatórios com colunas válidas.")
        sheets = self.read(batch)
        sheet = next((s for s in sheets if s["name"] == mapping.sheet), None)
        if not sheet or mapping.header_row > sheet["rows"]:
            raise HTTPException(422, "Aba ou linha de cabeçalho inválida.")
        if max(mapping.columns.values()) > sheet["columns"]:
            raise HTTPException(422, "Coluna inexistente nesta aba.")
        report = {
            "total": 0,
            "successful": 0,
            "ignored": 0,
            "warnings": 0,
            "errors": 0,
            "rows": [],
            "scope": "Uma aba e um módulo por operação. Repita para os demais.",
            "unmapped_columns": [
                get_column_letter(c)
                for c in range(1, sheet["columns"] + 1)
                if c not in mapping.columns.values()
            ],
            "pending_sheets": [s["name"] for s in sheets if s["name"] != sheet["name"]],
            "notice": "Contratos, renovações e dados sem campo de destino permanecem "
            "no original e não são convertidos nesta operação.",
        }
        outer = self.db.begin_nested()
        try:
            for index in range(mapping.header_row, len(sheet["values"])):
                row = sheet["values"][index]
                if not any(v is not None and v != "" for v in row):
                    continue
                number = index + 1
                warnings = []
                result = {"row": number, "status": "", "message": "", "warnings": warnings}
                report["total"] += 1
                if report["unmapped_columns"]:
                    warnings.append("Há colunas sem destino; consulte o original preservado.")
                source_key = checksum(
                    f"{batch.checksum}:{mapping.sheet}:{number}:{mapping.entity}".encode()
                )
                try:
                    with self.db.begin_nested():
                        existing = self.db.scalar(
                            select(ImportOrigin).where(ImportOrigin.source_key == source_key)
                        )
                        if existing:
                            result.update(status="IGNORADO", message="Origem já importada.")
                            report["ignored"] += 1
                        else:
                            data = {}
                            for field, col in mapping.columns.items():
                                value = row[col - 1]
                                coordinate = f"{get_column_letter(col)}{number}"
                                issue = sheet["issues"].get(coordinate)
                                if issue:
                                    if value is None or "erro do Excel" in issue:
                                        raise ValueError(f"{coordinate}: {issue}")
                                    warnings.append(f"{coordinate}: {issue}")
                                if value is not None and value != "":
                                    data[field] = self.convert(field, value, mapping)
                            if mapping.entity == "customers":
                                address = {k: data.pop(k) for k in ADDRESS if k in data}
                                if address:
                                    data["addresses"] = [address]
                            if mapping.entity in {"equipment", "prices", "stock"}:
                                product = self.db.scalar(
                                    select(Product).where(
                                        Product.code == str(data.pop("product_code", "")).upper()
                                    )
                                )
                                if not product:
                                    raise ValueError("Código de produto não cadastrado.")
                                data["product_id"] = product.id
                            if mapping.entity in {"stock", "prices"}:
                                data["reason"] = f"Importação {batch.id}, linha {number}"
                            if mapping.entity == "stock":
                                data.update(
                                    to_status="DISPONIVEL",
                                    from_status=None,
                                    request_key=uuid5(NAMESPACE_URL, source_key),
                                )
                            payload = SCHEMAS[mapping.entity].model_validate(data)
                            service = MasterService(self.db, self.user)
                            if mapping.entity == "prices":
                                previous = self.db.scalar(
                                    select(Price.id).where(
                                        Price.product_id == payload.product_id,
                                        Price.period == payload.period,
                                        Price.effective_date == payload.effective_date,
                                    )
                                )
                                if previous:
                                    raise ValueError(
                                        "Preço já existe nesta vigência; revise manualmente."
                                    )
                                saved = service.price(payload)
                            elif mapping.entity == "stock":
                                if self.db.scalar(
                                    select(StockMovement.id)
                                    .where(StockMovement.product_id == payload.product_id)
                                    .limit(1)
                                ):
                                    raise ValueError("Estoque já inicializado; ajuste manualmente.")
                                # Source identity prevents retry duplication.
                                saved = service.move(payload)
                            else:
                                saved = service.save(MODELS[mapping.entity], payload)
                            self.db.add(
                                ImportOrigin(
                                    source_key=source_key,
                                    batch_id=batch.id,
                                    sheet=mapping.sheet,
                                    row_number=number,
                                    entity=mapping.entity,
                                    entity_id=saved["id"],
                                    source={"cells": sheet["source"][index]},
                                    warnings="; ".join(warnings),
                                )
                            )
                            self.db.flush()
                            result.update(status="PRONTO" if dry_run else "IMPORTADO", message="")
                            report["successful"] += 1
                except (ValidationError, HTTPException, ValueError, IntegrityError) as error:
                    if isinstance(error, ValidationError):
                        messages = []
                        for e in error.errors(include_input=False):
                            field = str(e["loc"][0]) if e["loc"] else ""
                            label = LABELS.get(field, field or "Registro")
                            if e["type"] == "missing":
                                detail = "Campo obrigatório."
                            elif e["type"] == "value_error":
                                detail = e["msg"].removeprefix("Value error, ")
                            else:
                                detail = "Valor inválido; confira formato, opções e limites."
                            messages.append(label + ": " + detail)
                        message = "; ".join(messages)
                    elif isinstance(error, HTTPException):
                        message = str(error.detail)
                    elif isinstance(error, IntegrityError):
                        message = "Conflito de código, documento ou referência existente."
                    else:
                        message = str(error)
                    result.update(status="ERRO", message=message)
                    report["errors"] += 1
                if warnings:
                    report["warnings"] += 1
                report["rows"].append(result)
            if dry_run:
                outer.rollback()
            else:
                outer.commit()
        except Exception:
            outer.rollback()
            raise
        digest_report = json.loads(json.dumps(report))
        for row in digest_report["rows"]:
            if row["status"] == "IMPORTADO":
                row["status"] = "PRONTO"
        report["digest"] = hashlib.sha256(
            json.dumps(
                {"mapping": mapping.model_dump(), "report": digest_report},
                sort_keys=True,
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        return report

    @staticmethod
    def convert(field, value, mapping):
        if field in BOOL:
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in {"sim", "true", "1", "s"}:
                return True
            if text in {"não", "nao", "false", "0", "n"}:
                return False
            raise ValueError(f"{field}: use sim ou não.")
        if field in {"amount", "quantity"}:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return format(Decimal(str(value)), "f")
            text = str(value).strip()
            # Explicit separator; no guessing or implicit rounding.
            pattern = r"\d+(,\d+)?" if mapping.decimal_separator == "," else r"\d+(\.\d+)?"
            if not re.fullmatch(pattern, text):
                raise ValueError(f"{field}: separador inválido ou valor ambíguo.")
            return text.replace(",", ".")
        if field == "effective_date":
            text = str(value).strip()
            try:
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}(T.*)?", text):
                    return date.fromisoformat(text[:10]).isoformat()
                if mapping.date_format == "DMY":
                    return datetime.strptime(text, "%d/%m/%Y").date().isoformat()
            except ValueError:
                pass
            raise ValueError("Data inválida; use dd/mm/aaaa ou ISO conforme seleção.")
        if isinstance(value, float) and value == int(value):
            value = int(value)
        return str(value).strip()

    def confirm(self, batch, payload):
        if batch.status == "IMPORTED":
            raise HTTPException(409, "Importação já confirmada. Consulte o relatório.")
        preview = self.process(batch, payload.mapping)
        if preview["digest"] != payload.preview_digest:
            raise HTTPException(409, "Dados mudaram. Gere nova prévia antes de confirmar.")
        report = self.process(batch, payload.mapping, dry_run=False)
        batch.status = "IMPORTED"
        batch.imported_at = int(time.time())
        batch.imported_by = self.user.id
        batch.mapping = payload.mapping.model_dump()
        batch.report = report
        batch.total_rows = report["total"]
        batch.successful_rows = report["successful"]
        batch.warning_rows = report["warnings"]
        batch.failed_rows = report["errors"]
        batch.ignored_rows = report["ignored"]
        IdentityService(self.db, self.user).audit(
            "imports.confirm",
            "ImportBatch",
            batch.id,
            {"successful": report["successful"], "errors": report["errors"]},
        )
        self.db.flush()
        return batch_view(batch)
