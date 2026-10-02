"""v1.6.0 bundled web_search plugin: parsers, SSRF guard, manifest, sandbox run. No network."""

import importlib.util
import json
import re
import socket
import sys
from pathlib import Path

import pytest

from core_system.extensions.sandbox import run_tool

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "core_system" / "extensions" / "bundled" / "web_search"


def _load():
    spec = importlib.util.spec_from_file_location("web_search_plugin", PLUGIN_DIR / "main.py")
    mod = importlib.util.module_from_spec(spec)
    # Keep __pycache__ out of the bundled plugin dir (the registry hashes its contents).
    old, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = old
    return mod


web = _load()

DDG_HTML = """
<html><body><div id="links" class="results">
<div class="result results_links results_links_deep result--ad ">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a rel="nofollow" class="result__a" href="https://duckduckgo.com/y.js?ad_domain=shop.example&amp;ad_provider=bing">Buy Widgets Now</a>
    </h2>
    <a class="result__snippet" href="https://duckduckgo.com/y.js?ad_domain=shop.example">Sponsored widgets at low prices</a>
  </div>
</div>
<div class="result results_links results_links_deep web-result ">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.python.org%2Fdownloads%2F%3Fa%3D1%26b%3D2&amp;rut=abc123">Download <b>Python</b> | Python.org</a>
    </h2>
    <div class="result__extras"><a class="result__url" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.python.org%2Fdownloads%2F">www.python.org/downloads/</a></div>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.python.org%2Fdownloads%2F">The official home of the <b>Python</b> Programming Language &amp; more</a>
  </div>
</div>
<div class="result results_links results_links_deep web-result ">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fen.wikipedia.org%2Fwiki%2FPython_(programming_language)&amp;rut=def456">Python (programming language) - Wikipedia</a>
    </h2>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=x">Python is a high-level,
       general-purpose programming language.</a>
  </div>
</div>
</div></body></html>
"""

PAGE_HTML = """<!doctype html>
<html><head><title>  My  Test Page </title>
<style>body { color: red; }</style>
<script>var secret = "SCRIPT_TEXT";</script><!-- pragma: allowlist secret -->
</head><body>
<nav><a href="/">Home</a> NAV_TEXT</nav>
<h1>Hello   world</h1>
<p>First paragraph.</p><p>Second &amp; last.</p>
<noscript>NOSCRIPT_TEXT</noscript>
<svg><text>SVG_TEXT</text></svg>
<footer>FOOTER_TEXT</footer>
</body></html>"""


# --------------------------------------------------------------------------- #
# search parsing
# --------------------------------------------------------------------------- #

def test_ddg_parser_extracts_unwraps_and_skips_ads():
    results = web._parse_ddg(DDG_HTML)
    assert [r["title"] for r in results] == [
        "Download Python | Python.org",
        "Python (programming language) - Wikipedia",
    ]
    assert results[0]["url"] == "https://www.python.org/downloads/?a=1&b=2"
    assert results[1]["url"] == "https://en.wikipedia.org/wiki/Python_(programming_language)"
    assert results[0]["snippet"] == "The official home of the Python Programming Language & more"
    assert results[1]["snippet"] == "Python is a high-level, general-purpose programming language."
    assert not any("y.js" in r["url"] or "Widgets" in r["title"] for r in results)


def test_web_search_ddg_formats_numbered_results(monkeypatch):
    calls = []

    def fake_fetch(url, data=None, guard=True):
        calls.append((url, data, guard))
        return "text/html", "utf-8", DDG_HTML.encode(), len(DDG_HTML)

    monkeypatch.setattr(web, "_fetch", fake_fetch)
    out = web.web_search(query="python", n=1)
    assert calls == [(web.DDG_URL, {"q": "python"}, True)]
    assert out == ("1. Download Python | Python.org\n"
                   "   https://www.python.org/downloads/?a=1&b=2\n"
                   "   The official home of the Python Programming Language & more")


def test_web_search_searxng_mapping(monkeypatch):
    payload = json.dumps({"results": [
        {"title": "Result One", "url": "https://one.example/", "content": "first  snippet"},
        {"title": "Result Two", "url": "https://two.example/", "content": ""},
        {"title": "no url", "content": "dropped"},
    ]}).encode()
    seen = {}

    def fake_fetch(url, data=None, guard=True):
        seen.update(url=url, guard=guard)
        return "application/json", "utf-8", payload, len(payload)

    monkeypatch.setattr(web, "_fetch", fake_fetch)
    out = web.web_search(query="a b", n=5, searxng_url="http://127.0.0.1:8888/")
    assert seen["url"] == "http://127.0.0.1:8888/search?q=a+b&format=json"
    assert seen["guard"] is False  # self-hosted SearXNG is usually on localhost/LAN
    assert out == ("1. Result One\n   https://one.example/\n   first snippet\n"
                   "2. Result Two\n   https://two.example/")


def test_web_search_errors_never_raise(monkeypatch):
    def boom(url, data=None, guard=True):
        raise OSError("connection reset")

    monkeypatch.setattr(web, "_fetch", boom)
    assert web.web_search(query="x").startswith("Error: search failed")
    assert web.web_search(query="  ").startswith("Error:")
    assert web.web_search(query=None).startswith("Error:")


# --------------------------------------------------------------------------- #
# fetch / text extraction
# --------------------------------------------------------------------------- #

def test_html_to_text_strips_noise_and_keeps_title():
    title, text = web._html_to_text(PAGE_HTML)
    assert title == "My Test Page"
    assert "Hello world" in text
    assert "First paragraph." in text and "Second & last." in text
    for junk in ("SCRIPT_TEXT", "color: red", "NAV_TEXT", "NOSCRIPT_TEXT", "SVG_TEXT", "FOOTER_TEXT"):
        assert junk not in text


def test_truncation_marker():
    assert web._truncate("short") == "short"
    out = web._truncate("x" * 7000)
    assert out.endswith("[truncated]")
    assert len(out) == web.MAX_CHARS + len(web.TRUNCATED)


def _fake_dns(mapping):
    def fake(host, port, *a, **kw):
        if host not in mapping:
            raise socket.gaierror(f"unexpected DNS lookup for {host}")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (mapping[host], port))]
    return fake


@pytest.mark.parametrize("url", [
    "file:///C:/Windows/win.ini",
    "ftp://example.com/file",
    "http://127.0.0.1/",
    "http://localhost:8080/",
    "http://192.168.1.1/",
    "http://10.0.0.1/admin",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/",
    "http://router.lan/",
])
def test_web_fetch_refuses_non_public(monkeypatch, url):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns({"localhost": "127.0.0.1", "router.lan": "172.16.0.1"}))

    def no_fetch(*a, **kw):
        raise AssertionError("must not fetch")

    monkeypatch.setattr(web, "_fetch", no_fetch)
    out = web.web_fetch(url=url)
    assert out.startswith("Error:"), out


def test_web_fetch_public_html(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns({"example.com": "93.184.216.34"}))
    monkeypatch.setattr(web, "_fetch", lambda url, data=None, guard=True:
                        ("text/html", "utf-8", PAGE_HTML.encode(), len(PAGE_HTML)))
    out = web.web_fetch(url="https://example.com/page")
    assert out.startswith("Title: My Test Page\nURL: https://example.com/page\n\n")
    assert "First paragraph." in out and "SCRIPT_TEXT" not in out


def test_web_fetch_non_text(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns({"example.com": "93.184.216.34"}))
    monkeypatch.setattr(web, "_fetch", lambda url, data=None, guard=True: ("application/pdf", "utf-8", b"", 12345))
    out = web.web_fetch(url="https://example.com/a.pdf")
    assert "application/pdf" in out and "12345 bytes" in out


def test_redirect_to_private_blocked():
    import urllib.error
    import urllib.request

    req = urllib.request.Request("https://93.184.216.34/")
    with pytest.raises(urllib.error.URLError):
        web._GuardedRedirect().redirect_request(req, None, 302, "Found", {}, "http://127.0.0.1/admin")


# --------------------------------------------------------------------------- #
# manifest + sandbox
# --------------------------------------------------------------------------- #

def test_manifest_valid_and_tools_exist():
    manifest = json.loads((PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "web_search"
    assert manifest["entry"] == "main.py" and (PLUGIN_DIR / manifest["entry"]).is_file()
    assert manifest["permissions"] == {"network": True, "files": "none"}
    names = [t["name"] for t in manifest["tools"]]
    assert names == ["web_search", "web_fetch"]
    for tool in manifest["tools"]:
        assert re.fullmatch(r"[a-z0-9_]{1,40}", tool["name"])
        assert tool["description"]
        assert tool["parameters"]["type"] == "object"
        assert "searxng_url" not in tool["parameters"]["properties"]
        assert callable(getattr(web, tool["name"]))


def test_sandbox_refuses_loopback_without_hanging():
    policy = {"network": False, "read_paths": [], "write_paths": [], "mem_mb": 512}
    r = run_tool(PLUGIN_DIR, "main.py", "web_fetch", {"url": "http://127.0.0.1/"}, policy, timeout=30)
    refused = r["ok"] and r["result"].startswith("Error: refusing")
    assert refused or r["denied"], r


# --------------------------------------------------------------------------- #
# install wizard opt-in
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("answer", [True, False])
def test_wizard_web_search_opt_in(tmp_path, monkeypatch, answer):
    import shutil

    import install_wizard

    shutil.copytree(PLUGIN_DIR, tmp_path / "core_system" / "extensions" / "bundled" / "web_search")
    approved = []
    monkeypatch.setattr(install_wizard, "wait_for_enter", lambda *a, **kw: answer)
    monkeypatch.setattr(install_wizard, "_approve_bundled_plugin", lambda name: approved.append(name) or True)
    install_wizard.setup_web_search(tmp_path)
    dst = tmp_path / "extensions" / "plugins" / "web_search"
    assert (dst / "plugin.json").is_file() == answer
    assert approved == (["web_search"] if answer else [])
