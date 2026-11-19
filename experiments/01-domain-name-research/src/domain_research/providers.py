"""Provider lookups: plain HTTP, no LLM involved.

Each function takes a list of domains and returns one Quote per domain. A
lookup never guesses: anything it cannot confirm comes back as "unknown" with
a note saying why.
"""

import asyncio
import hashlib
import os
from collections.abc import Awaitable, Callable

import httpx

from .config import offline
from .schemas import Quote

TIMEOUT = httpx.Timeout(20.0)
RETRY_STATUS = {429, 500, 502, 503, 504}
Lookup = Callable[[list[str], httpx.AsyncClient], Awaitable[list[Quote]]]


def _unknown(provider: str, domains: list[str], note: str) -> list[Quote]:
    return [Quote(domain=d, provider=provider, status="unknown", note=note) for d in domains]


async def _request(client: httpx.AsyncClient, method: str, url: str, **kwargs) -> httpx.Response:
    """One HTTP call with up to three attempts on rate limits and server errors."""
    for attempt in range(3):
        try:
            response = await client.request(method, url, **kwargs)
            if response.status_code not in RETRY_STATUS:
                return response
        except httpx.TransportError:
            if attempt == 2:
                raise
        await asyncio.sleep(1.5 * (attempt + 1))
    return response


def _float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def godaddy(domains: list[str], client: httpx.AsyncClient) -> list[Quote]:
    token = os.environ.get("GODADDY_PAT")
    if not token:
        return _unknown("godaddy", domains, "GODADDY_PAT is not set")
    gate = asyncio.Semaphore(4)

    async def one(domain: str) -> Quote:
        async with gate:
            r = await _request(
                client,
                "GET",
                "https://api.godaddy.com/v3/domains/check-availability",
                params={"domain": domain},
                headers={"Authorization": f"Bearer {token}"},
            )
        if r.status_code != 200:
            return _unknown("godaddy", [domain], f"HTTP {r.status_code}")[0]
        body = r.json()
        if not body.get("available"):
            return Quote(domain=domain, provider="godaddy", status="taken")
        # Prices are per registration term, in the smallest currency unit (cents).
        prices = body.get("prices") or []
        first = min(prices, key=lambda p: _float(p.get("period")) or 99, default={})
        price = _float((first.get("price") or {}).get("value"))
        renewal = _float((first.get("renewalPrice") or {}).get("value"))
        return Quote(
            domain=domain,
            provider="godaddy",
            status="available",
            price=price / 100 if price is not None else None,
            renewal_price=renewal / 100 if renewal is not None else None,
            currency=(first.get("price") or {}).get("currencyCode") or "USD",
            note="" if body.get("definitive") else "availability not confirmed with the registry",
        )

    return list(await asyncio.gather(*(one(d) for d in domains)))


async def namecom(domains: list[str], client: httpx.AsyncClient) -> list[Quote]:
    user, token = os.environ.get("NAMECOM_USERNAME"), os.environ.get("NAMECOM_TOKEN")
    if not (user and token):
        return _unknown("namecom", domains, "NAMECOM_USERNAME or NAMECOM_TOKEN is not set")
    host = os.environ.get("NAMECOM_API_HOST", "api.name.com")
    quotes: list[Quote] = []
    for start in range(0, len(domains), 50):  # the API accepts 50 domains per call
        chunk = domains[start : start + 50]
        r = await _request(
            client,
            "POST",
            f"https://{host}/core/v1/domains:checkAvailability",
            json={"domainNames": chunk, "purchaseType": "registration"},
            auth=(user, token),
        )
        if r.status_code != 200:
            quotes += _unknown("namecom", chunk, f"HTTP {r.status_code}")
            continue
        by_name = {x.get("domainName"): x for x in r.json().get("results", [])}
        for domain in chunk:
            x = by_name.get(domain)
            if x is None:
                quotes += _unknown("namecom", [domain], "not in the provider's response")
            elif x.get("purchasable"):
                quotes.append(
                    Quote(
                        domain=domain,
                        provider="namecom",
                        status="available",
                        price=_float(x.get("purchasePrice")),
                        renewal_price=_float(x.get("renewalPrice")),
                        premium=x.get("premium"),
                    )
                )
            else:
                quotes.append(
                    Quote(domain=domain, provider="namecom", status="taken", note=x.get("reason") or "")
                )
    return quotes


async def porkbun(domains: list[str], client: httpx.AsyncClient) -> list[Quote]:
    key, secret = os.environ.get("PORKBUN_API_KEY"), os.environ.get("PORKBUN_SECRET_KEY")
    if not (key and secret):
        return _unknown("porkbun", domains, "PORKBUN_API_KEY or PORKBUN_SECRET_KEY is not set")
    quotes: list[Quote] = []
    for start in range(0, len(domains), 25):  # the API accepts 25 domains per call
        chunk = domains[start : start + 25]
        r = await _request(
            client,
            "POST",
            "https://api.porkbun.com/api/json/v3/domain/checkDomain",
            json={"apikey": key, "secretapikey": secret, "domains": chunk},
        )
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code != 200 or body.get("status") != "SUCCESS":
            quotes += _unknown("porkbun", chunk, body.get("message") or f"HTTP {r.status_code}")
            continue
        answered = body.get("domains") or {}
        for domain in chunk:
            x = answered.get(domain)
            if not x:
                quotes += _unknown("porkbun", [domain], "the registry did not answer in time")
            elif x.get("avail") == "yes":
                renewal = ((x.get("additional") or {}).get("renewal") or {}).get("price")
                quotes.append(
                    Quote(
                        domain=domain,
                        provider="porkbun",
                        status="available",
                        price=_float(x.get("price")),
                        renewal_price=_float(renewal),
                        premium=x.get("premium") == "yes",
                        note="first-year promo price" if x.get("firstYearPromo") == "yes" else "",
                    )
                )
            else:
                quotes.append(Quote(domain=domain, provider="porkbun", status="taken"))
    return quotes


async def registry(domains: list[str], client: httpx.AsyncClient) -> list[Quote]:
    """Registration status from the public RDAP system. No credentials, no prices."""
    gate = asyncio.Semaphore(4)

    async def one(domain: str) -> Quote:
        async with gate:
            r = await _request(client, "GET", f"https://rdap.org/domain/{domain}", follow_redirects=True)
        if r.status_code == 200:
            return Quote(domain=domain, provider="registry", status="taken")
        if r.status_code == 404:
            return Quote(
                domain=domain,
                provider="registry",
                status="available",
                note="not registered according to RDAP; this is not a price quote",
            )
        return _unknown("registry", [domain], f"HTTP {r.status_code}")[0]

    return list(await asyncio.gather(*(one(d) for d in domains)))


LOOKUPS: dict[str, Lookup] = {
    "godaddy": godaddy,
    "namecom": namecom,
    "porkbun": porkbun,
    "registry": registry,
}


def _fake(provider: str, domains: list[str]) -> list[Quote]:
    """Deterministic made-up quotes for offline mode."""
    quotes = []
    for domain in domains:
        seed = int(hashlib.sha256(f"{provider}:{domain}".encode()).hexdigest(), 16)
        taken = int(hashlib.sha256(domain.encode()).hexdigest(), 16) % 4 == 0
        if taken:
            quotes.append(Quote(domain=domain, provider=provider, status="taken", note="offline fake"))
        elif provider == "registry":
            quotes.append(Quote(domain=domain, provider=provider, status="available", note="offline fake"))
        else:
            price = 8 + seed % 1500 / 100
            quotes.append(
                Quote(
                    domain=domain,
                    provider=provider,
                    status="available",
                    price=round(price, 2),
                    renewal_price=round(price + 6, 2),
                    note="offline fake",
                )
            )
    return quotes


async def check(provider: str, domains: list[str]) -> list[Quote]:
    """Look up every domain at one provider. Never raises: failures become "unknown"."""
    domains = list(dict.fromkeys(d.strip().lower() for d in domains if d.strip()))
    if offline():
        return _fake(provider, domains)
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            return await LOOKUPS[provider](domains, client)
    except Exception as error:  # a provider outage must not take the run down
        return _unknown(provider, domains, f"lookup failed: {type(error).__name__}: {error}")
