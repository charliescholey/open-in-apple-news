// Injected into the article tab with chrome.scripting.executeScript, so it
// must be self-contained (no imports, no outer variables).
export function readPageUrls() {
  const attr = (selector, name) => document.querySelector(selector)?.getAttribute(name) || null;
  return {
    href: location.href,
    canonical: attr('link[rel="canonical"]', "href"),
    ogUrl: attr('meta[property="og:url"]', "content"),
    title: attr('meta[property="og:title"]', "content") || document.title || null,
  };
}
