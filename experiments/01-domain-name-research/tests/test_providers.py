import httpx
import pytest

from domain_research import providers

pytestmark = pytest.mark.asyncio


def client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_godaddy_converts_cents_and_reports_taken(monkeypatch):
    monkeypatch.setenv("GODADDY_PAT", "t")

    def handler(request):
        if request.url.params["domain"] == "free.com":
            price = {"period": 1, "price": {"currencyCode": "USD", "value": 1199},
                     "renewalPrice": {"currencyCode": "USD", "value": 2199}}
            return httpx.Response(200, json={"available": True, "definitive": True, "prices": [price]})
        return httpx.Response(200, json={"available": False})

    async with client(handler) as c:
        free, taken = await providers.godaddy(["free.com", "taken.com"], c)
    assert (free.status, free.price, free.renewal_price) == ("available", 11.99, 21.99)
    assert taken.status == "taken"


async def test_namecom_maps_purchasable_and_missing(monkeypatch):
    monkeypatch.setenv("NAMECOM_USERNAME", "u")
    monkeypatch.setenv("NAMECOM_TOKEN", "t")
    results = [
        {"domainName": "free.com", "purchasable": True, "purchasePrice": 10.99, "renewalPrice": 17.99, "premium": False},
        {"domainName": "taken.com", "purchasable": False},
    ]
    async with client(lambda r: httpx.Response(200, json={"results": results})) as c:
        free, taken, missing = await providers.namecom(["free.com", "taken.com", "gone.com"], c)
    assert (free.status, free.price) == ("available", 10.99)
    assert taken.status == "taken"
    assert missing.status == "unknown"


async def test_porkbun_maps_avail_and_unresolved(monkeypatch):
    monkeypatch.setenv("PORKBUN_API_KEY", "k")
    monkeypatch.setenv("PORKBUN_SECRET_KEY", "s")
    body = {
        "status": "SUCCESS",
        "domains": {
            "free.com": {"avail": "yes", "price": "9.73", "firstYearPromo": "yes", "premium": "no",
                         "additional": {"renewal": {"price": "11.08"}}},
            "taken.com": {"avail": "no"},
        },
        "unresolved": ["slow.com"],
    }
    async with client(lambda r: httpx.Response(200, json=body)) as c:
        free, taken, slow = await providers.porkbun(["free.com", "taken.com", "slow.com"], c)
    assert (free.status, free.price, free.renewal_price, free.premium) == ("available", 9.73, 11.08, False)
    assert taken.status == "taken"
    assert slow.status == "unknown"


async def test_missing_credentials_and_http_errors_become_unknown(monkeypatch):
    monkeypatch.delenv("GODADDY_PAT", raising=False)
    async with client(lambda r: httpx.Response(200)) as c:
        assert (await providers.godaddy(["a.com"], c))[0].status == "unknown"
    monkeypatch.setenv("GODADDY_PAT", "t")
    async with client(lambda r: httpx.Response(403)) as c:
        quote = (await providers.godaddy(["a.com"], c))[0]
    assert (quote.status, quote.note) == ("unknown", "HTTP 403")
