// End-to-end: loads the unpacked extension in Playwright's Chromium, registers
// the helper for that profile only, and drives the real flow. This opens the
// News app on this Mac.
//
// Playwright can't click Chrome's toolbar, so the button's handler is called
// through the service worker's test entry point instead; page URL extraction
// runs in a real article page.
//
// Run: npm run test:e2e
import { after, before, test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import { readPageUrls } from "../extension/lib/page.js";
import { articleUrlFromPage } from "../extension/lib/url.js";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const extensionDir = path.join(root, "extension");
const EXTENSION_ID = "onlgflfjkkffflnafnehnmihpcagmlpo";

// From the feasibility run: News resolves this one (verified) and not the NYT one.
const FOUND_URL = "https://www.theatlantic.com/ideas/archive/2024/05/birthday-milestone-age-happiness/678378/";
const NOT_FOUND_URL = "https://www.nytimes.com/2026/10/19/us/politics/supreme-court-race-school-admissions.html";

let profileDir, context, worker;

before(async () => {
  profileDir = mkdtempSync(path.join(tmpdir(), "open-in-news-e2e-"));
  execFileSync("zsh", [path.join(root, "helper/install.sh"), "--target-dir",
    path.join(profileDir, "NativeMessagingHosts")], { stdio: "ignore" });
  context = await chromium.launchPersistentContext(profileDir, {
    channel: "chromium",
    headless: true,
    args: [`--disable-extensions-except=${extensionDir}`, `--load-extension=${extensionDir}`],
  });
  worker = context.serviceWorkers()[0] || await context.waitForEvent("serviceworker");
});

after(async () => {
  await context?.close();
  rmSync(profileDir, { recursive: true, force: true });
});

const run = (fn, arg) => worker.evaluate(fn, arg);

test("extension loads with the ID the helper allows", () => {
  assert.equal(new URL(worker.url()).host, EXTENSION_ID);
});

test("helper answers over native messaging", async () => {
  assert.deepEqual(await run(() => pingHelper()), { ok: true, version: "1.0.0" });
});

test("canonical https URL is read from a real article page", async () => {
  const page = await context.newPage();
  await page.goto(FOUND_URL.replace("https://", "http://") + "?utm_source=e2e#top",
    { waitUntil: "domcontentloaded", timeout: 45000 });
  const urls = await page.evaluate(readPageUrls);
  assert.equal(articleUrlFromPage(urls), FOUND_URL);
  await page.close();
});

test("article in Apple News opens and is verified", async () => {
  const result = await run((url) => openInAppleNews(url), FOUND_URL);
  assert.equal(result.kind, "found", JSON.stringify(result));
  assert.equal(result.verified, true);
  assert.match(result.articleId, /^A[\w-]{15,}$/);
  assert.equal(await run(() => chrome.action.getBadgeText({})), "✓");
});

test("second open uses the cached article ID", async () => {
  const result = await run((url) => openInAppleNews(url), FOUND_URL);
  assert.equal(result.kind, "found");
  assert.equal(result.cached, true);
});

test("article not in Apple News is reported as missing", async () => {
  const result = await run((url) => openInAppleNews(url), NOT_FOUND_URL);
  assert.equal(result.kind, "missing", JSON.stringify(result));
  assert.equal(await run(() => chrome.action.getBadgeText({})), "✗");
  const cache = await run(() => chrome.storage.local.get("resolved"));
  assert.ok(!(NOT_FOUND_URL in (cache.resolved || {})), "misses must not be cached");
});

test("pages without a web URL get an error, not a hand-off", async () => {
  const result = await run(() => openInAppleNews(null));
  assert.equal(result.kind, "error");
  assert.equal(await run(() => chrome.action.getBadgeText({})), "!");
});
