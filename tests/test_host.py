"""Unit tests for the native helper. Fixtures are real News 12.0 logs and a real
apple.news page captured on 2026-10-19.
Run: python3 -m unittest discover -s tests
"""
import io
import json
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "helper"))

import open_in_news_host as host  # noqa: E402
from extension_id import extension_id  # noqa: E402

FOUND_URL = "https://www.theatlantic.com/technology/2026/10/blocking-internet-archive-will-not-stop-ai/689065/?utm_source=feed"
NOT_FOUND_URL = "https://www.nytimes.com/2026/10/19/us/politics/supreme-court-race-school-admissions.html"


def fixture(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as f:
        return f.read()


def replay(url, log_name):
    """Feed a captured log to the watcher, using each line's own timestamp."""
    watcher = host.NewsLogWatcher(url)
    for i, line in enumerate(fixture(log_name).splitlines()):
        watcher.feed(line, now=float(i))
    return watcher


class FramingTest(unittest.TestCase):
    def test_round_trip(self):
        buf = io.BytesIO()
        host.write_message(buf, {"ok": True, "text": "café"})
        buf.seek(0)
        self.assertEqual(host.read_message(buf), {"ok": True, "text": "café"})

    def test_length_prefix_is_little_endian(self):
        buf = io.BytesIO()
        host.write_message(buf, {})
        self.assertEqual(struct.unpack("<I", buf.getvalue()[:4])[0], 2)

    def test_empty_input_returns_none(self):
        self.assertIsNone(host.read_message(io.BytesIO(b"")))


class CheckUrlTest(unittest.TestCase):
    def test_accepts_https_article(self):
        self.assertIsNone(host.check_url(FOUND_URL))

    def test_rejects_non_https(self):
        for url in ("http://example.com/a", "file:///etc/passwd", "javascript:alert(1)",
                    "applenewss:///A6UDOEwKKT0S0Sz5jk9FW_g", "-a Terminal"):
            self.assertIsNotNone(host.check_url(url), url)

    def test_rejects_whitespace_and_control_characters(self):
        self.assertIsNotNone(host.check_url("https://example.com/a b"))
        self.assertIsNotNone(host.check_url("https://example.com/a\nb"))

    def test_rejects_missing_or_oversized(self):
        self.assertIsNotNone(host.check_url(None))
        self.assertIsNotNone(host.check_url(""))
        self.assertIsNotNone(host.check_url("https://example.com/" + "a" * 3000))


class WatcherTest(unittest.TestCase):
    def test_found_log_yields_article_id(self):
        watcher = replay(FOUND_URL, "news-log-found.log")
        self.assertEqual(watcher.article_id, "A2_tZ09PCQqe_l7ndpu3-1g")
        self.assertEqual(watcher.outcome(now=999, started_at=0), "found")

    def test_not_found_log_times_out_as_miss(self):
        watcher = replay(NOT_FOUND_URL, "news-log-not-found.log")
        self.assertIsNotNone(watcher.received_at)
        self.assertIsNone(watcher.article_id)
        self.assertIsNone(watcher.outcome(now=watcher.received_at + 1, started_at=0))
        self.assertEqual(watcher.outcome(now=watcher.received_at + host.RESOLVE_TIMEOUT,
                                         started_at=0), "not_found")

    def test_ignores_articles_opened_for_other_urls(self):
        # Our URL never reaches News, so the other URL's article must not count.
        watcher = replay("https://example.com/not-this-one", "news-log-found.log")
        self.assertIsNone(watcher.article_id)
        self.assertEqual(watcher.outcome(now=host.HANDOFF_TIMEOUT, started_at=0), "no_handoff")

    def test_ignores_article_ids_logged_before_handoff(self):
        watcher = host.NewsLogWatcher(NOT_FOUND_URL)
        watcher.feed("... Presenting created article view controller, articleID=AAAAAAAAAAAAAAAAAAAA", 0)
        for i, line in enumerate(fixture("news-log-not-found.log").splitlines()):
            watcher.feed(line, i + 1)
        self.assertIsNone(watcher.article_id)


class ApplePageTest(unittest.TestCase):
    def test_parses_publisher_url_and_title(self):
        canonical, title = host.parse_apple_news_page(fixture("apple-news-article.html"))
        self.assertEqual(canonical, "https://www.theatlantic.com/ideas/2026/08/college-loneliness-socializing/688307/?utm_source=apple_news")
        self.assertEqual(title, "Even College Students Have Stopped Hanging Out")

    def test_same_article_url(self):
        self.assertTrue(host.same_article_url(
            "https://www.theatlantic.com/ideas/2026/08/college-loneliness-socializing/688307/?utm_source=apple_news",
            "https://theatlantic.com/ideas/2026/08/college-loneliness-socializing/688307"))
        self.assertFalse(host.same_article_url(
            "https://www.theatlantic.com/ideas/2026/08/college-loneliness-socializing/688307/",
            "https://www.theatlantic.com/ideas/2026/08/other-story/688308/"))

    def test_fetch_rejects_malformed_ids_without_network(self):
        self.assertIsNone(host.fetch_apple_news_page("../etc"))


class HandleTest(unittest.TestCase):
    def test_ping(self):
        self.assertEqual(host.handle({"action": "ping"}), {"ok": True, "version": host.VERSION})

    def test_bad_url_is_refused_before_opening_anything(self):
        result = host.handle({"action": "open", "url": "file:///Applications/Calculator.app"})
        self.assertEqual(result["status"], "error")

    def test_bad_article_id(self):
        self.assertEqual(host.handle({"action": "openArticle", "articleId": "x; rm -rf"})["status"], "error")

    def test_unknown_action(self):
        self.assertFalse(host.handle({"action": "nope"})["ok"])
        self.assertFalse(host.handle(["not", "a", "dict"])["ok"])


class ExtensionIdTest(unittest.TestCase):
    def test_id_matches_manifest_key(self):
        with open(os.path.join(HERE, "..", "extension", "manifest.json")) as f:
            key = json.load(f)["key"]
        self.assertEqual(extension_id(key), "onlgflfjkkffflnafnehnmihpcagmlpo")


if __name__ == "__main__":
    unittest.main()
