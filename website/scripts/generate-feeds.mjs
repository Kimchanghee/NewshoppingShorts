import fs from "node:fs";
import path from "node:path";

const SITE_URL = "https://shoppingshorts.store";
const SITE_NAME = "SSMaker";
const FEED_TITLE = "SSMaker 공지사항과 업데이트";
const FEED_DESCRIPTION =
  "SSMaker 업데이트, 초기 세팅 매뉴얼, 쿠팡 파트너스, Linktree, YouTube OAuth, Google Cloud 설정 가이드 모음";
const RELEASES_API = "https://api.github.com/repos/Kimchanghee/NewshoppingShorts/releases?per_page=20";
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || process.env.GH_TOKEN || "";
const FEED_FALLBACK_UPDATED = "2026-04-30T00:00:00.000Z";

const staticItems = [
  {
    title: "신규 구독 1개월 추가 제공 이벤트",
    url: `${SITE_URL}/notice/spring-2026-new-subscriber-extra-month/index.html`,
    summary: "2026년 4월 30일부터 2026년 5월 14일까지 신규 가입 후 구독 확정 시 1개월을 추가 제공하는 SSMaker 2주 한정 이벤트입니다.",
    date: "2026-04-30T00:00:00.000Z",
  },
  {
    title: "쿠팡 파트너스 초기 채널 등록 매뉴얼",
    url: `${SITE_URL}/notice/coupang-partners-channel-setup/index.html`,
    summary: "쿠팡 파트너스에 YouTube 채널 또는 Linktree 공개 프로필을 등록하고 승인 증빙 캡쳐를 준비하는 방법입니다.",
    date: "2026-04-29T00:00:00.000Z",
  },
  {
    title: "Linktree 처음 가입 및 상품 링크 세팅 매뉴얼",
    url: `${SITE_URL}/notice/linktree-signup-link-setup/index.html`,
    summary: "Linktree 가입, 관리자 Links 화면, 상품 링크 추가, 공개 프로필 상품 버튼 확인 방법입니다.",
    date: "2026-04-29T00:00:00.000Z",
  },
  {
    title: "쿠팡 파트너스 상품 링크 가져오기 매뉴얼",
    url: `${SITE_URL}/notice/coupang-partners-product-link/index.html`,
    summary: "쿠팡 파트너스에서 link.coupang.com/a/... 단축 링크를 만들고 SSMaker 풀자동 입력에 사용하는 방법입니다.",
    date: "2026-04-29T00:00:00.000Z",
  },
  {
    title: "YouTube 채널 연결용 Google Cloud OAuth 설정 가이드",
    url: `${SITE_URL}/notice/youtube-oauth-client-guide/index.html`,
    summary: "SSMaker YouTube Shorts 자동 업로드를 위한 Google Cloud YouTube Data API v3와 데스크톱 앱 OAuth JSON 설정 방법입니다.",
    date: "2026-04-29T00:00:00.000Z",
  },
  {
    title: "Google Cloud 실제 화면 캡쳐로 보는 YouTube OAuth 설정",
    url: `${SITE_URL}/notice/youtube-google-cloud-oauth-screenshots/index.html`,
    summary: "Google Cloud Console 실제 화면 기준으로 YouTube Data API v3, Google 인증 플랫폼, 데스크톱 OAuth 클라이언트 생성 단계를 확인합니다.",
    date: "2026-04-29T00:00:00.000Z",
  },
  {
    title: "업로드 후 YouTube·댓글·Linktree 검수 매뉴얼",
    url: `${SITE_URL}/notice/youtube-linktree-upload-check/index.html`,
    summary: "YouTube Shorts 업로드 후 상품명, 댓글, 구매 링크, Linktree 번호 링크가 제대로 반영됐는지 검수하는 방법입니다.",
    date: "2026-04-29T00:00:00.000Z",
  },
  {
    title: "SSMaker 정식 출시 안내",
    url: `${SITE_URL}/notice/ssmaker-launch/index.html`,
    summary: "중국 쇼핑 숏폼 영상을 한국어 쇼핑 콘텐츠로 자동 변환하는 SSMaker 정식 출시 안내입니다.",
    date: "2026-04-29T00:00:00.000Z",
  },
  {
    title: "무료 이용권 안내",
    url: `${SITE_URL}/notice/free-voucher/index.html`,
    summary: "SSMaker 무료 체험 이용권과 기본 무료 사용 안내입니다.",
    date: "2026-04-29T00:00:00.000Z",
  },
  {
    title: "구글 제미나이 API 키 발급 방법",
    url: `${SITE_URL}/notice/gemini-api-guide/index.html`,
    summary: "SSMaker AI 스크립트 생성에 사용할 Google Gemini API 키 발급과 설정 방법입니다.",
    date: "2026-04-29T00:00:00.000Z",
  },
];

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function stripMarkdown(value) {
  return String(value)
    .replace(/```[\s\S]*?```/g, "")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[#>*_~|-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function summarize(value, maxLength = 220) {
  const plain = stripMarkdown(value);
  if (plain.length <= maxLength) return plain;
  return `${plain.slice(0, maxLength - 1)}…`;
}

async function fetchReleaseItems() {
  try {
    const headers = {
      Accept: "application/vnd.github+json",
      "User-Agent": "ssmaker-feed-generator",
    };
    if (GITHUB_TOKEN) {
      headers.Authorization = `Bearer ${GITHUB_TOKEN}`;
    }

    const res = await fetch(RELEASES_API, {
      headers,
    });

    if (!res.ok) {
      console.warn(`release feed fetch failed: ${res.status}`);
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
      .map((release) => {
        const title = release.name || `${release.tag_name} 업데이트`;
        const date = release.published_at;
        return {
          title,
          url: `${SITE_URL}/notice/release-${encodeURIComponent(release.tag_name)}/index.html`,
          summary: summarize(release.body || "SSMaker 릴리즈 업데이트 안내"),
          date,
        };
      });
  } catch (error) {
    console.warn("release feed fetch failed:", error instanceof Error ? error.message : error);
    return [];
  }
}

function sortItems(items) {
  return [...items].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
}

function renderRss(items, feedUpdated) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(FEED_TITLE)}</title>
    <link>${SITE_URL}/notice/index.html</link>
    <description>${escapeXml(FEED_DESCRIPTION)}</description>
    <language>ko-KR</language>
    <lastBuildDate>${new Date(feedUpdated).toUTCString()}</lastBuildDate>
    <atom:link href="${SITE_URL}/feed.xml" rel="self" type="application/rss+xml" />
${items
  .map(
    (item) => `    <item>
      <title>${escapeXml(item.title)}</title>
      <link>${item.url}</link>
      <guid isPermaLink="true">${item.url}</guid>
      <pubDate>${new Date(item.date).toUTCString()}</pubDate>
      <description>${escapeXml(item.summary)}</description>
    </item>`,
  )
  .join("\n")}
  </channel>
</rss>
`;
}

function renderAtom(items, feedUpdated) {
  return `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>${SITE_URL}/notice/index.html</id>
  <title>${escapeXml(FEED_TITLE)}</title>
  <subtitle>${escapeXml(FEED_DESCRIPTION)}</subtitle>
  <link href="${SITE_URL}/notice/index.html" />
  <link href="${SITE_URL}/atom.xml" rel="self" type="application/atom+xml" />
  <updated>${new Date(feedUpdated).toISOString()}</updated>
  <author>
    <name>${SITE_NAME}</name>
  </author>
${items
  .map(
    (item) => `  <entry>
    <id>${item.url}</id>
    <title>${escapeXml(item.title)}</title>
    <link href="${item.url}" />
    <updated>${new Date(item.date).toISOString()}</updated>
    <summary>${escapeXml(item.summary)}</summary>
  </entry>`,
  )
  .join("\n")}
</feed>
`;
}

function renderJsonFeed(items) {
  return `${JSON.stringify(
    {
      version: "https://jsonfeed.org/version/1.1",
      title: FEED_TITLE,
      home_page_url: `${SITE_URL}/`,
      feed_url: `${SITE_URL}/feed.json`,
      language: "ko-KR",
      description: FEED_DESCRIPTION,
      authors: [{ name: SITE_NAME }],
      items: items.map((item) => ({
        id: item.url,
        url: item.url,
        title: item.title,
        summary: item.summary,
        content_text: item.summary,
        date_published: new Date(item.date).toISOString(),
        date_modified: new Date(item.date).toISOString(),
      })),
    },
    null,
    2,
  )}\n`;
}

const releaseItems = await fetchReleaseItems();
const items = sortItems([...staticItems, ...releaseItems]);
const feedUpdated = items[0]?.date ?? FEED_FALLBACK_UPDATED;
const publicDir = path.join(process.cwd(), "public");

fs.writeFileSync(path.join(publicDir, "feed.xml"), renderRss(items, feedUpdated), "utf8");
fs.writeFileSync(path.join(publicDir, "atom.xml"), renderAtom(items, feedUpdated), "utf8");
fs.writeFileSync(path.join(publicDir, "feed.json"), renderJsonFeed(items), "utf8");

console.log(`wrote RSS/Atom/JSON feeds (${items.length} items)`);
