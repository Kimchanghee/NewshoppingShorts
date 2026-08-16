import fs from "node:fs";
import path from "node:path";

import { durationToSeconds, SAMPLE_MEDIA } from "./sample-media.mjs";

const SITE_URL = "https://shoppingshorts.store";
const RELEASES_API = "https://api.github.com/repos/Kimchanghee/NewshoppingShorts/releases?per_page=100";
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || process.env.GH_TOKEN || "";
const NOTICE_SLUGS = [
  "spring-2026-new-subscriber-extra-month",
  "coupang-partners-channel-setup",
  "linktree-signup-link-setup",
  "coupang-partners-product-link",
  "youtube-oauth-client-guide",
  "youtube-google-cloud-oauth-screenshots",
  "youtube-linktree-upload-check",
  "ssmaker-launch",
  "free-voucher",
  "gemini-api-guide",
];

const baseRoutes = [
  { loc: "/", lastmod: "2026-08-16" },
  { loc: "/notice/index.html", lastmod: "2026-08-15" },
  { loc: "/samples/index.html", lastmod: "2026-08-16", videos: SAMPLE_MEDIA },
  { loc: "/contact/index.html", lastmod: "2026-08-15" },
];

const noticeRoutes = NOTICE_SLUGS.map((slug) => ({
  loc: `/notice/${slug}/index.html`,
  lastmod: "2026-08-15",
}));

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

async function fetchReleaseRoutes() {
  try {
    const headers = {
      Accept: "application/vnd.github+json",
      "User-Agent": "ssmaker-sitemap-generator",
    };
    if (GITHUB_TOKEN) headers.Authorization = `Bearer ${GITHUB_TOKEN}`;

    const res = await fetch(RELEASES_API, { headers });
    if (!res.ok) {
      console.warn(`release fetch failed: ${res.status}`);
      return [];
    }

    const releases = await res.json();
    if (!Array.isArray(releases)) return [];

    return releases
      .filter(
        (release) =>
          typeof release?.tag_name === "string" &&
          !release.draft &&
          !release.prerelease &&
          typeof release.published_at === "string",
      )
      .slice(0, 20)
      .map((release) => ({
        loc: `/notice/release-${encodeURIComponent(release.tag_name)}/index.html`,
        lastmod: release.published_at.slice(0, 10),
      }));
  } catch (error) {
    console.warn("release fetch failed:", error instanceof Error ? error.message : error);
    return [];
  }
}

function renderVideo(video, kind) {
  const isBefore = kind === "before";
  const label = isBefore ? "Before 원본" : "After SSMaker 제작본";
  return `    <video:video>
      <video:thumbnail_loc>${escapeXml(isBefore ? video.beforePoster : video.afterPoster)}</video:thumbnail_loc>
      <video:title>${escapeXml(`${video.title} ${label}`)}</video:title>
      <video:description>${escapeXml(`${video.description} ${label} 영상입니다.`)}</video:description>
      <video:content_loc>${escapeXml(isBefore ? video.beforeVideo : video.afterVideo)}</video:content_loc>
      <video:duration>${durationToSeconds(isBefore ? video.beforeDuration : video.afterDuration)}</video:duration>
      <video:publication_date>${video.uploadDate}</video:publication_date>
      <video:family_friendly>yes</video:family_friendly>
    </video:video>`;
}

function renderRoute(route) {
  const videos = route.videos?.flatMap((video) => [renderVideo(video, "before"), renderVideo(video, "after")]) ?? [];
  return `  <url>
    <loc>${escapeXml(`${SITE_URL}${route.loc}`)}</loc>
    <lastmod>${route.lastmod}</lastmod>${videos.length ? `\n${videos.join("\n")}` : ""}
  </url>`;
}

const releaseRoutes = await fetchReleaseRoutes();
const routes = [...baseRoutes, ...noticeRoutes, ...releaseRoutes];
const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">
${routes.map(renderRoute).join("\n")}
</urlset>
`;

const outPath = path.join(process.cwd(), "public", "sitemap.xml");
fs.writeFileSync(outPath, xml, "utf8");
console.log(`wrote ${outPath} (${routes.length} urls, ${SAMPLE_MEDIA.length * 2} videos)`);
