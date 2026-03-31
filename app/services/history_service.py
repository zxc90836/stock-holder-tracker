from datetime import datetime, timedelta
from app.providers.tdcc_provider import get_available_dates, get_stock_holding_by_date
from app.services.chip_service import calculate_chip_ratio_from_rows

def get_history(stock_id: str, months: int = 6):
    dates_info = get_available_dates()
    dates = dates_info.get("dates", [])

    if not dates:
        return []

    cutoff = datetime.today() - timedelta(days=30 * months)

    result = []

    for date_str in dates:
        date_obj = datetime.strptime(date_str, "%Y%m%d")

        if date_obj < cutoff:
            continue

        raw = get_stock_holding_by_date(stock_id, date_str)

        if not raw:
            continue

        chip = calculate_chip_ratio_from_rows(stock_id, date_str, raw)

        if not chip:
            continue

        result.append({
            "date": date_str,
            "big_holder_ratio": chip["big_holder_ratio"],
            "retail_ratio": chip["retail_ratio"],
        })

    return sorted(result, key=lambda x: x["date"])