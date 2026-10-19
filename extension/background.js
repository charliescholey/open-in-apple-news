import { articleUrlFromPage, cleanArticleUrl } from "./lib/url.js";
import { readPageUrls } from "./lib/page.js";

const HOST = "com.open_in_apple_news.helper";
const CACHE_KEY = "resolved"; // article URL -> { articleId, appleTitle, at }
const CACHE_LIMIT = 500;
const BADGE_CLEAR_MS = 15000;

const BADGES = {
  working: { text: "…", color: "#8E8E93" },
  found: { text: "✓", color: "#1F9D55" },
  check: { text: "?", color: "#D97706" },
  missing: { text: "✗", color: "#D93025" },
  error: { text: "!", color: "#D93025" },
};

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({ id: "open-page", title: "Open page in Apple News", contexts: ["page"] });
    chrome.contextMenus.create({ id: "open-link", title: "Open link in Apple News", contexts: ["link"] });
  });
});

chrome.action.onClicked.addListener((tab) => openTab(tab));

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "open-link") openUrl(cleanArticleUrl(info.linkUrl), tab?.id);
  else if (tab) openTab(tab);
});

async function openTab(tab) {
  let page = { href: tab.url };
  try {
    const [injection] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: readPageUrls,
    });
    if (injection?.result) page = injection.result;
  } catch {
    // Browser pages, PDFs and the Web Store can't be scripted; use the tab URL.
  }
  return openUrl(articleUrlFromPage(page), tab.id);
}

const inFlight = new Set();

async function openUrl(url, tabId) {
  if (!url) {
    return report(tabId, "error", "This page has no web address Apple News can use.");
  }
  if (inFlight.has(url)) return { status: "busy" };
  inFlight.add(url);
  setBadge(tabId, "working", "Opening in Apple News…");
  try {
    const cache = await readCache();
    const cached = cache[url];
    let result;
    if (cached) {
      result = await sendToHelper({ action: "openArticle", articleId: cached.articleId });
      if (result.ok) result = { ...result, appleTitle: cached.appleTitle, verified: true };
    } else {
      result = await sendToHelper({ action: "open", url });
      if (result.status === "found" && result.verified !== false) {
        await writeCache(cache, url, result);
      }
    }
    return describe(tabId, result);
  } finally {
    inFlight.delete(url);
  }
}

async function sendToHelper(message) {
  try {
    return await chrome.runtime.sendNativeMessage(HOST, message);
  } catch (err) {
    const text = String(err?.message || err);
    if (/not found|forbidden/i.test(text)) {
      return { ok: false, status: "error", helperMissing: true,
               message: "The helper isn't installed. Run helper/install.sh, then try again." };
    }
    return { ok: false, status: "error", message: `Couldn't reach the helper: ${text}` };
  }
}

function describe(tabId, result) {
  if (result.status === "found") {
    const title = result.appleTitle ? `: ${result.appleTitle}` : "";
    if (result.verified === false) {
      return report(tabId, "check",
        `Apple News opened an article filed under a different URL${title}. Check it's the same story.`,
        result, { notify: true });
    }
    const unchecked = result.verified == null ? " (couldn't double-check the match)" : "";
    return report(tabId, "found", `Opened in Apple News${title}${unchecked}`, result);
  }
  if (result.status === "not_found") {
    return report(tabId, "missing",
      "Apple News doesn't have this article. News may show the publisher's web page instead. " +
      "(WSJ and NYT articles aren't matched.)",
      result, { notify: true });
  }
  return report(tabId, "error", result.message || "Something went wrong.", result, { notify: true });
}

function report(tabId, kind, message, result = {}, { notify = kind === "error" } = {}) {
  setBadge(tabId, kind, message);
  if (notify) {
    chrome.notifications.create({
      type: "basic",
      iconUrl: "icons/icon-128.png",
      title: kind === "missing" ? "Not in Apple News" : "Open in Apple News",
      message,
    });
  }
  return { ...result, kind, message };
}

function setBadge(tabId, kind, title) {
  const { text, color } = BADGES[kind];
  const target = tabId == null ? {} : { tabId };
  chrome.action.setBadgeText({ ...target, text });
  chrome.action.setBadgeBackgroundColor({ ...target, color });
  chrome.action.setTitle({ ...target, title });
  if (kind !== "working") {
    setTimeout(() => {
      chrome.action.setBadgeText({ ...target, text: "" }).catch(() => {});
      chrome.action.setTitle({ ...target, title: "Open in Apple News" }).catch(() => {});
    }, BADGE_CLEAR_MS);
  }
}

async function readCache() {
  const stored = await chrome.storage.local.get(CACHE_KEY);
  return stored[CACHE_KEY] || {};
}

async function writeCache(cache, url, { articleId, appleTitle }) {
  cache[url] = { articleId, appleTitle: appleTitle || null, at: Date.now() };
  const entries = Object.entries(cache);
  if (entries.length > CACHE_LIMIT) {
    entries.sort((a, b) => b[1].at - a[1].at);
    cache = Object.fromEntries(entries.slice(0, CACHE_LIMIT));
  }
  await chrome.storage.local.set({ [CACHE_KEY]: cache });
}

// Entry points for the end-to-end test (service-worker scope only).
globalThis.openInAppleNews = openUrl;
globalThis.pingHelper = () => sendToHelper({ action: "ping" });
