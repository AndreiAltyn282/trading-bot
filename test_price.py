from tinkoff.invest import Client

TOKEN = "t.fAbRlOPVkHo3BWzlRMEK-AOXMxnTDCrWW7nPnO8AGsSfNM5E48-UTfiJKOvr7BVQHoVel3YPx7mfJ0tldfB57w"

with Client(TOKEN) as client:
    shares = client.instruments.shares()
    figi = None
    for inst in shares.instruments:
        if inst.ticker == "SBER":
            figi = inst.figi
            print(f"✅ Найден: {inst.name}")
            break
    if figi:
        prices = client.market_data.get_last_prices(figi=[figi])
        if prices.last_prices:
            price = prices.last_prices[0].price
            print(f"💰 Цена SBER: {price.units}.{price.nano // 100000000} ₽")
