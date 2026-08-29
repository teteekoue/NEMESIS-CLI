import json
import urllib.request
import urllib.parse
import urllib.error
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class WebSearchInput:
    query: str
    max_results: int = 5


@dataclass
class WebSearchResult:
    success: bool
    results: List[dict] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.results is None:
            self.results = []


DESCRIPTION_FULL = """Search the web using DuckDuckGo.
- Returns titles, URLs, and snippets.
- Use max_results to control result count (max 10)."""


def web_search(input: WebSearchInput) -> WebSearchResult:
    query = input.query.strip()
    if not query:
        return WebSearchResult(success=False, error="Empty query.")

    results = []
    try:
        results = _ddg_search(query, min(input.max_results, 10))
    except Exception as e:
        pass

    if not results:
        try:
            results = _ddg_html_search(query, min(input.max_results, 10))
        except Exception as e:
            return WebSearchResult(success=False, error=str(e))

    return WebSearchResult(success=True, results=results)


def _ddg_search(query: str, max_results: int) -> List[dict]:
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
                for r in results
            ]
    except ImportError:
        raise
    except Exception:
        raise


def _ddg_html_search(query: str, max_results: int) -> List[dict]:
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; NemesisBot/2.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Search request failed: {e}")

    from html.parser import HTMLParser

    class DDGParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.results = []
            self.current = {}
            self.in_result = False
            self.in_title = False
            self.in_snippet = False
            self.tag_stack = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "a" and "result__a" in attrs.get("class", ""):
                self.in_result = True
                self.current = {"title": "", "url": "", "snippet": ""}
                href = attrs.get("href", "")
                if href.startswith("//"):
                    href = "https:" + href
                self.current["url"] = href
                self.in_title = True
            elif tag == "a" and "result__snippet" in attrs.get("class", ""):
                self.in_snippet = True

        def handle_endtag(self, tag):
            if tag == "a" and self.in_title:
                self.in_title = False
            if tag == "a" and self.in_snippet:
                self.in_snippet = False
                if self.current.get("title"):
                    self.results.append(self.current)
                self.current = {}
                self.in_result = False

        def handle_data(self, data):
            if self.in_title:
                self.current["title"] += data
            elif self.in_snippet:
                self.current["snippet"] += data

    parser = DDGParser()
    parser.feed(html)
    return parser.results[:max_results]
