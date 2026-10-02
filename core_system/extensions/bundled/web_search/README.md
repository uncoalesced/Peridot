# web_search (bundled plugin, beta)

Gives the model two tools:

- `web_search(query, n=5)` - numbered results (title, URL, snippet).
- `web_fetch(url)` - fetches a public http/https page and returns its readable text
  (scripts, styles, navigation and footers stripped; capped at ~6000 characters).

Off by default: it only runs when `web.enabled` is on and the plugin is approved
in the Extensions tab. Runs in the plugin sandbox with network access and no file access.

## Privacy

Using these tools sends data off your machine:

- Search queries go to DuckDuckGo (`html.duckduckgo.com`), or to your own SearXNG
  instance if `web.searxng_url` is set (then nothing goes to DuckDuckGo).
- `web_fetch` connects directly to the site the model asks for.

`web_fetch` refuses localhost, private LAN ranges (10.x, 172.16-31.x, 192.168.x),
link-local and other reserved addresses, including via redirects.

## Limitations

- DuckDuckGo's HTML page is not an API; a layout change or anti-bot page can make
  searches return no results. Point `web.searxng_url` at a SearXNG instance
  (with the JSON format enabled) for a stable backend.
- System proxy settings are not used.
