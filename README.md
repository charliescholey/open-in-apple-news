# Open in Apple News

A Chrome extension for macOS that opens the article you're reading in the
Apple News app. If you subscribe to Apple News+, that's often the easiest way
to read a story that's paywalled on the web.

It doesn't guess from headlines. The extension hands the article's URL to the
News app, and News looks it up in Apple's own URL-to-article mapping. The
extension then tells you whether News found the article and checks that it's
the right one.

> Not affiliated with or endorsed by Apple. Apple News and Apple News+ are
> trademarks of Apple Inc.

## Requirements

- macOS with the News app (tested with News 12.0 on macOS 27.0.1)
- Google Chrome, Chromium, Brave or Microsoft Edge
- Python 3.9 or later for the helper. macOS's own `/usr/bin/python3` works once
  the Command Line Tools are installed (`xcode-select --install`).
- An Apple News+ subscription to read paywalled stories in full

## Install

1. Download this repository:

   ```bash
   git clone https://github.com/charliescholey/open-in-apple-news.git
   ```

2. In Chrome, open `chrome://extensions`, turn on **Developer mode**, click
   **Load unpacked**, and choose the `extension` folder.
3. Install the helper:

   ```bash
   zsh open-in-apple-news/helper/install.sh
   ```

   This copies a small helper to `~/Library/Application Support/OpenInAppleNews`
   and registers it with each Chrome-family browser it finds. Only this
   extension (ID `onlgflfjkkffflnafnehnmihpcagmlpo`, fixed by the key in
   `manifest.json`) is allowed to use it.

Why a helper? Chrome extensions can't launch Mac apps with arguments, and none
of the `applenews:` link forms reach News's article lookup. Details in
[docs/research.md](docs/research.md).

## Use

- Click the toolbar button, or press **Alt+Shift+N**, on an article page.
- Right-click a page → **Open page in Apple News**.
- Right-click a link → **Open link in Apple News**.

The button's badge shows the result. Hover over it for details.

| Badge | Meaning |
|---|---|
| … | Waiting for News |
| ✓ | Opened in Apple News; the article is filed under this page's URL |
| ? | News opened an article filed under a different URL. Check it's the same story |
| ✗ | Apple News doesn't have this article |
| ! | Something went wrong, e.g. the helper isn't installed |

For ?, ✗ and !, a notification explains what happened.

## How it works

```
Chrome tab ─▶ extension ─▶ helper ─▶ News app ─▶ Apple's URL-to-article lookup
                  ▲                     │
                  └──── ✓ / ✗ / ? ──────┘
```

1. The extension reads the page's canonical URL (`<link rel=canonical>`, then
   `og:url`, then the address bar), forces `https://`, and removes tracking
   parameters. News misses `http://` URLs that it finds as `https://`.
2. It sends the URL to the helper over Chrome
   [native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging).
3. The helper runs `open -a News <url>` and watches News's log. News logs a
   found article as `articleID=…`, typically within 1.5 s; if nothing appears
   within 6 s, the helper reports a miss.
4. For a hit, the helper fetches `https://apple.news/<articleID>` and checks
   that the publisher URL on that page matches the one it sent.
5. Hits are cached in the extension, so reopening an article goes straight to it.

## Privacy

The extension reads the current page's URL, and only when you click it. Two
network requests come from the lookup:

- News's own lookup (Apple's service, through Apple's privacy proxy)
- one request from the helper to `apple.news` to check a hit

There's no analytics and no other server. The cache of resolved articles stays
in Chrome's local extension storage.

## How well it works

Every hit was checked against its apple.news page, independently of News. Full
data and method are in [docs/research.md](docs/research.md).

| Test | Result |
|---|---|
| 41 articles from 11 publishers (answer key) | 33 found, **33 correct**, 8 not found (3 NYT, 5 WSJ) |
| 20 fresh articles News hadn't seen | 15 found, **15 correct**, 5 not found |
| Wrong matches | **0** |

Web search, the obvious alternative, found 0 of 33 of the same articles.

## Known limitations

- **NYT doesn't work,** because it isn't in Apple News.
- **WSJ works only partly.** Some WSJ articles resolve (for example
  `wsj.com/tech/…`), but none of 5 older-style `wsj.com/articles/…` URLs did.
- **News opens even on a miss.** The helper only learns the result after handing
  the URL over; on a miss, News probably shows the publisher's web page.
- **It depends on News's log wording.** If a macOS update changes it, every
  article will show ✗. Check the helper directly with:
  `python3 tools/ask_helper.py '{"action":"open","url":"<article url>"}'`
- **"Open link in Apple News" uses the link as-is.** Shortened or redirecting
  links (such as `t.co`) won't resolve. Open the article first.
- **macOS only.** It's not in the Chrome Web Store, because it needs the helper.
- **Tested on one Mac,** with News 12.0.

## Uninstall

```bash
zsh helper/uninstall.sh
```

Then remove the extension from `chrome://extensions`.

## Development

```
extension/   Chrome extension (Manifest V3)
helper/      native-messaging helper (Python 3.9+), install and uninstall scripts
tests/       unit tests (Node, Python) and an end-to-end test (Playwright)
tools/       icon generator and command-line helpers
docs/        research notes and measurement data
```

```bash
npm test             # URL handling (Node) + helper (Python 3.9, real captured News logs)
npm install          # once, for the end-to-end test
npm run test:e2e     # real Chromium + extension + helper + News app; opens News
```

The end-to-end test copies the helper to
`~/Library/Application Support/OpenInAppleNews`, registers it only for a
temporary browser profile, and opens the News app. Playwright can't click Chrome's toolbar, so the test calls the
button's handler directly.

## License

[MIT](LICENSE)
