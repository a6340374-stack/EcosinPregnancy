#!/usr/bin/env python3
"""
Собирает статическую копию каталога в shop.html.

Зачем: каталог на сайте рисует widget.js с alinaecosin.store. Робот Яндекса
исполняет JavaScript плохо, поэтому без этой сборки в исходном HTML товаров
нет вообще — ни названий, ни цен. Скрипт тянет тот же API, что и виджет, и
вклеивает два блока:

  * видимые карточки товаров внутри #ecosin-shop — их затирает widget.js,
    когда загружается, так что живой посетитель видит обычный магазин;
  * разметку Schema.org (ItemList из Product с ценами и наличием).

Правятся исходники в src/, после чего сразу запускается tools/build.py и
пересобирает shop.html в корне. Руками корневой shop.html не трогать: он
собирается и любая правка в нём затрётся при следующей сборке.

Запускать после каждого изменения каталога:

    python tools/build_shop.py

Файлы правятся на месте, ничего не коммитится.
"""

import html
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build

API = "https://alinaecosin.store"
PRODUCTS_URL = f"{API}/shop-api/products"
SITE = "https://alinaecosin.ru"
SHOP_URL = f"{SITE}/shop.html"

ROOT = Path(__file__).resolve().parent.parent
# Карточки живут в теле страницы, разметка — в хвосте, который подклеивается
# после подвала. Оба файла исходные: корневой shop.html собирает build.py.
CARDS_FILE = ROOT / "src" / "pages" / "shop.html"
JSONLD_FILE = ROOT / "src" / "partials" / "tail-shop.html"

TELEGRAM = "https://t.me/alina_ecosin"


def fetch_products():
    req = urllib.request.Request(
        PRODUCTS_URL, headers={"User-Agent": "ecosin-build-shop/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if not isinstance(data, list) or not data:
        raise SystemExit("API вернул пустой или неожиданный ответ — сборка отменена")
    return data


def money(value):
    """2340 -> '2 340 ₽' (неразрывный пробел, как в виджете)."""
    return f"{int(value):,}".replace(",", " ") + " ₽"


def lead(description):
    """Первый абзац описания — до списка активных компонентов."""
    text = (description or "").replace("\r\n", "\n").strip()
    first = text.split("\n##")[0].split("\n\n")[0]
    return " ".join(first.split())


def plain(description):
    """Описание целиком без markdown-заголовков — для Schema.org."""
    text = (description or "").replace("\r\n", "\n")
    text = re.sub(r"^##\s*", "", text, flags=re.M)
    return " ".join(text.split())


def image_url(product):
    images = product.get("images") or []
    if not images:
        return None
    src = images[0]
    return src if src.startswith("http") else API + src


def sku(product):
    for spec in product.get("specs") or []:
        if spec.get("key", "").strip().lower() == "артикул":
            return str(spec.get("value", "")).strip()
    return None


def in_stock(product):
    """Наличие: количество на складе, иначе товар идёт под заказ."""
    return bool(product.get("in_stock")) and int(product.get("stock_qty") or 0) > 0


def render_cards(products):
    e = html.escape
    out = [
        '<div class="shop-static">',
        '  <ul class="sp-grid">',
    ]
    for p in products:
        img = image_url(p)
        stock_text = (
            f"в наличии: {int(p['stock_qty'])} шт" if in_stock(p) else "под заказ"
        )
        stock_attr = "" if in_stock(p) else " data-order"
        out.append('    <li class="sp-card">')
        if img:
            out.append(
                f'      <img class="sp-img" src="{e(img)}" alt="{e(p["name"])}"'
                f' width="1200" height="630" loading="lazy" decoding="async" />'
            )
        out.append('      <div class="sp-body">')
        out.append(f'        <h3 class="sp-name">{e(p["name"])}</h3>')
        if p.get("unit"):
            out.append(f'        <p class="sp-unit">{e(p["unit"])}</p>')
        out.append(f'        <p class="sp-desc">{e(lead(p.get("description")))}</p>')
        price_line = f'<span class="sp-now">{money(p["price"])}</span>'
        if p.get("old_price") and p["old_price"] > p["price"]:
            price_line += f' <s class="sp-old">{money(p["old_price"])}</s>'
        out.append(f'        <p class="sp-price">{price_line}</p>')
        out.append(f'        <p class="sp-stock"{stock_attr}>{stock_text}</p>')
        out.append("      </div>")
        out.append("    </li>")
    out.append("  </ul>")
    out.append(
        '  <p class="shop-static-note">Каталог с корзиной и оформлением заказа'
        " загружается автоматически. Если он не открылся — напишите мне в"
        f' <a href="{TELEGRAM}" target="_blank" rel="noopener">Telegram'
        " @alina_ecosin</a>, оформлю заказ вручную.</p>"
    )
    out.append("</div>")
    return "\n".join(out)


def render_jsonld(products):
    items = []
    for i, p in enumerate(products, start=1):
        product = {
            "@type": "Product",
            "name": p["name"],
            "description": plain(p.get("description")),
            "url": SHOP_URL,
            "offers": {
                "@type": "Offer",
                "price": p["price"],
                "priceCurrency": "RUB",
                "url": SHOP_URL,
                "itemCondition": "https://schema.org/NewCondition",
                "availability": (
                    "https://schema.org/InStock"
                    if in_stock(p)
                    else "https://schema.org/PreOrder"
                ),
                "seller": {"@type": "Organization", "name": "Ecosin"},
            },
        }
        img = image_url(p)
        if img:
            product["image"] = img
        code = sku(p)
        if code:
            product["sku"] = code
        if p.get("unit"):
            product["size"] = p["unit"]
        items.append({"@type": "ListItem", "position": i, "item": product})

    data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Магазин Ecosin — липосомальные добавки и магний",
        "numberOfItems": len(items),
        "itemListElement": items,
    }
    body = json.dumps(data, ensure_ascii=False, indent=2)
    return f'<script type="application/ld+json">\n{body}\n</script>'


def replace_block(text, name, payload):
    start, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
    pattern = re.compile(
        re.escape(start) + ".*?" + re.escape(end), re.S
    )
    if not pattern.search(text):
        raise SystemExit(f"В shop.html не найдены маркеры {start} … {end}")
    return pattern.sub(f"{start}\n{payload}\n{end}", text, count=1)


def touch_updated(text):
    """Дата в шапке страницы — сегодняшняя. Из неё build.py делает lastmod."""
    return re.sub(r"^updated:.*$", f"updated: {date.today().isoformat()}", text, count=1, flags=re.M)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    products = fetch_products()

    cards = CARDS_FILE.read_text(encoding="utf-8")
    cards = replace_block(cards, "SHOP:STATIC", render_cards(products))
    CARDS_FILE.write_text(touch_updated(cards), encoding="utf-8")

    jsonld = JSONLD_FILE.read_text(encoding="utf-8")
    JSONLD_FILE.write_text(
        replace_block(jsonld, "SHOP:JSONLD", render_jsonld(products)), encoding="utf-8"
    )

    available = sum(1 for p in products if in_stock(p))
    print(f"Товаров в каталоге: {len(products)} (в наличии {available}, "
          f"под заказ {len(products) - available})")
    print("Обновлены исходники: карточки и разметка Schema.org")
    print()
    print("Пересборка страниц:")

    return build.main([])


if __name__ == "__main__":
    sys.exit(main())
