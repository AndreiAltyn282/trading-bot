from tinkoff.invest import Client
from tinkoff.invest.constants import INVEST_GRPC_API_SANDBOX

TOKEN = "t.fAbRlOPVkHo3BWzlRMEK-AOXMxnTDCrWW7nPnO8AGsSfNM5E48-UTfiJKOvr7BVQHoVel3YPx7mfJ0tldfB57w"  # ВСТАВЬТЕ СВОЙ ТОКЕН

try:
    with Client(TOKEN, target=INVEST_GRPC_API_SANDBOX) as client:
        accounts = client.users.get_accounts()
        print("✅ Токен работает (песочница)! Ваши счета:")
        for acc in accounts.accounts:
            print(f"  📁 {acc.name}")
except Exception as e:
    print(f"❌ Ошибка: {e}")
