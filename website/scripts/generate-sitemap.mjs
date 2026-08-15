import fs from "node:fs";
import path from "node:path";

// Canonical source: src/constants/site.ts — keep in sync
const SITE_URL = "https://shoppingshorts.store";
const today = (() => {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
})();
const RELEASES_API = "https://api.github.com/repos/Kimchanghee/NewshoppingShorts/releases?per_page=20";
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
  { loc: "/", changefreq: "daily", priority: "1.0" },
  { loc: "/notice/index.html", changefreq: "weekly", priority: "0.8" },
  { loc: "/samples/index.html", changefreq: "weekly", priority: "0.9" },
  { loc: "/contact/index.html", changefreq: "monthly", priority: "0.6" },
];

const noticeRoutes = NOTICE_SLUGS.map((slug) => ({
  loc: `/notice/${slug}/index.html`,
  changefreq: "weekly",
  priority: "0.75",
  lastmod: today,
}));

async function fetchReleaseRoutes() {
  try {
    const headers = {
      Accept: "application/vnd.github+json",
      "User-Agent": "ssmaker-sitemap-generator",
    };
    if (GITHUB_TOKEN) {
      headers.Authorization = `Bearer ${GITHUB_TOKEN}`;
    }

    const res = await fetch(RELEASES_API, {
      headers,
    });

    if (!res.ok) {
      console.warn(`release fetch failed: ${res.status}`);
      return [];
    }

    const releases = await res.json();
    if (!Array.isArray(releases)) return [];

    return releases
      .filter((release) => typeof release?.tag_name === "string")
      .map((release) => ({
        loc: `/notice/release-${encodeURIComponent(release.tag_name)}/index.html`,
        changefreq: "weekly",
        priority: "0.72",
        lastmod: typeof release.published_at === "string" ? release.published_at.slice(0, 10) : today,
      }));
  } catch (error) {
    console.warn("release fetch failed:", error instanceof Error ? error.message : error);
    return [];
  }
}

const releaseRoutes = await fetchReleaseRoutes();
const routes = [
  ...baseRoutes.map((route) => ({ ...route, lastmod: today })),
  ...noticeRoutes,
  ...releaseRoutes,
];

const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${routes
  .map(
    (r) => `  <url>
    <loc>${SITE_URL}${r.loc}</loc>
    <lastmod>${r.lastmod ?? today}</lastmod>
    <changefreq>${r.changefreq}</changefreq>
    <priority>${r.priority}</priority>
  </url>`,
  )
  .join("\n")}
</urlset>
`;

const outPath = path.join(process.cwd(), "public", "sitemap.xml");
fs.writeFileSync(outPath, xml, "utf8");
console.log(`wrote ${outPath} (${routes.length} urls)`);
