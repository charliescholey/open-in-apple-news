# Research notes: finding the Apple News version of a web article

These notes explain why the extension works the way it does, and record the
measurements behind it. All tests were run on 2026-10-19 with News 12.0 on
macOS 27.0.1.

Data: [search-vs-news-lookup.csv](search-vs-news-lookup.csv) (approach comparison) ·
[validation-results.csv](validation-results.csv) (final run through the shipped helper)

## The problem

To open a web article in Apple News you need its Apple News ID
(`https://apple.news/A…`). Apple offers no public API that maps a publisher URL
to that ID.

## What apple.news pages contain

An article page such as `https://apple.news/A6UDOEwKKT0S0Sz5jk9FW_g` is small,
plain HTML. It contains:

- `og:title` / `twitter:title`: the headline
- the publisher's own article URL, used as a fallback redirect
  (with `?utm_source=apple_news`)
- a redirect to the News app: `applenewss:///<ID>`

IDs encode their type: `A…` article, `T…` channel, `I…` magazine issue.

The page script handles **Chrome on macOS** specially: it sends the browser to
the News app and deliberately does not fall back to the publisher URL. The
embedded publisher URL also gives an independent way to check a match: the
article must be filed under the URL you started from.

## Approach 1: web search (rejected)

The obvious approach is to search for `site:apple.news "<headline>"`.

- Scripted requests to DuckDuckGo and Bing return bot-check pages, so the
  search would have to run in a visible browser tab.
- **DuckDuckGo** (in a real tab) honours `site:apple.news`, but found
  **0 of 33** sampled articles. A control article that is indexed was found,
  so the query works; the index simply has very few apple.news article pages.
- Unquoted headline searches return *unrelated* apple.news articles. Picking
  the top one would open the wrong story.
- **Bing** ignores `site:apple.news`. **Google** returned a CAPTCHA, so testing
  there stopped.

The 33 articles were sampled from 11 publishers' RSS feeds (newest, middle and
oldest item per feed), so the sample doesn't depend on any search index.

## Approach 2: let the News app resolve the URL (adopted)

News registers the `applenews` and `applenewss` URL schemes, and its log shows
how it routes each URL it receives. Tests:

| Handed to News | Result |
|---|---|
| `applenewss:///<ID>` | Opens the article (`articleDeeplink`) |
| `applenewss:///search?q=…` | Opens the search screen but drops the query (`searchHome(query: nil)`) |
| `applenewss://<host>/<path>`, `applenewss:///https://…`, `applenewss:https://…`, `applenewss://?url=…` | Don't reach the article lookup |
| **`open -a News https://publisher.com/article`** | **`articleWebLink`: News looks the URL up and opens the matching article** |

For that last form, News runs a `WebURLResolution` step: a hashed bucket lookup
against Apple's URL-to-article mapping, fetched through Apple's privacy proxy.
On a hit it logs `articleID=<ID>` and opens the article in its reader. On a
miss it logs nothing further.

Because only `open -a News <url>` works, and a Chrome extension can't run
commands, the extension needs a small native-messaging helper.

### Measurements

Each hit was checked independently of News: the helper fetches
`https://apple.news/<ID>` and compares the publisher URL on that page with the
URL it sent (host + path).

| Set | Found | Verified correct | Wrong |
|---|---|---|---|
| RSS sample, URLs as they appear in the feeds (33) | 24 | 24 | 0 |
| Follow-up: 2023–2024 articles, recent WSJ, URL variants (12) | 9 | 9 | 0 |
| Answer key re-run through the shipped helper (41 unique URLs) | 33 | 33 | 0 |
| Fresh articles News hadn't seen before (20) | 15 | 15 | 0 |

By publisher, with clean `https://` URLs: The Atlantic, Bloomberg, Business
Insider, The Economist, LA Times, The New Yorker, New York Magazine, Vanity Fair
and Wired all resolved. Articles from 2023 and 2024 resolved too.

Misses:

- **WSJ:** 0 of 5 in these runs (January 2025 and October 2026), all
  `wsj.com/articles/…` URLs, four of them from a WSJ feed that stopped updating
  in January 2025. Later (2026-10-29), a section-style WSJ URL
  (`wsj.com/tech/apple-iphone-memory-chips-ai-c0084cc9`) resolved and verified
  in 0.7 s. So WSJ is at least partly covered; the URL format is a likely but
  unconfirmed reason for the misses.
- **NYT:** 0 of 3. NYT isn't in Apple News.
- **Fresh misses:** 3 New Yorker print-magazine pieces dated a week ahead
  (published online before the issue), and 2 Vanity Fair photo galleries.

Other findings:

- **`http://` breaks the lookup; tracking parameters don't.** The same Wired
  article missed as `http://…` and resolved as `https://…?utm_source=rss`. The
  New York Magazine feed's `http://` links caused its first-run misses.
- **Matching is by URL, not headline.** Two Bloomberg stories carry different
  headlines in Apple News and still matched.
- **Timing:** once News has received a URL, hits log their article ID in
  0.26–1.47 s (40 measurements). The helper treats 6 s with no ID as a miss.
  A cold start (News not running) took 4.9 s end to end.

## Not established

- What News shows on screen for a miss (likely the publisher's web page).
  Only the logs were checked.
- Why some WSJ URLs miss: possibly older `/articles/` URLs that WSJ now
  redirects to section-style URLs. Not checked; WSJ blocks scripted requests.
- Behaviour on other macOS or News versions.
