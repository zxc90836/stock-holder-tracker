from fastapi import FastAPI
from app.stock_api import router as stock_router

app = FastAPI(title="StockBot API")

app.include_router(stock_router)