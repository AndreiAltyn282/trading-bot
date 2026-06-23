"""
Торговый бот для ПЕСОЧНИЦЫ с отслеживанием портфеля
Показывает баланс, прибыль/убыток и текущие позиции
"""

import time
import requests
from datetime import datetime
from tinkoff.invest import Client
from tinkoff.invest.constants import INVEST_GRPC_API_SANDBOX

# ========== НАСТРОЙКИ ==========
TOKEN = "t.fAbRlOPVkHo3BWzlRMEK-AOXMxnTDCrWW7nPnO8AGsSfNM5E48-UTfiJKOvr7BVQHoVel3YPx7mfJ0tldfB57w"          # ВСТАВЬТЕ СВОЙ ТОКЕН
TICKERS = ["SBER", "GAZP", "LKOH"]
INTERVAL = 30
MAX_AMOUNT = 10000
MIN_AMOUNT = 2000
INITIAL_BALANCE = 1000000    # Начальный виртуальный баланс (1 млн ₽)

# ========== ПОРТФЕЛЬ ==========
portfolio = {}               # Словарь: ticker -> {'quantity': 0, 'avg_price': 0}
balance = INITIAL_BALANCE    # Текущий баланс виртуальных рублей
total_buys = 0
total_sells = 0
first_run = True

# ========== ЛОГИРОВАНИЕ ==========
def log_message(text: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("trading_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{timestamp}: {text}\n")
    print(text)

# ========== ПОЛУЧЕНИЕ ТЕКУЩЕЙ ЦЕНЫ ==========
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

# ========== ОБРАБОТКА ОТВЕТА ИИ ==========
def parse_decision(text):
    text = text.upper()
    if "BUY" in text or "КУПИТЬ" in text or "ПОКУП" in text:
        return "BUY"
    elif "SELL" in text or "ПРОДАТ" in text or "ПРОДАЖ" in text:
        return "SELL"
    else:
        return "HOLD"

# ========== ЗАПРОС К ИИ (Ollama) ==========
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

# ========== РАСЧЁТ СУММЫ СДЕЛКИ ==========
def calculate_amount(price):
    if price <= 0:
        return MIN_AMOUNT
    base_amount = MAX_AMOUNT / (price / 100)
    amount = max(MIN_AMOUNT, min(MAX_AMOUNT, base_amount))
    return int(amount / price) * price

# ========== ПОКУПКА ==========
def buy_stock(ticker, price, quantity):
    global balance, total_buys, portfolio
    cost = price * quantity
    if cost > balance:
        print(f"⚠️ Недостаточно средств для покупки {ticker} (нужно {cost:.0f} ₽, доступно {balance:.0f} ₽)")
        return False
    
    if ticker in portfolio:
        # Усредняем цену
        total_cost = portfolio[ticker]['avg_price'] * portfolio[ticker]['quantity'] + cost
        total_qty = portfolio[ticker]['quantity'] + quantity
        portfolio[ticker]['avg_price'] = total_cost / total_qty
        portfolio[ticker]['quantity'] = total_qty
    else:
        portfolio[ticker] = {'quantity': quantity, 'avg_price': price}
    
    balance -= cost
    total_buys += 1
    msg = f"🔵 ПОКУПКА {ticker}: {quantity} шт. по {price:.2f} ₽ (сумма: {cost:.0f} ₽)"
    log_message(msg)
    return True

# ========== ПРОДАЖА ==========
def sell_stock(ticker, price):
    global balance, total_sells, portfolio
    if ticker not in portfolio or portfolio[ticker]['quantity'] <= 0:
        print(f"⚠️ Нет акций {ticker} для продажи")
        return False
    
    quantity = portfolio[ticker]['quantity']
    revenue = price * quantity
    balance += revenue
    total_sells += 1
    
    msg = f"🔴 ПРОДАЖА {ticker}: {quantity} шт. по {price:.2f} ₽ (выручка: {revenue:.0f} ₽)"
    log_message(msg)
    
    # Удаляем позицию
    del portfolio[ticker]
    return True

# ========== РАСЧЁТ СТОИМОСТИ ПОРТФЕЛЯ ==========
def calculate_portfolio_value(client):
    total_value = 0
    for ticker, data in portfolio.items():
        price = get_price(client, ticker)
        if price:
            total_value += price * data['quantity']
    return total_value

# ========== РАСЧЁТ ПРИБЫЛИ/УБЫТКА ==========
def calculate_profit_loss():
    total_invested = 0
    total_current = 0
    for ticker, data in portfolio.items():
        invested = data['avg_price'] * data['quantity']
        total_invested += invested
        # Текущую стоимость считаем отдельно при выводе
    return total_invested

# ========== ОТОБРАЖЕНИЕ ПОРТФЕЛЯ ==========
def show_portfolio(client):
    global balance, portfolio
    print("\n" + "=" * 60)
    print("📊 ТЕКУЩИЙ ПОРТФЕЛЬ")
    print("=" * 60)
    
    if not portfolio:
        print("  📭 Портфель пуст")
    else:
        total_invested = 0
        total_current = 0
        for ticker, data in portfolio.items():
            price = get_price(client, ticker)
            if price:
                invested = data['avg_price'] * data['quantity']
                current = price * data['quantity']
                profit = current - invested
                profit_pct = (profit / invested * 100) if invested > 0 else 0
                total_invested += invested
                total_current += current
                
                sign = "+" if profit >= 0 else ""
                print(f"  📈 {ticker}: {data['quantity']} шт.")
                print(f"     Средняя цена: {data['avg_price']:.2f} ₽")
                print(f"     Текущая цена: {price:.2f} ₽")
                print(f"     Прибыль/убыток: {sign}{profit:.0f} ₽ ({sign}{profit_pct:.1f}%)")
                print("  " + "-" * 40)
        
        # Общая прибыль/убыток по портфелю
        total_profit = total_current - total_invested
        total_profit_pct = (total_profit / total_invested * 100) if total_invested > 0 else 0
        sign_total = "+" if total_profit >= 0 else ""
        print(f"\n  💰 Общая стоимость портфеля: {total_current:.0f} ₽")
        print(f"  💰 Всего вложено: {total_invested:.0f} ₽")
        print(f"  📊 Общая прибыль/убыток: {sign_total}{total_profit:.0f} ₽ ({sign_total}{total_profit_pct:.1f}%)")
    
    print(f"\n  💵 Остаток на счете: {balance:.0f} ₽")
    print(f"  💰 Общий капитал: {balance + calculate_portfolio_value(client):.0f} ₽")
    print("=" * 60)

# ========== ГЛАВНЫЙ ЦИКЛ ==========
def main():
    global balance, portfolio, total_buys, total_sells, first_run
    
    print("🤖 Торговый бот запущен в ПЕСОЧНИЦЕ (виртуальные деньги)!")
    print(f"📊 Акции: {', '.join(TICKERS)}")
    print(f"💰 Начальный баланс: {INITIAL_BALANCE} ₽")
    print(f"💰 Сумма сделки: {MIN_AMOUNT} - {MAX_AMOUNT} ₽")
    print(f"⏱️ Интервал: {INTERVAL} сек")
    print("=" * 50)
    log_message("🤖 Торговый бот запущен (песочница)")

    with Client(TOKEN, target=INVEST_GRPC_API_SANDBOX) as client:
        while True:
            try:
                # Получаем цены и принимаем решения
                for ticker in TICKERS:
                    price = get_price(client, ticker)
                    if price is None:
                        continue
                    
                    print(f"\n📈 {ticker}: {price:.2f} ₽")
                    decision = ask_ai(ticker, price)
                    print(f"🧠 Решение: {decision}")
                    
                    if decision == "BUY":
                        amount = calculate_amount(price)
                        quantity = int(amount / price)
                        if quantity > 0:
                            buy_stock(ticker, price, quantity)
                    elif decision == "SELL":
                        sell_stock(ticker, price)
                    else:
                        print(f"  ⏸️ Ожидание")

                # Показываем портфель
                show_portfolio(client)
                
                print(f"📊 Статистика: покупок: {total_buys}, продаж: {total_sells}")
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
        print("⚠️ Вставьте токен в переменную TOKEN!")
    else:
        main()
