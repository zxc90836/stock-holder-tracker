# app/services/chart_service.py

import matplotlib.pyplot as plt
from io import BytesIO

from app.services.history_service import get_history


def generate_chart(stock_id: str, months: int = 6):
    data = get_history(stock_id, months)

    if not data:
        return None

    dates = [d["date"] for d in data]
    big = [d["big_holder_ratio"] for d in data]
    retail = [d["retail_ratio"] for d in data]

    plt.figure(figsize=(10, 5))
    plt.plot(dates, big, label="Big Holder")
    plt.plot(dates, retail, label="Retail")

    plt.xticks(rotation=45)
    plt.title(f"{stock_id} Holder Ratio (Last {months} Months)")
    plt.xlabel("Date")
    plt.ylabel("Ratio (%)")
    plt.legend()
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    plt.close()

    buf.seek(0)
    return buf