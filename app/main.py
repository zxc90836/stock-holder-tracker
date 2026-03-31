from fastapi import FastAPI
from app.stock_api import router as stock_router
from app.histock_api import router as histock_router
from app.line_bot import router as line_bot_router
from app.watchlist_db import init_db

app = FastAPI(title="StockBot API")

init_db()
app.include_router(stock_router)
app.include_router(histock_router)
app.include_router(line_bot_router)