import io

import pytest
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_masters import product

from app.auth.models import AuditLog
from app.imports.models import ImportBatch, ImportOrigin
from app.masters.models import Customer, Equipment, Price, Product, StockMovement

pytest_plugins = ["test_masters"]


@pytest.fixture(autouse=True)
def storage(client, tmp_path):
    client.app.state.settings.import_directory = tmp_path / "uploads"


def workbook(rows, extra=False):
    book = Workbook()
    sheet = book.active
    sheet.title = "Minha aba livre"
    for row in rows:
        sheet.append(row)
    if extra:
        other = book.create_sheet("Contratos antigos")
        other.append(["Código", "Fórmula"])
        other.append(["9193.1", "=1+1"])
        other.merge_cells("D1:E1")
    data = io.BytesIO()
    book.save(data)
    return data.getvalue()


def upload(client, admin, rows, extra=False):
    content = workbook(rows, extra)
    response = client.post(
        "/api/imports/upload",
        files={"file": ("../../legado.xlsx", content)},
        headers=admin[1],
    )
    assert response.status_code == 201, response.text
    return response.json(), content


def mapping(entity, columns, **extra):
    return {
        "sheet": "Minha aba livre",
        "header_row": 1,
        "entity": entity,
        "columns": columns,
        **extra,
    }


def preview(client, admin, batch, target):
    response = client.post(f"/api/imports/{batch}/preview", json=target, headers=admin[1])
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client, admin, batch, target, report):
    return client.post(
        f"/api/imports/{batch}/confirm",
        json={"mapping": target, "preview_digest": report["digest"], "confirm": True},
        headers=admin[1],
    )


def count(client, model):
    with Session(client.app.state.engine) as db:
        return db.scalar(select(func.count()).select_from(model))


def test_dynamic_upload_preview_rollback_partial_confirm_and_provenance(client, admin):
    rows = [
        ["Inventário", "Descrição", "Medida", "Observação livre"],
        ["TEST-01", "Andaime", "UN", "Preservar esta informação"],
        ["TEST-01", "Duplicado no arquivo", "UN", "Conflito"],
        ["TEST-02", "Escada", "UN", None],
        ["TEST-03", None, "UN", None],
    ]
    data, content = upload(client, admin, rows, extra=True)
    batch = data["batch"]["id"]
    assert data["batch"]["filename"] == "legado.xlsx"
    assert len(data["sheets"]) == 2
    assert data["sheets"][1]["formula_count"] == 1
    assert data["sheets"][1]["merged_ranges"] == ["D1:E1"]
    assert client.get(f"/api/imports/{batch}/original").content == content
    target = mapping("products", {"code": 1, "name": 2, "unit": 3})
    audits_before = count(client, AuditLog)
    report = preview(client, admin, batch, target)
    assert report["total"] == 4 and report["successful"] == 2 and report["errors"] == 2
    assert report["unmapped_columns"] == ["D"]
    assert report["pending_sheets"] == ["Contratos antigos"]
    assert count(client, Product) == count(client, ImportOrigin) == 0
    assert count(client, AuditLog) == audits_before
    with Session(client.app.state.engine) as db:
        assert db.get(ImportBatch, batch).report is None
    saved = confirm(client, admin, batch, target, report)
    assert saved.status_code == 200, saved.text
    assert saved.json()["successful_rows"] == 2
    assert count(client, Product) == count(client, ImportOrigin) == 2
    with Session(client.app.state.engine) as db:
        origin = db.scalar(select(ImportOrigin).order_by(ImportOrigin.row_number))
        assert origin.sheet == "Minha aba livre" and origin.row_number == 2
        assert origin.source["cells"][3]["value"] == "Preservar esta informação"
    assert confirm(client, admin, batch, target, report).status_code == 409
    assert client.get(f"/api/imports/{batch}/report").json()["errors"] == 2
    # Same source resent: already-imported lines are ignored, never duplicated.
    response = client.post(f"/api/imports/{batch}/new-conversion", headers=admin[1])
    assert response.status_code == 201
    again = response.json()
    repeated = preview(client, admin, again["batch"]["id"], target)
    assert repeated["ignored"] == 2 and count(client, Product) == 2


def test_stale_preview_rejects_without_new_writes(client, admin):
    data, _ = upload(client, admin, [["C", "N", "U"], ["P-001", "Escada", "UN"]])
    batch = data["batch"]["id"]
    target = mapping("products", {"code": 1, "name": 2, "unit": 3})
    report = preview(client, admin, batch, target)
    product(client, admin)
    assert confirm(client, admin, batch, target, report).status_code == 409
    assert count(client, Product) == 1 and count(client, ImportOrigin) == 0


def test_customers_address_leading_zeros_and_duplicate_conflict(client, admin):
    data, _ = upload(
        client,
        admin,
        [
            ["Tipo", "Nome", "Documento", "Rua", "Cidade", "UF", "CEP"],
            ["PF", "Cliente legado", "00000000001", "Rua A", "Recife", "PE", "50000000"],
            ["PF", "Outro cliente", "00000000001", "Rua B", "Recife", "PE", "50000000"],
        ],
    )
    target = mapping(
        "customers",
        {
            "person_type": 1,
            "legal_name": 2,
            "document": 3,
            "street": 4,
            "city": 5,
            "state": 6,
            "postal_code": 7,
        },
    )
    batch = data["batch"]["id"]
    report = preview(client, admin, batch, target)
    assert report["successful"] == 1 and report["errors"] == 1
    assert confirm(client, admin, batch, target, report).status_code == 200
    assert count(client, Customer) == 1
    customer = client.get("/api/customers").json()["items"][0]
    assert customer["document"] == "00000000001"
    assert customer["addresses"][0]["city"] == "Recife"


@pytest.mark.parametrize(
    "entity,rows,columns,model",
    [
        (
            "equipment",
            [["Produto", "Código"], ["P-001", "EQ-1"]],
            {"product_code": 1, "code": 2},
            Equipment,
        ),
        (
            "prices",
            [
                ["Produto", "Período", "Valor", "Data"],
                ["P-001", "DIARIA", "0,10", "08/10/2026"],
                ["P-001", "DIARIA", "0,20", "31/02/2026"],
            ],
            {"product_code": 1, "period": 2, "amount": 3, "effective_date": 4},
            Price,
        ),
        (
            "stock",
            [["Produto", "Quantidade"], ["P-001", "1,125"], ["P-001", "-1"]],
            {"product_code": 1, "quantity": 2},
            StockMovement,
        ),
    ],
)
def test_related_modules_decimal_dates_and_history(client, admin, entity, rows, columns, model):
    product(client, admin, individual=entity == "equipment")
    data, _ = upload(client, admin, rows)
    batch = data["batch"]["id"]
    target = mapping(entity, columns)
    before = count(client, model)
    report = preview(client, admin, batch, target)
    assert report["successful"] == 1
    assert report["errors"] == len(rows) - 2
    assert count(client, model) == before
    response = confirm(client, admin, batch, target, report)
    assert response.status_code == 200, response.text
    assert count(client, model) == before + 1
    if entity == "prices":
        assert client.get("/api/prices").json()["items"][0]["amount"] == "0.10"
    if entity == "stock":
        assert client.get("/api/stock").json()["items"][0]["balances"]["DISPONIVEL"] == "1.125"


def test_formula_without_cache_is_not_silently_zero(client, admin):
    data, _ = upload(client, admin, [["C", "N", "U"], ["X", "=1+1", "UN"]])
    target = mapping("products", {"code": 1, "name": 2, "unit": 3})
    report = preview(client, admin, data["batch"]["id"], target)
    assert report["successful"] == 0 and report["errors"] == 1
    assert "Fórmula sem resultado" in report["rows"][0]["message"]


def test_bad_files_mapping_and_confirmation_requirements(client, admin):
    for name, content in [("file.xls", b"old"), ("file.xlsx", b"not a workbook")]:
        assert (
            client.post(
                "/api/imports/upload", files={"file": (name, content)}, headers=admin[1]
            ).status_code
            == 422
        )
    data, _ = upload(client, admin, [["C", "N", "U"], ["P", "Produto", "UN"]])
    batch = data["batch"]["id"]
    target = mapping("products", {"code": 1, "name": 2, "unit": 3})
    for columns in [
        {"name": 2},
        {"code": 201, "name": 2, "unit": 3},
        {"code": 1, "name": 2, "unit": 3, "password": 1},
    ]:
        assert (
            client.post(
                f"/api/imports/{batch}/preview",
                json=target | {"columns": columns},
                headers=admin[1],
            ).status_code
            == 422
        )
    report = preview(client, admin, batch, target)
    assert (
        client.post(
            f"/api/imports/{batch}/confirm",
            json={"mapping": target, "preview_digest": report["digest"], "confirm": False},
            headers=admin[1],
        ).status_code
        == 422
    )
    assert client.post(f"/api/imports/{batch}/preview", json=target).status_code == 403
    original = client.app.state.settings.import_directory / (batch + ".xlsx")
    original.write_bytes(b"modified")
    assert client.get(f"/api/imports/{batch}").status_code == 409


def test_imports_require_authenticated_authorized_role(client, admin):
    content = workbook([["C"], ["D"]])
    client.post("/api/auth/logout", headers=admin[1])
    assert client.get("/api/imports").status_code == 401
    with Session(client.app.state.engine) as db:
        from app.auth.service import IdentityService

        IdentityService(db, local=True).create_user(
            "operator", "Operador", "Import-fixture-test!", ["OPERACAO"], must_change=False
        )
        db.commit()
    response = client.post(
        "/api/auth/login",
        json={
            "username": "operator",
            "password": "Import-fixture-test!",
        },
        headers={"Origin": "http://localhost:5173", "X-LocaControl-Request": "1"},
    )
    headers = {
        "Origin": "http://localhost:5173",
        "X-LocaControl-Request": "1",
        "X-CSRF-Token": response.json()["csrf_token"],
    }
    assert client.get("/api/imports").status_code == 403
    assert (
        client.post(
            "/api/imports/upload", files={"file": ("file.xlsx", content)}, headers=headers
        ).status_code
        == 403
    )


def test_reader_checks_limits_and_zero_padding():
    from app.imports.workbook import read_workbook

    book = Workbook()
    sheet = book.active
    sheet.append(["Código"])
    sheet.append([12])
    sheet["A2"].number_format = "00000"
    output = io.BytesIO()
    book.save(output)
    assert read_workbook(output.getvalue())[0]["values"][1][0] == "00012"
    sheet["GS1"] = "Mais de 200 colunas"
    output = io.BytesIO()
    book.save(output)
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        read_workbook(output.getvalue())
