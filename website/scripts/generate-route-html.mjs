import fs from "node:fs";
import path from "node:path";

import { SAMPLE_MEDIA } from "./sample-media.mjs";

const SITE_URL = "https://shoppingshorts.store";
const OG_IMAGE = `${SITE_URL}/og.jpg`;
const RELEASES_API = "https://api.github.com/repos/Kimchanghee/NewshoppingShorts/releases?per_page=20";
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || process.env.GH_TOKEN || "";
const ROBOTS = "index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1";
const excludedReleasePaths = [];
const KEYWORDS = [
  "SSMaker",
  "쇼핑 숏폼",
  "쇼핑 숏폼 자동화",
  "AI 영상 편집",
  "유튜브 쇼츠 자동 업로드",
  "쿠팡 파트너스 단축 링크",
  "링크트리 자동 등록",
  "중국 쇼핑 영상 변환",
  "중국어 자막 블러",
  "구매대행 마케팅",
].join(", ");

const staticRoutes = [
  {
    path: "/samples",
    title: "영상 샘플 10개 Before / After | SSMaker",
    description: "SSMaker 실제 프로그램으로 처리한 원본 10개와 제작본 10개를 나란히 재생하고 비교하는 샘플 페이지입니다.",
    type: "website",
    h1: "SSMaker Before / After 영상 샘플 10개",
    paragraphs: [
      "중국어 자막 위치와 노출 시간을 감지해 블러한 OCR 샘플 5건과 쿠팡 상품 소스 매칭, 세로 편집, 한국어 음성·자막까지 완료한 풀자동 제작 샘플 5건을 공개합니다.",
      "각 샘플은 원본 Before 영상과 SSMaker 제작 After 영상을 함께 제공하며 총 20개의 실제 MP4 영상을 직접 재생할 수 있습니다.",
    ],
    links: SAMPLE_MEDIA.map((sample) => ({
      href: `/samples/index.html#sample-${sample.id}`,
      title: `${sample.title} Before / After`,
      summary: `${sample.categoryLabel}: ${sample.description}`,
    })),
  },
  {
    path: "/notice",
    title: "공지사항 | SSMaker",
    description: "SSMaker 업데이트, 초기 세팅 매뉴얼, 쿠팡 파트너스, Linktree, YouTube OAuth 설정 가이드를 확인하세요.",
    type: "website",
    h1: "SSMaker 공지사항",
    paragraphs: [
      "SSMaker 공지사항은 업데이트 안내와 초기 세팅 매뉴얼을 모아둔 공식 안내 페이지입니다.",
      "쿠팡 파트너스 채널 등록, Linktree 가입과 링크 세팅, 쿠팡 상품 링크 가져오기, YouTube OAuth 연결, 업로드 후 검수 방법을 개별 게시물로 제공합니다.",
    ],
    links: [
      {
        href: "/notice/spring-2026-new-subscriber-extra-month/index.html",
        title: "신규 구독 1개월 추가 제공 이벤트",
        summary:
          "2026년 4월 30일부터 2026년 5월 14일까지 신규 가입 후 구독 확정 시 1개월을 자동 추가하고, 2026년 5월 15일부터는 마감으로 표시되는 2주 한정 이벤트입니다.",
      },
      {
        href: "/notice/coupang-partners-channel-setup/index.html",
        title: "쿠팡 파트너스 초기 채널 등록 매뉴얼",
        summary: "쿠팡 파트너스에 YouTube 채널 또는 Linktree 공개 프로필을 등록하고 승인 증빙 캡쳐를 준비하는 방법입니다.",
      },
      {
        href: "/notice/linktree-signup-link-setup/index.html",
        title: "Linktree 처음 가입 및 상품 링크 세팅 매뉴얼",
        summary: "Linktree 가입, 관리자 Links 화면, 상품 링크 추가, 공개 프로필 상품 버튼 확인 방법입니다.",
      },
      {
        href: "/notice/coupang-partners-product-link/index.html",
        title: "쿠팡 파트너스 상품 링크 가져오기 매뉴얼",
        summary: "쿠팡 파트너스에서 link.coupang.com/a/... 단축 링크를 만들고 SSMaker 풀자동 입력에 사용하는 방법입니다.",
      },
      {
        href: "/notice/youtube-oauth-client-guide/index.html",
        title: "YouTube 채널 연결용 Google Cloud OAuth 설정 가이드",
        summary: "SSMaker YouTube Shorts 자동 업로드를 위한 Google Cloud YouTube Data API v3와 데스크톱 앱 OAuth JSON 설정 방법입니다.",
      },
      {
        href: "/notice/youtube-google-cloud-oauth-screenshots/index.html",
        title: "Google Cloud 실제 화면 캡쳐로 보는 YouTube OAuth 설정",
        summary: "Google Cloud Console 실제 화면 기준으로 YouTube Data API v3와 데스크톱 OAuth 클라이언트 생성 단계를 확인합니다.",
      },
      {
        href: "/notice/youtube-linktree-upload-check/index.html",
        title: "업로드 후 YouTube·댓글·Linktree 검수 매뉴얼",
        summary: "YouTube Shorts 업로드 후 상품명, 댓글, 구매 링크, Linktree 번호 링크가 제대로 반영됐는지 검수하는 방법입니다.",
      },
    ],
  },
  {
    path: "/contact",
    title: "문의하기 | SSMaker",
    description: "SSMaker 문의, 버그 리포트, 기능 제안, 세팅 지원 요청은 문의 페이지에서 확인하세요.",
    type: "website",
    h1: "SSMaker 문의하기",
    paragraphs: [
      "SSMaker 사용 중 설치, 로그인, API 설정, YouTube 업로드, Linktree 세팅 문제가 있으면 문의 페이지에서 지원 채널을 확인할 수 있습니다.",
    ],
  },
  {
    path: "/notice/spring-2026-new-subscriber-extra-month",
    title: "신규 구독 1개월 추가 제공 이벤트 | SSMaker",
    description: "2026년 4월 30일부터 2026년 5월 14일까지 신규 가입 후 구독 확정 시 1개월을 추가 제공하는 SSMaker 2주 한정 이벤트입니다.",
    type: "article",
    h1: "신규 구독 1개월 추가 제공 이벤트",
    paragraphs: [
      "2026년 4월 30일 00:00 KST부터 2026년 5월 14일 23:59 KST까지 신규 가입 후 구독이 확정된 계정에는 구독 기간 1개월이 자동으로 추가됩니다.",
      "2026년 5월 15일 00:00 KST부터는 공지 상태가 마감으로 표시되고 추가 1개월 혜택도 더 이상 적용되지 않습니다.",
    ],
  },
  {
    path: "/notice/coupang-partners-channel-setup",
    title: "쿠팡 파트너스 초기 채널 등록 매뉴얼 | SSMaker",
    description: "쿠팡 파트너스에 YouTube 채널 또는 Linktree 공개 프로필을 등록하고 승인 증빙 캡쳐를 준비하는 방법입니다.",
    type: "article",
    h1: "쿠팡 파트너스 초기 채널 등록 매뉴얼",
    paragraphs: [
      "쿠팡 파트너스에 유튜브 채널 또는 Linktree 공개 프로필을 등록할 때는 웹사이트 목록 입력칸, 등록된 채널 행, 증빙 안내 문구가 함께 보이게 캡쳐합니다.",
      "계정명, 채널명, 핸들 등 식별 정보는 개인정보 가림 처리한 뒤 제출용 캡쳐로 사용합니다.",
    ],
  },
  {
    path: "/notice/linktree-signup-link-setup",
    title: "Linktree 처음 가입 및 상품 링크 세팅 매뉴얼 | SSMaker",
    description: "Linktree 가입, 관리자 Links 화면, 상품 링크 추가, 공개 프로필 상품 버튼 확인 방법입니다.",
    type: "article",
    h1: "Linktree 처음 가입 및 상품 링크 세팅 매뉴얼",
    paragraphs: [
      "일반 사용자는 Linktree API Key가 필요하지 않습니다. Linktree 관리자에서 직접 링크를 추가하거나 공개 프로필 주소를 저장하면 됩니다.",
      "SSMaker의 완전 자동 발행은 Linktree에 직접 쓰는 일반 API가 아니라 Make, Zapier, n8n, Cloudflare Worker 같은 Webhook 중계 주소로 상품 링크 데이터를 보내는 방식입니다.",
    ],
  },
  {
    path: "/notice/coupang-partners-product-link",
    title: "쿠팡 파트너스 상품 링크 가져오기 매뉴얼 | SSMaker",
    description: "쿠팡 파트너스에서 link.coupang.com/a/... 단축 링크를 만들고 SSMaker 풀자동 입력에 사용하는 방법입니다.",
    type: "article",
    h1: "쿠팡 파트너스 상품 링크 가져오기 매뉴얼",
    paragraphs: [
      "이미 쿠팡 파트너스 단축 링크가 있다면 쿠팡 API Key는 필요하지 않습니다.",
      "쿠팡 API Key는 원본 coupang.com 상품 URL을 프로그램이 자동으로 쿠팡 파트너스 딥링크로 변환하게 하고 싶을 때만 선택적으로 사용합니다.",
    ],
  },
  {
    path: "/notice/youtube-oauth-client-guide",
    title: "YouTube 채널 연결용 Google Cloud OAuth 설정 가이드 | SSMaker",
    description: "SSMaker YouTube Shorts 자동 업로드를 위한 Google Cloud YouTube Data API v3와 데스크톱 앱 OAuth JSON 설정 방법입니다.",
    type: "article",
    h1: "YouTube 채널 연결용 Google Cloud OAuth 설정 가이드",
    paragraphs: [
      "YouTube 업로드에는 API Key만으로는 부족합니다. 사용자의 YouTube 채널 권한을 승인하는 데스크톱 앱 OAuth 클라이언트 JSON이 필요합니다.",
      "Google Cloud 프로젝트에서 YouTube Data API v3를 사용 설정하고 OAuth 동의 화면과 데스크톱 앱 클라이언트를 준비합니다.",
    ],
  },
  {
    path: "/notice/youtube-google-cloud-oauth-screenshots",
    title: "Google Cloud 실제 화면 캡쳐로 보는 YouTube OAuth 설정 | SSMaker",
    description: "Google Cloud Console 실제 화면 기준으로 YouTube Data API v3, Google 인증 플랫폼, 데스크톱 OAuth 클라이언트 생성 단계를 확인합니다.",
    type: "article",
    h1: "Google Cloud 실제 화면 캡쳐로 보는 YouTube OAuth 설정",
    paragraphs: [
      "Chrome에서 실제 Google Cloud Console을 열어 확인한 YouTube OAuth 설정 화면입니다.",
      "계정, 프로젝트, 이메일, 클라이언트 식별 정보는 개인정보 가림 처리했고 입력칸과 눌러야 할 버튼은 노란 박스와 라벨로 표시했습니다.",
    ],
  },
  {
    path: "/notice/youtube-linktree-upload-check",
    title: "업로드 후 YouTube·댓글·Linktree 검수 매뉴얼 | SSMaker",
    description: "YouTube Shorts 업로드 후 상품명, 댓글, 구매 링크, Linktree 번호 링크가 제대로 반영됐는지 검수하는 방법입니다.",
    type: "article",
    h1: "업로드 후 YouTube·댓글·Linktree 검수 매뉴얼",
    paragraphs: [
      "업로드 후 YouTube Shorts 탭에서 새 영상 노출, 제목, 상품명, 댓글의 상품 설명과 Linktree 링크를 확인합니다.",
      "Linktree 관리자 화면에서는 상품 링크 제목 앞에 [000] 형식 번호가 붙고 링크 토글이 켜져 있는지 확인합니다.",
    ],
  },
  {
    path: "/notice/ssmaker-launch",
    title: "SSMaker 정식 출시 안내 | SSMaker",
    description: "중국 쇼핑 숏폼 영상을 한국어 쇼핑 콘텐츠로 자동 변환하는 SSMaker 정식 출시 안내입니다.",
    type: "article",
    h1: "SSMaker 정식 출시 안내",
    paragraphs: [
      "SSMaker는 중국 쇼핑 숏폼 영상을 한국어 쇼핑 숏폼 콘텐츠로 자동 변환하는 데스크톱 프로그램입니다.",
    ],
  },
  {
    path: "/notice/free-voucher",
    title: "무료 이용권 안내 | SSMaker",
    description: "SSMaker 무료 체험 이용권과 기본 무료 사용 안내입니다.",
    type: "article",
    h1: "무료 이용권 안내",
    paragraphs: ["SSMaker는 설치 후 로그인한 사용자에게 무료 체험 기회를 제공해 주요 기능을 먼저 확인할 수 있게 합니다."],
  },
  {
    path: "/notice/gemini-api-guide",
    title: "구글 제미나이 API 키 발급 방법 | SSMaker",
    description: "SSMaker AI 스크립트 생성에 사용할 Google Gemini API 키 발급과 설정 방법입니다.",
    type: "article",
    h1: "구글 제미나이 API 키 발급 방법",
    paragraphs: [
      "Google AI Studio에서 Gemini API 키를 만들고 SSMaker 설정 화면에 입력하면 AI 스크립트 생성 기능을 사용할 수 있습니다.",
    ],
  },
];

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
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

function summarize(value, maxLength = 180) {
  const plain = stripMarkdown(value || "SSMaker 릴리즈 업데이트 안내");
  if (plain.length <= maxLength) return plain;
  return `${plain.slice(0, maxLength - 1)}…`;
}

async function fetchReleaseRoutes() {
  try {
    const headers = {
      Accept: "application/vnd.github+json",
      "User-Agent": "ssmaker-static-route-generator",
    };
    if (GITHUB_TOKEN) {
      headers.Authorization = `Bearer ${GITHUB_TOKEN}`;
    }

    const res = await fetch(RELEASES_API, {
      headers,
    });

    if (!res.ok) {
      console.warn(`release route fetch failed: ${res.status}`);
      return [];
    }

    const releases = await res.json();
    if (!Array.isArray(releases)) return [];

    return releases
      .filter((release) => {
        if (typeof release?.tag_name !== "string") return false;
        if (release.draft || release.prerelease) {
          excludedReleasePaths.push(`/notice/release-${encodeURIComponent(release.tag_name)}`);
          return false;
        }
        return typeof release.published_at === "string";
      })
      .map((release) => {
        const tagName = release.tag_name;
        const title = release.name || `${tagName} 업데이트 안내`;
        const description = summarize(release.body);
        return {
          path: `/notice/release-${encodeURIComponent(tagName)}`,
          title: `${title} | SSMaker`,
          description,
          type: "article",
          h1: title,
          datePublished: release.published_at,
          dateModified: release.published_at,
          paragraphs: [
            description,
            "SSMaker 릴리즈 공지는 최신 설치 파일, 자동화 개선 사항, YouTube Shorts 업로드, Linktree, 쿠팡 파트너스 관련 변경 사항을 안내합니다.",
          ],
        };
      });
  } catch (error) {
    console.warn("release route fetch failed:", error instanceof Error ? error.message : error);
    return [];
  }
}

function render(route) {
  const canonicalPath = route.path === "/" ? "/" : `${route.path.replace(/\/+$/, "")}/index.html`;
  const canonical = `${SITE_URL}${canonicalPath}`;
  const schemaType = route.type === "article" ? "Article" : route.path === "/contact" ? "ContactPage" : "WebPage";
  const pageSchema = {
    "@type": schemaType,
    "@id": canonical,
    name: route.h1,
    ...(route.type === "article" && { headline: route.h1 }),
    description: route.description,
    url: canonical,
    inLanguage: "ko-KR",
    image: OG_IMAGE,
    ...(route.datePublished && { datePublished: route.datePublished }),
    ...(route.dateModified && { dateModified: route.dateModified }),
    publisher: {
      "@type": "Organization",
      "@id": `${SITE_URL}#organization`,
      name: "SSMaker",
      url: SITE_URL,
      logo: OG_IMAGE,
    },
  };
  const videoSchemas =
    route.path === "/samples"
      ? SAMPLE_MEDIA.flatMap((sample) =>
          ["before", "after"].map((kind) => {
            const isBefore = kind === "before";
            const label = isBefore ? "Before 원본" : "After SSMaker 제작본";
            const watchUrl = `${canonical}#sample-${sample.id}`;
            return {
              "@type": "VideoObject",
              "@id": `${watchUrl}-${kind}`,
              name: `${sample.title} ${label}`,
              description: `${sample.description} ${label} 영상입니다.`,
              thumbnailUrl: isBefore ? sample.beforePoster : sample.afterPoster,
              uploadDate: sample.uploadDate,
              contentUrl: isBefore ? sample.beforeVideo : sample.afterVideo,
              duration: isBefore ? sample.beforeDuration : sample.afterDuration,
              url: watchUrl,
              isPartOf: { "@id": canonical },
              inLanguage: "ko-KR",
              encodingFormat: "video/mp4",
              isFamilyFriendly: true,
              publisher: { "@id": `${SITE_URL}#organization` },
            };
          }),
        )
      : [];
  const schema = {
    "@context": "https://schema.org",
    "@graph": [pageSchema, ...videoSchemas],
  };
  const fallbackLinks = Array.isArray(route.links)
    ? `
        <ul>
        ${route.links
          .map(
            (item) => `<li>
          <a href="${escapeHtml(item.href)}">${escapeHtml(item.title)}</a>
          <p>${escapeHtml(item.summary)}</p>
        </li>`,
          )
          .join("\n        ")}
      </ul>`
    : "";

  return `<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${escapeHtml(route.title)}</title>
    <meta name="description" content="${escapeHtml(route.description)}" data-static-seo />
    <meta name="keywords" content="${escapeHtml(KEYWORDS)}" data-static-seo />
    <meta name="robots" content="${ROBOTS}" data-static-seo />
    <meta name="googlebot" content="${ROBOTS}" data-static-seo />
    <meta name="author" content="SSMaker Team" data-static-seo />
    <meta name="language" content="ko-KR" data-static-seo />
    <meta name="subject" content="AI 쇼핑 숏폼 자동 제작, 쿠팡 파트너스, YouTube Shorts, Linktree 자동화" data-static-seo />
    <link rel="canonical" href="${canonical}" data-static-seo />
    <link rel="alternate" hreflang="ko-KR" href="${canonical}" data-static-seo />
    <link rel="alternate" hreflang="x-default" href="${canonical}" data-static-seo />
    <link rel="alternate" type="text/plain" href="/llms.txt" title="SSMaker LLM summary" data-static-seo />
    <link rel="alternate" type="text/plain" href="/llms-full.txt" title="SSMaker full LLM context" data-static-seo />
    <link rel="alternate" type="application/rss+xml" href="/feed.xml" title="SSMaker RSS feed" data-static-seo />
    <link rel="alternate" type="application/atom+xml" href="/atom.xml" title="SSMaker Atom feed" data-static-seo />
    <link rel="alternate" type="application/feed+json" href="/feed.json" title="SSMaker JSON feed" data-static-seo />
    <meta property="og:type" content="${route.type}" data-static-seo />
    <meta property="og:url" content="${canonical}" data-static-seo />
    <meta property="og:title" content="${escapeHtml(route.title)}" data-static-seo />
    <meta property="og:description" content="${escapeHtml(route.description)}" data-static-seo />
    <meta property="og:image" content="${OG_IMAGE}" data-static-seo />
    <meta property="og:image:alt" content="${escapeHtml(route.h1)}" data-static-seo />
    <meta property="og:locale" content="ko_KR" data-static-seo />
    <meta name="twitter:card" content="summary_large_image" data-static-seo />
    <meta name="twitter:title" content="${escapeHtml(route.title)}" data-static-seo />
    <meta name="twitter:description" content="${escapeHtml(route.description)}" data-static-seo />
    <meta name="twitter:image" content="${OG_IMAGE}" data-static-seo />
    <script type="application/ld+json" data-static-seo>${JSON.stringify(schema)}</script>
  </head>
  <body>
    <div id="root">
      <main data-static-fallback>
        <h1>${escapeHtml(route.h1)}</h1>
        ${route.paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("\n        ")}${fallbackLinks}
        <p><a href="/">SSMaker 홈으로 이동</a></p>
      </main>
    </div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
`;
}

const releaseRoutes = await fetchReleaseRoutes();
const routes = [...staticRoutes, ...releaseRoutes];

for (const routePath of excludedReleasePaths) {
  const dir = path.join(process.cwd(), routePath.replace(/^\/+/, ""));
  if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true });
}

for (const route of routes) {
  const dir = path.join(process.cwd(), route.path.replace(/^\/+/, ""));
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "index.html"), render(route), "utf8");
}

console.log(`wrote ${routes.length} static route html files`);
