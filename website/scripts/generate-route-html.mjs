import fs from "node:fs";
import path from "node:path";

const SITE_URL = "https://shoppingshorts.store";
const OG_IMAGE = `${SITE_URL}/og.jpg`;
const RELEASES_API = "https://api.github.com/repos/Kimchanghee/NewshoppingShorts/releases?per_page=20";
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || process.env.GH_TOKEN || "";
const ROBOTS = "index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1";
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
    path: "/notice/release-source-v1.5.72",
    title: "SSMaker v1.5.72 반응형 UI 프리뷰 | SSMaker",
    description:
      "SSMaker v1.5.72는 다양한 모니터 크기와 Windows 화면 배율에서 텍스트와 버튼이 가려지지 않도록 데스크톱 앱과 공식 웹사이트의 반응형 레이아웃을 전면 개선한 소스 프리릴리스입니다.",
    type: "article",
    h1: "SSMaker v1.5.72 반응형 UI 프리뷰",
    paragraphs: [
      "공개일: 2026년 8월 21일. 앱 상단, 로그인, 시작 화면과 공식 웹사이트 다운로드 영역에 버전과 업데이트 날짜를 함께 표시합니다.",
      "작은 모니터, 고해상도 화면, Windows 배율 확대, 모바일과 브라우저 확대에서도 주요 텍스트와 버튼에 도달할 수 있도록 스크롤, 줄바꿈, 패널 전환과 대화상자 크기 제한을 정비했습니다.",
      "일반 Windows 설치 파일은 코드서명 안정판 v1.5.70을 계속 제공하며, v1.5.72 소스는 GitHub 릴리스에서 내려받을 수 있습니다.",
    ],
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
    path: "/privacy",
    title: "개인정보처리방침 | SSMaker",
    description: "SSMaker 데스크톱 앱과 인증·구독 서비스의 개인정보 처리 기준, 보유 및 삭제, 이용자 권리를 안내합니다.",
    type: "website",
    h1: "SSMaker 개인정보처리방침",
    paragraphs: [
      "시행일: 2026년 8월 6일",
      "YMcompany는 회원가입 및 인증을 위해 이름, 아이디, 비밀번호의 단방향 해시, 연락처, 선택 입력 이메일, 가입·접속 IP, 로그인 및 앱 버전 기록을 처리합니다.",
      "구독 상태와 결제 식별자 및 처리 결과를 보관하며 카드 원문 전체를 직접 저장하지 않습니다. 대부분의 제작 데이터와 외부 서비스 인증 정보는 이용자의 PC에 저장됩니다.",
      "계정 생성과 본인 인증, 중복 로그인 방지, 무료 체험·구독 및 작업량 관리, 결제 처리, 고객 지원, 오류·보안 대응, 앱 업데이트 제공을 위해 정보를 이용합니다.",
      "이용자가 기능을 실행할 때 YouTube, Instagram, TikTok, Threads, Linktree, 쿠팡 파트너스, 생성형 AI 및 음성·영상 처리 서비스로 선택한 콘텐츠나 인증 정보가 전송될 수 있습니다.",
      "개인정보는 서비스 제공과 법적 의무 이행에 필요한 기간 동안만 보유하고 목적이 끝나면 삭제하거나 익명화합니다. 계정 정보의 열람·정정·삭제는 support@ssmaker.co.kr로 요청할 수 있습니다.",
      "전송 구간 암호화, 비밀번호 해시, 민감한 결제 키 암호화, 접근 권한 제한, 요청 속도 제한과 보안 로그 최소화를 적용합니다.",
      "SSMaker는 아동을 대상으로 설계된 서비스가 아니며 법정대리인의 동의 없이 아동의 개인정보를 의도적으로 수집하지 않습니다.",
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
      .filter((release) => typeof release?.tag_name === "string")
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
  const schema = {
    "@context": "https://schema.org",
    "@type": schemaType,
    name: route.h1,
    headline: route.h1,
    description: route.description,
    url: canonical,
    inLanguage: "ko-KR",
    image: OG_IMAGE,
    publisher: {
      "@type": "Organization",
      name: "SSMaker",
      url: SITE_URL,
    },
  };
  const noscriptLinks = Array.isArray(route.links)
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
    <meta name="description" content="${escapeHtml(route.description)}" />
    <meta name="keywords" content="${escapeHtml(KEYWORDS)}" />
    <meta name="robots" content="${ROBOTS}" />
    <meta name="googlebot" content="${ROBOTS}" />
    <meta name="author" content="SSMaker Team" />
    <meta name="language" content="ko-KR" />
    <meta name="subject" content="AI 쇼핑 숏폼 자동 제작, 쿠팡 파트너스, YouTube Shorts, Linktree 자동화" />
    <link rel="canonical" href="${canonical}" />
    <link rel="alternate" hrefLang="ko-KR" href="${canonical}" />
    <link rel="alternate" hrefLang="x-default" href="${canonical}" />
    <link rel="alternate" type="text/plain" href="/llms.txt" title="SSMaker LLM summary" />
    <link rel="alternate" type="text/plain" href="/llms-full.txt" title="SSMaker full LLM context" />
    <link rel="alternate" type="application/rss+xml" href="/feed.xml" title="SSMaker RSS feed" />
    <link rel="alternate" type="application/atom+xml" href="/atom.xml" title="SSMaker Atom feed" />
    <link rel="alternate" type="application/feed+json" href="/feed.json" title="SSMaker JSON feed" />
    <meta property="og:type" content="${route.type}" />
    <meta property="og:url" content="${canonical}" />
    <meta property="og:title" content="${escapeHtml(route.title)}" />
    <meta property="og:description" content="${escapeHtml(route.description)}" />
    <meta property="og:image" content="${OG_IMAGE}" />
    <meta property="og:image:alt" content="${escapeHtml(route.h1)}" />
    <meta property="og:locale" content="ko_KR" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="${escapeHtml(route.title)}" />
    <meta name="twitter:description" content="${escapeHtml(route.description)}" />
    <meta name="twitter:image" content="${OG_IMAGE}" />
    <script type="application/ld+json">${JSON.stringify(schema)}</script>
  </head>
  <body>
    <div id="root"></div>
    <noscript>
      <main>
        <h1>${escapeHtml(route.h1)}</h1>
        ${route.paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("\n        ")}${noscriptLinks}
      </main>
    </noscript>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
`;
}

const releaseRoutes = await fetchReleaseRoutes();
const routes = [...staticRoutes, ...releaseRoutes];

for (const route of routes) {
  const dir = path.join(process.cwd(), route.path.replace(/^\/+/, ""));
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "index.html"), render(route), "utf8");
}

console.log(`wrote ${routes.length} static route html files`);
