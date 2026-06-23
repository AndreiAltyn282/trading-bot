"""
Торговый бот для песочницы Т-Банка
С реальным исполнением ордеров и выводом прибыли
"""

import time
import requests
from datetime import datetime
from tinkoff.invest import Client
from tinkoff.invest.constants import INVEST_GRPC_API_SANDBOX

# ============================================
# НАСТРОЙКИ (ЗАМЕНИТЕ НА СВОИ)
# ============================================
TOKEN = "t.fAbRlOPVkHo3BWzlRMEK-AOXMxnTDCrWW7nPnO8AGsSfNM5E48-UTfiJKOvr7BVQHoVel3YPx7mfJ0tldfB57w"  # Вставьте Sandbox-токен!
TICKERS = ["SBER", "GAZP", "LKOH"]
INTERVAL = 60
MAX_POSITION_SIZE = 50000
MIN_POSITION_SIZE = 5000

# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def log_message(text: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("trading_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{timestamp}: {text}\n")
    print(f"{timestamp}: {text}")

def get_figi_by_ticker(client, ticker: str):
    try:
        shares = client.instruments.shares()
        for inst in shares.instruments:
            if inst.ticker == ticker:
                return inst.figi
        return None
    except Exception as e:
        log_message(f"Ошибка поиска FIGI для {ticker}: {e}")
        return None

def get_price(client, ticker: str):
    try:
        figi = get_figi_by_ticker(client, ticker)
        if not figi:
            return None
        prices = client.market_data.get_last_prices(figi=[figi])
        if prices.last_prices:
            price = prices.last_prices[0].price
            return price.units + price.nano / 1_000_000_000
        return None
    except Exception as e:
        log_message(f"Ошибка получения цены {ticker}: {e}")
        return None

def get_current_position(client, figi: str):
    try:
        accounts = client.users.get_accounts()
        if not accounts.accounts:
            return 0
        account_id = accounts.accounts[0].id
        
        # Используем новый метод через operations
        positions = client.operations.get_positions(account_id=account_id)
        for pos in positions.positions:
            if pos.figi == figi:
                return pos.quantity.units + pos.quantity.nano / 1_000_000_000
        return 0
    except Exception as e:
        log_message(f"Ошибка получения позиции: {e}")
        return 0

# ============================================
# НОВАЯ ФУНКЦИЯ ПОЛУЧЕНИЯ БАЛАНСА (исправленная)
# ============================================

def get_sandbox_balance(client):
    try:
        accounts = client.users.get_accounts()
        if not accounts.accounts:
            return 0, 0
        
        account_id = accounts.accounts[0].id
        
        # Используем новый метод получения портфеля
        portfolio = client.operations.get_portfolio(account_id=account_id)
        
        # Получаем общую стоимость портфеля
        total = portfolio.total_amount_portfolio
        balance = total.units + total.nano / 1_000_000_000
        
        # Если баланс 0, пробуем получить деньги через positions
        if balance == 0:
            try:
                positions = client.operations.get_positions(account_id=account_id)
                for pos in positions.positions:
                    # Проверяем, есть ли деньги в позициях
                    if hasattr(pos, 'money') and pos.money:
                        for money in pos.money:
                            if money.currency == "rub":
                                balance = money.units + money.nano / 1_000_000_000
                                break
            except Exception:
                pass
        
        # Считаем прибыль/убыток
        total_profit = 0
        if hasattr(portfolio, 'positions') and portfolio.positions:
            for pos in portfolio.positions:
                if hasattr(pos, 'expected_yield') and pos.expected_yield:
                    profit = pos.expected_yield.units + pos.expected_yield.nano / 1_000_000_000
                    total_profit += profit
        
        return balance, total_profit
        
    except Exception as e:
        log_message(f"Ошибка получения баланса: {e}")
        return 0, 0

# ============================================
# ИИ ДЛЯ ПРИНЯТИЯ РЕШЕНИЙ
# ============================================

def parse_decision(text: str):
    text = text.upper()
    if "BUY" in text or "КУПИТЬ" in text or "ПОКУП" in text:
        return "BUY"
    elif "SELL" in text or "ПРОДАТ" in text or "ПРОДАЖ" in text:
        return "SELL"
    else:
        return "HOLD"

def ask_ai(ticker: str, price: float):
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
            timeout=30
        )
        response_text = resp.json().get("response", "HOLD")
        return parse_decision(response_text)
    except Exception as e:
        log_message(f"Ошибка ИИ: {e}")
        return "HOLD"

# ============================================
# ИСПОЛНЕНИЕ ТОРГОВЫХ ОРДЕРОВ
# ============================================

def calculate_quantity(price: float, max_amount: float, min_amount: float):
    if price <= 0:
        return 0
    
    amount = min(max_amount, (max_amount + min_amount) / 2)
    quantity = int(amount / price)
    
    if quantity * price < min_amount:
        quantity = int(min_amount / price) + 1
    
    return max(1, quantity)

def execute_buy(client, ticker: str, price: float):
    try:
        figi = get_figi_by_ticker(client, ticker)
        if not figi:
            return False
        
        quantity = calculate_quantity(price, MAX_POSITION_SIZE, MIN_POSITION_SIZE)
        total_cost = quantity * price
        
        balance, _ = get_sandbox_balance(client)
        if balance < total_cost:
            log_message(f"Недостаточно средств: {balance:.2f} руб, нужно {total_cost:.2f} руб")
            return False
        
        accounts = client.users.get_accounts()
        if not accounts.accounts:
            log_message("Нет аккаунтов")
            return False
        account_id = accounts.accounts[0].id
        
        # Используем новый метод post_sandbox_order
        client.sandbox.post_sandbox_order(
            account_id=account_id,
            figi=figi,
            quantity=quantity,
            price=price,
            direction=1,
            order_type=1,
        )
        
        log_message(f"ПОКУПКА {ticker}: {quantity} шт по {price:.2f} руб (сумма: {total_cost:.2f} руб)")
        return True
        
    except Exception as e:
        log_message(f"Ошибка покупки {ticker}: {e}")
        return False

def execute_sell(client, ticker: str, price: float):
    try:
        figi = get_figi_by_ticker(client, ticker)
        if not figi:
            return False
        
        quantity = get_current_position(client, figi)
        if quantity <= 0:
            log_message(f"Нет акций {ticker} для продажи")
            return False
        
        accounts = client.users.get_accounts()
        if not accounts.accounts:
            log_message("Нет аккаунтов")
            return False
        account_id = accounts.accounts[0].id
        
        client.sandbox.post_sandbox_order(
            account_id=account_id,
            figi=figi,
            quantity=int(quantity),
            price=price,
            direction=2,
            order_type=1,
        )
        
        total_cost = quantity * price
        log_message(f"ПРОДАЖА {ticker}: {int(quantity)} шт по {price:.2f} руб (сумма: {total_cost:.2f} руб)")
        return True
        
    except Exception as e:
        log_message(f"Ошибка продажи {ticker}: {e}")
        return False

# ============================================
# ГЛАВНЫЙ ЦИКЛ
# ============================================

def main():
    print("Торговый бот запущен (ПЕСОЧНИЦА Т-БАНКА)")
    print(f"Акции: {', '.join(TICKERS)}")
    print(f"Сумма на позицию: {MIN_POSITION_SIZE} - {MAX_POSITION_SIZE} руб")
    print(f"Интервал: {INTERVAL} сек")
    print("=" * 60)
    log_message("Торговый бот запущен (ПЕСОЧНИЦА)")

    with Client(TOKEN, target=INVEST_GRPC_API_SANDBOX) as client:
        # Пополняем песочницу деньгами
        try:
            accounts = client.users.get_accounts()
            if accounts.accounts:
                client.sandbox.sandbox_pay_in(
                    account_id=accounts.accounts[0].id,
                    amount=1000000
                )
                log_message("Песочница пополнена на 1 000 000 руб")
        except Exception as e:
            log_message(f"Не удалось пополнить песочницу: {e}")

        total_trades = 0
        
        while True:
            try:
                balance, profit = get_sandbox_balance(client)
                log_message(f"\nБаланс: {balance:.2f} руб | Прибыль: {profit:+.2f} руб")
                
                for ticker in TICKERS:
                    price = get_price(client, ticker)
                    if price is None:
                        continue
                    
                    log_message(f"{ticker}: {price:.2f} руб")
                    decision = ask_ai(ticker, price)
                    log_message(f"Решение: {decision}")
                    
                    if decision == "BUY":
                        if execute_buy(client, ticker, price):
                            total_trades += 1
                    elif decision == "SELL":
                        if execute_sell(client, ticker, price):
                            total_trades += 1
                    else:
                        log_message(f"{ticker}: Пропускаем")
                
                log_message(f"\nВсего сделок: {total_trades}")
                log_message(f"Следующая проверка через {INTERVAL} сек...")
                print("=" * 60)
                
                time.sleep(INTERVAL)
                
            except KeyboardInterrupt:
                log_message("\nБот остановлен")
                break
            except Exception as e:
                log_message(f"Ошибка: {e}")
                time.sleep(INTERVAL)

if __name__ == "__main__":
    if TOKEN == "ВАШ_SANDBOX_ТОКЕН":
        print("Вставьте Sandbox-токен в переменную TOKEN!")
        print("Получить токен: https://www.tbank.ru/invest/settings/")
    else:
        main()
