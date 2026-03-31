from fastapi import APIRouter, HTTPException, Query

from app.providers.histock_provider import HiStockProvider, HiStockProviderError

router = APIRouter(prefix="/histock", tags=["histock"])

provider = HiStockProvider()


@router.get("/latest/{stock_id}")
def get_histock_latest(stock_id: str):
    try:
        return provider.fetch_latest(stock_id)
    except HiStockProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HiStock latest 查詢失敗: {exc}") from exc


@router.get("/history/{stock_id}")
def get_histock_history(
    stock_id: str,
    limit: int = Query(10, ge=1, le=52, description="最多回傳幾筆歷史資料"),
):
    try:
        return {
            "stock_id": stock_id,
            "count": limit,
            "rows": provider.fetch_history(stock_id, limit=limit),
        }
    except HiStockProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HiStock history 查詢失敗: {exc}") from exc


@router.get("/compare/{stock_id}")
def get_histock_compare(
    stock_id: str,
    date_now: str = Query(..., description="格式: YYYYMMDD"),
    date_prev: str = Query(..., description="格式: YYYYMMDD"),
):
    try:
        return provider.fetch_two_dates(stock_id, date_now, date_prev)
    except HiStockProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HiStock compare 查詢失敗: {exc}") from exc


@router.get("/summary/{stock_id}")
def get_histock_summary(
    stock_id: str,
    date_now: str = Query(..., description="格式: YYYYMMDD"),
    date_prev: str = Query(..., description="格式: YYYYMMDD"),
):
    try:
        return {
            "stock_id": stock_id,
            "date_now": date_now,
            "date_prev": date_prev,
            "summary": provider.summarize_two_dates(stock_id, date_now, date_prev),
        }
    except HiStockProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HiStock summary 查詢失敗: {exc}") from exc


@router.get("/compare/latest/{stock_id}")
def get_histock_compare_latest(stock_id: str):
    try:
        return provider.fetch_latest_two_records(stock_id)
    except HiStockProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HiStock latest compare 查詢失敗: {exc}") from exc


@router.get("/summary/latest/{stock_id}")
def get_histock_summary_latest(stock_id: str):
    try:
        result = provider.fetch_latest_two_records(stock_id)
        return {
            "stock_id": stock_id,
            "date_now": result["date_now"],
            "date_prev": result["date_prev"],
            "summary": provider.summarize_latest_two_dates(stock_id),
        }
    except HiStockProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HiStock latest summary 查詢失敗: {exc}") from exc
    
@router.get("/trend/6m/{stock_id}")
def get_histock_trend_6m(stock_id: str):
    try:
        return provider.fetch_six_month_trend(stock_id)
    except HiStockProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HiStock 6m trend 查詢失敗: {exc}") from exc


@router.get("/trend/6m/summary/{stock_id}")
def get_histock_trend_6m_summary(stock_id: str):
    try:
        result = provider.fetch_six_month_trend(stock_id)
        return {
            "stock_id": stock_id,
            "period": "6m",
            "latest_date": result["latest_date"],
            "oldest_date": result["oldest_date"],
            "summary": provider.summarize_six_month_trend(stock_id),
        }
    except HiStockProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"HiStock 6m summary 查詢失敗: {exc}") from exc