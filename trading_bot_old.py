"""
Торговый бот с ИИ для нескольких акций
"""

import time
import requests
from datetime import datetime
from tinkoff.invest import Client

TOKEN = "t.fAbRlOPVkHo3BWzlRMEK-AOXMxnTDCrWW7nPnO8AGsSfNM5E48-UTfiJKOvr7BVQHoVel3YPx7mfJ0tldfB57w"
TICKERS = ["SBER", "GAZP", "LKOH"]
INTERVAL = 30
MAX_AMOUNT = 10000
MIN_AMOUNT = 2000

def log_message(text: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("trading_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{timestamp}: {text}\n")
    print(text)

def get_price(client, ticker):
    try:
        shares = client.instruments.shares()
        figi = None
        for inst in shares.instruments:
            if inst.ticker == ticker:
                figi = inst.figi
                break
        if not figi:
            return None
        prices = client.market_data.get_last_prices(figi=[figi])
        if prices.last_prices:
            price = prices.last_prices[0].price
            return price.units + price.nano / 1000000000
        return None
    except Exception as e:
        print(f"❌ Ошибка {ticker}: {e}")
        return None

def parse_decision(text):
    text = text.upper()
    if "BUY" in text or "КУПИТЬ" in text or "ПОКУП" in text:
        return "BUY"
    elif "SELL" in text or "ПРОДАТ" in text or "ПРОДАЖ" in text:
        return "SELL"
    else:
        return "HOLD"

def ask_ai(ticker, price):
    OLLAMA_URL = "http://localhost:11434/api/generate"
    prompt = f"""Акция {ticker} стоит {price:.2f} рублей.
Ты торговый робот. Ответь одной командой: BUY, SELL или HOLD.
Пример: BUY"""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": "llama3.2:latest",
                "prompt": prompt,
                "stream": False,
                "options": {"num_predict": 10, "temperature": 0.1}
            },
            timeout=60
        )
        return parse_decision(resp.json().get("response", "HOLD"))
    except Exception as e:
        print(f"⚠️ Ошибка ИИ: {e}")
        return "HOLD"

def calculate_amount(price):
    if price <= 0:
        return MIN_AMOUNT
    base_amount = MAX_AMOUNT / (price / 100)
    amount = max(MIN_AMOUNT, min(MAX_AMOUNT, base_amount))
    return int(amount / price) * price

def execute_trade(ticker, decision, price):
    if decision == "BUY":
        amount = calculate_amount(price)
        quantity = int(amount / price)
        if quantity <= 0:
            return
        msg = f"🔵 ПОКУПКА {ticker}: {quantity} шт. по {price:.2f} ₽ (сумма: {amount:.0f} ₽)"
    elif decision == "SELL":
        msg = f"🔴 ПРОДАЖА {ticker}: по {price:.2f} ₽"
    else:
        msg = f"⏸️ {ticker}: Ожидание"
    log_message(msg)
    return msg

def main():
    print("🤖 Торговый бот запущен!")
    print(f"📊 Акции: {', '.join(TICKERS)}")
    print(f"💰 Сумма: {MIN_AMOUNT} - {MAX_AMOUNT} ₽")
    print(f"⏱️ Интервал: {INTERVAL} сек")
    print("=" * 50)
    log_message("🤖 Торговый бот запущен!")

    with Client(TOKEN) as client:
        total_buys = 0
        total_sells = 0

        while True:
            try:
                for ticker in TICKERS:
                    price = get_price(client, ticker)
                    if price is None:
                        continue
                    print(f"\n📈 {ticker}: {price:.2f} ₽")
                    decision = ask_ai(ticker, price)
                    print(f"🧠 Решение: {decision}")
                    result = execute_trade(ticker, decision, price)
                    if "ПОКУПКА" in str(result):
                        total_buys += 1
                    elif "ПРОДАЖА" in str(result):
                        total_sells += 1

                print(f"\n📊 Статистика: покупок: {total_buys}, продаж: {total_sells}")
                print(f"⏱️ Следующая проверка через {INTERVAL} сек...")
                time.sleep(INTERVAL)

            except KeyboardInterrupt:
                print("\n🛑 Бот остановлен!")
                log_message("🛑 Торговый бот остановлен")
                break
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                time.sleep(INTERVAL)

if __name__ == "__main__":
    if TOKEN == "ВАШ_ТОКЕН":
        print("⚠️ Вставьте токен Т-Банка!")
    else:
        main()
