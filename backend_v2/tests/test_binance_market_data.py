from src.services import binance_market_data


def test_get_candles_maps_binance_klines(monkeypatch):
    def fake_request(path, params):
        assert path == "/api/v3/klines"
        assert params["symbol"] == "BTCUSDT"
        return [[1000, "10.0", "12.0", "9.0", "11.0", "123.45"]]

    monkeypatch.setattr(binance_market_data, "_request_json", fake_request)

    candles = binance_market_data.get_candles("BTCUSDT", "1h", 1)

    assert candles == [
        {"time": 1, "open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0, "volume": 123.45}
    ]


def test_get_order_book_maps_bids_asks_and_spread(monkeypatch):
    def fake_request(path, params):
        assert path == "/api/v3/depth"
        assert params == {"symbol": "ETHUSDT", "limit": 5}
        return {
            "lastUpdateId": 10,
            "bids": [["100.0", "2.0"], ["99.5", "1.0"]],
            "asks": [["101.0", "3.0"], ["101.5", "4.0"]],
        }

    monkeypatch.setattr(binance_market_data, "_request_json", fake_request)

    book = binance_market_data.get_order_book("ETHUSDT", 5)

    assert book["source"] == "binance"
    assert book["bids"][0] == {"price": 100.0, "quantity": 2.0, "total": 200.0}
    assert book["asks"][0] == {"price": 101.0, "quantity": 3.0, "total": 303.0}
    assert book["spread"] == 1.0
    assert book["mid_price"] == 100.5


def test_http_client_is_reused_for_the_same_base_url(monkeypatch):
    created = []

    class FakeClient:
        pass

    def build_client(**kwargs):
        created.append(kwargs)
        return FakeClient()

    binance_market_data._HTTP_CLIENTS.clear()
    monkeypatch.setattr(binance_market_data.httpx, "Client", build_client)

    first = binance_market_data._get_http_client("https://example.test")
    second = binance_market_data._get_http_client("https://example.test")

    assert first is second
    assert len(created) == 1
