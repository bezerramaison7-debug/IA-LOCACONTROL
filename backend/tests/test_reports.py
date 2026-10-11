# ruff: noqa: F811 — pytest fixtures imported from other test modules are test parameters.
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook
from test_contracts import confirmed, contract_body
from test_operations import by_code, call, returning, withdrawal, world  # noqa: F401
from test_quotes import START, TODAY, admin, line, login, post  # noqa: F401


@pytest.fixture
def scene(client, admin, world):
    """Contrato 1 ativo (2 andaimes + gerador A), renovação 1.1 (1 andaime) e 1 devolvido."""
    person, scaffold, generator, units = world
    contract = confirmed(
        client,
        admin,
        person,
        [line(scaffold["id"], "4.000", "SEMANAL", 1), line(generator["id"], "1.000", "DIARIA", 5)],
    )
    and_item, ger_item = by_code(contract, "AND-1")["id"], by_code(contract, "GER-1")["id"]
    active = call(
        client,
        admin,
        contract["id"],
        "withdrawals",
        withdrawal(
            [
                {"contract_item_id": and_item, "quantity": "4.000"},
                {
                    "contract_item_id": ger_item,
                    "quantity": "1.000",
                    "equipment_ids": [units[0]["id"]],
                },
            ]
        ),
    )
    renewal = call(
        client,
        admin,
        contract["id"],
        "renew",
        {
            "version": active["version"],
            "start_date": START,
            "price_option": "ANTERIORES",
            "items": [
                {
                    "source_item_id": and_item,
                    "quantity": "2.000",
                    "period": "SEMANAL",
                    "period_count": 1,
                }
            ],
        },
    )
    call(
        client,
        admin,
        renewal["id"],
        "returns",
        returning(
            [
                {
                    "contract_item_id": renewal["items"][0]["id"],
                    "quantity": "1.000",
                    "condition": "BOM",
                }
            ]
        ),
    )
    post(
        client, admin, "contracts", contract_body(person["id"], [line(scaffold["id"])])
    )  # rascunho
    return person, scaffold, generator, contract, renewal


def rows(client, key, **params):
    response = client.get(f"/api/reports/{key}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_dashboard_reflects_real_contracts_and_stock(client, admin, scene):
    _person, _scaffold, _generator, contract, renewal = scene
    data = client.get("/api/dashboard").json()
    cards = data["cards"]
    assert cards["active_contracts"] == 2 and cards["awaiting_withdrawal"] == 0
    assert cards["rented_items"] == "4.000"  # 3 andaimes + 1 gerador com o cliente
    assert cards["equipment_available"] == 1 and cards["equipment_maintenance"] == 0
    # 4 × 390,00 + 1 × 90,00 × 5 no contrato 1; 2 × 390,00 na renovação.
    assert cards["contracted_value"] == "2790.00"
    # A devolução mais próxima é em 5 dias, fora da janela de 3 dias de "vencendo".
    assert cards["due_soon"] == cards["overdue"] == 0 and data["due_contracts"] == []
    assert data["due_soon_days"] == 3
    assert data["recent_events"][0]["kind"] == "CRIADO"  # o rascunho criado por último
    assert {event["contract_number"] for event in data["recent_events"]} >= {"1", "1.1"}
    assert renewal["number"] == "1.1" and contract["number"] == "1"


def test_every_report_runs_and_matches_the_operations(client, admin, scene):
    person, scaffold, _generator, _contract, _renewal = scene
    catalog = client.get("/api/reports").json()["items"]
    assert len(catalog) == 12
    for entry in catalog:
        report = rows(client, entry["key"])
        assert report["title"] == entry["title"] and report["columns"]
        assert report["total"] == len(report["rows"])

    active = rows(client, "active_rentals")
    assert [row["number"] for row in active["rows"]] == ["1", "1.1"]
    assert [row["status"] for row in active["rows"]] == ["ATIVO", "ATIVO"]
    assert rows(client, "overdue")["total"] == 0
    rented = rows(client, "rented_products")["rows"]
    assert {row["code"]: row["rented"] for row in rented} == {"AND-1": "3.000", "GER-1": "1.000"}
    available = {
        row["code"]: row["available"] for row in rows(client, "available_products")["rows"]
    }
    assert available == {"AND-1": "7.000", "GER-1": "1.000"}
    custody = rows(client, "equipment_by_customer")["rows"]
    assert sorted((row["number"], row["equipment"], row["quantity"]) for row in custody) == [
        ("1", "", "2.000"),
        ("1", "GER-A", "1.000"),
        ("1.1", "", "1.000"),
    ]
    history = rows(client, "equipment_history", q="GER-A")["rows"]
    assert [row["to_status"] for row in history] == ["LOCADO", "DISPONIVEL"]
    renewals = rows(client, "renewals")["rows"]
    assert [(row["number"], row["previous"], row["price_option"]) for row in renewals] == [
        ("1.1", "1", "ANTERIORES")
    ]
    returned = rows(client, "returns")["rows"]
    assert len(returned) == 1 and returned[0]["quantity"] == "1.000"
    assert returned[0]["condition"] == "BOM" and returned[0]["number"] == "1.1"
    revenue = rows(client, "contracted_revenue")
    assert revenue["rows"] == [{"month": START[:7], "contracts": 2, "total": "2790.00"}]
    assert "não representam pagamentos" in revenue["note"]
    products = rows(client, "top_products")["rows"]
    assert products[0]["code"] == "AND-1" and products[0]["rentals"] == 2
    assert products[0]["quantity"] == "6.000" and products[0]["total"] == "2340.00"
    customers = rows(client, "top_customers")["rows"]
    assert customers == [
        {
            "customer": person["legal_name"],
            "document": person["document"],
            "contracts": 2,
            "total": "2790.00",
        }
    ]
    tomorrow = (TODAY + timedelta(days=1)).isoformat()
    assert rows(client, "contracted_revenue", date_from=tomorrow)["total"] == 0
    assert rows(client, "top_products", product_id=scaffold["id"])["total"] == 1
    assert rows(client, "returns", limit=1, offset=1)["rows"] == []
    assert client.get("/api/reports/inexistente").status_code == 404


def test_exports_keep_numbers_and_dates_typed(client, admin, scene):
    response = client.get("/api/reports/active_rentals/export", params={"format": "xlsx"})
    assert response.status_code == 200 and response.content.startswith(b"PK")
    assert "relatorio-active_rentals.xlsx" in response.headers["content-disposition"]
    sheet = load_workbook(BytesIO(response.content)).active
    header = [cell.value for cell in sheet[1]]
    assert header[0] == "Contrato" and header[-1] == "Valor contratado"
    first = [cell.value for cell in sheet[2]]
    assert first[0] == "1" and first[5] == "Ativo"
    assert first[3].date() == date.fromisoformat(START)
    assert Decimal(str(first[-1])) == Decimal("2010")
    printable = client.get("/api/reports/contracted_revenue/export", params={"format": "pdf"})
    assert printable.status_code == 200 and printable.content.startswith(b"%PDF")
    assert client.get("/api/reports/overdue/export", params={"format": "csv"}).status_code == 422


def test_customer_summary_and_advanced_contract_search(client, admin, scene):
    person, _scaffold, _generator, contract, renewal = scene
    summary = client.get(f"/api/customers/{person['id']}/summary").json()
    assert summary["active_contracts"] == 2 and summary["total_contracts"] == 3
    assert summary["rented_items"] == "4.000" and summary["contracted_value"] == "2790.00"
    assert [row["number"] for row in summary["contracts"]] == ["2", "1.1", "1"]
    assert client.get("/api/customers/9999/summary").status_code == 404
    generated = client.post(f"/api/contracts/{contract['id']}/documents", json={}, headers=admin[1])
    assert generated.status_code == 201
    documents = client.get(f"/api/customers/{person['id']}/summary").json()["documents"]
    assert [(d["contract_number"], d["version"]) for d in documents] == [("1", 1)]

    def found(**params):
        data = client.get("/api/contracts", params=params).json()
        return sorted(row["number"] for row in data["items"])

    assert found(product="GER") == ["1"]
    assert found(product="andaime") == [] and found(product="AND-1") == ["1", "1.1", "2"]
    assert found(equipment="GER-A") == ["1"] and found(equipment="GER-B") == []
    assert found(period="DIARIA") == ["1"]
    assert found(origin="RENOVACAO") == ["1.1"] and found(origin="DIRETO") == ["1", "2"]
    assert found(q=person["document"], status="RASCUNHO") == ["2"]
    assert found(start_from=(TODAY + timedelta(days=1)).isoformat()) == []
    assert found(start_to=START, status="ATIVO") == ["1", "1.1"]
    assert found(start_to=START) == ["1", "1.1", "2"]
    assert renewal["chain_id"] == contract["id"]


@pytest.mark.parametrize(
    "role,dashboard,reports",
    [
        ("COMERCIAL", 200, 200),
        ("FINANCEIRO", 200, 200),
        ("OPERACAO", 200, 403),
        ("CLIENTE", 403, 403),
    ],
)
def test_report_permissions(client, admin, scene, role, dashboard, reports):
    person = scene[0]
    login(client, "worker", role)
    assert client.get("/api/dashboard").status_code == dashboard
    assert client.get(f"/api/customers/{person['id']}/summary").status_code == dashboard
    assert client.get("/api/reports").status_code == reports
    assert client.get("/api/reports/top_customers").status_code == reports
    assert client.get("/api/reports/top_customers/export").status_code == reports
    client.cookies.clear()
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/reports/returns/export").status_code == 401
