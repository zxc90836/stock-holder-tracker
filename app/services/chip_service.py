from app.providers.tdcc_provider import (
    get_stock_holding_by_date,
    get_latest_stock_holding,
    get_available_dates,
    get_latest_open_data_date,
)


def calculate_chip_ratio_from_rows(stock_id: str, date: str, data: list):
    if not data:
        return None

    big_holder_ratio = 0.0
    retail_ratio = 0.0

    for row in data:
        level_raw = str(row["持股分級"]).strip()
        ratio = float(row["占集保庫存數比例%"])

        # 開放資料格式：分級代碼 1~17
        if level_raw.isdigit():
            level = int(level_raw)

            # 大戶：原本你的定義是第 15 級
            if level == 15:
                big_holder_ratio += ratio

            # 散戶：原本你的定義是第 1~3 級
            if level in [1, 2, 3]:
                retail_ratio += ratio

        # 官方歷史查詢頁格式：區間文字
        else:
            # 散戶對應前 3 個區間
            if level_raw in ["1-999", "1,000-5,000", "5,001-10,000"]:
                retail_ratio += ratio

            # 大戶對應最大級距
            if level_raw == "1,000,001以上":
                big_holder_ratio += ratio

    return {
        "stock_id": stock_id,
        "date": date,
        "big_holder_ratio": round(big_holder_ratio, 2),
        "retail_ratio": round(retail_ratio, 2),
    }


def calculate_chip_ratio(stock_id: str, date: str):
    data = get_stock_holding_by_date(stock_id, date)
    print(f"[DEBUG] calculate_chip_ratio stock_id={stock_id}, date={date}, has_data={bool(data)}")
    return calculate_chip_ratio_from_rows(stock_id, date, data)


def calculate_latest_chip_ratio(stock_id: str):
    data = get_latest_stock_holding(stock_id)

    if not data:
        return None

    date = str(data[0]["資料日期"]).strip()
    return calculate_chip_ratio_from_rows(stock_id, date, data)


def find_previous_available_chip_ratio(stock_id: str, date_now: str):
    info = get_available_dates()
    dates = info.get("dates", [])

    if date_now not in dates:
        return None

    idx = dates.index(date_now)

    for prev_date in dates[idx + 1:]:
        print(f"[DEBUG] trying previous official date: {prev_date}")
        result = calculate_chip_ratio(stock_id, prev_date)
        if result:
            print(f"[DEBUG] found previous data at: {prev_date}")
            return result

    print("[DEBUG] no previous data found")
    return None


def calculate_chip_change(stock_id: str, date_now: str | None = None):
    if not date_now:
        latest_date = get_latest_open_data_date()
        if not latest_date:
            return {
                "stock_id": stock_id,
                "date_now": None,
                "date_prev": None,
                "current": None,
                "previous": None,
                "big_holder_diff": None,
                "retail_diff": None,
                "message": "查無最新資料",
            }
        date_now = latest_date

    current = calculate_chip_ratio(stock_id, date_now)
    previous = find_previous_available_chip_ratio(stock_id, date_now)

    result = {
        "stock_id": stock_id,
        "date_now": date_now,
        "date_prev": previous["date"] if previous else None,
        "current": current,
        "previous": previous,
        "big_holder_diff": None if not current or not previous else round(
            current["big_holder_ratio"] - previous["big_holder_ratio"], 2
        ),
        "retail_diff": None if not current or not previous else round(
            current["retail_ratio"] - previous["retail_ratio"], 2
        ),
    }

    if not current:
        result["message"] = "查無當期資料"
    elif not previous:
        result["message"] = "目前查無前一期可比對資料"

    return result