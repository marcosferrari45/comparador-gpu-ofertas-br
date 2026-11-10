#!/usr/bin/env python3
"""Atualiza as cotações em reais do catálogo do comparador."""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "fontes.json"
CATALOG = ROOT / "catalogo.json"
OUTPUT = ROOT / "precos.json"
BOT = "GPUPriceMonitor"
HEADERS = {
    "User-Agent": f"{BOT}/1.0 (+https://github.com/marcosferrari45/comparador-gpu-ofertas-br)"
}
BRL_PRICE = re.compile(r"R\$\s*((?:\d{1,3}(?:\.\d{3})+|\d+),\d{2})(?!\d)")
SOURCE_DATE = re.compile(r"\bEm\s+(\d{1,2}/\d{1,2}(?:/\d{4})?\s+às\s+\d{1,2}h(?:\d{2})?)", re.I)
EXPLICIT_VRAM = {"RTX3050", "RTX3060", "RTX3080"}


def normalize_name(value):
    value = re.sub(r"^(?:(?:nvidia|amd|intel|geforce|radeon)\s+)+", "", value.strip(), flags=re.I)
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def catalog_aliases(catalog):
    families = Counter(normalize_name(card["gpu"]) for card in catalog)
    aliases = {}
    for card in catalog:
        family = normalize_name(card["gpu"])
        aliases[normalize_name(card["modelo"])] = card["modelo"]
        if families[family] == 1 and family not in EXPLICIT_VRAM:
            aliases[family] = card["modelo"]
    return aliases


def public_url(value):
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("URL pública HTTPS inválida")
    return parsed


def fetch_page(url, session, robots):
    parsed = public_url(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in robots:
        response = session.get(origin + "/robots.txt", headers=HEADERS, timeout=15, allow_redirects=False)
        if response.status_code == 404:
            robots[origin] = None
        else:
            if response.status_code != 200 or not re.search(r"^\s*User-agent:", response.text, re.I | re.M):
                raise ValueError(f"Robots.txt indisponível (HTTP {response.status_code})")
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
            robots[origin] = parser
    rules = robots[origin]
    if rules and not rules.can_fetch(BOT, url):
        raise ValueError("Consulta vedada pelo robots.txt")

    response = session.get(url, headers=HEADERS, timeout=25, allow_redirects=False)
    if response.status_code != 200:
        raise ValueError(f"Consulta da fonte retornou HTTP {response.status_code}")
    return response.text


def parse_brl(value):
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip()
    brl = BRL_PRICE.fullmatch(text)
    if brl:
        text = brl[1].replace(".", "").replace(",", ".")
    try:
        price = Decimal(text)
        if price.is_finite() and price > 0:
            return float(price.quantize(Decimal("0.01")))
    except InvalidOperation:
        pass
    return None


def offer(source, model, price, link, source_date=None):
    return {
        "id": f'{source["id"]}-{normalize_name(model).lower()}',
        "modelo": model,
        "preco": price,
        "moeda": "BRL",
        "loja": source["loja"],
        "url": link,
        "fonte_em": source_date,
    }


def price_table(html, source, aliases):
    soup = BeautifulSoup(html, "html.parser")
    source_date = SOURCE_DATE.search(soup.get_text(" ", strip=True))
    origin = public_url(source["url"])
    variants = source.get("variantes", {})
    items = {}
    matched = set()
    for table in soup.find_all("table"):
        headers = [cell.get_text(" ", strip=True).casefold() for cell in table.find_all("th")]
        expected = ("modelo", "a partir de", "loja", "ofertas em estoque")
        if not all(header in headers for header in expected):
            continue
        model_col, price_col, store_col, stock_col = map(headers.index, expected)
        for row in table.find_all("tr"):
            if not row.find("td", recursive=False):
                continue
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) <= max(model_col, price_col, store_col, stock_col):
                continue
            anchor = cells[model_col].find("a", href=True)
            if not anchor:
                continue
            link = urljoin(source["url"], anchor["href"])
            parsed = urlsplit(link)
            slug = re.fullmatch(r"/gpu/([a-z0-9-]+)/?", parsed.path)
            if parsed.scheme != "https" or parsed.netloc != origin.netloc or not slug:
                continue
            label = normalize_name(anchor.get_text(" ", strip=True))
            name = variants.get(slug[1])
            model = aliases.get(normalize_name(name)) if name else aliases.get(label)
            if not model:
                continue
            matched.add(model)
            stock = cells[stock_col].get_text(" ", strip=True)
            price_text = cells[price_col].get_text(" ", strip=True)
            if not stock.isdecimal() or int(stock) <= 0 or not BRL_PRICE.fullmatch(price_text):
                continue
            price = parse_brl(price_text)
            if not price or (model in items and price >= items[model]["preco"]):
                continue
            quote = offer(source, model, price, link, source_date[1] if source_date else None)
            shop = re.sub(r"\s*\+\d+\s*$", "", cells[store_col].get_text(" ", strip=True))
            if shop and shop != "—":
                quote["loja"] = shop + " · " + source["loja"]
            items[model] = quote
    if not matched:
        raise ValueError("Tabela de ofertas sem correspondências verificáveis no catálogo")
    return list(items.values())

def objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)


def product_offer(html, source, aliases):
    model = aliases.get(normalize_name(source.get("modelo", "")))
    if not model:
        raise ValueError("Informe um modelo do catálogo, incluindo a VRAM da variante")
    soup = BeautifulSoup(html, "html.parser")
    available = []
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(tag.get_text())
        except (json.JSONDecodeError, RecursionError):
            continue
        for product in objects(data):
            types = product.get("@type", [])
            if "Product" not in ([types] if isinstance(types, str) else (types or [])):
                continue
            name = normalize_name(str(product.get("name", "")))
            exact = normalize_name(model)
            if exact not in name:
                continue
            options = product.get("offers", [])
            for candidate in options if isinstance(options, list) else [options]:
                if not isinstance(candidate, dict) or candidate.get("priceCurrency") != "BRL":
                    continue
                if str(candidate.get("availability", "")).split("/")[-1] not in {"InStock", "LimitedAvailability"}:
                    continue
                price = parse_brl(candidate.get("price"))
                if price:
                    available.append(price)
    if len(set(available)) != 1:
        raise ValueError("A página não identificou um preço único em BRL e em estoque para o modelo")
    return [offer(source, model, available[0], source["url"])]


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))["modelos"]
    aliases = catalog_aliases(catalog)
    prices, errors = [], []
    robots = {}
    with requests.Session() as session:
        for source in config.get("fontes", []):
            if not source.get("ativo", True):
                continue
            try:
                html = fetch_page(source["url"], session, robots)
                reader = price_table if source.get("tipo") == "tabela_radar_gpu" else product_offer
                prices.extend(reader(html, source, aliases))
            except (KeyError, ValueError, requests.RequestException, RecursionError) as error:
                errors.append({"fonte": source.get("loja", "Fonte"), "erro": str(error)[:180]})
            time.sleep(max(0, float(config.get("intervalo_segundos", 2))))

    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = {
        "atualizado_em": checked_at,
        "modelos_total": len(catalog),
        "ofertas": prices,
        "erros": errors,
    }
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(OUTPUT)
    print(f"{len({item['modelo'] for item in prices})}/{len(catalog)} modelos com preço · {len(errors)} falhas de fonte")


if __name__ == "__main__":
    main()
