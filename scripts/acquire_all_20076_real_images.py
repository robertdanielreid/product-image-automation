#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
import re
import base64
import shutil
import threading
import time
import urllib.parse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from io import BytesIO
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps, ImageStat

UA = "Mozilla/5.0 (compatible; ReidIntegrativeHealthStrictProductImageAudit/28.0)"
TIMEOUT = 35
BAD_URL_WORDS = {
    "logo", "placeholder", "banner", "favicon", "sprite", "avatar", "icon", "payment",
    "badge", "loader", "spinner", "newsletter", "header", "footer", "trustpilot", "social",
    "certificate", "seal", "category", "collection", "blog", "author", "ingredient", "facts",
}
BAD_PAGE_DOMAINS = {
    "barcodelookup.com", "amazon.com", "amazon.ca", "ebay.com", "ebay.ca", "walmart.com",
    "pinterest.com", "facebook.com", "instagram.com", "tiktok.com", "youtube.com",
    "ea.com", "netflix.com", "imdb.com", "wikipedia.org", "en.wikipedia.org",
    "steampowered.com", "store.steampowered.com", "epicgames.com", "store.epicgames.com",
    "youtube.com", "twitch.tv", "reddit.com", "twitter.com", "x.com",
    "apex.tracker.gg", "apexlegendsstatus.com",
}
# OG image URL patterns that indicate a site-default or SEO preview image, not a product image.
SITE_DEFAULT_OG_PATTERNS = [
    "seo_preview_image", "default_image", "placeholder", "site-banner",
    "facebook_sharing", "default-og", "og_default", "site_logo",
]
STOPWORDS = {
    "and", "the", "with", "for", "of", "a", "an", "plus", "formula", "support", "complex",
    "capsules", "capsule", "caps", "tablets", "tablet", "tabs", "softgels", "softgel", "liquid",
    "powder", "cream", "spray", "drops", "supplement", "professional", "advanced", "natural",
}
UNIT_ALIASES = {
    "capsules": "caps", "capsule": "caps", "vcaps": "caps", "v-caps": "caps", "vegcaps": "caps",
    "tablets": "tabs", "tablet": "tabs", "softgel": "softgels", "soft gels": "softgels",
    "milliliters": "ml", "millilitres": "ml", "milliliter": "ml", "millilitre": "ml",
    "grams": "g", "gram": "g", "ounces": "oz", "ounce": "oz", "fluid ounces": "fl oz",
}
DIRECT_IMAGE_EXT = re.compile(r"\.(?:jpe?g|png|webp|gif|avif|tiff?)(?:$|[?#])", re.I)
SPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-z0-9]+")

_thread_local = threading.local()
_domain_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_domain_last: dict[str, float] = defaultdict(float)


def session() -> requests.Session:
    s = getattr(_thread_local, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update({"User-Agent": UA, "Accept-Language": "en-CA,en;q=0.9"})
        _thread_local.session = s
    return s


def rate_limited_get(url: str, *, referer: str = "", stream: bool = False) -> requests.Response:
    domain = urllib.parse.urlparse(url).netloc.lower()
    with _domain_locks[domain]:
        wait = 0.30 - (time.monotonic() - _domain_last[domain])
        if wait > 0:
            time.sleep(wait)
        headers = {"Referer": referer} if referer else {}
        resp = session().get(url, timeout=TIMEOUT, headers=headers, allow_redirects=True, stream=stream)
        _domain_last[domain] = time.monotonic()
    resp.raise_for_status()
    return resp


def clean_url(value: str, base: str) -> str:
    if not value:
        return ""
    value = html.unescape(value.strip())
    if value.startswith("//"):
        value = "https:" + value
    value = urllib.parse.urljoin(base, value)
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return ""
    return value


def norm(text: str) -> str:
    text = html.unescape(text or "").lower().replace("™", " ").replace("®", " ")
    for old, new in UNIT_ALIASES.items():
        text = text.replace(old, new)
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return SPACE_RE.sub(" ", text).strip()


def significant_tokens(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(norm(text)) if len(t) > 1 and t not in STOPWORDS]


def token_coverage(needle: str, haystack: str) -> float:
    tokens = significant_tokens(needle)
    if not tokens:
        return 1.0
    hs = set(significant_tokens(haystack))
    return sum(t in hs for t in tokens) / len(tokens)


def size_signatures(text: str) -> set[str]:
    n = norm(text)
    out: set[str] = set()
    patterns = [
        r"\b\d+(?:\.\d+)?\s*(?:ml|g|kg|mg|mcg|oz|fl oz|caps|tabs|softgels|count|ct|packets|sachets|servings)\b",
        r"\b\d+\s*[x×]\s*\d+\b",
        r"\b\d+\s*(?:billion|million)\b",
    ]
    for p in patterns:
        out.update(re.sub(r"\s+", "", m) for m in re.findall(p, n))
    # common volume equivalence, only for evidence matching
    for sig in list(out):
        if sig == "30ml": out.add("1floz")
        if sig == "60ml": out.add("2floz")
        if sig == "120ml": out.add("4floz")
    return out


def exact_size_match(expected: str, evidence: str) -> bool:
    exp = size_signatures(expected)
    if not exp:
        return True
    ev = size_signatures(evidence)
    return bool(exp & ev)


def decode_microlink(url: str) -> str:
    if "api.microlink.io" not in (url or ""):
        return url
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    return q.get("url", [""])[0]


def is_bad_image_url(url: str) -> bool:
    low = urllib.parse.unquote(url).lower()
    if any(w in low for w in BAD_URL_WORDS):
        return True
    # Reject known site-default OG/seo preview images that are not product photos.
    if any(p in low for p in SITE_DEFAULT_OG_PATTERNS):
        return True
    return False


def canonical_domain(url: str) -> str:
    d = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
    return d[4:] if d.startswith("www.") else d


@dataclass
class Candidate:
    url: str
    page_url: str
    origin: str
    alt: str = ""
    page_title: str = ""
    page_text: str = ""
    structured_product_name: str = ""
    structured_brand: str = ""
    score: float = 0.0


@dataclass
class ImageResult:
    batchIndex: str
    immutableKey: str
    brand: str
    productName: str
    size: str
    targetJpgPath: str
    status: str
    resolvedImageUrl: str = ""
    evidencePage: str = ""
    origin: str = ""
    width: int = 0
    height: int = 0
    bytes: int = 0
    sha256: str = ""
    perceptualHash: str = ""
    pageBrandCoverage: float = 0.0
    pageProductCoverage: float = 0.0
    exactSizeEvidence: bool = False
    imageCandidateScore: float = 0.0
    autoApprovalEligible: bool = False
    reason: str = ""
    stagingPath: str = ""
    finalPath: str = ""


def jsonld_products(soup: BeautifulSoup) -> list[dict]:
    products: list[dict] = []
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            obj = json.loads(tag.string or tag.get_text(" "))
        except Exception:
            continue
        stack = obj if isinstance(obj, list) else [obj]
        while stack:
            cur = stack.pop()
            if isinstance(cur, dict):
                typ = cur.get("@type")
                types = typ if isinstance(typ, list) else [typ]
                if any(str(x).lower() == "product" for x in types):
                    products.append(cur)
                graph = cur.get("@graph")
                if isinstance(graph, list): stack.extend(graph)
            elif isinstance(cur, list):
                stack.extend(cur)
    return products


def collect_page_candidates(page_url: str) -> tuple[list[Candidate], str, str]:
    resp = rate_limited_get(page_url)
    ctype = resp.headers.get("content-type", "").lower()
    if ctype.startswith("image/"):
        return [Candidate(resp.url, page_url, "direct-image-response")], "", ""
    soup = BeautifulSoup(resp.text, "lxml")
    title = SPACE_RE.sub(" ", soup.title.get_text(" ", strip=True) if soup.title else "")
    page_text = SPACE_RE.sub(" ", soup.get_text(" ", strip=True))[:250_000]
    out: list[Candidate] = []

    for product in jsonld_products(soup):
        pname = str(product.get("name") or "")
        brand_obj = product.get("brand") or ""
        pbrand = str(brand_obj.get("name") if isinstance(brand_obj, dict) else brand_obj)
        imgs = product.get("image") or []
        if isinstance(imgs, str): imgs = [imgs]
        if isinstance(imgs, dict): imgs = [imgs.get("url") or imgs.get("contentUrl")]
        for img in imgs:
            if isinstance(img, dict): img = img.get("url") or img.get("contentUrl")
            u = clean_url(str(img or ""), resp.url)
            if u:
                out.append(Candidate(u, resp.url, "jsonld-product-image", pname, title, page_text, pname, pbrand))

    selectors = [
        ('meta[property="og:image"]', "content", "og-image"),
        ('meta[property="og:image:secure_url"]', "content", "og-image"),
        ('meta[name="twitter:image"]', "content", "twitter-image"),
        ('link[rel="image_src"]', "href", "image-src-link"),
    ]
    for sel, attr, origin in selectors:
        for tag in soup.select(sel):
            u = clean_url(tag.get(attr, ""), resp.url)
            if u: out.append(Candidate(u, resp.url, origin, "", title, page_text))

    for tag in soup.select("img"):
        alt = " ".join(filter(None, [tag.get("alt", ""), tag.get("title", ""), tag.get("data-caption", "")]))
        classes = " ".join(tag.get("class", []))
        origin = "woocommerce-gallery" if any(x in classes.lower() for x in ("wp-post-image", "woocommerce", "product")) else "page-img"
        attrs = ("data-large_image", "data-zoom-image", "data-src", "data-lazy-src", "data-original", "src")
        for attr in attrs:
            u = clean_url(tag.get(attr, ""), resp.url)
            if u: out.append(Candidate(u, resp.url, origin, alt, title, page_text))
        for attr in ("srcset", "data-srcset"):
            srcset = tag.get(attr, "")
            for part in srcset.split(","):
                u = clean_url(part.strip().split()[0] if part.strip() else "", resp.url)
                if u: out.append(Candidate(u, resp.url, origin + "-srcset", alt, title, page_text))

    # Shopify JSON endpoint often exposes the clean original image.
    parsed = urllib.parse.urlparse(resp.url)
    if "/products/" in parsed.path:
        slug = parsed.path.split("/products/", 1)[1].split("/", 1)[0]
        shopify_json = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, f"/products/{slug}.js", "", "", ""))
        try:
            jr = rate_limited_get(shopify_json, referer=resp.url)
            if "json" in jr.headers.get("content-type", "").lower() or jr.text.lstrip().startswith("{"):
                data = jr.json()
                pname = str(data.get("title") or "")
                vendor = str(data.get("vendor") or "")
                imgs = data.get("images") or []
                featured = data.get("featured_image")
                if featured: imgs = [featured] + list(imgs)
                for img in imgs:
                    u = clean_url(str(img), resp.url)
                    if u: out.append(Candidate(u, resp.url, "shopify-product-json", pname, title, page_text, pname, vendor))
        except Exception:
            pass

    dedup: dict[str, Candidate] = {}
    for c in out:
        if not c.url or is_bad_image_url(c.url):
            continue
        prior = dedup.get(c.url)
        if prior is None or len(c.alt) > len(prior.alt):
            dedup[c.url] = c
    return list(dedup.values()), title, page_text


def _decode_bing_url(encoded: str) -> str:
    """Decode Bing's a1-prefixed base64url-encoded destination URL."""
    if encoded.startswith("a1"):
        encoded = encoded[2:]
    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += "=" * padding
    return base64.urlsafe_b64decode(encoded).decode("utf-8")


def bing_search_pages(query: str, preferred_domains: Iterable[str],
                     brand: str = "", product_name: str = "") -> list[str]:
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "count": "10"})
    try:
        resp = rate_limited_get(url)
    except Exception:
        return []
    soup = BeautifulSoup(resp.text, "lxml")
    links: list[str] = []
    pref = [d.lower() for d in preferred_domains if d]
    brand_tokens = set(significant_tokens(brand)) if brand else set()
    product_tokens = set(significant_tokens(product_name)) if product_name else set()
    relevance_tokens = brand_tokens | product_tokens
    for a in soup.select("li.b_algo h2 a"):
        href = a.get("href", "")
        if not href:
            continue
        # Bing wraps results in click-tracking redirects with the real URL
        # base64url-encoded in the 'u' query parameter.
        if "/ck/a?" in href or "/ck/a!" in href:
            parsed = urllib.parse.urlparse(href)
            qs = urllib.parse.parse_qs(parsed.query)
            u = qs.get("u", [""])[0]
            if u:
                try:
                    href = _decode_bing_url(u)
                except Exception:
                    continue
        href = clean_url(href, resp.url)
        dom = canonical_domain(href)
        if not href or dom in BAD_PAGE_DOMAINS:
            continue
        # Filter out results that are clearly irrelevant.
        # The result title and URL must share at least one significant token
        # with the brand or product name, or the domain must be a preferred one.
        result_text = (a.get_text(" ", strip=True) + " " + href).lower()
        if relevance_tokens:
            text_tokens = set(TOKEN_RE.findall(result_text))
            if not (text_tokens & relevance_tokens) and not any(
                dom == d or dom.endswith("." + d) for d in pref
            ):
                continue
        # De-prioritize non-product URLs (category, blog, search results).
        links.append(href)
    links = list(dict.fromkeys(links))
    return sorted(links, key=lambda u: (0 if any(canonical_domain(u).endswith(d) for d in pref) else 1, links.index(u)))[:8]


# Keep legacy name for compatibility with any external callers.
def ddg_search_pages(query: str, preferred_domains: Iterable[str],
                     brand: str = "", product_name: str = "") -> list[str]:
    return bing_search_pages(query, preferred_domains, brand=brand, product_name=product_name)


GOOGLE_EVASION_HEADERS = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
     "Accept-Language": "en-US,en;q=0.9"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
     "Accept-Language": "en-CA,en;q=0.9"},
    {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
     "Accept-Language": "en-GB,en;q=0.8"},
]
_google_req_count = 0
_google_blocked = False


def google_search_pages(query: str, preferred_domains: Iterable[str],
                        brand: str = "", product_name: str = "") -> list[str]:
    """Search Google for product pages. Falls back to Bing automatically if blocked."""
    global _google_req_count, _google_blocked
    if _google_blocked:
        return []

    pref = [d.lower() for d in preferred_domains if d]
    brand_tokens = set(significant_tokens(brand)) if brand else set()
    product_tokens = set(significant_tokens(product_name)) if product_name else set()
    relevance_tokens = brand_tokens | product_tokens

    url = "https://www.google.com/search?" + urllib.parse.urlencode({"q": query, "num": "10", "hl": "en", "gl": "ca"})
    headers = GOOGLE_EVASION_HEADERS[_google_req_count % len(GOOGLE_EVASION_HEADERS)]
    headers["Referer"] = "https://www.google.com/"

    # Be gentler than Bing — Google blocks aggressively
    time.sleep(1.5 + (_google_req_count % 3) * 0.5)

    try:
        s = requests.Session()
        s.headers.update(headers)
        resp = s.get(url, timeout=TIMEOUT, allow_redirects=True)
        _google_req_count += 1
    except Exception:
        return []  # network error, just fall back

    if resp.status_code != 200:
        if resp.status_code in (429, 403, 503):
            print(f"  google blocked (HTTP {resp.status_code}) after {_google_req_count} requests; falling back to Bing", flush=True)
            _google_blocked = True
        return []

    html_text = resp.text.lower()
    if "captcha" in html_text or "sorry" in html_text or "our systems have detected unusual traffic" in html_text:
        print(f"  google captcha after {_google_req_count} requests; falling back to Bing", flush=True)
        _google_blocked = True
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    links: list[str] = []

    # Google result blocks come in several flavors. Try the most common selectors.
    result_selectors = [
        "div.g a[href^='http']",           # classic result blocks
        "a[jsname][href^='http']",          # newer result links
        "div[data-sokoban-container] a[href^='http']",  # modern container
        "h3 + div a[href^='http']",         # adjacent-to-heading pattern
        "a[href^='http']",                  # fallback: any external link
    ]

    seen: set[str] = set()
    for selector in result_selectors:
        for a in soup.select(selector):
            href = a.get("href", "")
            if not href or not href.startswith("http"):
                continue
            # Skip Google's own domains
            if "google.com" in href or "google.ca" in href or "youtube.com" in href:
                continue
            href = clean_url(href, resp.url)
            dom = canonical_domain(href)
            if not href or dom in BAD_PAGE_DOMAINS:
                continue
            if href in seen:
                continue
            seen.add(href)

            # Relevance filter (same logic as Bing)
            result_text = (a.get_text(" ", strip=True) + " " + href).lower()
            if relevance_tokens:
                text_tokens = set(TOKEN_RE.findall(result_text))
                if not (text_tokens & relevance_tokens) and not any(
                    dom == d or dom.endswith("." + d) for d in pref
                ):
                    continue
            links.append(href)
        if len(links) >= 5:
            break  # got enough results

    links = list(dict.fromkeys(links))
    return sorted(links, key=lambda u: (0 if any(canonical_domain(u).endswith(d) for d in pref) else 1, links.index(u)))[:8]


def multi_search_pages(query: str, preferred_domains: Iterable[str],
                       brand: str = "", product_name: str = "") -> list[str]:
    """Try Google first, fall back to Bing if Google is blocked or returns nothing."""
    results = google_search_pages(query, preferred_domains, brand=brand, product_name=product_name)
    if not results:
        results = bing_search_pages(query, preferred_domains, brand=brand, product_name=product_name)
    return results


def page_match(row: dict, candidate: Candidate, official_domains: set[str]) -> tuple[float, float, bool, bool]:
    # Fail closed: broad page body is discovery context only. It may list related
    # products and every size option, so it cannot prove the selected image identity.
    identity_evidence = " ".join([
        candidate.structured_product_name,
        candidate.structured_brand,
        candidate.alt,
        candidate.page_title,
        urllib.parse.unquote(candidate.url),
    ])
    image_evidence = " ".join([
        candidate.structured_product_name,
        candidate.structured_brand,
        candidate.alt,
        urllib.parse.unquote(candidate.url),
    ])
    brand_cov = token_coverage(row["brand"], identity_evidence)
    product_cov = token_coverage(row["productName"], identity_evidence)
    # Exact package evidence must be attached to the selected image/product object.
    # A size merely appearing somewhere in the page body is not accepted.
    size_ok = exact_size_match(row["size"] or row["rawSize"], image_evidence)
    dom = canonical_domain(candidate.page_url)
    official = any(dom == d or dom.endswith("." + d) for d in official_domains)
    # Official domain improves provenance but never substitutes for product identity.
    exact = brand_cov >= 0.50 and product_cov >= 0.82 and size_ok
    return brand_cov, product_cov, size_ok, exact

def candidate_score(row: dict, c: Candidate, official_domains: set[str]) -> tuple[float, tuple[float, float, bool, bool]]:
    brand_cov, product_cov, size_ok, exact = page_match(row, c, official_domains)
    score = 0.0
    score += {
        "jsonld-product-image": 45, "shopify-product-json": 42, "woocommerce-gallery": 38,
        "woocommerce-gallery-srcset": 38, "direct-current-image": 36, "direct-image-response": 35,
        "og-image": 24, "image-src-link": 22, "twitter-image": 18, "page-img": 8,
        "page-img-srcset": 10,
    }.get(c.origin, 5)
    score += brand_cov * 20 + product_cov * 45
    score += 25 if size_ok else -25
    score += 15 if exact else -10
    url_alt = f"{urllib.parse.unquote(c.url)} {c.alt}"
    score += token_coverage(row["productName"], url_alt) * 18
    if exact_size_match(row["size"], url_alt): score += 12
    if any(canonical_domain(c.page_url).endswith(d) for d in official_domains): score += 14
    if is_bad_image_url(c.url): score -= 100
    return score, (brand_cov, product_cov, size_ok, exact)


def image_quality(data: bytes) -> tuple[Image.Image, int, int, float, str]:
    if len(data) < 2_000:
        raise ValueError("image smaller than 2 KB")
    im = Image.open(BytesIO(data))
    im.load()
    im = ImageOps.exif_transpose(im)
    w, h = im.size
    if min(w, h) < 240:
        raise ValueError(f"dimensions too small: {w}x{h}")
    ratio = w / h
    if ratio < 0.18 or ratio > 5.5:
        raise ValueError(f"extreme aspect ratio: {ratio:.3f}")
    rgb = im.convert("RGB")
    stat = ImageStat.Stat(rgb.resize((96, 96)))
    entropy = sum(rgb.resize((128, 128)).entropy() for _ in [0])
    std_mean = sum(stat.stddev) / 3
    if entropy < 2.0 or std_mean < 4.0:
        raise ValueError("blank or near-blank image")
    tiny = rgb.convert("L").resize((9, 8))
    px = list(tiny.getdata())
    bits = []
    for y in range(8):
        for x in range(8):
            bits.append(px[y*9+x] > px[y*9+x+1])
    ph = f"{sum((1 << i) for i, b in enumerate(bits) if b):016x}"
    return rgb, w, h, entropy, ph


def save_jpg(im: Image.Image, path: Path) -> tuple[int, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    im.save(tmp, "JPEG", quality=92, optimize=True, progressive=True)
    os.replace(tmp, path)
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest()


def load_official_domains(path: Path) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f): out[norm(r["brand"])].add(r["officialDomain"].lower())
    return out




def load_rejected_candidates(path: Path) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    if not path.exists():
        return out
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            key = (r.get("immutableKey") or "").strip()
            url = (r.get("resolvedImageUrl") or r.get("imageUrl") or "").strip()
            if key and url:
                out[key].add(url)
    return out

def read_overrides(path: Path) -> dict[str, dict]:
    if not path.exists(): return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["immutableKey"]: r for r in csv.DictReader(f) if r.get("immutableKey")}


def discover_candidates(row: dict, official_domains: set[str], search_fallback: bool, override: dict | None) -> list[Candidate]:
    candidates: list[Candidate] = []
    if override and override.get("approvedDirectImageUrl"):
        candidates.append(Candidate(override["approvedDirectImageUrl"], override.get("approvedSourcePageUrl") or row["sourcePage"], "manual-override", override.get("evidenceNote", "")))
    current = row.get("currentImageReference", "")
    if current.startswith("http") and "api.microlink.io" not in current and DIRECT_IMAGE_EXT.search(current):
        candidates.append(Candidate(current, row.get("sourcePage") or current, "direct-current-image", row.get("imageAlt", "")))
    pages: list[str] = []
    shared_conflict = row.get("isSharedSourceConflict", "").lower() == "true"
    # A source page reused across incompatible identities is never authoritative.
    # Skip it entirely and force variant-specific discovery instead of selecting a
    # generic/default package image from the shared page.
    if (not shared_conflict and row.get("sourcePage")
            and row.get("isBarcodeDatabaseSource", "").lower() != "true"):
        pages.append(row["sourcePage"])
    decoded = decode_microlink(current)
    if (not shared_conflict and decoded and decoded not in pages
            and canonical_domain(decoded) not in BAD_PAGE_DOMAINS):
        pages.append(decoded)
    for page in pages[:3]:
        try:
            cs, _, _ = collect_page_candidates(page)
            candidates.extend(cs)
        except Exception:
            pass

    if search_fallback and (not candidates
            or row.get("isBarcodeDatabaseSource", "").lower() == "true"
            or shared_conflict):
        barcode = ""
        if row.get("sourcePage"):
            m = re.search(r"(?:barcodelookup\.com/)(\d{8,14})", row["sourcePage"])
            if m: barcode = m.group(1)
        # Build a targeted search query. When we have official domains, restrict
        # to those sites; otherwise use brand + product + size with purchase intent.
        if official_domains:
            site_constraint = " OR ".join(f"site:{d}" for d in list(official_domains)[:3])
            query = f"({site_constraint}) {row['productName']} {row['size']}"
        else:
            query_parts = [f'"{row["brand"]}"', f'"{row["productName"]}"', f'"{row["size"]}"']
            if row.get("format"): query_parts.append(f'"{row["format"]}"')
            if row.get("sku"): query_parts.append(f'"{row["sku"]}"')
            query = " ".join(query_parts) + " buy product"
        if barcode: query += f" {barcode}"
        for page in multi_search_pages(query, official_domains,
                                       brand=row["brand"],
                                       product_name=row["productName"]):
            try:
                cs, _, _ = collect_page_candidates(page)
                candidates.extend(cs)
            except Exception:
                continue
    dedup: dict[str, Candidate] = {}
    for c in candidates:
        if c.url and not is_bad_image_url(c.url):
            dedup.setdefault(c.url, c)
    return list(dedup.values())


def process_row(row: dict, package: Path, store: Path, domains_by_brand: dict[str, set[str]], search_fallback: bool, overrides: dict[str, dict], rejected_by_key: dict[str, set[str]]) -> ImageResult:
    result = ImageResult(
        batchIndex=row["batchIndex"], immutableKey=row["immutableKey"], brand=row["brand"],
        productName=row["productName"], size=row["size"], targetJpgPath=row["targetJpgPath"],
        status="UNRESOLVED",
    )
    official_domains = set(domains_by_brand.get(norm(row["brand"]), set()))
    if row.get("sourceClass") == "official-manufacturer-product-page" and row.get("sourceDomain"):
        official_domains.add(row["sourceDomain"].lower())
    override = overrides.get(row["immutableKey"])
    try:
        candidates = discover_candidates(row, official_domains, search_fallback, override)
    except Exception as exc:
        result.reason = f"candidate discovery failed: {exc}"
        return result
    ranked = []
    for c in candidates:
        score, match = candidate_score(row, c, official_domains)
        c.score = score
        ranked.append((score, c, match))
    ranked.sort(key=lambda x: x[0], reverse=True)
    errors: list[str] = []
    rejected_urls = rejected_by_key.get(row["immutableKey"], set())
    for score, c, match in ranked[:60]:
        if c.url in rejected_urls:
            errors.append(f"previously rejected candidate skipped: {c.url[:120]}")
            continue
        # Hard filter: OG/twitter images must contain at least some product
        # identifier in the URL or alt text, otherwise they are almost certainly
        # site-default banners/SEO previews, not product photos.
        if c.origin in ("og-image", "twitter-image"):
            product_tokens_in_url = token_coverage(row["productName"], urllib.parse.unquote(c.url))
            brand_tokens_in_url = token_coverage(row["brand"], urllib.parse.unquote(c.url))
            if product_tokens_in_url < 0.25 and brand_tokens_in_url < 0.4:
                errors.append(f"og-image with no product/brand identity skipped: {c.url[:100]}")
                continue
        brand_cov, product_cov, size_ok, exact = match
        # Skip candidates with critically weak identity evidence. The image
        # cannot be trusted if the page provides no brand or product tokens.
        if brand_cov < 0.3 and product_cov < 0.5:
            errors.append(f"critically weak identity match skipped: brand_cov={brand_cov:.2f} prod_cov={product_cov:.2f}")
            continue
        try:
            resp = rate_limited_get(c.url, referer=c.page_url)
            if resp.url in rejected_urls:
                errors.append(f"previously rejected redirected candidate skipped: {resp.url[:120]}")
                continue
            ctype = resp.headers.get("content-type", "").lower()
            if not ctype.startswith("image/") and not DIRECT_IMAGE_EXT.search(resp.url):
                errors.append(f"not image: {c.url[:120]}")
                continue
            rgb, w, h, _, ph = image_quality(resp.content)
            staging = store / "staging" / f"{row['batchIndex'].zfill(5)}_{Path(row['targetJpgPath']).name}"
            byte_count, sha = save_jpg(rgb, staging)
            manual_override_ok = bool(override and override.get("exactVariantConfirmed", "").lower() == "true")
            high_conf = (
                exact and score >= 105 and c.origin in {
                    "jsonld-product-image", "shopify-product-json", "woocommerce-gallery",
                    "woocommerce-gallery-srcset", "manual-override",
                }
            ) or manual_override_ok
            # Shared source conflicts require exact size evidence in image URL/alt or reviewed override.
            shared = row.get("isSharedSourceConflict", "").lower() == "true"
            # Also treat WooCommerce variable-product pages as shared: different
            # size variants share one product image, so size evidence must be in
            # the image-level metadata, not just the page.
            is_variable_product_page = bool(
                re.search(r"[?&]attribute_", c.page_url)
                or re.search(r"[?&]attribute_", row.get("sourcePage", ""))
            )
            if shared or is_variable_product_page:
                image_level_evidence = f"{c.url} {c.alt} {c.structured_product_name}"
                size_in_image_evidence = exact_size_match(row["size"], image_level_evidence)
                product_in_image_evidence = token_coverage(row["productName"], image_level_evidence) >= 0.80
                brand_in_image_evidence = token_coverage(row["brand"], f"{c.structured_brand} {image_level_evidence}") >= 0.60
                if not ((size_in_image_evidence and product_in_image_evidence and brand_in_image_evidence)
                        or manual_override_ok):
                    high_conf = False
                # For variable-product pages without size evidence, skip downloading
                # entirely — the image is shared across sizes and cannot be trusted
                # for a specific variant without visual verification.
                if is_variable_product_page and not size_in_image_evidence and not manual_override_ok:
                    errors.append(f"variable product page without size evidence skipped: {c.url[:100]}")
                    continue
            status = "STAGED_HIGH_CONFIDENCE_NEEDS_VISUAL_REVIEW" if high_conf else "STAGED_NEEDS_MANUAL_REVIEW"
            result.__dict__.update({
                "status": status, "resolvedImageUrl": resp.url, "evidencePage": c.page_url,
                "origin": c.origin, "width": w, "height": h, "bytes": byte_count,
                "sha256": sha, "perceptualHash": ph, "pageBrandCoverage": round(brand_cov, 3),
                "pageProductCoverage": round(product_cov, 3), "exactSizeEvidence": bool(size_ok),
                "imageCandidateScore": round(score, 2), "autoApprovalEligible": bool(high_conf),
                "reason": "Candidate bytes decoded and staged; exact brand, product name, and package must still be visually approved.",
                "stagingPath": str(staging.relative_to(store)).replace("\\", "/"),
            })
            return result
        except Exception as exc:
            errors.append(f"{c.origin}: {exc}")
    result.reason = "; ".join(errors[:6]) or "no exact image candidate found"
    return result


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = fields or list(rows[0])
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--store-root", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=20076)
    ap.add_argument("--search-fallback", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--results-dir", type=Path, default=None)
    args = ap.parse_args()
    package = args.package_root.resolve(); store = args.store_root.resolve()
    audit_path = package / "data" / "all_20076_strict_image_audit.csv"
    all_rows = list(csv.DictReader(audit_path.open(encoding="utf-8-sig", newline="")))
    rows = all_rows[args.start:args.start + args.limit]
    domains = load_official_domains(package / "data" / "brand_official_domain_map.csv")
    results_dir = (args.results_dir or (package / "output")).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)
    overrides_path = package / "output" / "manual_overrides.csv"
    overrides = read_overrides(overrides_path)
    rejected_by_key = load_rejected_candidates(results_dir / "rejected_candidates.csv")
    results_path = results_dir / "all_20076_acquisition_results.csv"
    prior: dict[str, dict] = {}
    if args.resume and results_path.exists():
        prior = {r["immutableKey"]: r for r in csv.DictReader(results_path.open(encoding="utf-8-sig", newline=""))}
    todo = []
    results: dict[str, dict] = {}
    for row in rows:
        p = prior.get(row["immutableKey"])
        if p and p.get("status", "").startswith("STAGED") and (store / p.get("stagingPath", "")).exists():
            results[row["immutableKey"]] = p
        else:
            todo.append(row)
    print(f"Scope: {len(rows)} rows; resuming {len(results)} staged; processing {len(todo)}", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(process_row, r, package, store, domains, args.search_fallback, overrides, rejected_by_key): r for r in todo}
        done = 0
        for fut in as_completed(futs):
            row = futs[fut]
            try: res = fut.result()
            except Exception as exc:
                res = ImageResult(row["batchIndex"], row["immutableKey"], row["brand"], row["productName"], row["size"], row["targetJpgPath"], "ERROR", reason=str(exc))
            results[row["immutableKey"]] = asdict(res)
            done += 1
            if done % 50 == 0:
                ordered = [results[r["immutableKey"]] for r in rows if r["immutableKey"] in results]
                write_csv(results_path, ordered)
                counts = Counter(x["status"] for x in ordered)
                print(f"{done}/{len(todo)} processed: {dict(counts)}", flush=True)
    ordered = [results[r["immutableKey"]] for r in rows]

    # Duplicate-byte/perceptual conflicts across incompatible identities.
    by_sha: dict[str, list[dict]] = defaultdict(list)
    by_phash: dict[str, list[dict]] = defaultdict(list)
    for r in ordered:
        if r.get("sha256"): by_sha[r["sha256"]].append(r)
        if r.get("perceptualHash"): by_phash[r["perceptualHash"]].append(r)
    conflicts: list[dict] = []
    identity = lambda r: (norm(r["brand"]), norm(r["productName"]), frozenset(size_signatures(r["size"])))
    for kind, groups in (("sha256", by_sha), ("phash", by_phash)):
        for digest, group in groups.items():
            if len(group) < 2: continue
            ids = {identity(x) for x in group}
            if len(ids) > 1:
                for x in group:
                    conflicts.append({"conflictType": kind, "digest": digest, **x})
                    if x["status"].startswith("STAGED"):
                        x["status"] = "STAGED_DUPLICATE_CONFLICT_NEEDS_REVIEW"
                        x["autoApprovalEligible"] = False
                        x["reason"] = "Same or perceptually identical bytes are assigned to incompatible product/package identities."

    write_csv(results_path, ordered)
    review_fields = [
        "batchIndex", "immutableKey", "brand", "productName", "size", "targetJpgPath",
        "resolvedImageUrl", "evidencePage", "origin", "width", "height", "sha256",
        "perceptualHash", "pageBrandCoverage", "pageProductCoverage", "exactSizeEvidence",
        "imageCandidateScore", "status", "manualVisualDecision", "reviewer", "evidenceNote",
        "brandExact", "productNameExact", "sizeQuantityExact",
        "strengthExactOrNotApplicable", "formExactOrNotApplicable",
        "flavourAudienceBundleExactOrNotApplicable", "officialProductImageOrBottle",
        "noLogoPlaceholderLifestyle", "reviewedBrand", "reviewedProductName", "reviewedSizeQuantity",
    ]
    existing_review = {}
    review_path = results_dir / "manual_visual_review.csv"
    if review_path.exists():
        existing_review = {r["immutableKey"]: r for r in csv.DictReader(review_path.open(encoding="utf-8-sig", newline=""))}
    review_rows = []
    for r in ordered:
        old = existing_review.get(r["immutableKey"], {})
        rr = {k: r.get(k, "") for k in review_fields}
        rr["manualVisualDecision"] = old.get("manualVisualDecision", "PENDING")
        rr["reviewer"] = old.get("reviewer", "")
        rr["evidenceNote"] = old.get("evidenceNote", "")
        for field in [
            "brandExact", "productNameExact", "sizeQuantityExact",
            "strengthExactOrNotApplicable", "formExactOrNotApplicable",
            "flavourAudienceBundleExactOrNotApplicable", "officialProductImageOrBottle",
            "noLogoPlaceholderLifestyle", "reviewedBrand", "reviewedProductName", "reviewedSizeQuantity",
        ]:
            rr[field] = old.get(field, "")
        review_rows.append(rr)
    write_csv(review_path, review_rows, review_fields)
    write_csv(results_dir / "duplicate_conflicts.csv", conflicts)
    if not overrides_path.exists():
        write_csv(overrides_path, [{
            "immutableKey": "", "approvedDirectImageUrl": "", "approvedSourcePageUrl": "",
            "exactVariantConfirmed": "false", "reviewer": "", "evidenceNote": "",
        }])
    summary = {
        "scopeRows": len(rows), "statusCounts": dict(Counter(r["status"] for r in ordered)),
        "stagedRows": sum(r["status"].startswith("STAGED") for r in ordered),
        "unresolvedRows": sum(not r["status"].startswith("STAGED") for r in ordered),
        "uniqueDownloadedJpgBytes": len({r["sha256"] for r in ordered if r.get("sha256")}),
        "duplicateConflictRows": len({r["immutableKey"] for r in conflicts}),
        "note": "No staged row is production-approved until manual_visual_review.csv records APPROVED_EXACT_PRODUCT_PACKAGE and final validation passes.",
    }
    (results_dir / "acquisition_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
