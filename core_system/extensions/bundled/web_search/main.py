# -----------------------------------------------------------------------------
# PERIDOT SOVEREIGN KERNEL v1.6.0 | BUNDLED PLUGIN: web_search
# Copyright (C) 2026 uncoalesced
# Licensed under the MIT License.
# Engineered by uncoalesced.
# -----------------------------------------------------------------------------

"""
Web search (DuckDuckGo HTML or a SearXNG instance) and page fetch.

Runs inside core_system/extensions/sandbox_child.py: stdlib only, no Peridot
imports, network only when the manifest grant is honoured.

Hidden argument `searxng_url`: web_search() accepts an optional searxng_url
that is NOT in the plugin.json schema, so the model never sees it. The parent
dispatcher injects it from the `web.searxng_url` setting (the sandbox child
cannot read settings). The dispatcher must also drop any searxng_url the model
supplies itself, because SearXNG requests skip the private-address guard
(self-hosted instances usually live on localhost / the LAN).
"""

import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
DDG_URL = "https://html.duckduckgo.com/html/"
TIMEOUT = 15
MAX_BYTES = 2 * 1024 * 1024
MAX_CHARS = 6000
TRUNCATED = "\n[truncated]"

_TEXT_TYPES = ("application/json", "application/xml", "application/xhtml+xml",
               "application/rss+xml", "application/atom+xml", "application/javascript")
_SKIP_TAGS = frozenset({"script", "style", "noscript", "nav", "footer", "svg", "template"})
_BLOCK_TAGS = frozenset({"p", "div", "br", "li", "ul", "ol", "tr", "table", "section",
                         "article", "header", "main", "aside", "blockquote", "pre",
                         "h1", "h2", "h3", "h4", "h5", "h6", "dt", "dd", "hr"})


# --------------------------------------------------------------------------- #
# SSRF guard
# --------------------------------------------------------------------------- #

def _bad_ip(ip) -> bool:
    return (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
            or ip.is_multicast or ip.is_unspecified)


def _check_url(url: str):
    """Return an error string if url is not a public http(s) URL, else None."""
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        return f"invalid URL ({exc})"
    if parts.scheme not in ("http", "https"):
        return "only http:// and https:// URLs are allowed"
    if not host:
        return "URL has no host"
    host = host.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return f"refusing to fetch local address {host}"
    try:
        addrs = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, port or (443 if parts.scheme == "https" else 80),
                                       proto=socket.IPPROTO_TCP)
        except OSError as exc:
            return f"cannot resolve {host} ({exc})"
        addrs = [ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos]
    if not addrs or any(_bad_ip(a) for a in addrs):
        return f"refusing to fetch private/local address {host}"
    # ponytail: check-then-connect leaves a DNS-rebinding window; pin the resolved IP
    # in a custom HTTPConnection if that ever matters.
    return None


class _GuardedRedirect(urllib.request.HTTPRedirectHandler):
    """Re-run the SSRF check on every redirect hop."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        err = _check_url(newurl)
        if err:
            raise urllib.error.URLError(f"redirect blocked: {err}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #

def _is_text(ctype: str) -> bool:
    return (ctype.startswith("text/") or ctype in _TEXT_TYPES
            or ctype.endswith("+json") or ctype.endswith("+xml"))


def _fetch(url: str, data: dict = None, guard: bool = True):
    """Return (content_type, charset, body_bytes, size). Body is empty for non-text types."""
    # ProxyHandler({}) skips the Windows registry proxy lookup, which the sandbox denies.
    # ponytail: system proxies are ignored; pass them in via the dispatcher if users need them.
    handlers = [urllib.request.ProxyHandler({})]
    if guard:
        handlers.append(_GuardedRedirect())
    opener = urllib.request.build_opener(*handlers)
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with opener.open(req, timeout=TIMEOUT) as resp:
        ctype = resp.headers.get_content_type()
        charset = resp.headers.get_content_charset() or "utf-8"
        length = resp.headers.get("Content-Length")
        if not _is_text(ctype):
            return ctype, charset, b"", int(length) if length and length.isdigit() else -1
        raw = resp.read(MAX_BYTES)
    return ctype, charset, raw, len(raw)


def _decode(raw: bytes, charset: str) -> str:
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _truncate(text: str, limit: int = MAX_CHARS) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + TRUNCATED


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------- #
# DuckDuckGo HTML parser
# --------------------------------------------------------------------------- #

def _unwrap_ddg(href: str) -> str:
    if href.startswith("//"):
        href = "https:" + href
    parts = urllib.parse.urlsplit(href)
    if parts.netloc.endswith("duckduckgo.com") and parts.path.startswith("/l/"):
        target = urllib.parse.parse_qs(parts.query).get("uddg")
        if target:
            return target[0]
    return href


class _DDGParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results = []
        self._ad = False
        self._cap = None  # [field, tag, depth, chunks]

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if self._cap is not None:
            if tag == self._cap[1]:
                self._cap[2] += 1
            return
        if tag == "div" and "result" in classes:
            self._ad = "result--ad" in classes
        elif "result__a" in classes:
            href = a.get("href") or ""
            if self._ad or "y.js" in href:
                return
            self.results.append({"title": "", "url": _unwrap_ddg(href), "snippet": ""})
            self._cap = ["title", tag, 0, []]
        elif "result__snippet" in classes and not self._ad and self.results:
            self._cap = ["snippet", tag, 0, []]

    def handle_endtag(self, tag):
        if self._cap is None or tag != self._cap[1]:
            return
        if self._cap[2]:
            self._cap[2] -= 1
            return
        field, _, _, chunks = self._cap
        self.results[-1][field] = _clean("".join(chunks))
        self._cap = None

    def handle_data(self, data):
        if self._cap is not None:
            self._cap[3].append(data)


def _parse_ddg(html: str) -> list:
    p = _DDGParser()
    p.feed(html)
    p.close()
    return [r for r in p.results if r["url"].startswith(("http://", "https://"))]


def _parse_searxng(raw: str) -> list:
    data = json.loads(raw)
    return [{"title": _clean(str(r.get("title") or "")), "url": str(r.get("url") or ""),
             "snippet": _clean(str(r.get("content") or ""))}
            for r in data.get("results") or [] if r.get("url")]


def _format(results: list, n: int) -> str:
    lines = []
    for i, r in enumerate(results[:n], 1):
        lines.append(f"{i}. {r['title'] or r['url']}\n   {r['url']}")
        if r["snippet"]:
            lines.append(f"   {r['snippet']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# HTML -> text
# --------------------------------------------------------------------------- #

class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip = 0
        self._chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self._chunks.append(data)


def _html_to_text(html: str):
    """Return (title, text) with script/style/nav/etc. removed and whitespace collapsed."""
    p = _TextParser()
    p.feed(html)
    p.close()
    lines = (re.sub(r"[ \t\r\f\v]+", " ", ln).strip() for ln in "".join(p._chunks).split("\n"))
    return _clean(p.title), "\n".join(ln for ln in lines if ln)


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #

def web_search(query: str = "", n: int = 5, searxng_url: str = None, **_ignored) -> str:
    """Search the web; returns numbered results."""
    if not isinstance(query, str) or not query.strip():
        return "Error: query must be a non-empty string"
    try:
        n = max(1, min(10, int(n)))
    except (TypeError, ValueError):
        n = 5
    query = query.strip()[:500]
    try:
        if searxng_url:
            # No DDG fallback on failure: the user chose SearXNG to keep queries away from DDG.
            url = searxng_url.rstrip("/") + "/search?" + urllib.parse.urlencode(
                {"q": query, "format": "json"})
            _, charset, raw, _ = _fetch(url, guard=False)
            results = _parse_searxng(_decode(raw, charset))
        else:
            _, charset, raw, _ = _fetch(DDG_URL, data={"q": query})
            results = _parse_ddg(_decode(raw, charset))
    except urllib.error.HTTPError as exc:
        return f"Error: search failed (HTTP {exc.code})"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return f"Error: search failed ({getattr(exc, 'reason', exc)})"
    if not results:
        return f"No results for {query!r}."
    return _format(results, n)


def web_fetch(url: str = "", **_ignored) -> str:
    """Fetch a public http(s) page and return its readable text."""
    if not isinstance(url, str) or not url.strip():
        return "Error: url must be a non-empty string"
    url = url.strip()
    err = _check_url(url)
    if err:
        return f"Error: {err}"
    try:
        ctype, charset, raw, size = _fetch(url)
    except urllib.error.HTTPError as exc:
        return f"Error: fetch failed (HTTP {exc.code})"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return f"Error: fetch failed ({getattr(exc, 'reason', exc)})"
    if not _is_text(ctype):
        shown = f"{size} bytes" if size >= 0 else "unknown size"
        return f"Non-text content ({ctype}, {shown}) at {url}; not displayed."
    text = _decode(raw, charset)
    title = ""
    if ctype in ("text/html", "application/xhtml+xml"):
        title, text = _html_to_text(text)
    head = f"Title: {title}\nURL: {url}\n\n" if title else f"URL: {url}\n\n"
    return head + _truncate(text)
