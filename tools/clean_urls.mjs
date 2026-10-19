// Clean URLs (one per line on stdin) exactly as the extension does.
import { cleanArticleUrl } from "../extension/lib/url.js";
const input = await new Promise((resolve) => { let s = ""; process.stdin.on("data", (d) => (s += d)).on("end", () => resolve(s)); });
for (const line of input.split("\n").map((l) => l.trim()).filter(Boolean)) console.log(cleanArticleUrl(line) ?? "INVALID " + line);
