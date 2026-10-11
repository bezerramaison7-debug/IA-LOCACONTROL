"""Read uploaded workbooks only; never execute formulas, macros or external references."""

import hashlib
import io
import re
import zipfile
from datetime import date, datetime

from fastapi import HTTPException
from openpyxl import load_workbook

MAX_BYTES = 10 * 1024 * 1024


def scalar(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def read_workbook(data: bytes):
    if not data or len(data) > MAX_BYTES:
        raise HTTPException(422, "O Excel deve ter no máximo 10 MB.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 2000 or sum(e.file_size for e in entries) > 30 * 1024 * 1024:
                raise ValueError("Arquivo expandido excede limite")
            if any(e.flag_bits & 1 for e in entries):
                raise ValueError("Arquivo criptografado")
        formulas = load_workbook(io.BytesIO(data), data_only=False, keep_links=False)
        cached = load_workbook(io.BytesIO(data), data_only=True, keep_links=False)
        result = []
        total = 0
        for sheet in formulas:
            if sheet.max_row > 10001 or sheet.max_column > 200:
                raise ValueError("Limite: 10.000 linhas e 200 colunas por aba")
            total += sheet.max_row * sheet.max_column
            if total > 200000:
                raise ValueError("Limite total: 200.000 células")
            values, issues, source, formula_list = [], {}, [], []
            for row in sheet:
                output, original = [], []
                for cell in row:
                    value = cell.value
                    original.append(
                        {
                            "column": cell.column,
                            "value": scalar(value),
                            "type": cell.data_type,
                            "format": cell.number_format,
                        }
                    )
                    if cell.data_type == "f":
                        formula_list.append({"cell": cell.coordinate, "formula": value})
                        value = cached[sheet.title][cell.coordinate].value
                        issues[cell.coordinate] = (
                            "Fórmula: valor salvo no Excel pode estar desatualizado."
                            if value is not None
                            else "Fórmula sem resultado salvo; recalcule e salve o Excel."
                        )
                    elif cell.data_type == "e":
                        issues[cell.coordinate] = "Célula contém erro do Excel."
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        if re.fullmatch(r"0{2,}", cell.number_format) and value == int(value):
                            value = str(int(value)).zfill(len(cell.number_format))
                    output.append(scalar(value))
                values.append(output)
                source.append(original)
            result.append(
                {
                    "name": sheet.title,
                    "rows": sheet.max_row,
                    "columns": sheet.max_column,
                    "visibility": sheet.sheet_state,
                    "merged_ranges": [str(r) for r in sheet.merged_cells.ranges],
                    "formula_count": len(formula_list),
                    "formulas": formula_list[:100],
                    "values": values,
                    "source": source,
                    "issues": issues,
                }
            )
        formulas.close()
        cached.close()
        return result
    except (HTTPException, MemoryError):
        raise
    except Exception as error:
        raise HTTPException(
            422,
            "Excel inválido, protegido ou acima dos limites. Use .xlsx/.xlsm. "
            "Limites: 10 MB, 10.000 linhas/aba, 200 colunas e 200.000 células.",
        ) from error


def analysis(sheets):
    return [
        {key: value for key, value in sheet.items() if key not in {"values", "source", "issues"}}
        | {
            "sample": sheet["values"][:20],
            "warnings": list(sheet["issues"].items())[:100],
        }
        for sheet in sheets
    ]


def checksum(data):
    return hashlib.sha256(data).hexdigest()
