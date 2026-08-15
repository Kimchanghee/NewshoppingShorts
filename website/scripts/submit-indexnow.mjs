import fs from "node:fs";
import path from "node:path";

const SITE_URL = "https://shoppingshorts.store";
const HOST = "shoppingshorts.store";
const INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow";
const INDEXNOW_KEY = process.env.INDEXNOW_KEY || "9947ed4d3009402a4fe6ddf81a7061ca";
const KEY_LOCATION = `${SITE_URL}/${INDEXNOW_KEY}.txt`;

function readSitemapUrls() {
  const sitemapPath = path.join(process.cwd(), "public", "sitemap.xml");
  const sitemap = fs.readFileSync(sitemapPath, "utf8");
  return [...sitemap.matchAll(/<loc>(.*?)<\/loc>/g)].map((match) => match[1]);
}

const urlList = [
  ...readSitemapUrls(),
  `${SITE_URL}/feed.xml`,
  `${SITE_URL}/atom.xml`,
  `${SITE_URL}/feed.json`,
  `${SITE_URL}/llms.txt`,
  `${SITE_URL}/llms-full.txt`,
  `${SITE_URL}/${INDEXNOW_KEY}.txt`,
].filter((url) => url.startsWith(SITE_URL));

const body = {
  host: HOST,
  key: INDEXNOW_KEY,
  keyLocation: KEY_LOCATION,
  urlList: [...new Set(urlList)],
};

const response = await fetch(INDEXNOW_ENDPOINT, {
  method: "POST",
  headers: {
    "Content-Type": "application/json; charset=utf-8",
    "User-Agent": "ssmaker-indexnow-submitter",
  },
  body: JSON.stringify(body),
});

const responseText = await response.text();
console.log(`IndexNow response: ${response.status} ${response.statusText}`);
if (responseText.trim()) console.log(responseText.trim());

if (![200, 202].includes(response.status)) {
  process.exitCode = 1;
}
