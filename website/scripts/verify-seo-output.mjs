import fs from "node:fs";
import path from "node:path";

const distDir = path.join(process.cwd(), "dist");
const read = (relativePath) => fs.readFileSync(path.join(distDir, relativePath), "utf8");
const fail = (message) => {
  throw new Error(`SEO verification failed: ${message}`);
};

const homeHtml = read("index.html");
const samplesHtml = read(path.join("samples", "index.html"));
const sitemap = read("sitemap.xml");
const robots = read("robots.txt");
const feed = read("feed.xml");

if (!homeHtml.includes("data-static-fallback")) fail("home raw HTML has no textual fallback");
if (!samplesHtml.includes("data-static-fallback")) fail("samples raw HTML has no textual fallback");
if (!samplesHtml.includes("data-static-seo")) fail("static schema handoff marker is missing");
if (!samplesHtml.includes('rel="canonical"') || !samplesHtml.includes("data-static-seo")) {
  fail("raw canonical metadata is missing its client handoff marker");
}
if ((samplesHtml.match(/\"@type\":\"VideoObject\"/g) || []).length !== 20) {
  fail("samples raw HTML must expose exactly 20 VideoObject records");
}
if ((sitemap.match(/<video:video>/g) || []).length !== 20) fail("video sitemap must contain 20 videos");
if ((sitemap.match(/<video:content_loc>/g) || []).length !== 20) fail("every sitemap video needs a content URL");
if (!sitemap.includes('xmlns:video="http://www.google.com/schemas/sitemap-video/1.1"')) {
  fail("video sitemap namespace is missing");
}
if (!sitemap.includes("<lastmod>2026-08-16</lastmod>")) fail("significant page update date is missing");
if (/FAQPage|HowTo|SpeakableSpecification/.test(homeHtml)) {
  fail("home contains deprecated or inapplicable rich-result markup");
}
if ((robots.match(/^User-agent:/gm) || []).length !== 1) {
  fail("crawler-specific groups can override the shared private-path exclusions");
}
if (!robots.includes("Disallow: /api/") || !robots.includes("Disallow: /admin/")) {
  fail("private/API crawl exclusions are missing");
}
if (/ocr-showcase-20260815|website-samples-20260815/.test(feed)) {
  fail("media-only prereleases leaked into the public update feed");
}
for (const prereleaseRoute of ["release-ocr-showcase-20260815", "release-website-samples-20260815"]) {
  if (fs.existsSync(path.join(distDir, "notice", prereleaseRoute))) {
    fail(`media-only prerelease generated a crawlable notice page: ${prereleaseRoute}`);
  }
}

console.log("SEO output verified: crawlable text, 20 VideoObjects, video sitemap, accurate crawler policy");
