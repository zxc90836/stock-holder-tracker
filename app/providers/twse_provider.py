import requests


def get_stock_price(stock_id: str):
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&stockNo={stock_id}"

    res = requests.get(url)
    data = res.json()

    if "data" not in data or not data["data"]:
        return None

    title = data.get("title", "")
    parts = title.split()

    stock_name = "未知"
    if len(parts) >= 3:
        stock_name = parts[2]

    last_day = data["data"][-1]

    return {
        "date": last_day[0],
        "close_price": last_day[6],
        "stock_name": stock_name
    }