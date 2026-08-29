import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional


@dataclass
class WebFetchInput:
    url: str
    format: str = "markdown"


@dataclass
class WebFetchResult:
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    content_type: Optional[str] = None


DESCRIPTION_FULL = """Fetch content from a URL.
- Returns markdown-formatted content by default.
- Use format=text for plain text, format=html for raw HTML.
- HTTP URLs are upgraded to HTTPS."""


def web_fetch(input: WebFetchInput) -> WebFetchResult:
    url = input.url.strip()
    if not url:
        return WebFetchResult(success=False, error="Empty URL.")

    if url.startswith("http://"):
        url = "https://" + url[7:]

    if not url.startswith("https://"):
        return WebFetchResult(success=False, error="URL must start with https://")

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; NemesisBot/2.0)",
            "Accept": "text/html,text/plain,*/*",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw = resp.read()
    except urllib.error.URLError as e:
        return WebFetchResult(success=False, error=f"Fetch failed: {e}")
    except Exception as e:
        return WebFetchResult(success=False, error=str(e))

    charset = "utf-8"
    if "charset=" in content_type:
        charset = content_type.split("charset=")[-1].split(";")[0].strip()

    try:
        text = raw.decode(charset, errors="replace")
    except Exception:
        text = raw.decode("utf-8", errors="replace")

    fmt = input.format.lower()
    if fmt == "html":
        content = text
    elif fmt == "markdown":
        content = _html_to_markdown(text, url)
    else:
        content = _strip_html(text)

    limit = 10_000_000  # 10 Mo - augmente de 100 Ko
    if len(content) > limit:
        content = content[:limit] + f"\n\n... (truncated at {limit} chars)"

    return WebFetchResult(
        success=True,
        content=content,
        content_type=content_type,
    )


def _strip_html(html: str) -> str:
    import re
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _html_to_markdown(html: str, base_url: str) -> str:
    try:
        import markdownify
        return markdownify.markdownify(html, heading_style="ATX", strip=["img", "script", "style"])
    except ImportError:
        try:
            from markdownify import markdownify as md
            return md(html, heading_style="ATX", strip=["img", "script", "style"])
        except ImportError:
            return _strip_html(html)
