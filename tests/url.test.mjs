// Run: node --test tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { articleUrlFromPage, cleanArticleUrl } from "../extension/lib/url.js";

test("http is upgraded to https (News misses http:// URLs)", () => {
  // The New York Magazine feed link that missed in the feasibility test.
  assert.equal(
    cleanArticleUrl("http://nymag.com/intelligencer/article/doj-ilhan-omar-probe.html?utm_source=rss&utm_medium=social_acct&utm_campaign=feed-part"),
    "https://nymag.com/intelligencer/article/doj-ilhan-omar-probe.html",
  );
});

test("tracking parameters and fragments are dropped, other parameters kept", () => {
  assert.equal(
    cleanArticleUrl("https://example.com/story?id=42&utm_source=x&fbclid=y&mod=hp#comments"),
    "https://example.com/story?id=42",
  );
});

test("credentials in the URL are dropped", () => {
  assert.equal(cleanArticleUrl("https://user:pw@example.com/a"), "https://example.com/a");
});

test("non-web URLs are rejected", () => {
  for (const url of ["chrome://newtab/", "file:///tmp/a.html", "javascript:alert(1)", "about:blank", "not a url", "", undefined]) {
    assert.equal(cleanArticleUrl(url), null, String(url));
  }
});

test("canonical URL wins over the address bar", () => {
  assert.equal(
    articleUrlFromPage({
      href: "https://amp.example.com/story/amp?utm_source=twitter",
      canonical: "https://www.example.com/story/",
      ogUrl: "https://www.example.com/og-story/",
    }),
    "https://www.example.com/story/",
  );
});

test("relative canonical is resolved against the page", () => {
  assert.equal(
    articleUrlFromPage({ href: "https://example.com/news/a?x=1", canonical: "/news/a" }),
    "https://example.com/news/a",
  );
});

test("og:url is used when there is no canonical", () => {
  assert.equal(
    articleUrlFromPage({ href: "https://example.com/a?ref=x", canonical: null, ogUrl: "http://example.com/a" }),
    "https://example.com/a",
  );
});

test("a canonical pointing at the home page is ignored for an article page", () => {
  assert.equal(
    articleUrlFromPage({ href: "https://example.com/2026/10/story", canonical: "https://example.com/" }),
    "https://example.com/2026/10/story",
  );
});

test("broken canonical values fall back to the page URL", () => {
  assert.equal(
    articleUrlFromPage({ href: "https://example.com/story", canonical: "javascript:void(0)", ogUrl: "http://[bad" }),
    "https://example.com/story",
  );
});

test("pages with no usable URL return null", () => {
  assert.equal(articleUrlFromPage({ href: "chrome://settings/" }), null);
});
