"""Chrome native-messaging host for the "Open in Apple News" extension.

Chrome can't hand a publisher URL to News.app itself, so this helper runs
`open -a News <url>`. News then looks the URL up in Apple's own URL-to-article
mapping. When it finds the article, News logs "articleID=<ID>" within about a
second; when it doesn't, it logs nothing more. The helper watches News's log
to tell the two apart, then checks the article's apple.news page names the
same URL before reporting success.

Protocol: one JSON request per run, framed by Chrome (4-byte length prefix).
  {"action": "ping"}
  {"action": "open", "url": "https://..."}
  {"action": "openArticle", "articleId": "A..."}
Requires Python 3.9+ (macOS's /usr/bin/python3 is 3.9).
"""
import json
import os
import re
import select
import struct
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit

VERSION = "1.0.0"

# Measured on News 12.0: hits log their article ID 0.26-0.85s after News
# receives the URL (32 articles). Anything still unresolved after this is a miss.
RESOLVE_TIMEOUT = 6.0
# Upper bound for News to receive the URL at all (covers a cold launch).
HANDOFF_TIMEOUT = 20.0

LOG_PREDICATE = (
    'process == "News" AND '
    '(eventMessage CONTAINS "Handling url" OR eventMessage CONTAINS "articleID=")'
)
HANDLING_RE = re.compile(r"Handling url route=openURL, url=(.*), options=\{")
RESOLVED_RE = re.compile(
    r"(?:Presenting created article view controller|Did route to article), "
    r"articleID=([A-Za-z0-9_-]+)"
)
ARTICLE_ID_RE = re.compile(r"^A[A-Za-z0-9_-]{15,40}$")
MAX_URL_LENGTH = 2048

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


# --- Chrome native-messaging framing -------------------------------------

def read_message(stream):
    header = stream.read(4)
    if len(header) < 4:
        return None
    (length,) = struct.unpack("<I", header)
    return json.loads(stream.read(length).decode("utf-8"))


def write_message(stream, message):
    data = json.dumps(message).encode("utf-8")
    stream.write(struct.pack("<I", len(data)))
    stream.write(data)
    stream.flush()


# --- Input checks ---------------------------------------------------------

def check_url(url):
    """Return an error string, or None if the URL is safe to hand to News."""
    if not isinstance(url, str) or not url:
        return "No URL was sent."
    if len(url) > MAX_URL_LENGTH:
        return "The URL is too long."
    if any(ord(c) < 0x21 or ord(c) == 0x7F for c in url):
        return "The URL contains spaces or control characters."
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        return "Only https:// article URLs can be opened in Apple News."
    return None


def same_article_url(a, b):
    """Compare URLs the way apple.news pages report them: host (minus www.) + path."""
    def key(u):
        p = urlsplit(u)
        host = (p.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host + p.path.rstrip("/")
    return key(a) == key(b)


# --- Watching News --------------------------------------------------------

class NewsLogWatcher:
    """Follows News log lines for one hand-off and records the outcome."""

    def __init__(self, url):
        self.url = url
        self.received_at = None  # when News logged that it received our URL
        self.resolved_at = None
        self.article_id = None

    def feed(self, line, now):
        if self.received_at is None:
            m = HANDLING_RE.search(line)
            if m and m.group(1) == self.url:
                self.received_at = now
            return
        if self.article_id is None:
            m = RESOLVED_RE.search(line)
            if m:
                self.article_id = m.group(1)
                self.resolved_at = now

    def outcome(self, now, started_at):
        """'found', 'not_found', 'no_handoff', or None while still undecided."""
        if self.article_id:
            return "found"
        if self.received_at is not None:
            return "not_found" if now - self.received_at >= RESOLVE_TIMEOUT else None
        return "no_handoff" if now - started_at >= HANDOFF_TIMEOUT else None


class _LineReader:
    """Line reader over a pipe that works with select() (no hidden buffering)."""

    def __init__(self, fd):
        self.fd = fd
        self.buf = b""

    def read_lines(self, timeout):
        ready, _, _ = select.select([self.fd], [], [], timeout)
        if not ready:
            return []
        chunk = os.read(self.fd, 65536)
        if not chunk:
            raise EOFError
        self.buf += chunk
        *lines, self.buf = self.buf.split(b"\n")
        return [l.decode("utf-8", "replace") for l in lines]


def open_in_news(url):
    stream = subprocess.Popen(
        ["/usr/bin/log", "stream", "--style", "compact", "--predicate", LOG_PREDICATE],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        reader = _LineReader(stream.stdout.fileno())
        # `log stream` prints a "Filtering the log data..." header once it's live.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if any("Filtering" in l for l in reader.read_lines(0.5)):
                break
        else:
            return {"ok": False, "status": "error", "message": "Couldn't read the News log."}

        started = time.monotonic()
        subprocess.run(["/usr/bin/open", "-a", "News", url], check=True, timeout=15,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        watcher = NewsLogWatcher(url)
        while True:
            for line in reader.read_lines(0.25):
                watcher.feed(line, time.monotonic())
            result = watcher.outcome(time.monotonic(), started)
            if result:
                break
    except subprocess.CalledProcessError:
        return {"ok": False, "status": "error", "message": "macOS couldn't open the News app."}
    except (subprocess.TimeoutExpired, EOFError):
        return {"ok": False, "status": "error", "message": "The News app didn't respond."}
    finally:
        stream.terminate()

    elapsed_ms = int((time.monotonic() - started) * 1000)
    if result == "no_handoff":
        return {"ok": False, "status": "error", "elapsedMs": elapsed_ms,
                "message": "The News app never received the link."}
    if result == "not_found":
        return {"ok": True, "status": "not_found", "elapsedMs": elapsed_ms}

    response = {"ok": True, "status": "found", "articleId": watcher.article_id,
                "elapsedMs": elapsed_ms,
                "resolveMs": int((watcher.resolved_at - watcher.received_at) * 1000),
                "verified": None, "appleTitle": None}
    page = fetch_apple_news_page(watcher.article_id)
    if page:
        canonical, title = page
        response["appleTitle"] = title
        if canonical:
            response["verified"] = same_article_url(canonical, url)
            response["appleUrl"] = canonical
    return response


# --- Independent check against apple.news ----------------------------------

def parse_apple_news_page(html):
    """Return (publisher URL, headline) from an apple.news article page."""
    canonical = re.search(r'redirectToUrl\("([^"]+)"\)', html)
    title = re.search(r'<meta name="twitter:title" content="([^"]*)"', html)
    unescape = lambda s: (s.replace("&#x27;", "'").replace("&quot;", '"')
                          .replace("&#8217;", "’").replace("&amp;", "&"))
    return (canonical.group(1) if canonical else None,
            unescape(title.group(1)) if title else None)


def fetch_apple_news_page(article_id, timeout=6):
    if not ARTICLE_ID_RE.match(article_id):
        return None
    request = urllib.request.Request(
        "https://apple.news/" + article_id, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return parse_apple_news_page(resp.read().decode("utf-8", "replace"))
    except Exception:
        return None


# --- Requests --------------------------------------------------------------

def handle(message):
    action = message.get("action") if isinstance(message, dict) else None
    if action == "ping":
        return {"ok": True, "version": VERSION}
    if action == "open":
        error = check_url(message.get("url"))
        if error:
            return {"ok": False, "status": "error", "message": error}
        return open_in_news(message["url"])
    if action == "openArticle":
        article_id = message.get("articleId")
        if not isinstance(article_id, str) or not ARTICLE_ID_RE.match(article_id):
            return {"ok": False, "status": "error", "message": "Invalid article ID."}
        subprocess.run(["/usr/bin/open", "applenewss:///" + article_id], check=False,
                       timeout=15, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"ok": True, "status": "found", "articleId": article_id, "cached": True}
    return {"ok": False, "status": "error", "message": "Unknown request."}


def main():
    message = read_message(sys.stdin.buffer)
    if message is None:
        return
    try:
        response = handle(message)
    except Exception as exc:  # report, don't crash: Chrome only sees a closed pipe
        response = {"ok": False, "status": "error", "message": "Helper error: %s" % exc}
    write_message(sys.stdout.buffer, response)


if __name__ == "__main__":
    main()
