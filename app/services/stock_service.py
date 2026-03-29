from app.providers.twse_provider import get_stock_price


def convert_to_ad_date(roc_date: str):
    parts = roc_date.split("/")
    year = int(parts[0]) + 1911
    return f"{year}/{parts[1]}/{parts[2]}"


def get_stock_summary(stock_id: str):
    price_data = get_stock_price(stock_id)

    if not price_data:
        return {
            "stock_id": stock_id,
            "error": "查無資料"
        }

    ad_date = convert_to_ad_date(price_data["date"])
    stock_name = price_data.get("stock_name", "未知")

    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "latest_date": ad_date,
        "latest_price": price_data["close_price"],
        "summary": f"{stock_name}（{stock_id}）最新交易日 {ad_date}，收盤價 {price_data['close_price']} 元。"
    }