"""Pure-Python scrapers for Blueprint sites, Protocol Museum, bryanjohnson.com, Kate Tolo, and YouTube."""

from __future__ import annotations

import html
import json
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from bryan_protocol_mcp.html_utils import html_to_markdown, youtube_timestamp_url

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cookie": "CONSENT=PENDING+999; SOCS=CAESEwgDEgk0ODE3Nzk3MjQaAmVuIAEaBgiA_LyaBg",
}

_BLUEPRINT_INFO_PAGES = (
    "https://blueprint.bryanjohnson.com/pages/about",
    "https://blueprint.bryanjohnson.com/pages/hsa-fsa",
    "https://blueprint.bryanjohnson.com/pages/coas",
    "https://blueprint.bryanjohnson.com/pages/find-my-protocol",
    "https://blueprint.bryanjohnson.com/pages/longevity-mix-actives",
    "https://blueprint.bryanjohnson.com/pages/12-longevity-actives",
    "https://blueprint.bryanjohnson.com/pages/longevity-mix-vs-all-in-one-powders-v1",
    "https://blueprint.bryanjohnson.com/pages/longevity-mix-consolidators-5-reasons-v1",
    "https://blueprint.bryanjohnson.com/pages/developers",
)

_IMMORTALS_INFO_PAGES = (
    "https://immortals.com/pages/immortals-medicine",
    "https://immortals.com/pages/glp-microdose",
    "https://immortals.com/pages/tadalafil-for-women",
    "https://immortals.com/pages/peptide-skin-complex",
    "https://immortals.com/pages/biomarkers",
    "https://immortals.com/pages/explore-treatments",
    "https://immortals.com/pages/personalized-glp-1",
    "https://immortals.com/pages/mens-sex-complex",
    "https://immortals.com/pages/glp-1-treatments",
)


def _http_get(
    url: str,
    data: bytes | None = None,
    extra_headers: dict[str, str] | None = None,
    retries: int = 4,
) -> tuple[str, dict[str, str]]:
    headers = dict(_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=25) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return raw, dict(resp.headers)
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code == 429 and data is None:
                try:
                    proc = subprocess.run(
                        ["curl", "-fsSL", "--max-time", "25", "-A", headers["User-Agent"], url],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    return proc.stdout, {}
                except Exception:  # noqa: BLE001
                    pass
                if attempt >= 1:
                    break
                time.sleep(2.5)
            elif exc.code in (502, 503, 504):
                time.sleep(2.0 * (attempt + 1))
            else:
                break
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"Failed fetching {url}: {last_err}")


def _fetch_wp_collection(base_url: str, endpoint: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_num = 1
    while True:
        url = f"{base_url.rstrip('/')}/wp-json/wp/v2/{endpoint}?per_page=100&page={page_num}"
        try:
            body, hdrs = _http_get(url)
        except RuntimeError:
            if page_num == 1:
                raise
            break
        batch = json.loads(body)
        if not batch:
            break
        items.extend(batch)
        total_pages = int(hdrs.get("X-WP-TotalPages") or hdrs.get("x-wp-totalpages") or 1)
        if page_num >= total_pages:
            break
        page_num += 1
    return items


def scrape_protocol_pages(data_dir: Path) -> list[dict[str, Any]]:
    """Fetch all published WordPress pages from protocol.bryanjohnson.com."""
    out_dir = data_dir / "protocol"
    out_dir.mkdir(parents=True, exist_ok=True)
    all_pages = _fetch_wp_collection("https://protocol.bryanjohnson.com", "pages")

    saved: list[dict[str, Any]] = []
    for raw in all_pages:
        slug = raw.get("slug") or f"page-{raw['id']}"
        title = html.unescape(raw.get("title", {}).get("rendered", slug)).strip()
        markdown = html_to_markdown(raw.get("content", {}).get("rendered", ""))
        excerpt = html_to_markdown(raw.get("excerpt", {}).get("rendered", ""))
        canonical_url = raw.get("link") or f"https://protocol.bryanjohnson.com/#{slug}"

        doc = {
            "id": f"protocol:{slug}",
            "wp_id": raw.get("id"),
            "slug": slug,
            "title": title,
            "url": canonical_url,
            "published_at": (raw.get("date_gmt") or "")[:10],
            "updated_at": (raw.get("modified_gmt") or "")[:10],
            "summary": excerpt or markdown[:300],
            "markdown": f"# {title}\n\n{markdown}".strip(),
            "metadata": {
                "wp_id": raw.get("id"),
                "slug": slug,
                "parent": raw.get("parent", 0),
                "menu_order": raw.get("menu_order", 0),
            },
        }
        (out_dir / f"{slug}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        (out_dir / f"{slug}.md").write_text(
            f"---\ntitle: {json.dumps(title)}\nurl: {canonical_url}\nupdated_at: {doc['updated_at']}\n---\n\n{doc['markdown']}\n",
            encoding="utf-8",
        )
        saved.append({"id": doc["id"], "slug": slug, "title": title, "url": canonical_url, "updated_at": doc["updated_at"]})

    (out_dir / "index.json").write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
    return saved


def scrape_protocol_museum(data_dir: Path) -> list[dict[str, Any]]:
    """Fetch historical Blueprint pages & monthly changelogs from protocol-museum.bryanjohnson.com."""
    out_dir = data_dir / "museum"
    out_dir.mkdir(parents=True, exist_ok=True)
    docs: list[dict[str, Any]] = []

    for endpoint in ("pages", "posts"):
        rows = _fetch_wp_collection("https://protocol-museum.bryanjohnson.com", endpoint)
        for raw in rows:
            slug = raw.get("slug") or f"{endpoint}-{raw['id']}"
            title = html.unescape(raw.get("title", {}).get("rendered", slug)).strip()
            markdown = html_to_markdown(raw.get("content", {}).get("rendered", ""))
            canonical_url = raw.get("link") or f"https://protocol-museum.bryanjohnson.com/#{slug}"
            docs.append({
                "id": f"museum:{endpoint}:{slug}",
                "slug": slug,
                "title": f"[Historical Archive] {title}",
                "url": canonical_url,
                "published_at": (raw.get("date_gmt") or "")[:10],
                "updated_at": (raw.get("modified_gmt") or "")[:10],
                "summary": markdown[:350],
                "markdown": f"# {title} (Historical Protocol Museum)\n\n{markdown}".strip(),
                "metadata": {"wp_id": raw.get("id"), "endpoint": endpoint},
            })

    (out_dir / "museum.json").write_text(json.dumps(docs, indent=2, ensure_ascii=False), encoding="utf-8")
    return docs


def _extract_article_from_html(url: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract clean article Markdown and JSON-LD metadata from a Blueprint blog URL."""
    html_text, _ = _http_get(url)
    slug = url.rstrip("/").split("/")[-1]
    meta_ld: dict[str, Any] = {}
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html_text, re.S):
        try:
            obj = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("@type") in {"Article", "BlogPosting", "NewsArticle"}:
            meta_ld = obj
            break

    fb = fallback or {}
    title = html.unescape(str(meta_ld.get("headline") or fb.get("title") or slug)).strip()
    published = str(meta_ld.get("datePublished") or fb.get("published_at") or "")[:10]
    updated = str(meta_ld.get("dateModified") or fb.get("updated_at") or published)[:10]
    author_obj = meta_ld.get("author")
    if isinstance(author_obj, dict):
        author = str(author_obj.get("name") or "")
    elif isinstance(author_obj, list) and author_obj and isinstance(author_obj[0], dict):
        author = str(author_obj[0].get("name") or "")
    else:
        author = str(fb.get("author") or "Bryan Johnson / Blueprint")

    art_match = re.search(r"<article[^>]*>(.*?)</article>", html_text, re.S)
    if art_match:
        markdown = html_to_markdown(art_match.group(1))
    else:
        body_raw = html.unescape(str(meta_ld.get("articleBody") or fb.get("markdown") or ""))
        markdown = "\n\n".join(line.strip() for line in body_raw.splitlines() if line.strip())

    markdown = re.sub(r"\n+Leave a comment.*$", "", markdown, flags=re.S | re.I).strip()

    return {
        "id": f"article:{slug}",
        "slug": slug,
        "title": title,
        "url": url,
        "published_at": published,
        "updated_at": updated,
        "summary": markdown[:350],
        "markdown": f"# {title}\n\n{markdown}".strip(),
        "metadata": {"author": author, "tags": fb.get("tags", [])},
    }


def scrape_blueprint_articles(data_dir: Path, workers: int = 3) -> list[dict[str, Any]]:
    """Fetch all official blog articles listed in blueprint.bryanjohnson.com/sitemap_articles_1.xml."""
    out_dir = data_dir / "articles"
    out_dir.mkdir(parents=True, exist_ok=True)

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    atom_by_slug: dict[str, dict[str, Any]] = {}
    try:
        xml_text, _ = _http_get("https://blueprint.bryanjohnson.com/blogs/news.atom")
        root = ET.fromstring(xml_text)
        for entry in root.findall("atom:entry", ns):
            alt_link = ""
            for link_el in entry.findall("atom:link", ns):
                if link_el.attrib.get("rel") == "alternate":
                    alt_link = link_el.attrib.get("href", "")
                    break
            slug = (alt_link or entry.findtext("atom:id", default="", namespaces=ns)).rstrip("/").split("/")[-1]
            if not slug:
                continue
            atom_by_slug[slug] = {
                "title": html.unescape(entry.findtext("atom:title", default=slug, namespaces=ns)).strip(),
                "published_at": entry.findtext("atom:published", default="", namespaces=ns)[:10],
                "updated_at": entry.findtext("atom:updated", default="", namespaces=ns)[:10],
                "author": entry.findtext("atom:author/atom:name", default="Bryan Johnson / Blueprint", namespaces=ns).strip(),
                "tags": [c.attrib.get("term", "") for c in entry.findall("atom:category", ns) if c.attrib.get("term")],
                "markdown": html_to_markdown(entry.findtext("atom:content", default="", namespaces=ns)),
            }
    except Exception:  # noqa: BLE001
        pass

    sitemap_xml, _ = _http_get("https://blueprint.bryanjohnson.com/sitemap_articles_1.xml")
    urls = list(dict.fromkeys(re.findall(r"<loc>(https://blueprint\.bryanjohnson\.com/blogs/[^<]+)</loc>", sitemap_xml)))

    articles: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(_extract_article_from_html, url, atom_by_slug.get(url.rstrip("/").split("/")[-1])): url
            for url in urls
        }
        for fut in as_completed(futs):
            try:
                articles.append(fut.result())
            except Exception as exc:  # noqa: BLE001
                url = futs[fut]
                slug = url.rstrip("/").split("/")[-1]
                if slug in atom_by_slug:
                    fb = atom_by_slug[slug]
                    articles.append({
                        "id": f"article:{slug}",
                        "slug": slug,
                        "title": fb["title"],
                        "url": url,
                        "published_at": fb["published_at"],
                        "updated_at": fb["updated_at"],
                        "summary": fb["markdown"][:350],
                        "markdown": f"# {fb['title']}\n\n{fb['markdown']}".strip(),
                        "metadata": {"author": fb["author"], "tags": fb["tags"], "scrape_note": str(exc)},
                    })

    articles.sort(key=lambda a: (a.get("published_at", ""), a["slug"]), reverse=True)
    (out_dir / "articles.json").write_text(json.dumps(articles, indent=2, ensure_ascii=False), encoding="utf-8")
    return articles


def _scrape_shopify_page(url: str, source_type: str, channel: str, prefix: str) -> dict[str, Any]:
    html_text, _ = _http_get(url)
    slug = url.rstrip("/").split("/")[-1]
    title_m = re.search(r"<title>(.*?)</title>", html_text, re.S)
    title = html.unescape(title_m.group(1)).split("|")[0].split("–")[0].strip() if title_m else slug
    main_m = re.search(r"<main[^>]*>(.*?)</main>", html_text, re.S)
    body_html = main_m.group(1) if main_m else html_text
    markdown = html_to_markdown(body_html)
    return {
        "id": f"{prefix}:{slug}",
        "tier": 2,
        "source_type": source_type,
        "title": title,
        "url": url,
        "channel_or_site": channel,
        "published_at": "",
        "updated_at": "",
        "summary": markdown[:350],
        "markdown": f"# {title}\n\n{markdown}".strip(),
        "metadata": {"slug": slug},
    }


def scrape_blueprint_extra(data_dir: Path, workers: int = 1) -> list[dict[str, Any]]:
    """Fetch Blueprint/Immortals product specs, key informational pages, and Kate Tolo's official profile."""
    out_dir = data_dir / "extra"
    out_dir.mkdir(parents=True, exist_ok=True)
    docs: list[dict[str, Any]] = []

    # 1. Blueprint & Immortals products JSON (exact supplement/Rx formulation specs)
    for domain, prefix, site_label in (
        ("https://blueprint.bryanjohnson.com", "bp_product", "blueprint.bryanjohnson.com"),
        ("https://immortals.com", "imm_product", "immortals.com"),
    ):
        time.sleep(1.0)
        try:
            raw, _ = _http_get(f"{domain}/products.json?limit=250")
            prods = json.loads(raw).get("products", [])
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] {domain}/products.json skipped: {exc}")
            prods = []
        seen_handles: set[str] = set()
        for p in prods:
            handle = p.get("handle") or str(p.get("id"))
            if handle in seen_handles:
                continue
            seen_handles.add(handle)
            title = str(p.get("title") or handle).strip()
            body_md = html_to_markdown(p.get("body_html") or "")
            variants = [
                f"{v.get('title')}: ${v.get('price')}"
                for v in p.get("variants", [])[:5]
                if v.get("price")
            ]
            tags = ", ".join(p.get("tags") or [])
            full_md = f"# {title}\n\n{body_md}".strip()
            if variants:
                full_md += f"\n\nOptions: {'; '.join(variants)}"
            if tags:
                full_md += f"\n\nTags: {tags}"
            docs.append({
                "id": f"{prefix}:{handle}",
                "tier": 2,
                "source_type": "blueprint_product",
                "title": title,
                "url": f"{domain}/products/{handle}",
                "channel_or_site": site_label,
                "published_at": str(p.get("published_at") or "")[:10],
                "updated_at": str(p.get("updated_at") or "")[:10],
                "summary": body_md[:350] or title,
                "markdown": full_md,
                "metadata": {"vendor": p.get("vendor", ""), "product_type": p.get("product_type", "")},
            })

    # 2. Key Blueprint & Immortals informational pages
    page_jobs = [
        (u, "official_article", "blueprint.bryanjohnson.com", "bp_page") for u in _BLUEPRINT_INFO_PAGES
    ] + [
        (u, "official_article", "immortals.com", "imm_page") for u in _IMMORTALS_INFO_PAGES
    ]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_scrape_shopify_page, u, st, ch, pre): u for u, st, ch, pre in page_jobs}
        for fut in as_completed(futs):
            try:
                docs.append(fut.result())
            except Exception:  # noqa: BLE001
                continue

    # 3. Kate Tolo official site (katetolo.com)
    try:
        kt_html, _ = _http_get("https://katetolo.com/")
        main_m = re.search(r"<main[^>]*>(.*?)</main>", kt_html, re.S)
        body_m = re.search(r"<body[^>]*>(.*?)</body>", kt_html, re.S)
        kt_md = html_to_markdown(main_m.group(1) if main_m else (body_m.group(1) if body_m else kt_html))
        kt_md = re.sub(
            r"^(?:\[Skip to content\]\(#main-content\)\s*|\[Kate Tolo\]\(#\)\s*|- \[(?:About|Press|Career|Contact)\]\(#[^)]+\)\s*)+",
            "",
            kt_md,
        ).strip()
        docs.append({
            "id": "kate:profile",
            "tier": 1,
            "source_type": "kate_tolo_profile",
            "title": "Kate Tolo - Co-Founder of Blueprint, Don't Die, and Immortals (Female Protocol)",
            "url": "https://katetolo.com/",
            "channel_or_site": "katetolo.com",
            "published_at": "2026-01-01",
            "updated_at": "2026-11-01",
            "summary": kt_md[:350],
            "markdown": f"# Kate Tolo - Official Profile & Female Protocol\n\n{kt_md}".strip(),
            "metadata": {"person": "Kate Tolo"},
        })
    except Exception:  # noqa: BLE001
        pass

    (out_dir / "extra_docs.json").write_text(json.dumps(docs, indent=2, ensure_ascii=False), encoding="utf-8")
    return docs


def _parse_bryanjohnson_essay(url: str) -> dict[str, Any]:
    html_text, _ = _http_get(url)
    slug = url.rstrip("/").split("/")[-1]
    h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.S)
    title = html.unescape(re.sub(r"<[^>]+>", "", h1_m.group(1))).strip() if h1_m else slug.replace("-", " ").title()
    body_m = re.search(
        r'<div[^>]*class="[^"]*(?:rich-text|w-richtext)[^"]*"[^>]*>(.*?)</div>\s*</div>',
        html_text,
        re.S | re.I,
    )
    markdown = html_to_markdown(body_m.group(1) if body_m else "")
    if len(markdown) < 120:
        return {"id": "", "markdown": ""}
    date_m = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
        html_text,
    )
    published = ""
    if date_m:
        try:
            published = datetime.strptime(date_m.group(0), "%B %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            published = ""
    return {
        "id": f"essay:{slug}",
        "tier": 2,
        "source_type": "bryanjohnson_essay",
        "title": title,
        "url": url,
        "channel_or_site": "bryanjohnson.com",
        "published_at": published,
        "updated_at": published,
        "summary": markdown[:350],
        "markdown": f"# {title}\n\n{markdown}".strip(),
        "metadata": {"slug": slug},
    }


def scrape_bryanjohnson_essays(data_dir: Path, workers: int = 8) -> list[dict[str, Any]]:
    """Fetch all essays from www.bryanjohnson.com/sitemap.xml."""
    out_dir = data_dir / "essays"
    out_dir.mkdir(parents=True, exist_ok=True)
    sitemap_xml, _ = _http_get("https://www.bryanjohnson.com/sitemap.xml")
    urls = list(dict.fromkeys(re.findall(r"<loc>(https://www\.bryanjohnson\.com/articles/[^<]+)</loc>", sitemap_xml)))

    essays: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_parse_bryanjohnson_essay, u): u for u in urls}
        for fut in as_completed(futs):
            try:
                doc = fut.result()
                if doc.get("id") and doc.get("markdown"):
                    essays.append(doc)
            except Exception:  # noqa: BLE001
                continue

    essays.sort(key=lambda d: (d.get("published_at", ""), d["id"]), reverse=True)
    (out_dir / "essays.json").write_text(json.dumps(essays, indent=2, ensure_ascii=False), encoding="utf-8")
    return essays


def _walk_yt_videos(obj: Any, found: list[dict[str, str]], tokens: list[str]) -> None:
    if isinstance(obj, dict):
        if "lockupViewModel" in obj:
            lvm = obj["lockupViewModel"]
            vid = lvm.get("contentId", "")
            if vid and len(vid) == 11:
                md = lvm.get("metadata", {}).get("lockupMetadataViewModel", {})
                title = md.get("title", {}).get("content", "")
                rows = md.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
                parts = [p.get("text", {}).get("content", "") for r in rows for p in r.get("metadataParts", [])]
                found.append({"video_id": vid, "title": title, "meta": " | ".join(parts)})
        elif "shortsLockupViewModel" in obj:
            sl = obj["shortsLockupViewModel"]
            vid = (
                sl.get("onTap", {})
                .get("innertubeCommand", {})
                .get("reelWatchEndpoint", {})
                .get("videoId", "")
            )
            if vid and len(vid) == 11:
                title = (
                    sl.get("overlayMetadata", {}).get("primaryText", {}).get("content")
                    or sl.get("accessibilityText", "")
                )
                found.append({"video_id": vid, "title": title, "meta": "short"})
        elif "videoRenderer" in obj:
            vr = obj["videoRenderer"]
            vid = vr.get("videoId", "")
            if vid and len(vid) == 11:
                title = "".join(r.get("text", "") for r in vr.get("title", {}).get("runs", []))
                pub = vr.get("publishedTimeText", {}).get("simpleText", "")
                found.append({"video_id": vid, "title": title, "meta": pub})
        if "continuationCommand" in obj:
            tok = obj["continuationCommand"].get("token")
            if tok:
                tokens.append(tok)
        for val in obj.values():
            _walk_yt_videos(val, found, tokens)
    elif isinstance(obj, list):
        for item in obj:
            _walk_yt_videos(item, found, tokens)


def discover_youtube_channel_videos(
    handle: str = "@BryanJohnson",
    tabs: tuple[str, ...] = ("videos", "streams", "shorts"),
    video_source_type: str = "official_video",
    stream_source_type: str = "official_stream",
    short_source_type: str = "official_short",
    channel_label: str | None = None,
) -> list[dict[str, Any]]:
    """Enumerate videos, streams, and shorts across a YouTube channel's tabs using Innertube pagination."""
    discovered: dict[str, dict[str, Any]] = {}
    for tab in tabs:
        url = f"https://www.youtube.com/{handle}/{tab}"
        html_text, _ = _http_get(url)
        api_key_m = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html_text)
        cver_m = re.search(r'"clientVersion":"([^"]+)"', html_text)
        init_m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});</script>", html_text)
        if not (api_key_m and init_m):
            continue
        api_key = api_key_m.group(1)
        cver = cver_m.group(1) if cver_m else "2.20261101.00.00"
        data = json.loads(init_m.group(1))

        # Verify tab actually exists on channel (YouTube falls back to Home tab when tab is absent)
        found: list[dict[str, str]] = []
        tokens: list[str] = []
        _walk_yt_videos(data, found, tokens)

        seen_toks: set[str] = set()
        pages = 0
        max_pages = 3 if tab == "shorts" else 30
        while tokens and pages < max_pages:
            tok = tokens.pop(0)
            if tok in seen_toks:
                continue
            seen_toks.add(tok)
            payload = json.dumps({
                "context": {"client": {"clientName": "WEB", "clientVersion": cver}},
                "continuation": tok,
            }).encode("utf-8")
            resp_text, _ = _http_get(
                f"https://www.youtube.com/youtubei/v1/browse?key={api_key}",
                data=payload,
                extra_headers={"Content-Type": "application/json"},
            )
            new_toks: list[str] = []
            _walk_yt_videos(json.loads(resp_text), found, new_toks)
            tokens.extend(new_toks)
            pages += 1

        if tab == "streams":
            source_type = stream_source_type
        elif tab == "shorts":
            source_type = short_source_type
        else:
            source_type = video_source_type

        for item in found:
            vid = item["video_id"]
            if vid not in discovered:
                spec: dict[str, Any] = {
                    "video_id": vid,
                    "title_hint": item["title"],
                    "tab": tab,
                    "tier": 2,
                    "source_type": source_type,
                }
                if channel_label:
                    spec["show"] = channel_label
                discovered[vid] = spec
    return list(discovered.values())


def _parse_timedtext_xml(xml_text: str, video_id: str, chunk_seconds: int = 35) -> list[dict[str, Any]]:
    """Parse YouTube timedtext XML (format=3) into readable ~35s timestamped segments."""
    if not xml_text.strip():
        return []
    root = ET.fromstring(xml_text)
    raw_lines: list[tuple[float, float, str]] = []
    for p in root.iter("p"):
        t_ms = int(p.attrib.get("t", 0))
        d_ms = int(p.attrib.get("d", 0))
        text = html.unescape(" ".join("".join(p.itertext()).split()))
        text = re.sub(r"</?(?:b|i|em|strong|u|s|br|p|span|font)[^>]*>", " ", text, flags=re.I)
        text = " ".join(text.split()).strip()
        if not text:
            continue
        start = t_ms / 1000.0
        end = (t_ms + d_ms) / 1000.0
        raw_lines.append((start, end, text))

    if not raw_lines:
        return []

    merged: list[dict[str, Any]] = []
    buf_start = raw_lines[0][0]
    buf_end = raw_lines[0][1]
    buf_texts: list[str] = []

    for start, end, text in raw_lines:
        buf_texts.append(text)
        buf_end = max(buf_end, end)
        elapsed = buf_end - buf_start
        if elapsed >= chunk_seconds or (elapsed >= 15 and text.endswith((".", "?", "!"))):
            merged.append({
                "start_sec": int(buf_start),
                "end_sec": int(buf_end),
                "text": " ".join(buf_texts),
                "deep_link": youtube_timestamp_url(video_id, buf_start),
            })
            buf_texts = []
            buf_start = end

    if buf_texts:
        merged.append({
            "start_sec": int(buf_start),
            "end_sec": int(buf_end),
            "text": " ".join(buf_texts),
            "deep_link": youtube_timestamp_url(video_id, buf_start),
        })
    return merged


def scrape_single_youtube_video(spec: dict[str, Any], out_dir: Path, refresh: bool = False) -> dict[str, Any]:
    """Fetch metadata and English transcript for one YouTube video via Innertube ANDROID client."""
    vid = spec["video_id"]
    out_file = out_dir / f"{vid}.json"
    if out_file.exists() and not refresh:
        return {"video_id": vid, "status": "cached"}

    watch_url = f"https://www.youtube.com/watch?v={vid}"
    html_text, _ = _http_get(watch_url)
    api_key_m = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html_text)
    if not api_key_m:
        return {"video_id": vid, "status": "error", "error": "INNERTUBE_API_KEY missing"}

    web_pr: dict[str, Any] = {}
    pr_m = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.*?\});", html_text)
    if pr_m:
        try:
            web_pr = json.loads(pr_m.group(1))
        except json.JSONDecodeError:
            web_pr = {}

    payload = json.dumps({
        "context": {"client": {"clientName": "ANDROID", "clientVersion": "20.10.38"}},
        "videoId": vid,
    }).encode("utf-8")
    android_raw, _ = _http_get(
        f"https://www.youtube.com/youtubei/v1/player?key={api_key_m.group(1)}",
        data=payload,
        extra_headers={
            "Content-Type": "application/json",
            "User-Agent": "com.google.android.youtube/20.10.38 (Linux; U; Android 14)",
        },
    )
    android_pr = json.loads(android_raw)

    vd = android_pr.get("videoDetails") or web_pr.get("videoDetails") or {}
    micro = (
        web_pr.get("microformat", {}).get("playerMicroformatRenderer")
        or android_pr.get("microformat", {}).get("playerMicroformatRenderer")
        or {}
    )
    tracks = android_pr.get("captions", {}).get("playerCaptionsTracklistRenderer", {}).get("captionTracks", [])
    en_tracks = [t for t in tracks if (t.get("languageCode") or "").startswith("en")]
    en_tracks.sort(key=lambda t: (0 if t.get("kind") != "asr" else 1, 0 if t.get("languageCode") == "en" else 1))

    segments: list[dict[str, Any]] = []
    caption_kind = "none"
    if en_tracks:
        chosen = en_tracks[0]
        caption_kind = chosen.get("kind") or "manual"
        xml_text, _ = _http_get(chosen["baseUrl"])
        segments = _parse_timedtext_xml(xml_text, vid)

    title = vd.get("title") or spec.get("title_hint") or spec.get("title") or vid
    published_at = (micro.get("publishDate") or micro.get("uploadDate") or "")[:10]
    channel = spec.get("show") or vd.get("author") or "Bryan Johnson"
    description = vd.get("shortDescription") or ""
    duration_sec = int(vd.get("lengthSeconds") or 0)
    view_count = int(vd.get("viewCount") or 0)

    record = {
        "id": f"yt:{vid}",
        "video_id": vid,
        "tier": int(spec.get("tier", 2)),
        "source_type": spec.get("source_type", "official_video"),
        "title": title,
        "url": watch_url,
        "channel": channel,
        "published_at": published_at,
        "duration_sec": duration_sec,
        "description": description,
        "caption_kind": caption_kind,
        "segments": segments,
        "metadata": {
            "view_count": view_count,
            "author": vd.get("author", ""),
            "channel_id": vd.get("channelId", ""),
            "notes": spec.get("notes", ""),
        },
    }
    out_file.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "video_id": vid,
        "status": "ok" if segments else "no_captions",
        "segments": len(segments),
        "title": title,
    }


def scrape_all_youtube(
    data_dir: Path,
    workers: int = 8,
    refresh: bool = False,
    max_videos: int | None = None,
) -> dict[str, Any]:
    """Scrape @BryanJohnson (videos/streams/shorts), @katetolo (videos/shorts), and external podcasts."""
    transcripts_dir = data_dir / "transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    specs_by_id: dict[str, dict[str, Any]] = {}
    for s in discover_youtube_channel_videos("@BryanJohnson", tabs=("videos", "streams", "shorts")):
        specs_by_id[s["video_id"]] = s

    for s in discover_youtube_channel_videos(
        "@katetolo",
        tabs=("videos", "shorts"),
        video_source_type="kate_tolo_video",
        short_source_type="kate_tolo_short",
        channel_label="Kate Tolo",
    ):
        if s["video_id"] not in specs_by_id:
            specs_by_id[s["video_id"]] = s

    ext_file = data_dir / "external_podcasts.json"
    if ext_file.exists():
        for ext in json.loads(ext_file.read_text(encoding="utf-8")):
            vid = ext["video_id"]
            if vid not in specs_by_id:
                specs_by_id[vid] = {
                    "video_id": vid,
                    "title": ext["title"],
                    "show": ext["show"],
                    "notes": ext.get("notes", ""),
                    "tier": 3,
                    "source_type": "external_podcast",
                }

    all_specs = list(specs_by_id.values())
    if max_videos is not None:
        all_specs = all_specs[:max_videos]

    summary: dict[str, Any] = {"total": len(all_specs), "ok": 0, "cached": 0, "no_captions": 0, "error": 0, "errors": []}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(scrape_single_youtube_video, spec, transcripts_dir, refresh): spec for spec in all_specs}
        for fut in as_completed(futs):
            spec = futs[fut]
            try:
                res = fut.result()
                st = res["status"]
                summary[st] = summary.get(st, 0) + 1
            except Exception as exc:  # noqa: BLE001
                summary["error"] += 1
                summary["errors"].append({"video_id": spec["video_id"], "error": str(exc)})

    (transcripts_dir / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
