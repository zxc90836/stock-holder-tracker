from fastapi import APIRouter
from app.providers.tdcc_provider import (
    get_available_dates,
    get_stock_holding_by_date,
    get_latest_stock_holding,
)
from app.services.chip_service import (
    calculate_chip_ratio,
    calculate_chip_change,
    calculate_latest_chip_ratio,
)

router = APIRouter()


@router.get("/")
def read_root():
    return {"message": "StockBot API running"}


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/tdcc/raw/head")
def tdcc_raw_head():
    return get_available_dates()


@router.get("/tdcc/{stock_id}")
def tdcc_stock(stock_id: str):
    data = get_latest_stock_holding(stock_id)
    if not data:
        return {"stock_id": stock_id, "message": "查無最新資料"}
    return data


@router.get("/tdcc/{date}/{stock_id}")
def tdcc_stock_by_date(date: str, stock_id: str):
    data = get_stock_holding_by_date(stock_id, date)
    if not data:
        return []
    return data


# 這兩條要放前面
@router.get("/chip/latest/{stock_id}")
def chip_latest(stock_id: str):
    result = calculate_latest_chip_ratio(stock_id)
    if not result:
        return {"stock_id": stock_id, "message": "查無最新資料"}
    return result


@router.get("/chip/change/{stock_id}")
def chip_change(stock_id: str):
    return calculate_chip_change(stock_id)


# 這條放最後
@router.get("/chip/{date}/{stock_id}")
def chip_ratio(date: str, stock_id: str):
    result = calculate_chip_ratio(stock_id, date)
    if not result:
        return {"stock_id": stock_id, "date": date, "message": "查無資料"}
    return result