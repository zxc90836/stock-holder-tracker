from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup


HISTOCK_BASE_URL = "https://histock.tw/stock/large.aspx"


class HiStockProviderError(Exception):
    """Raised when HiStock data cannot be fetched or parsed."""


@dataclass
class HiStockHolderRow:
    stock_id: str
    date: str  # YYYYMMDD
    concentration_ratio: float       # 籌碼集中度
    foreign_ratio: float             # 外資籌碼
    big_holder_ratio: float          # 大戶籌碼
    director_supervisor_ratio: float # 董監持股

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HiStockProvider:
    """
    Provider for HiStock '主力籌碼集中度 歷史資料'.

    Main target fields:
      1. big_holder_ratio
      2. director_supervisor_ratio
      3. foreign_ratio
      4. concentration_ratio
    """

    def __init__(
        self,
        timeout: int = 15,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                ),
                "Referer": "https://histock.tw/",
            }
        )

    def fetch_history(
        self,
        stock_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch full history rows from HiStock.
        Returns rows sorted by date desc.
        """
        html = self._fetch_page_html(stock_id)

        rows = self._parse_by_regex(stock_id, html)
        if not rows:
            rows = self._parse_by_html_table(stock_id, html)

        if not rows:
            raise HiStockProviderError(
                f"Unable to parse HiStock history table for stock_id={stock_id}"
            )

        rows.sort(key=lambda x: x.date, reverse=True)

        if limit is not None:
            rows = rows[:limit]

        return [row.to_dict() for row in rows]

    def fetch_latest(self, stock_id: str) -> Dict[str, Any]:
        rows = self.fetch_history(stock_id, limit=1)
        if not rows:
            raise HiStockProviderError(f"No HiStock data found for stock_id={stock_id}")
        return rows[0]

    def fetch_two_dates(
        self,
        stock_id: str,
        date_now: str,
        date_prev: str,
    ) -> Dict[str, Any]:
        """
        Find two exact dates from fetched history.
        date format: YYYYMMDD
        """
        rows = self.fetch_history(stock_id)
        row_map = {row["date"]: row for row in rows}

        current = row_map.get(date_now)
        previous = row_map.get(date_prev)

        return {
            "stock_id": stock_id,
            "date_now": date_now,
            "date_prev": date_prev,
            "current": current,
            "previous": previous,
            "big_holder_diff": self._diff(current, previous, "big_holder_ratio"),
            "director_supervisor_diff": self._diff(
                current, previous, "director_supervisor_ratio"
            ),
            "foreign_diff": self._diff(current, previous, "foreign_ratio"),
            "concentration_diff": self._diff(current, previous, "concentration_ratio"),
        }

    def summarize_two_dates(
        self,
        stock_id: str,
        date_now: str,
        date_prev: str,
    ) -> str:
        """
        Return a plain-text summary for LINE Bot / API response.
        """
        result = self.fetch_two_dates(stock_id, date_now, date_prev)
        current = result["current"]
        previous = result["previous"]

        if not current and not previous:
            return (
                f"{stock_id} 在 HiStock 找不到 {date_now} 與 {date_prev} 的歷史資料。"
            )
        if not current:
            return f"{stock_id} 在 HiStock 找不到 {date_now} 的歷史資料。"
        if not previous:
            return f"{stock_id} 在 HiStock 找不到 {date_prev} 的歷史資料。"

        return (
            f"{stock_id} HiStock 籌碼摘要\n"
            f"比較區間：{date_prev} → {date_now}\n"
            f"大戶：{previous['big_holder_ratio']:.2f}% → {current['big_holder_ratio']:.2f}% "
            f"({result['big_holder_diff']:+.2f})\n"
            f"董監：{previous['director_supervisor_ratio']:.2f}% → {current['director_supervisor_ratio']:.2f}% "
            f"({result['director_supervisor_diff']:+.2f})\n"
            f"外資：{previous['foreign_ratio']:.2f}% → {current['foreign_ratio']:.2f}% "
            f"({result['foreign_diff']:+.2f})\n"
            f"籌碼集中度：{previous['concentration_ratio']:.2f}% → {current['concentration_ratio']:.2f}% "
            f"({result['concentration_diff']:+.2f})"
        )

    def _fetch_page_html(self, stock_id: str) -> str:
        try:
            response = self.session.get(
                HISTOCK_BASE_URL,
                params={"no": stock_id},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise HiStockProviderError(
                f"Failed to fetch HiStock page for stock_id={stock_id}: {exc}"
            ) from exc

        # requests usually handles encoding here, but keep a fallback
        if not response.encoding:
            response.encoding = response.apparent_encoding or "utf-8"

        return response.text

    def _parse_by_regex(self, stock_id: str, html: str) -> List[HiStockHolderRow]:
        """
        Primary parser:
        Parse from whole page text because HiStock may compress table text in HTML.
        """
        text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

        marker = "主力籌碼集中度 歷史資料"
        if marker in text:
            text = text.split(marker, 1)[1]

        # date + 4 percentage fields
        pattern = re.compile(
            r"(\d{4}/\d{2}/\d{2})\s*"
            r"([0-9]+(?:\.[0-9]+)?)%\s*"
            r"([0-9]+(?:\.[0-9]+)?)%\s*"
            r"([0-9]+(?:\.[0-9]+)?)%\s*"
            r"([0-9]+(?:\.[0-9]+)?)%"
        )

        rows: List[HiStockHolderRow] = []
        for match in pattern.finditer(text):
            date_raw, concentration, foreign_, big_holder, director = match.groups()
            rows.append(
                HiStockHolderRow(
                    stock_id=stock_id,
                    date=self._normalize_date(date_raw),
                    concentration_ratio=float(concentration),
                    foreign_ratio=float(foreign_),
                    big_holder_ratio=float(big_holder),
                    director_supervisor_ratio=float(director),
                )
            )

        rows = self._deduplicate_rows(rows)
        return rows

    def _parse_by_html_table(self, stock_id: str, html: str) -> List[HiStockHolderRow]:
        """
        Fallback parser:
        Try pandas.read_html and detect matching table by column names / content.
        """
        rows: List[HiStockHolderRow] = []

        try:
            tables = pd.read_html(html)
        except ValueError:
            return rows

        for df in tables:
            df = df.copy()
            df.columns = [str(col).strip() for col in df.columns]

            normalized_cols = "".join(df.columns)

            # Try to detect target table
            if not any(keyword in normalized_cols for keyword in ["日期", "集中度", "外資", "大戶", "董監"]):
                continue

            # Normalize common column names
            colmap = self._guess_column_map(df.columns)
            required = {
                "date",
                "concentration_ratio",
                "foreign_ratio",
                "big_holder_ratio",
                "director_supervisor_ratio",
            }
            if not required.issubset(colmap):
                continue

            for _, row in df.iterrows():
                try:
                    date_raw = str(row[colmap["date"]]).strip()
                    rows.append(
                        HiStockHolderRow(
                            stock_id=stock_id,
                            date=self._normalize_date(date_raw),
                            concentration_ratio=self._parse_percent(
                                row[colmap["concentration_ratio"]]
                            ),
                            foreign_ratio=self._parse_percent(
                                row[colmap["foreign_ratio"]]
                            ),
                            big_holder_ratio=self._parse_percent(
                                row[colmap["big_holder_ratio"]]
                            ),
                            director_supervisor_ratio=self._parse_percent(
                                row[colmap["director_supervisor_ratio"]]
                            ),
                        )
                    )
                except Exception:
                    continue

            if rows:
                break

        rows = self._deduplicate_rows(rows)
        return rows

    @staticmethod
    def _guess_column_map(columns: List[str]) -> Dict[str, str]:
        colmap: Dict[str, str] = {}

        for col in columns:
            c = str(col).replace("\n", "").replace(" ", "")
            if "日期" in c:
                colmap["date"] = col
            elif "集中度" in c:
                colmap["concentration_ratio"] = col
            elif "外資" in c:
                colmap["foreign_ratio"] = col
            elif "大戶" in c:
                colmap["big_holder_ratio"] = col
            elif "董監" in c:
                colmap["director_supervisor_ratio"] = col

        return colmap

    @staticmethod
    def _parse_percent(value: Any) -> float:
        text = str(value).strip().replace("%", "").replace(",", "")
        return float(text)

    @staticmethod
    def _normalize_date(date_text: str) -> str:
        date_text = date_text.strip().replace("-", "/")
        dt = datetime.strptime(date_text, "%Y/%m/%d")
        return dt.strftime("%Y%m%d")

    @staticmethod
    def _deduplicate_rows(rows: List[HiStockHolderRow]) -> List[HiStockHolderRow]:
        dedup: Dict[str, HiStockHolderRow] = {}
        for row in rows:
            dedup[row.date] = row
        return list(dedup.values())

    @staticmethod
    def _diff(
        current: Optional[Dict[str, Any]],
        previous: Optional[Dict[str, Any]],
        key: str,
    ) -> Optional[float]:
        if not current or not previous:
            return None
        return round(float(current[key]) - float(previous[key]), 2)
    
    def fetch_two_dates(
        self,
        stock_id: str,
        date_now: str,
        date_prev: str,
    ) -> Dict[str, Any]:
        rows = self.fetch_history(stock_id)
        row_map = {row["date"]: row for row in rows}

        current = row_map.get(date_now)
        previous = row_map.get(date_prev)

        return {
            "stock_id": stock_id,
            "date_now": date_now,
            "date_prev": date_prev,
            "current": current,
            "previous": previous,
            "big_holder_diff": self._diff(current, previous, "big_holder_ratio"),
            "director_supervisor_diff": self._diff(
                current, previous, "director_supervisor_ratio"
            ),
            "foreign_diff": self._diff(current, previous, "foreign_ratio"),
            "concentration_diff": self._diff(current, previous, "concentration_ratio"),
        }

    def summarize_two_dates(
        self,
        stock_id: str,
        date_now: str,
        date_prev: str,
    ) -> str:
        result = self.fetch_two_dates(stock_id, date_now, date_prev)
        current = result["current"]
        previous = result["previous"]

        if not current and not previous:
            return f"{stock_id} 在 HiStock 找不到 {date_now} 與 {date_prev} 的資料。"
        if not current:
            return f"{stock_id} 在 HiStock 找不到 {date_now} 的資料。"
        if not previous:
            return f"{stock_id} 在 HiStock 找不到 {date_prev} 的資料。"

        return (
            f"{stock_id} HiStock 籌碼摘要\n"
            f"比較區間：{date_prev} → {date_now}\n"
            f"大戶：{previous['big_holder_ratio']:.2f}% → {current['big_holder_ratio']:.2f}% "
            f"({result['big_holder_diff']:+.2f})\n"
            f"董監：{previous['director_supervisor_ratio']:.2f}% → {current['director_supervisor_ratio']:.2f}% "
            f"({result['director_supervisor_diff']:+.2f})\n"
            f"外資：{previous['foreign_ratio']:.2f}% → {current['foreign_ratio']:.2f}% "
            f"({result['foreign_diff']:+.2f})\n"
            f"籌碼集中度：{previous['concentration_ratio']:.2f}% → {current['concentration_ratio']:.2f}% "
            f"({result['concentration_diff']:+.2f})"
        )

    @staticmethod
    def _diff(
        current: Optional[Dict[str, Any]],
        previous: Optional[Dict[str, Any]],
        key: str,
    ) -> Optional[float]:
        if not current or not previous:
            return None
        return round(float(current[key]) - float(previous[key]), 2)
    def fetch_latest_two_records(self, stock_id: str) -> Dict[str, Any]:
        rows = self.fetch_history(stock_id, limit=2)

        if len(rows) < 2:
            raise HiStockProviderError(f"{stock_id} 的 HiStock 歷史資料不足 2 筆，無法比較。")

        current = rows[0]
        previous = rows[1]

        return {
            "stock_id": stock_id,
            "date_now": current["date"],
            "date_prev": previous["date"],
            "current": current,
            "previous": previous,
            "big_holder_diff": self._diff(current, previous, "big_holder_ratio"),
            "director_supervisor_diff": self._diff(
                current, previous, "director_supervisor_ratio"
            ),
            "foreign_diff": self._diff(current, previous, "foreign_ratio"),
            "concentration_diff": self._diff(current, previous, "concentration_ratio"),
        }

    def summarize_latest_two_dates(self, stock_id: str) -> str:
        result = self.fetch_latest_two_records(stock_id)
        current = result["current"]
        previous = result["previous"]

        return (
            f"{stock_id} HiStock 籌碼摘要\n"
            f"比較區間：{result['date_prev']} → {result['date_now']}\n"
            f"大戶：{previous['big_holder_ratio']:.2f}% → {current['big_holder_ratio']:.2f}% "
            f"({result['big_holder_diff']:+.2f})\n"
            f"董監：{previous['director_supervisor_ratio']:.2f}% → {current['director_supervisor_ratio']:.2f}% "
            f"({result['director_supervisor_diff']:+.2f})\n"
            f"外資：{previous['foreign_ratio']:.2f}% → {current['foreign_ratio']:.2f}% "
            f"({result['foreign_diff']:+.2f})\n"
            f"籌碼集中度：{previous['concentration_ratio']:.2f}% → {current['concentration_ratio']:.2f}% "
            f"({result['concentration_diff']:+.2f})"
        )
    def fetch_six_month_trend(self, stock_id: str, limit: int = 26) -> Dict[str, Any]:
        """
        6 個月約抓 26 週資料。
        HiStock 這頁通常是週資料，所以 26 筆可近似 6 個月。
        """
        rows = self.fetch_history(stock_id, limit=limit)

        if not rows:
            raise HiStockProviderError(f"{stock_id} 查無 HiStock 6 個月趨勢資料。")

        latest = rows[0]
        oldest = rows[-1]

        return {
            "stock_id": stock_id,
            "period": "6m",
            "count": len(rows),
            "latest_date": latest["date"],
            "oldest_date": oldest["date"],
            "latest": latest,
            "oldest": oldest,
            "big_holder_diff": self._diff(latest, oldest, "big_holder_ratio"),
            "director_supervisor_diff": self._diff(
                latest, oldest, "director_supervisor_ratio"
            ),
            "foreign_diff": self._diff(latest, oldest, "foreign_ratio"),
            "concentration_diff": self._diff(
                latest, oldest, "concentration_ratio"
            ),
            "rows": rows,
        }

    def summarize_six_month_trend(self, stock_id: str, limit: int = 26) -> str:
        result = self.fetch_six_month_trend(stock_id, limit=limit)

        latest = result["latest"]
        oldest = result["oldest"]

        return (
            f"{stock_id} HiStock 近6個月籌碼趨勢\n"
            f"區間：{result['oldest_date']} → {result['latest_date']}\n"
            f"大戶：{oldest['big_holder_ratio']:.2f}% → {latest['big_holder_ratio']:.2f}% "
            f"({result['big_holder_diff']:+.2f})\n"
            f"董監：{oldest['director_supervisor_ratio']:.2f}% → {latest['director_supervisor_ratio']:.2f}% "
            f"({result['director_supervisor_diff']:+.2f})\n"
            f"外資：{oldest['foreign_ratio']:.2f}% → {latest['foreign_ratio']:.2f}% "
            f"({result['foreign_diff']:+.2f})\n"
            f"籌碼集中度：{oldest['concentration_ratio']:.2f}% → {latest['concentration_ratio']:.2f}% "
            f"({result['concentration_diff']:+.2f})\n"
            f"整體判讀：{self._build_trend_comment(result)}"
        )

    def _build_trend_comment(self, result: Dict[str, Any]) -> str:
        rows = result.get("rows", [])
        if len(rows) < 3:
            return "資料不足，無法判讀趨勢"

        def analyze(series: list[float]) -> str:
            diff_total = series[0] - series[-1]
            recent_diff = series[0] - series[2]  # 最近三筆

            # 判斷方向
            if diff_total > 0:
                trend = "上升"
            elif diff_total < 0:
                trend = "下降"
            else:
                trend = "盤整"

            # 判斷近期
            if recent_diff > 0:
                recent = "近期走強"
            elif recent_diff < 0:
                recent = "近期轉弱"
            else:
                recent = "近期持平"

            # 判斷穩定度（波動）
            volatility = max(series) - min(series)
            if volatility < 1:
                stable = "走勢平穩"
            elif volatility < 3:
                stable = "略有波動"
            else:
                stable = "波動明顯"

            return f"{trend}（{recent}，{stable}）"

        big_holder_series = [r["big_holder_ratio"] for r in rows]
        foreign_series = [r["foreign_ratio"] for r in rows]
        concentration_series = [r["concentration_ratio"] for r in rows]

        return (
            f"籌碼集中度：{analyze(concentration_series)}；"
            f"大戶：{analyze(big_holder_series)}；"
            f"外資：{analyze(foreign_series)}"
        )