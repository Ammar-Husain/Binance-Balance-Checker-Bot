import hashlib
import hmac
import time

import requests

from .errors import CredentialsError


def get_balance_status(api_key, api_secret):
    base_url = "https://api.binance.com"
    endpoint = "/sapi/v1/asset/wallet/balance"

    timestamp = int(time.time() * 1000)
    query_string = f"timestamp={timestamp}"
    signature = hmac.new(
        api_secret.encode(), query_string.encode(), hashlib.sha256
    ).hexdigest()

    url = f"{base_url}{endpoint}?{query_string}&signature={signature}"
    headers = {"X-MBX-APIKEY": api_key}

    response = requests.get(url, headers=headers)
    data = response.json()

    if "code" in data and data.get("code") != 0:
        if data["code"] == -2008:
            raise CredentialsError("Invalid API Credentials")
        else:
            raise ValueError(f"Non zero status: {data}")

    else:
        price_url = f"{base_url}/api/v3/ticker/price?symbol=BTCUSDT"
        btc_price = float(requests.get(price_url).json()["price"])
        current_state = {}
        if isinstance(data, list):
            for entry in data:
                name = entry.get("walletName")
                balance = entry.get("balance")
                if balance and float(balance) > 0:
                    current_state[name] = round(float(balance) * btc_price, 2)
            return current_state
        else:
            raise ValueError(f"Unexpected response format: {data}")
