// Choosing and cleaning the URL handed to Apple News.
//
// News matches articles on the publisher's URL, not the headline. Tested on
// News 12.0: an http:// URL misses where the same https:// URL is found, and
// tracking parameters don't matter. So: prefer the page's canonical URL, force
// https, and drop fragments and well-known tracking parameters (which also
// keeps the cache keyed on one URL per article).

const TRACKING_PARAMS = new Set([
  "fbclid", "gclid", "dclid", "mc_cid", "mc_eid", "mod", "smid", "smtyp",
  "cmpid", "ocid", "guccounter", "taid",
]);

export function cleanArticleUrl(raw) {
  let url;
  try {
    url = new URL(raw);
  } catch {
    return null;
  }
  if (url.protocol === "http:") url.protocol = "https:";
  if (url.protocol !== "https:" || !url.hostname) return null;
  url.hash = "";
  url.username = "";
  url.password = "";
  for (const name of [...url.searchParams.keys()]) {
    if (name.toLowerCase().startsWith("utm_") || TRACKING_PARAMS.has(name.toLowerCase())) {
      url.searchParams.delete(name);
    }
  }
  return url.href;
}

// Pick the best article URL from what the page declares about itself.
// `canonical` and `ogUrl` may be relative or missing. A canonical that points
// at a site's home page while the page itself is deeper is a common publisher
// mistake, so such candidates are skipped.
export function articleUrlFromPage({ href, canonical, ogUrl }) {
  const page = cleanArticleUrl(href);
  for (const candidate of [canonical, ogUrl]) {
    if (!candidate) continue;
    let resolved;
    try {
      resolved = new URL(candidate, href).href;
    } catch {
      continue;
    }
    const cleaned = cleanArticleUrl(resolved);
    if (!cleaned) continue;
    if (isHomePage(cleaned) && page && !isHomePage(page)) continue;
    return cleaned;
  }
  return page;
}

function isHomePage(url) {
  const { pathname, search } = new URL(url);
  return (pathname === "/" || pathname === "") && !search;
}
