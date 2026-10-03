import urllib.request
import urllib.error
import urllib.parse
import ipaddress
import socket
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

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def _is_public_https_url(url: str) -> Optional[str]:
    """Return an error for non-public HTTPS destinations, else ``None``.

    Fetching is an agent capability, so it must not become a route to loopback,
    private networks, or cloud metadata services.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return "URL must start with https:// and include a hostname."
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return "Cannot resolve host: {0}".format(exc)
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            return "Private, loopback, or reserved network addresses are not allowed."
    return None


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """Avoid redirect-based SSRF; callers must fetch the final HTTPS URL directly."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def web_fetch(input: WebFetchInput) -> WebFetchResult:
    url = input.url.strip()
    if not url:
        return WebFetchResult(success=False, error="Empty URL.")

    if url.startswith("http://"):
        url = "https://" + url[7:]

    url_error = _is_public_https_url(url)
    if url_error:
        return WebFetchResult(success=False, error=url_error)

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; NemesisBot/2.0)",
            "Accept": "text/html,text/plain,*/*",
        },
    )

    try:
        opener = urllib.request.build_opener(_NoRedirects())
        with opener.open(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            declared_size = resp.headers.get("Content-Length")
            if declared_size and int(declared_size) > _MAX_RESPONSE_BYTES:
                return WebFetchResult(success=False, error="Response exceeds the 2 MiB fetch limit.")
            chunks = []
            total = 0
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > _MAX_RESPONSE_BYTES:
                    return WebFetchResult(success=False, error="Response exceeds the 2 MiB fetch limit.")
                chunks.append(chunk)
            raw = b"".join(chunks)
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
