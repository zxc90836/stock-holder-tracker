# 📊 StockBot - TDCC Chip Analysis API

A lightweight stock chip analysis API based on TDCC (Taiwan Depository & Clearing Corporation) data.

This project provides real-time and historical analysis of stock holding distribution, including **big holder ratio**, **retail ratio**, and **weekly changes**.

---

## 🚀 Features

- 📥 Fetch latest TDCC stock holding data
- 📅 Query historical holding data (up to 1 year)
- 📊 Calculate:
  - Big holder ratio (大戶持股比例)
  - Retail ratio (散戶持股比例)
- 🔄 Compare latest vs previous period
- ⚡ FastAPI-based RESTful API
- 🧠 Automatically handles:
  - TDCC open data (latest)
  - TDCC official web query (historical)

---

## 🧩 API Endpoints

### Health Check