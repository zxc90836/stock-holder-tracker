from providers.histock_provider import HiStockProvider

provider = HiStockProvider()

result = provider.fetch_two_dates("2206", "20260327", "20260320")
print(result)

print()
print(provider.summarize_two_dates("2206", "20260327", "20260320"))