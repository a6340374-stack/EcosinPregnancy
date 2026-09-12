#!/usr/bin/env python3
"""
Собирает статические страницы сайта из src/ в корень репозитория.

Зачем: шапка, подвал и счётчик Метрики нужны на каждой странице. Пока страниц
было две, копипаст терпели. Дальше их пятнадцать, и правка одного пункта меню
превращается в пятнадцать одинаковых правок, из которых две забудешь.

Как устроено:

    src/layouts/base.html   каркас страницы, дырки вида {{ title }}
    src/partials/*.html     шапка, подвал, Метрика — общие куски
    src/assets/*.css        стили, вклеиваются в <style> той страницы,
                            которая их запросила
    src/pages/**/*.html     сами страницы: шапка параметров и содержимое

На выходе — обычная статика в корне: index.html, shop.html, legal/*.html.
Деплой не меняется, GitHub Pages как публиковал ветку main, так и публикует.

Запуск:

    python tools/build.py            собрать всё
    python tools/build.py --check    проверить, что собранное совпадает с
                                     тем, что лежит в корне (ничего не пишет)

Ещё сборщик заново пишет sitemap.xml по списку страниц: адрес, дата из поля
updated, приоритет. Руками карту сайта больше не трогать.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
SITE = "https://alinaecosin.ru"

# Подстановки вида {{ ключ }} — пробелы внутри скобок необязательны.
SLOT = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def read(path):
    return path.read_text(encoding="utf-8")


def split_front_matter(text, where):
    """Шапка параметров между строками --- и всё остальное."""
    if not text.startswith("---"):
        raise SystemExit(f"{where}: нет шапки параметров (блока между ---)")
    _, block, body = text.split("---", 2)
    meta = {}
    for line in block.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise SystemExit(f"{where}: строка шапки без двоеточия — {line!r}")
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, body.lstrip("\n")


def fill(template, values, where):
    """Заменяет {{ ключ }} на значение. Незнакомый ключ — ошибка, а не пустота."""
    def one(match):
        key = match.group(1)
        if key not in values:
            raise SystemExit(f"{where}: в шаблоне есть {{{{ {key} }}}}, а значения нет")
        return values[key]

    return SLOT.sub(one, template)


def mark_current(nav_html, url):
    """Пункт меню, ведущий на текущую страницу, получает aria-current.

    Ищем только внутри .nav-links: логотип тоже ведёт на «/», и на главной
    метка садилась бы на него, а он не пункт меню.
    """
    start = nav_html.find('class="nav-links"')
    if start < 0:
        return nav_html
    head, links = nav_html[:start], nav_html[start:]
    return head + links.replace(f'href="{url}"', f'href="{url}" aria-current="page"', 1)


def optional_block(meta, key):
    """Поле шапки, которое ссылается на файл в src/. Нет поля — пустая строка."""
    name = meta.get(key)
    if not name:
        return ""
    path = SRC / name
    if not path.exists():
        raise SystemExit(f"{key}: файл {name} не найден")
    return read(path).rstrip("\n")


def render_magnet(meta, where):
    """Лид-магнит: блок с формой, который отдаёт файл за контакт.

    Страница объявляет в шапке поля magnet_*, сюда они приходят уже без
    приставки. Нет magnet_file — нет и блока, страница собирается как обычно.
    """
    if not meta.get("magnet_file"):
        return ""

    values = {k[len("magnet_"):]: v for k, v in meta.items() if k.startswith("magnet_")}

    if not (SRC.parent / values["file"].lstrip("/")).exists():
        raise SystemExit(f"{where}: файла {values['file']} нет в репозитории")

    # Через точку с запятой в шапке — строчками в вёрстке. Не запятая:
    # в фактах попадаются числа вроде «4,4 МБ», их бы разорвало пополам.
    facts = [f.strip() for f in values.get("facts", "").split(";") if f.strip()]
    values["facts"] = "".join(f"<li>{f}</li>" for f in facts)

    values.setdefault("title", "Забрать материал")
    values.setdefault("text", "")
    values.setdefault("button", "Получить")
    values.setdefault("goal", "")
    values.setdefault("topic", "Запрос материала с сайта")
    # Идентификатор для связки label и input: нужен свой на каждой странице,
    # иначе при двух магнитах в одном документе id совпадут.
    values.setdefault("id", "magnet")

    return fill(read(SRC / "partials" / "magnet.html").rstrip("\n"), values, where)


def collect_pages():
    pages = []
    for path in sorted((SRC / "pages").rglob("*.html")):
        meta, body = split_front_matter(read(path), path.name)
        for required in ("url", "out", "title", "description"):
            if required not in meta:
                raise SystemExit(f"{path.name}: в шапке нет обязательного поля {required}")
        pages.append((path, meta, body))
    return pages


def render(meta, body, partials, where):
    # css может перечислять несколько файлов через запятую: порядок в строке
    # задаёт порядок каскада. Первым обычно идёт chrome.css — общая обвязка.
    names = [n.strip() for n in meta.get("css", "").split(",") if n.strip()]
    css = "\n\n".join(read(SRC / "assets" / n).rstrip("\n") for n in names)

    # Магнит встаёт в тело страницы на место {{ magnet }}, а его скрипт
    # подклеивается к хвосту сам — объявлять его в шапке не нужно.
    magnet = render_magnet(meta, where)
    body = body.replace("{{ magnet }}", magnet)
    tail = optional_block(meta, "tail")
    if magnet:
        if "{{ magnet }}" in body:
            raise SystemExit(f"{where}: не удалось подставить магнит")
        tail = (tail + "\n\n" + read(SRC / "partials" / "magnet-script.html").rstrip("\n")).strip()

    values = {
        "title": meta["title"],
        "description": meta["description"],
        "canonical": SITE + meta["url"],
        "keywords": meta.get("keywords", ""),
        "og_title": meta.get("og_title", meta["title"]),
        "og_description": meta.get("og_description", meta["description"]),
        "og_image_alt": meta.get("og_image_alt", "Нутрициолог Алина Сингизова"),
        "twitter_title": meta.get("twitter_title", meta.get("og_title", meta["title"])),
        "twitter_description": meta.get(
            "twitter_description", meta.get("og_description", meta["description"])
        ),
        "robots": meta.get("robots", "index, follow, max-image-preview:large, max-snippet:-1"),
        "head_extra": optional_block(meta, "head_extra"),
        "css": css,
        "metrika": partials["metrika"],
        "nav": mark_current(partials["nav"], meta["url"]),
        "footer": partials["footer"],
        "content": body.rstrip("\n"),
        "tail": tail,
    }
    page = fill(partials["base"], values, where)
    # Пустые слоты оставляют за собой пустые строки — подчищаем, чтобы
    # исходник страницы читался глазами.
    return re.sub(r"\n{3,}", "\n\n", page)


def render_sitemap(pages):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
    ]
    indexable = [
        (meta) for _, meta, _ in pages
        if meta.get("sitemap", "yes") == "yes" and "noindex" not in meta.get("robots", "")
    ]
    for meta in sorted(indexable, key=lambda m: float(m.get("priority", "0.5")), reverse=True):
        lines.append("  <url>")
        lines.append(f"    <loc>{SITE}{meta['url']}</loc>")
        lines.append(f"    <lastmod>{meta['updated']}</lastmod>")
        lines.append(f"    <changefreq>{meta.get('changefreq', 'monthly')}</changefreq>")
        lines.append(f"    <priority>{meta.get('priority', '0.5')}</priority>")
        if meta.get("sitemap_image"):
            lines.append("    <image:image>")
            lines.append(f"      <image:loc>{SITE}{meta['sitemap_image']}</image:loc>")
            lines.append(f"      <image:title>{meta.get('sitemap_image_title', meta['title'])}</image:title>")
            lines.append("    </image:image>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def write_if_changed(path, text, check_only):
    old = read(path) if path.exists() else None
    if old == text:
        return "совпадает"
    if check_only:
        return "РАСХОЖДЕНИЕ"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return "записан" if old is not None else "создан"


def main(argv):
    check_only = "--check" in argv
    # Консоль Windows по умолчанию в cp866 — без этого русский вывод в кашу.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    partials = {
        "base": read(SRC / "layouts" / "base.html"),
        "nav": read(SRC / "partials" / "nav.html").rstrip("\n"),
        "footer": read(SRC / "partials" / "footer.html").rstrip("\n"),
        "metrika": read(SRC / "partials" / "metrika.html").rstrip("\n"),
    }

    pages = collect_pages()
    if not pages:
        raise SystemExit("В src/pages нет ни одной страницы")

    results = []
    for path, meta, body in pages:
        out = ROOT / meta["out"]
        results.append((meta["out"], write_if_changed(out, render(meta, body, partials, path.name), check_only)))

    results.append(("sitemap.xml", write_if_changed(ROOT / "sitemap.xml", render_sitemap(pages), check_only)))

    width = max(len(name) for name, _ in results)
    for name, status in results:
        print(f"  {name.ljust(width)}  {status}")

    diverged = [name for name, status in results if status == "РАСХОЖДЕНИЕ"]
    if diverged:
        print(f"\nСобранное не совпадает с корнем: {', '.join(diverged)}")
        return 1
    print(f"\nСтраниц собрано: {len(pages)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
