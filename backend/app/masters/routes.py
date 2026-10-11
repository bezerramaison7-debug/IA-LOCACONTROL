from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import DB, require
from app.auth.models import User
from app.masters import schemas as s
from app.masters.models import Customer, Equipment, Price, Product, StockMovement
from app.masters.service import MasterService, page, view

router = APIRouter(prefix="/api", tags=["Cadastros, estoque e preços"])
CustomersRead = Annotated[User, Depends(require("customers.read"))]
CustomersWrite = Annotated[User, Depends(require("customers.write"))]
ProductsRead = Annotated[User, Depends(require("products.read"))]
ProductsWrite = Annotated[User, Depends(require("products.write"))]
EquipmentRead = Annotated[User, Depends(require("equipment.read"))]
EquipmentWrite = Annotated[User, Depends(require("equipment.write"))]
StockRead = Annotated[User, Depends(require("stock.read"))]
StockWrite = Annotated[User, Depends(require("stock.write"))]
PricesRead = Annotated[User, Depends(require("prices.read"))]
PricesWrite = Annotated[User, Depends(require("prices.write"))]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, Query(max_length=160)]


def listing(db, model, **filters):
    items, total = page(db, model, **filters)
    return {"items": [view(row) for row in items], "total": total}


@router.get("/customers")
def customers(
    db: DB,
    user: CustomersRead,
    q: Search = "",
    active: bool | None = None,
    offset: Offset = 0,
    limit: Limit = 20,
):
    return listing(db, Customer, q=q, active=active, offset=offset, limit=limit)


@router.get("/customers/{record_id}")
def customer(record_id: int, db: DB, user: CustomersRead):
    return view(MasterService(db, user).get(Customer, record_id))


@router.post("/customers", status_code=201)
def create_customer(payload: s.CustomerInput, db: DB, user: CustomersWrite):
    return MasterService(db, user).save(Customer, payload)


@router.put("/customers/{record_id}")
def update_customer(record_id: int, payload: s.CustomerUpdate, db: DB, user: CustomersWrite):
    return MasterService(db, user).save(Customer, payload, record_id)


@router.delete("/customers/{record_id}")
def delete_customer(record_id: int, version: int, db: DB, user: CustomersWrite):
    return MasterService(db, user).deactivate(Customer, record_id, version)


@router.get("/products")
def products(
    db: DB,
    user: ProductsRead,
    q: Search = "",
    active: bool | None = None,
    offset: Offset = 0,
    limit: Limit = 20,
):
    return listing(db, Product, q=q, active=active, offset=offset, limit=limit)


@router.get("/products/{record_id}")
def product(record_id: int, db: DB, user: ProductsRead):
    return view(MasterService(db, user).get(Product, record_id))


@router.post("/products", status_code=201)
def create_product(payload: s.ProductInput, db: DB, user: ProductsWrite):
    return MasterService(db, user).save(Product, payload)


@router.put("/products/{record_id}")
def update_product(record_id: int, payload: s.ProductUpdate, db: DB, user: ProductsWrite):
    return MasterService(db, user).save(Product, payload, record_id)


@router.delete("/products/{record_id}")
def delete_product(record_id: int, version: int, db: DB, user: ProductsWrite):
    return MasterService(db, user).deactivate(Product, record_id, version)


@router.get("/equipment")
def equipment(
    db: DB,
    user: EquipmentRead,
    q: Search = "",
    product_id: int | None = None,
    status: s.State | None = None,
    offset: Offset = 0,
    limit: Limit = 20,
):
    return listing(
        db, Equipment, q=q, product_id=product_id, status=status, offset=offset, limit=limit
    )


@router.get("/equipment/{record_id}")
def equipment_detail(record_id: int, db: DB, user: EquipmentRead):
    return view(MasterService(db, user).get(Equipment, record_id))


@router.post("/equipment", status_code=201)
def create_equipment(payload: s.EquipmentInput, db: DB, user: EquipmentWrite):
    return MasterService(db, user).save(Equipment, payload)


@router.put("/equipment/{record_id}")
def update_equipment(record_id: int, payload: s.EquipmentUpdate, db: DB, user: EquipmentWrite):
    return MasterService(db, user).save(Equipment, payload, record_id)


@router.post("/equipment/{record_id}/status")
def equipment_status(record_id: int, payload: s.EquipmentStatus, db: DB, user: StockWrite):
    return MasterService(db, user).equipment_status(record_id, payload)


@router.delete("/equipment/{record_id}")
def retire_equipment(
    record_id: int,
    version: Annotated[int, Query(ge=1)],
    reason: Annotated[str, Query(min_length=5, max_length=500)],
    db: DB,
    user: StockWrite,
):
    payload = s.EquipmentStatus(version=version, reason=reason, status="BAIXADO")
    return MasterService(db, user).equipment_status(record_id, payload)


@router.get("/stock")
def stock(
    db: DB,
    user: StockRead,
    q: Search = "",
    active: bool | None = None,
    offset: Offset = 0,
    limit: Limit = 20,
):
    items, total = page(db, Product, q=q, active=active, offset=offset, limit=limit)
    service = MasterService(db, user)
    return {"items": [service.stock_view(row) for row in items], "total": total}


@router.get("/stock/movements")
def movements(
    db: DB, user: StockRead, product_id: int | None = None, offset: Offset = 0, limit: Limit = 20
):
    return listing(db, StockMovement, product_id=product_id, offset=offset, limit=limit)


@router.post("/stock/movements", status_code=201)
def move(payload: s.MovementInput, db: DB, user: StockWrite):
    return MasterService(db, user).move(payload)


@router.get("/prices/effective")
def effective_price(product_id: int, period: s.Period, at: date, db: DB, user: PricesRead):
    return MasterService(db, user).effective_price(product_id, period, at)


@router.get("/prices")
def prices(
    db: DB,
    user: PricesRead,
    product_id: int | None = None,
    period: s.Period | None = None,
    offset: Offset = 0,
    limit: Limit = 20,
):
    return listing(db, Price, product_id=product_id, period=period, offset=offset, limit=limit)


@router.get("/prices/{record_id}")
def price_detail(record_id: int, db: DB, user: PricesRead):
    return view(MasterService(db, user).get(Price, record_id))


@router.post("/prices", status_code=201)
def create_price(payload: s.PriceInput, db: DB, user: PricesWrite):
    return MasterService(db, user).price(payload)


@router.put("/prices/{record_id}", status_code=201)
def revise_price(record_id: int, payload: s.PriceInput, db: DB, user: PricesWrite):
    return MasterService(db, user).price(payload, record_id)


@router.delete("/prices/{record_id}", status_code=201)
def retire_price(record_id: int, payload: s.PriceRetire, db: DB, user: PricesWrite):
    return MasterService(db, user).price(payload, record_id, retire=True)
