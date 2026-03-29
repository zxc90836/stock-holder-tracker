import re
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup

TDCC_PAGE_URL = "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"
TDCC_CSV_URL = "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"


def _build_headers():
    return {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.tdcc.com.tw/",
    }


def get_tdcc_raw_data():
    """開放資料：通常適合抓最新整批資料。"""
    return pd.read_csv(TDCC_CSV_URL)


def get_latest_open_data_date():
    df = get_tdcc_raw_data()

    if "資料日期" not in df.columns:
        return None

    dates = (
        df["資料日期"]
        .astype(str)
        .str.strip()
        .dropna()
        .unique()
        .tolist()
    )

    if not dates:
        return None

    return sorted(dates, reverse=True)[0]


def get_stock_holding_from_open_data(stock_id: str, date: str | None = None):
    """從開放資料中本地篩選。"""
    df = get_tdcc_raw_data()

    stock_id = str(stock_id).strip()
    df["證券代號"] = df["證券代號"].astype(str).str.strip()
    df["資料日期"] = df["資料日期"].astype(str).str.strip()

    stock_df = df[df["證券代號"] == stock_id].copy()

    if date:
        stock_df = stock_df[stock_df["資料日期"] == str(date).strip()]

    if stock_df.empty:
        return []

    return stock_df.to_dict(orient="records")


def _get_qrystock_page():
    """先 GET 查詢頁，拿 token 與可用日期。"""
    headers = _build_headers()
    res = requests.get(TDCC_PAGE_URL, headers=headers, timeout=20)
    res.raise_for_status()
    return res.text


def _extract_available_dates(html: str):
    """從 qryStock 頁面抓出官方可選日期。"""
    dates = re.findall(r"\b20\d{6}\b", html)
    unique_dates = list(dict.fromkeys(dates))
    return unique_dates


def _extract_token(html: str):
    """
    從頁面抓 SYNCHRONIZER_TOKEN。
    頁面改版時，可能需要調整這裡的 regex / selector。
    """
    # 先用 regex 試 hidden input
    m = re.search(
        r'name="SYNCHRONIZER_TOKEN"\s+value="([^"]+)"',
        html,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1)

    # 備援：用 BeautifulSoup 找 hidden input
    soup = BeautifulSoup(html, "html.parser")
    token_input = soup.find("input", {"name": "SYNCHRONIZER_TOKEN"})
    if token_input and token_input.get("value"):
        return token_input["value"]

    return None


def get_available_dates():
    html = _get_qrystock_page()
    dates = _extract_available_dates(html)

    return {
        "count": len(dates),
        "latest_date": dates[0] if dates else None,
        "dates": dates,
    }



def get_stock_holding_by_history_query(stock_id: str, date: str):
    headers = _build_headers()

    with requests.Session() as session:
        # 1. 先 GET 查詢頁，保留 cookie
        res_get = session.get(TDCC_PAGE_URL, headers=headers, timeout=20)
        res_get.raise_for_status()
        html_get = res_get.text

        token = _extract_token(html_get)
        if not token:
            print("[DEBUG][history_query] token not found")
            return []

        available_dates = _extract_available_dates(html_get)
        if date not in available_dates:
            print(f"[DEBUG][history_query] date {date} not in available dates")
            return []

        latest_date = available_dates[0]

        payload = {
            "method": "submit",
            "firDate": latest_date,
            "scaDate": date,
            "sqlMethod": "StockNo",
            "stockNo": str(stock_id).strip(),
            "stockName": "",
            "SYNCHRONIZER_URI": "/portal/zh/smWeb/qryStock",
            "SYNCHRONIZER_TOKEN": token,
        }

        print(f"[DEBUG][history_query] payload={payload}")

        # 2. 用同一個 session POST
        res_post = session.post(
            TDCC_PAGE_URL,
            data=payload,
            headers=headers,
            timeout=20,
        )
        res_post.raise_for_status()

        html_post = res_post.text

        print(f"[DEBUG][history_query] post_url={res_post.url}")
        print(f"[DEBUG][history_query] post_html_head={html_post[:500]}")

        # 3. 試著解析表格
        try:
            tables = pd.read_html(StringIO(html_post), flavor="lxml")
        except Exception as e:
            print(f"[DEBUG][history_query] read_html failed: {e}")
            return []

        print(f"[DEBUG][history_query] tables_found={len(tables)}")

        target_df = None
        for i, df in enumerate(tables):
            cols = [str(c).strip() for c in df.columns]
            print(f"[DEBUG][history_query] table_{i}_cols={cols}")

            # 官方歷史查詢頁的實際欄位名稱
            if "持股/單位數分級" in cols and "占集保庫存數比例 (%)" in cols:
                target_df = df.copy()
                break

        if target_df is None:
            print("[DEBUG][history_query] target table not found")
            return []

        # 欄位重新命名，統一成你現有 service 可用的格式
        rename_map = {
            "持股/單位數分級": "持股分級",
            "股數/單位數": "股數",
            "占集保庫存數比例 (%)": "占集保庫存數比例%",
        }
        target_df = target_df.rename(columns=rename_map)

        # 補上你後續會用到的欄位
        target_df["證券代號"] = str(stock_id).strip()
        target_df["資料日期"] = str(date).strip()

        # 只保留需要的欄位，避免多餘欄位干擾
        keep_cols = ["資料日期", "證券代號", "持股分級", "人數", "股數", "占集保庫存數比例%"]
        existing_cols = [c for c in keep_cols if c in target_df.columns]
        target_df = target_df[existing_cols].copy()

        if target_df.empty:
            print("[DEBUG][history_query] target table empty after normalize")
            return []

        return target_df.to_dict(orient="records")

def get_stock_holding_by_date(stock_id: str, date: str):
    """
    指定日期查詢：
    先走官方歷史查詢頁；
    若失敗，再退回開放資料本地篩選。
    """
    try:
        result = get_stock_holding_by_history_query(stock_id, date)
        if result:
            return result
    except Exception as e:
        print(f"[DEBUG][history_query] fallback to open data, error={e}")

    return get_stock_holding_from_open_data(stock_id, date)


def get_latest_stock_holding(stock_id: str):
    """
    最新資料仍可優先用開放資料。
    """
    latest_date = get_latest_open_data_date()
    if not latest_date:
        return []

    return get_stock_holding_from_open_data(stock_id, latest_date)