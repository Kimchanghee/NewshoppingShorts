import Navigation from "@/components/Navigation";
import Footer from "@/components/Footer";
import { FadeIn } from "@/components/FadeIn";
import { ArrowLeft, Pin, ChevronRight, Package } from "lucide-react";
import { Link, useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Seo from "@/components/Seo";
import { Skeleton } from "@/components/ui/skeleton";
import { SITE_KEYWORDS } from "@/constants/site";
import {
  buildArticleSchema,
  buildBreadcrumbSchema,
  buildCollectionPageSchema,
  buildOrganizationSchema,
  buildWebPageSchema,
  parseKoreanDateToIso,
} from "@/lib/structuredData";
import {
  PROMOTION,
  PROMOTION_NOTICE_SLUG,
  getPromotionDescription,
  getPromotionStatus,
  getPromotionStatusLabel,
} from "@/constants/promotion";

/* ──────────────────────────── Types ──────────────────────────── */

interface NoticeImage {
  src: string;
  alt: string;
  caption?: string;
}

interface NoticeSection {
  heading: string;
  steps: string[];
  images?: NoticeImage[];
}

interface NoticeItem {
  id: number;
  title: string;
  date: string;
  pinned: boolean;
  content: string;
  slug: string;
  intro?: string;
  sections?: NoticeSection[];
}

interface GitHubRelease {
  id: number;
  tag_name: string;
  name: string;
  body: string;
  published_at: string;
  html_url: string;
}

/* ──────────────────────────── Static notices ──────────────────── */

const SCREENSHOT_BASE =
  "https://raw.githubusercontent.com/Kimchanghee/NewshoppingShorts/bcc609c55917b1c90777d49a1ef085d253787693/docs/website-manual-screenshots-v3";

const GOOGLE_CLOUD_OAUTH_SCREENSHOT_BASE = "/manual-screenshots/google-cloud-oauth";

const SETUP_MANUAL_SLUGS = [
  "coupang-partners-channel-setup",
  "linktree-signup-link-setup",
  "coupang-partners-product-link",
  "youtube-oauth-client-guide",
  "youtube-google-cloud-oauth-screenshots",
  "youtube-linktree-upload-check",
];

const NOTICE_LIST_PATH = "/notice/index.html";
const noticeDetailPath = (slug: string) => `/notice/${slug}/index.html`;
const releaseDetailPath = (tagName: string) => `/notice/release-${encodeURIComponent(tagName)}/index.html`;
const getNoticeStatusLabel = (notice: NoticeItem) =>
  notice.slug === PROMOTION_NOTICE_SLUG ? getPromotionStatusLabel(getPromotionStatus()) : null;

const notices: NoticeItem[] = [
  {
    id: 10,
    title: "신규 구독 1개월 추가 제공 이벤트",
    date: "2026년 4월 30일",
    pinned: true,
    slug: PROMOTION_NOTICE_SLUG,
    intro:
      "SSMaker 신규 가입자를 위한 2주 한정 이벤트입니다. 이벤트 상태는 기간에 따라 자동으로 진행중 또는 마감으로 표시됩니다.",
    sections: [
      {
        heading: "이벤트 기간과 자동 마감",
        steps: [
          "이벤트 기간은 2026년 4월 30일 00:00 KST부터 2026년 5월 14일 23:59 KST까지입니다.",
          "2026년 5월 15일 00:00 KST부터 공지 상태는 자동으로 ‘마감’으로 표시됩니다.",
          "마감 이후 결제 또는 승인된 구독에는 신규 구독 1개월 추가 혜택이 자동 적용되지 않습니다.",
        ],
      },
      {
        heading: "혜택과 적용 대상",
        steps: [
          "이벤트 기간 안에 신규 가입하고 같은 기간 안에 구독이 확정된 계정에 첫 구독 기간 1개월이 추가됩니다.",
          "결제 성공 웹훅 또는 관리자 구독 승인 시점에 서버가 가입일과 이벤트 기간을 확인한 뒤 구독 만료일에 30일을 자동으로 더합니다.",
          "기존 구독자, 관리자 계정, 이벤트 시작 전 가입 계정, 이벤트 종료 후 결제 확정 계정, 갱신 결제에는 중복 적용되지 않습니다.",
        ],
      },
      {
        heading: "확인 방법",
        steps: [
          "프로그램의 구독 관리 화면에서 구독 상태를 새로고침합니다.",
          "이벤트 적용 대상이면 서버에서 계산된 만료일이 기본 구독 기간보다 30일 길게 표시됩니다.",
          "이벤트 마감 후에는 프로그램과 공지사항 모두 혜택 종료 상태를 안내합니다.",
        ],
      },
    ],
    content:
      `${PROMOTION.periodLabel} 동안 신규 가입 후 구독이 확정된 계정에 구독 기간 1개월을 자동 추가하는 이벤트입니다.`,
  },
  {
    id: 5,
    title: "쿠팡 파트너스 초기 채널 등록 매뉴얼",
    date: "2026년 4월 29일",
    pinned: true,
    slug: "coupang-partners-channel-setup",
    intro:
      "쿠팡 파트너스에 유튜브 채널 또는 Linktree 공개 프로필을 등록할 때 확인해야 하는 화면입니다. 계정/채널 등 민감 정보는 개인정보 가림 처리했습니다.",
    sections: [
      {
        heading: "쿠팡 파트너스 초기 채널 등록",
        steps: [
          "partners.coupang.com에 로그인한 뒤 홈 또는 상품검색 화면이 정상으로 열리는지 확인합니다.",
          "상단 ‘내 정보’로 들어갈 때 인증 안내가 뜨면 인증을 진행하고 ‘인증 완료’를 누릅니다.",
          "‘내 정보 관리’의 ‘웹사이트 목록’ 입력칸에 유튜브 채널 또는 Linktree 공개 프로필 URL을 넣고 ‘추가하기’를 누릅니다.",
          "쿠파스 승인/증빙 제출용 캡쳐는 상단 ‘내 정보’ 메뉴, ‘웹사이트 목록’, 등록된 채널 행, 하단 증빙 안내 문구가 한 화면에 같이 보이게 찍습니다.",
          "채널 행만 너무 좁게 잘라내지 말고, 쿠팡 파트너스 화면이라는 맥락과 등록 상태가 함께 보이게 캡쳐합니다.",
        ],
        images: [
          {
            src: `${SCREENSHOT_BASE}/01-coupang-partners-home.png`,
            alt: "쿠팡 파트너스 홈과 상품검색 화면",
            caption: "1-1 캡쳐 장면: 쿠팡 파트너스 로그인 후 홈 또는 상품검색 화면이 보이는지 확인합니다.",
          },
          {
            src: `${SCREENSHOT_BASE}/02-coupang-auth-required.png`,
            alt: "쿠팡 파트너스 본인 인증 안내 화면",
            caption: "1-2 캡쳐 장면: ‘내 정보’ 진입 전 인증 안내가 뜨면 인증 절차를 완료합니다.",
          },
          {
            src: `${SCREENSHOT_BASE}/03-coupang-channel-registration.png`,
            alt: "쿠팡 파트너스 웹사이트 목록 등록 화면",
            caption: "1-3 캡쳐 장면: 웹사이트 목록 입력칸과 등록된 채널 행이 보이게 확인합니다.",
          },
          {
            src: `${SCREENSHOT_BASE}/09-coupang-proof-capture-guide.png`,
            alt: "쿠팡 파트너스 증빙 제출용 캡쳐 범위 예시",
            caption: "1-4 증빙 제출용 캡쳐 범위: 상단 메뉴, 웹사이트 목록, 등록된 채널 행, 하단 안내 문구가 함께 들어가야 합니다.",
          },
        ],
      },
    ],
    content:
      "쿠팡 파트너스 초기 채널 등록과 승인/증빙 제출용 캡쳐 범위를 실제 화면 기준으로 안내합니다.",
  },
  {
    id: 6,
    title: "Linktree 처음 가입 및 상품 링크 세팅 매뉴얼",
    date: "2026년 4월 29일",
    pinned: true,
    slug: "linktree-signup-link-setup",
    intro:
      "Linktree를 처음 쓰는 사용자가 가입부터 상품 버튼 확인까지 따라 할 수 있는 화면입니다. 계정 주소, QR 등 민감 정보는 개인정보 가림 처리했습니다.",
    sections: [
      {
        heading: "Linktree 처음 가입 및 링크 세팅",
        steps: [
          "linktr.ee/register에서 이메일 또는 Google/Apple로 가입을 시작합니다.",
          "관리자 ‘Links’ 화면에서 ‘Add’를 눌러 새 상품 링크를 추가합니다.",
          "제목에는 상품명을 넣고 URL에는 쿠팡 파트너스 단축 링크를 넣습니다. 토글은 켜진 상태여야 합니다.",
          "공개 프로필에서 방문자에게 상품 버튼이 실제로 보이는지 확인합니다.",
        ],
        images: [
          {
            src: `${SCREENSHOT_BASE}/05-linktree-signup.png`,
            alt: "Linktree 가입 시작 화면",
            caption: "2-1 캡쳐 장면: Linktree 가입 화면에서 계정 생성 방식을 선택합니다.",
          },
          {
            src: `${SCREENSHOT_BASE}/10-linktree-add-link-guide.png`,
            alt: "Linktree 링크 추가 버튼 위치",
            caption: "2-2 캡쳐 장면: 관리자 Links 화면에서 ‘Add’로 상품 링크를 추가합니다.",
          },
          {
            src: `${SCREENSHOT_BASE}/06-linktree-links-admin.png`,
            alt: "Linktree 상품 링크 관리자 화면",
            caption: "2-3 캡쳐 장면: 상품 제목, 쿠팡 단축 링크, 켜진 토글 상태를 확인합니다.",
          },
          {
            src: `${SCREENSHOT_BASE}/12-linktree-public-buttons-guide.png`,
            alt: "Linktree 공개 프로필 상품 버튼 확인 화면",
            caption: "2-4 캡쳐 장면: 공개 프로필에서 방문자가 누를 상품 버튼 영역을 확인합니다.",
          },
        ],
      },
      {
        heading: "Linktree API Key처럼 보이는 값은 언제 쓰나요?",
        steps: [
          "일반 사용자는 Linktree API Key가 필요하지 않습니다. Linktree 관리자에서 직접 링크를 추가하거나 공개 프로필 주소만 저장하면 됩니다.",
          "SSMaker의 자동 발행은 Linktree에 직접 쓰는 공식 일반 API가 아니라, Make/Zapier/n8n/Cloudflare Worker 같은 Webhook 중계 주소로 상품 링크 데이터를 보내는 방식입니다.",
          "Webhook 중계 서버가 인증 키를 요구할 때만 ‘Webhook 인증 키’를 입력합니다. 인증이 없는 개인 Webhook이면 비워도 됩니다.",
          "따라서 처음 세팅은 Linktree Profile URL 저장 → 수동 링크 확인 → 필요할 때만 Webhook 자동 발행 순서로 진행하면 됩니다.",
        ],
      },
    ],
    content:
      "Linktree 신규 가입, 링크 추가, 공개 상품 버튼 확인까지 필요한 화면을 실제 캡쳐 기준으로 안내합니다.",
  },
  {
    id: 7,
    title: "쿠팡 파트너스 상품 링크 가져오기 매뉴얼",
    date: "2026년 4월 29일",
    pinned: true,
    slug: "coupang-partners-product-link",
    intro:
      "SSMaker 풀자동 입력, YouTube 댓글, Linktree 상품 버튼에 사용할 쿠팡 파트너스 단축 링크 생성 방법입니다.",
    sections: [
      {
        heading: "쿠팡 파트너스 상품 링크 가져오기",
        steps: [
          "쿠팡 파트너스 상단 메뉴에서 ‘링크 생성’ → ‘간편 링크 만들기’로 이동합니다.",
          "쿠팡 상품 상세 URL, 검색 URL, 기획전 URL 중 사용할 주소를 붙여넣고 ‘링크 생성’을 누릅니다.",
          "생성된 단축 링크는 SSMaker 풀자동 입력, YouTube 댓글, Linktree 상품 버튼에 동일하게 사용합니다.",
        ],
        images: [
          {
            src: `${SCREENSHOT_BASE}/04-coupang-create-link.png`,
            alt: "쿠팡 파트너스 간편 링크 생성 화면",
            caption: "3-2 캡쳐 장면: URL 입력칸과 ‘링크 생성’ 버튼이 보이게 확인합니다.",
          },
        ],
      },
      {
        heading: "쿠팡 API Key는 필수인가요?",
        steps: [
          "아닙니다. 쿠팡 파트너스에서 이미 생성한 link.coupang.com/a/... 단축 링크를 SSMaker에 넣는다면 쿠팡 API Key는 필요 없습니다.",
          "쿠팡 API Key는 원본 coupang.com 상품 URL을 프로그램이 자동으로 쿠팡 파트너스 딥링크로 바꾸게 하고 싶을 때만 필요합니다.",
          "초기 사용자에게 가장 쉬운 방식은 쿠팡 파트너스 화면에서 단축 링크를 직접 만든 뒤, 그 링크를 SSMaker 풀자동 입력칸에 붙여넣는 방식입니다.",
          "API Key를 설정하지 않아도 상품 분석, 영상 생성, YouTube 업로드, Linktree Profile 링크 안내 흐름은 사용할 수 있습니다. 다만 원본 쿠팡 URL을 자동 제휴 링크로 변환하는 기능만 제한됩니다.",
        ],
      },
    ],
    content:
      "쿠팡 파트너스에서 상품 단축 링크를 만들고 SSMaker 자동화에 넣는 과정을 실제 화면 기준으로 안내합니다.",
  },
  {
    id: 8,
    title: "Google Cloud 실제 화면 캡쳐로 보는 YouTube OAuth 설정",
    date: "2026년 4월 29일",
    pinned: true,
    slug: "youtube-google-cloud-oauth-screenshots",
    intro:
      "Chrome에서 실제 Google Cloud Console을 열어 확인한 YouTube OAuth 설정 화면입니다. 계정, 프로젝트, 이메일, 클라이언트 식별 정보는 개인정보 가림 처리했고, 입력칸과 눌러야 할 버튼은 노란 박스와 라벨로 표시했습니다.",
    sections: [
      {
        heading: "Google Cloud에서 YouTube OAuth 준비",
        steps: [
          "Google Cloud Console에서 YouTube 업로드에 사용할 프로젝트를 선택합니다.",
          "API 및 서비스 화면에서 YouTube Data API v3가 사용 설정되어 있는지 확인합니다. 꺼져 있다면 API 라이브러리에서 YouTube Data API v3를 검색해 사용 설정합니다.",
          "Google 인증 플랫폼의 브랜딩 화면에서 앱 이름, 사용자 지원 이메일, 개발자 연락처 정보를 확인합니다. 공지용 캡쳐에서는 이메일 등 식별 정보는 개인정보 가림 처리합니다.",
          "클라이언트 화면에서 기존 데스크톱 OAuth 클라이언트가 있으면 새로 만들 필요 없이 해당 클라이언트를 사용합니다.",
          "새로 만드는 경우에는 클라이언트 만들기에서 애플리케이션 유형을 데스크톱 앱으로 선택합니다.",
          "이름을 확인한 뒤 만들기 버튼을 누르면 OAuth 클라이언트가 발급됩니다. 이 버튼은 실제 자격 증명을 만드는 단계이므로 본인 프로젝트가 맞는지 확인한 다음 진행합니다.",
          "생성 후 기존 클라이언트 상세 화면에서 JSON 다운로드를 받아 SSMaker의 YouTube 연결 창에서 선택합니다.",
        ],
        images: [
          {
            src: `${GOOGLE_CLOUD_OAUTH_SCREENSHOT_BASE}/01-api-dashboard.png`,
            alt: "Google Cloud API 및 서비스 대시보드",
            caption: "1-1 캡쳐 장면: API 및 서비스 대시보드에서 노란 표시의 API 사용 설정 버튼과 YouTube Data API v3 상태를 확인합니다.",
          },
          {
            src: `${GOOGLE_CLOUD_OAUTH_SCREENSHOT_BASE}/02-youtube-api-enabled.png`,
            alt: "YouTube Data API v3 사용 설정 확인 화면",
            caption: "1-2 캡쳐 장면: YouTube Data API v3 페이지에서 노란 표시의 ‘API 사용 설정됨’ 상태와 관리 버튼을 확인합니다.",
          },
          {
            src: `${GOOGLE_CLOUD_OAUTH_SCREENSHOT_BASE}/03-oauth-overview.png`,
            alt: "Google 인증 플랫폼 OAuth 개요 화면",
            caption: "1-3 캡쳐 장면: Google 인증 플랫폼의 OAuth 개요에서 동의 화면과 OAuth 상태를 확인합니다.",
          },
        ],
      },
      {
        heading: "브랜딩과 클라이언트 확인",
        steps: [
          "브랜딩 화면에서 앱 이름은 사용자가 알아볼 수 있는 이름으로 둡니다. 예: SSMaker 또는 SSMaker YouTube Upload",
          "사용자 지원 이메일과 개발자 연락처 이메일은 실제 운영자가 확인할 수 있는 이메일이어야 합니다.",
          "테스트 상태로 본인 계정만 쓰는 경우에는 공개 검증 전에도 테스트 사용이 가능합니다. 공개 배포 앱으로 운영하려면 Google 검증이 필요할 수 있습니다.",
          "클라이언트 목록에서 유형이 ‘데스크톱’인 OAuth 2.0 클라이언트를 확인합니다.",
        ],
        images: [
          {
            src: `${GOOGLE_CLOUD_OAUTH_SCREENSHOT_BASE}/04-oauth-branding.png`,
            alt: "Google 인증 플랫폼 브랜딩 설정 화면",
            caption: "2-1 캡쳐 장면: 브랜딩 화면에서 노란 표시의 앱 이름, 로고, 도메인, 인증 상태를 확인합니다. 이메일은 개인정보 가림 처리합니다.",
          },
          {
            src: `${GOOGLE_CLOUD_OAUTH_SCREENSHOT_BASE}/05-oauth-clients.png`,
            alt: "Google 인증 플랫폼 OAuth 클라이언트 목록",
            caption: "2-2 캡쳐 장면: 노란 표시의 클라이언트 만들기 버튼과 데스크톱 OAuth 클라이언트 행을 확인합니다.",
          },
        ],
      },
      {
        heading: "데스크톱 앱 OAuth 클라이언트 만들기",
        steps: [
          "클라이언트 만들기 화면에서 애플리케이션 유형을 누릅니다.",
          "목록에서 ‘데스크톱 앱’을 선택합니다. SSMaker는 로컬 데스크톱 프로그램이라 웹 애플리케이션이 아니라 데스크톱 앱 타입을 사용합니다.",
          "이름은 콘솔에서 구분하기 쉬운 값으로 입력합니다. 예: SSMaker Desktop",
          "만들기 버튼을 누르면 client_id와 client_secret이 포함된 OAuth 클라이언트가 생성됩니다. 이 JSON은 외부에 공유하면 안 됩니다.",
          "다운로드한 JSON 파일을 SSMaker의 YouTube 연결 창에서 선택하고, 브라우저 승인 화면에서 업로드할 채널 권한을 승인합니다.",
        ],
        images: [
          {
            src: `${GOOGLE_CLOUD_OAUTH_SCREENSHOT_BASE}/06-oauth-client-type.png`,
            alt: "OAuth 클라이언트 애플리케이션 유형 선택 목록",
            caption: "3-1 캡쳐 장면: 노란 표시의 애플리케이션 유형 목록에서 ‘데스크톱 앱’을 선택합니다.",
          },
          {
            src: `${GOOGLE_CLOUD_OAUTH_SCREENSHOT_BASE}/07-oauth-desktop-form.png`,
            alt: "데스크톱 앱 OAuth 클라이언트 만들기 직전 화면",
            caption: "3-2 캡쳐 장면: 노란 표시의 데스크톱 앱 유형과 이름 입력칸을 확인한 뒤 ‘만들기’를 누르면 실제 OAuth 클라이언트가 발급됩니다.",
          },
        ],
      },
    ],
    content:
      "Google Cloud Console 실제 화면 기준으로 YouTube Data API v3 사용 설정, Google 인증 플랫폼 브랜딩, 데스크톱 앱 OAuth 클라이언트 생성 직전 단계까지 안내합니다.",
  },
  {
    id: 9,
    title: "업로드 후 YouTube·댓글·Linktree 검수 매뉴얼",
    date: "2026년 4월 29일",
    pinned: true,
    slug: "youtube-linktree-upload-check",
    intro:
      "영상 업로드 뒤 Shorts 노출, 상품명, 댓글, Linktree 번호 링크가 제대로 반영됐는지 확인하는 검수 절차입니다. 채널 식별 정보는 개인정보 가림 처리했습니다.",
    sections: [
      {
        heading: "업로드 후 YouTube·댓글·Linktree 검수",
        steps: [
          "유튜브 채널의 Shorts 탭에서 새 영상이 노출되는지 확인합니다. 채널명과 핸들은 캡쳐 전에 반드시 가립니다.",
          "썸네일, 제목, 상품명이 입력한 쿠팡 상품과 맞는지 확인합니다.",
          "유튜브 댓글에는 상품 설명과 Linktree 링크가 함께 남아 있어야 합니다.",
          "Linktree 관리자 화면에서는 각 상품 링크 제목 앞에 [000] 형식 번호가 붙고 링크 토글이 켜져 있어야 합니다.",
          "공개 Linktree 화면에서 실제 방문자가 상품 버튼을 누를 수 있는지 마지막으로 확인합니다.",
        ],
        images: [
          {
            src: `${SCREENSHOT_BASE}/11-youtube-shorts-verify-guide.png`,
            alt: "유튜브 Shorts 업로드 확인 영역",
            caption: "4-1 캡쳐 장면: Shorts 탭의 새 영상 영역을 확인하되 채널 식별 정보는 가립니다.",
          },
          {
            src: `${SCREENSHOT_BASE}/08-youtube-shorts-check.png`,
            alt: "개인정보 가림 처리된 유튜브 Shorts 검수 화면",
            caption: "4-2 캡쳐 장면: 채널명, 핸들, 채널아트는 가리고 Shorts 목록만 검수합니다.",
          },
          {
            src: `${SCREENSHOT_BASE}/06-linktree-links-admin.png`,
            alt: "Linktree 번호가 붙은 링크 관리자 검수 화면",
            caption: "4-4 캡쳐 장면: 상품 링크 제목 앞의 [000] 번호와 토글 ON 상태를 확인합니다.",
          },
          {
            src: `${SCREENSHOT_BASE}/12-linktree-public-buttons-guide.png`,
            alt: "Linktree 공개 상품 버튼 검수 화면",
            caption: "4-5 캡쳐 장면: 공개 화면에서 방문자용 상품 버튼이 보이는지 확인합니다.",
          },
        ],
      },
    ],
    content:
      "YouTube Shorts 업로드, 댓글, Linktree 자동 등록 결과를 실제 화면 기준으로 검수하는 방법을 안내합니다.",
  },
  {
    id: 1,
    title: "SSMaker 정식 출시 안내",
    date: "2026년 2월 7일",
    pinned: true,
    slug: "ssmaker-launch",
    content: `안녕하세요, SSMaker 팀입니다.

SSMaker가 정식 출시되었습니다!

SSMaker는 중국 쇼핑 숏폼 영상(더우인/틱톡)을 한국어 쇼핑 숏폼 콘텐츠로 자동 변환하는 데스크톱 프로그램입니다.

영상 속 외국어 자막을 자동 감지하고, 자막을 블러 처리한 뒤, AI가 자연스러운 한국어 쇼핑 스크립트를 생성하고, TTS로 한국어 음성을 합성하여 완성된 영상을 자동으로 만들어줍니다.

반복 편집 단계를 한 흐름으로 줄이고 GPU 가속을 지원합니다. 영상 링크 하나로 제작하거나 링크 여러 개를 하나의 믹스 영상으로 구성할 수 있으며, 대기 작업은 순서대로 처리합니다.

많은 관심 부탁드립니다.

📌 문의사항이 있으시면 카카오톡으로 문의해주세요!
👉 카카오톡 문의하기: https://open.kakao.com/o/sVkZPsfi`,
  },
  {
    id: 2,
    title: "무료 이용권 안내",
    date: "2026년 2월 7일",
    pinned: true,
    slug: "free-voucher",
    content: `안녕하세요, SSMaker 팀입니다.

출시 기념 무료 이용권 안내드립니다.

■ 특별 혜택
2026년 2월 8일까지 가입한 사용자에 한하여 5회 무료 이용권을 제공합니다.

■ 기본 무료 체험
2026년 2월 8일 이후에는 매월 5회 무료 이용권이 제공됩니다.

감사합니다.

📌 문의사항이 있으시면 카카오톡으로 문의해주세요!
👉 카카오톡 문의하기: https://open.kakao.com/o/sVkZPsfi`,
  },
  {
    id: 3,
    title: "구글 제미나이 API 키 발급 방법 (초보자 가이드)",
    date: "2026년 2월 10일",
    pinned: true,
    slug: "gemini-api-guide",
    content: `안녕하세요, SSMaker를 사용하기 위해서는 구글 제미나이(Gemini) API 키가 필요합니다.

초등학생도 따라할 수 있도록 하나하나 자세히 설명드리겠습니다! 🎯

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 STEP 1: 구글 계정 로그인
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ 크롬 브라우저를 엽니다
2️⃣ 구글 계정에 로그인합니다 (Gmail 계정)
※ 구글 계정이 없다면? → accounts.google.com에서 계정을 만드세요

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔑 STEP 2: API 키 발급하기
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ 아래 링크를 정확히 복사해서 주소창에 붙여넣으세요:

👉 https://aistudio.google.com/app/api-keys

2️⃣ 페이지가 열리면 왼쪽 메뉴에서 "API 키" 를 클릭

3️⃣ 오른쪽 위에 있는 파란색 버튼을 찾으세요
버튼 이름: "API 키 만들기" 또는 "Create API key"

4️⃣ 버튼을 클릭하면 작은 창이 나타납니다

5️⃣ "새 프로젝트에서 API 키 만들기" 를 선택
(영어: "Create API key in new project")

6️⃣ 잠시 기다리면... 짠! ✨ API 키가 생성됩니다!

7️⃣ 생성된 API 키가 화면에 나타나면:
- 📋 복사 버튼(사각형 겨쳐진 아이콘)을 클릭
- 메모장에 붙여넣어서 안전하게 보관하세요

⚠️ 중요: API 키는 비밀번호처럼 중요합니다!
다른 사람에게 절대 알려주지 마세요!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⭐ STEP 3: Tier 1로 업그레이드하기
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tier 1이란?
무료 버전(Free tier)보다 더 많이 사용할 수 있는 버전입니다!
월 5달러($5)만 결제하면 업그레이드할 수 있어요.

왜 Tier 1이 필요한가요?
- ✅ 더 많은 요청 가능 (하루 1,500회 → 무제한!)
- ✅ 속도 제한 완화
- ✅ SSMaker 사용 시 끊김 없이 쟨적하게!

업그레이드 방법:

1️⃣ 아래 링크를 주소창에 붙여넣으세요:

👉 https://console.cloud.google.com/billing

2️⃣ 왼쪽 위 "☰" (메뉴 아이콘) 클릭

3️⃣ "결제" 메뉴를 찾아서 클릭
(영어: "Billing")

4️⃣ "결제 계정 만들기" 버튼 클릭
(영어: "Create billing account")

5️⃣ 필요한 정보 입력:
- 📧 이메일 주소
- 🏠 주소 (한글로 입력 가능)
- 💳 신용카드 또는 체크카드 정보

※ 카드 정보는 구글에 안전하게 암호화되어 저장됩니다

6️⃣ "계속" 또는 "Continue" 버튼 클릭

7️⃣ 결제 계정이 생성되면 완료! 🎉

8️⃣ 다시 Google AI Studio로 돌아가서:
👉 https://aistudio.google.com/app/api-keys

9️⃣ 내 API 키 옆에 "할당량 등급" 또는 "Tier"를 확인하세요
- "Tier 1"로 표시되면 성공!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 요금 안내
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

▪ Free Tier (무료)
- 하루 15회 요청 제한
- 분당 2회 요청
- 무료!

▪ Tier 1 (추천!)
- 하루 1,500회 요청
- 분당 1,500회 요청
- 월 약 $5-10 (사용량에 따라 다름)
- 💡 일반 사용자는 월 $5 이하로 충분!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🆘 자주 묻는 질문 (FAQ)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1: API 키를 잃어버렸어요!
A1: https://aistudio.google.com/app/api-keys 에서
키를 삭제하고 새로 만들면 됩니다!

Q2: 결제가 무서워요 ㅠㅠ
A2: 구글은 사용한 만큼만 청구합니다!
월 예산 한도를 설정할 수도 있어요.

Q3: 무료 버전으로는 안 되나요?
A3: 가능하지만 하루 15회만 사용할 수 있어서
SSMaker를 제대로 쓰기 어려워요 😭

Q4: Tier 1로 업그레이드했는데 확인이 안 돼요
A4: 결제 정보 입력 후 5-10분 정도 기다려주세요.
그래도 안 되면 페이지를 새로고침(F5)하세요!

Q5: 영어로 나와서 무서워요
A5: 크롬 브라우저에서 마우스 우클릭 →
"한국어로 번역" 선택하면 됩니다!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎓 완벽 정리!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. https://aistudio.google.com/app/api-keys 접속
2. "API 키 만들기" 버튼 클릭
3. "새 프로젝트에서 API 키 만들기" 선택
4. 생성된 API 키 복사해서 보관
5. (선택) https://console.cloud.google.com/billing 에서 결제 추가
6. SSMaker 프로그램에서 API 키 입력
7. 끝! 🎉

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 도움이 필요하신가요?

문의하기: 카카오톡 오픈채팅으로 문의해주세요! 👉 https://open.kakao.com/o/sVkZPsfi
스크린샷을 찍어서 보내주시면 더 빠르게 도와드릴 수 있습니다 😊

※ 이 가이드를 따라했는데도 안 되시나요?
→ 화면 캡처(스크린샷)를 찍어서 문의해주세요!
→ Windows: "PrtSc" 키 또는 "Windows + Shift + S"
→ Mac: "Command + Shift + 4"

행복한 영상 제작 되세요! 🎬✨

📌 문의사항이 있으시면 카카오톡으로 문의해주세요!
👉 카카오톡 문의하기: https://open.kakao.com/o/sVkZPsfi`,
  },
  {
    id: 4,
    title: "YouTube 채널 연결용 Google Cloud OAuth 설정 가이드",
    date: "2026년 2월 13일",
    pinned: true,
    slug: "youtube-oauth-client-guide",
    content: `안녕하세요, SSMaker 팀입니다.

SSMaker에서 YouTube Shorts를 자동 업로드하려면 Google Cloud에서 YouTube Data API v3를 켜고, 데스크톱 앱용 OAuth 클라이언트 JSON 파일을 받아야 합니다.

중요: 일반 유튜브 채널 업로드에는 서비스 계정 JSON이 아니라 OAuth 클라이언트 JSON이 필요합니다. 서비스 계정은 일반 개인/브랜드 채널 업로드용으로 쓰지 않습니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 STEP 1: Google Cloud 프로젝트 준비
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ Google Cloud Console에 접속합니다.
👉 https://console.cloud.google.com

2️⃣ 상단 프로젝트 선택 메뉴에서 새 프로젝트를 만들거나 기존 프로젝트를 선택합니다.

3️⃣ 프로젝트명은 알아보기 쉽게 입력합니다.
예: ssmaker-youtube-upload

4️⃣ 프로젝트가 선택된 상태인지 다시 확인합니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📺 STEP 2: YouTube Data API v3 사용 설정
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ 왼쪽 메뉴에서 "API 및 서비스" → "라이브러리"로 이동합니다.

2️⃣ 검색창에 "YouTube Data API v3"를 입력합니다.

3️⃣ YouTube Data API v3 페이지를 엽니다.

4️⃣ "사용" 또는 "Enable" 버튼을 눌러 API를 켭니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡 STEP 3: OAuth 동의 화면 설정
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ "API 및 서비스" → "OAuth 동의 화면" 또는 "Google Auth Platform" 메뉴로 이동합니다.

2️⃣ 앱 이름에는 사용자가 알아볼 이름을 입력합니다.
예: SSMaker YouTube Upload

3️⃣ 사용자 지원 이메일과 개발자 연락처 이메일을 입력합니다.

4️⃣ 테스트 단계에서는 사용자 유형과 게시 상태가 계정 상황에 따라 다르게 보일 수 있습니다. 개인 테스트라면 본인 Google 계정을 테스트 사용자에 추가합니다.

5️⃣ 저장 후 다음 단계로 이동합니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔑 STEP 4: OAuth 클라이언트 ID 만들기
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ "API 및 서비스" → "사용자 인증 정보"로 이동합니다.

2️⃣ "사용자 인증 정보 만들기"를 누릅니다.

3️⃣ "OAuth 클라이언트 ID"를 선택합니다.

4️⃣ 애플리케이션 유형은 "데스크톱 앱"을 선택합니다.

5️⃣ 이름은 알아보기 쉽게 입력합니다.
예: SSMaker Desktop

6️⃣ 만들기 버튼을 누르면 클라이언트 ID가 생성됩니다.

7️⃣ 다운로드 버튼으로 JSON 파일을 저장합니다.

⚠️ 이 JSON에는 client_id와 client_secret이 들어 있습니다. 다른 사람에게 공유하지 마세요.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📁 STEP 5: SSMaker에 OAuth JSON 연결
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ SSMaker에서 "업로드/채널" 화면으로 이동합니다.

2️⃣ YouTube 카드에서 "연결"을 누릅니다.

3️⃣ "OAuth JSON 파일 선택"을 눌러 방금 다운로드한 JSON 파일을 선택합니다.

4️⃣ 브라우저가 열리면 업로드할 YouTube 채널이 연결된 Google 계정으로 로그인합니다.

5️⃣ 권한 요청 화면에서 YouTube 업로드/조회/댓글 권한을 확인하고 승인합니다.

6️⃣ SSMaker에 채널명이 자동으로 표시되면 연결 완료입니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 자주 헷갈리는 부분
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q. API Key만 만들면 되나요?
A. 아닙니다. YouTube 업로드는 사용자 채널 권한이 필요하므로 OAuth 클라이언트 JSON이 필요합니다.

Q. 서비스 계정을 만들면 되나요?
A. 일반 개인/브랜드 채널 업로드용으로는 아닙니다. SSMaker는 OAuth 브라우저 승인 방식으로 채널 권한을 받습니다.

Q. 테스트 모드에서 "앱이 확인되지 않음"이 뜨면요?
A. 본인 프로젝트를 본인만 쓰는 테스트 단계라면 고급/계속 진행으로 승인할 수 있습니다. 공개 배포용 OAuth 앱은 Google 검증이 필요할 수 있습니다.

Q. JSON 파일을 잃어버렸어요.
A. Google Cloud의 사용자 인증 정보 화면에서 OAuth 클라이언트를 다시 확인하거나 새로 만들 수 있습니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎓 완벽 정리!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Google Cloud 프로젝트 선택
2. YouTube Data API v3 사용 설정
3. OAuth 동의 화면 설정
4. 데스크톱 앱 OAuth 클라이언트 ID 생성
5. OAuth JSON 다운로드
6. SSMaker에서 JSON 선택 후 브라우저 승인
7. 채널 연결 완료

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📌 도움이 필요하신가요?

문의하기: 카카오톡 오픈채팅으로 문의해주세요! 👉 https://open.kakao.com/o/sVkZPsfi
스크린샷을 찍어서 보내주시면 더 빠르게 도와드릴 수 있습니다 😊

📌 문의사항이 있으시면 카카오톡으로 문의해주세요!
👉 카카오톡 문의하기: https://open.kakao.com/o/sVkZPsfi`,
  },
];

/* ──────────────────────────── GitHub releases fetch ──────────── */

async function fetchReleases(): Promise<GitHubRelease[]> {
  const res = await fetch("https://api.github.com/repos/Kimchanghee/NewshoppingShorts/releases", {
    headers: { Accept: "application/vnd.github+json" },
  });
  if (!res.ok) throw new Error("Failed to fetch releases");
  return res.json();
}

function formatDate(iso: string) {
  const d = new Date(iso);
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
}

function cleanReleaseBody(body: string): string {
  if (!body) return "";
  let cleaned = body;
  cleaned = cleaned.replace(/#{1,6}\s*SHA256[\s\S]*/gi, "");
  cleaned = cleaned.replace(/^#{1,6}\s+/gm, "");
  cleaned = cleaned.trim();
  return cleaned;
}

function summarizeText(input: string, maxLength = 160) {
  const plain = input
    .replace(/!\[[^\]]*\]\((https?:\/\/[^\s)]+)\)/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (plain.length <= maxLength) return plain;
  return `${plain.slice(0, maxLength - 1)}…`;
}

/**
 * Render a release/notice body as plain text, but turn Markdown image syntax
 * `![alt](https://...)` into inline <figure><img/></figure> blocks.
 * Defensive: any parsing issue falls back to the plain-text rendering.
 */
function ReleaseBodyContent({ body }: { body: string }) {
  const text = body && body.trim().length > 0 ? body : "업데이트 내용이 없습니다.";
  try {
    const imageRegex = /!\[([^\]]*)\]\((https?:\/\/[^\s)]+)\)/g;
    const nodes: JSX.Element[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;
    let key = 0;
    while ((match = imageRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        const chunk = text.slice(lastIndex, match.index).replace(/^\n+|\n+$/g, "");
        if (chunk.trim().length > 0) {
          nodes.push(
            <span key={`t-${key}`} className="block whitespace-pre-line">
              {chunk}
            </span>,
          );
        }
      }
      const alt = match[1];
      const url = match[2];
      nodes.push(
        <figure
          key={`i-${key}`}
          className="my-6 overflow-hidden rounded-xl border border-border/50 bg-background/40"
        >
          <img src={url} alt={alt || "스크린샷"} loading="lazy" className="block w-full" />
          {alt ? (
            <figcaption className="px-4 py-3 text-center text-xs text-muted-foreground md:text-sm">
              {alt}
            </figcaption>
          ) : null}
        </figure>,
      );
      lastIndex = imageRegex.lastIndex;
      key += 1;
    }
    if (lastIndex < text.length) {
      const rest = text.slice(lastIndex).replace(/^\n+/, "");
      if (rest.trim().length > 0) {
        nodes.push(
          <span key={`t-${key}`} className="block whitespace-pre-line">
            {rest}
          </span>,
        );
      }
    }
    if (nodes.length === 0) {
      return (
        <div className="whitespace-pre-line leading-relaxed text-muted-foreground">{text}</div>
      );
    }
    return <div className="leading-relaxed text-muted-foreground">{nodes}</div>;
  } catch {
    return (
      <div className="whitespace-pre-line leading-relaxed text-muted-foreground">{text}</div>
    );
  }
}

/* ──────────────────────────── Notice detail view ─────────────── */

function NoticeDetail({ notice }: { notice: NoticeItem }) {
  const navigate = useNavigate();
  const publishedIso = parseKoreanDateToIso(notice.date);
  const detailPath = noticeDetailPath(notice.slug);
  const description = summarizeText(notice.content, 170);
  const noticeStatusLabel = getNoticeStatusLabel(notice);
  const isPromotionNotice = notice.slug === PROMOTION_NOTICE_SLUG;
  const promotionStatus = getPromotionStatus();
  const structuredData = [
    buildOrganizationSchema(),
    buildBreadcrumbSchema([
      { name: "홈", path: "/" },
      { name: "공지사항", path: NOTICE_LIST_PATH },
      { name: notice.title, path: detailPath },
    ]),
    buildWebPageSchema({
      name: `${notice.title} | 공지사항`,
      description,
      path: detailPath,
      breadcrumbPaths: [
        { name: "홈", path: "/" },
        { name: "공지사항", path: NOTICE_LIST_PATH },
        { name: notice.title, path: detailPath },
      ],
    }),
    buildArticleSchema({
      headline: notice.title,
      description,
      path: detailPath,
      datePublished: publishedIso,
      dateModified: publishedIso,
      articleSection: "공지사항",
    }),
  ];

  return (
    <div className="min-h-screen bg-background">
      <Seo
        title={`${notice.title} | 공지사항 | SSMaker`}
        description={description}
        path={detailPath}
        type="article"
        keywords={[...SITE_KEYWORDS, "공지사항", notice.title]}
        publishedTime={publishedIso}
        modifiedTime={publishedIso}
        articleSection="공지사항"
        articleTags={["SSMaker", "공지사항", "업데이트"]}
        structuredData={structuredData}
      />
      <Navigation />
      <div className="container mx-auto px-4 pb-20 pt-28 sm:px-6 sm:pt-32">
        <FadeIn>
          <button
            onClick={() => navigate(NOTICE_LIST_PATH)}
            className="mb-8 flex min-h-11 items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            목록으로 돌아가기
          </button>

          <div className="glass-card rounded-xl p-5 sm:p-8 md:p-12">
            <div className="mb-6 flex items-center gap-3">
              {notice.pinned && (
                <span className="inline-flex items-center gap-1 rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                  <Pin className="h-3 w-3" />
                  고정
                </span>
              )}
              {noticeStatusLabel && (
                <span
                  className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ${
                    promotionStatus === "closed"
                      ? "bg-muted text-muted-foreground"
                      : "bg-primary text-primary-foreground"
                  }`}
                >
                  {noticeStatusLabel}
                </span>
              )}
              <span className="text-sm text-muted-foreground">{notice.date}</span>
            </div>

            <h1 className="mb-8 text-2xl font-bold text-foreground md:text-3xl">{notice.title}</h1>

            {isPromotionNotice && (
              <div className="mb-8 rounded-lg border border-primary/20 bg-primary/[0.04] p-4">
                <p className="text-sm font-semibold text-foreground">
                  현재 상태: {getPromotionStatusLabel(promotionStatus)} · {PROMOTION.periodLabel}
                </p>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                  {getPromotionDescription(promotionStatus)}
                </p>
              </div>
            )}

            <div className="border-t border-border/50 pt-8">
              {notice.sections && notice.sections.length > 0 ? (
                <div className="space-y-12">
                  {notice.intro && (
                    <p className="text-sm leading-relaxed text-muted-foreground">{notice.intro}</p>
                  )}
                  {notice.sections.map((section) => (
                    <section key={section.heading} className="space-y-4">
                      <h2 className="text-xl font-semibold text-foreground md:text-2xl">
                        {section.heading}
                      </h2>
                      <ol className="list-decimal space-y-2 pl-5 text-sm leading-relaxed text-muted-foreground md:text-base">
                        {section.steps.map((step, i) => (
                          <li key={i}>{step}</li>
                        ))}
                      </ol>
                      {section.images && section.images.length > 0 && (
                        <div className="grid gap-4 sm:grid-cols-2">
                          {section.images.map((img) => (
                            <figure key={img.src} className="space-y-2">
                              <img
                                src={img.src}
                                alt={img.alt}
                                loading="lazy"
                                className="w-full rounded-lg border border-border/60 bg-muted/20"
                              />
                              {img.caption && (
                                <figcaption className="text-xs leading-relaxed text-muted-foreground md:text-sm">
                                  {img.caption}
                                </figcaption>
                              )}
                            </figure>
                          ))}
                        </div>
                      )}
                    </section>
                  ))}
                </div>
              ) : (
                <div className="whitespace-pre-line leading-relaxed text-muted-foreground">{notice.content}</div>
              )}
            </div>
          </div>
        </FadeIn>
      </div>
      <Footer />
    </div>
  );
}

/* ──────────────────────────── Release detail view ────────────── */

function ReleaseDetail({ tagName }: { tagName: string }) {
  const navigate = useNavigate();
  const { data: releases, isLoading } = useQuery({
    queryKey: ["github-releases"],
    queryFn: fetchReleases,
    staleTime: 5 * 60 * 1000,
  });

  const release = releases?.find((r) => r.tag_name === tagName);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <Navigation />
        <div className="container mx-auto px-4 pb-20 pt-28 sm:px-6 sm:pt-32">
          <Skeleton className="mb-4 h-8 w-48" />
          <Skeleton className="mb-2 h-6 w-full" />
          <Skeleton className="h-6 w-3/4" />
        </div>
        <Footer />
      </div>
    );
  }

  if (!release) {
    return (
      <div className="min-h-screen bg-background">
        <Seo
          title="업데이트 정보를 찾을 수 없음 | 공지사항 | SSMaker"
          description="요청하신 릴리즈 정보를 찾을 수 없습니다."
          path={`/notice/release-${tagName}`}
          noIndex
        />
        <Navigation />
        <div className="container mx-auto px-4 pb-20 pt-28 text-center sm:px-6 sm:pt-32">
          <p className="text-muted-foreground">해당 업데이트 정보를 찾을 수 없습니다.</p>
          <button onClick={() => navigate(NOTICE_LIST_PATH)} className="mt-4 text-primary hover:underline">
            목록으로 돌아가기
          </button>
        </div>
        <Footer />
      </div>
    );
  }

  const detailPath = releaseDetailPath(release.tag_name);
  const releaseDescription = summarizeText(cleanReleaseBody(release.body) || "SSMaker 릴리즈 업데이트 안내", 170);
  const publishedIso = new Date(release.published_at).toISOString();
  const structuredData = [
    buildOrganizationSchema(),
    buildBreadcrumbSchema([
      { name: "홈", path: "/" },
      { name: "공지사항", path: NOTICE_LIST_PATH },
      { name: `${release.tag_name} 업데이트`, path: detailPath },
    ]),
    buildWebPageSchema({
      name: `${release.tag_name} 업데이트 안내`,
      description: releaseDescription,
      path: detailPath,
      breadcrumbPaths: [
        { name: "홈", path: "/" },
        { name: "공지사항", path: NOTICE_LIST_PATH },
        { name: `${release.tag_name} 업데이트`, path: detailPath },
      ],
    }),
    buildArticleSchema({
      headline: `${release.tag_name} 업데이트 안내`,
      description: releaseDescription,
      path: detailPath,
      datePublished: publishedIso,
      dateModified: publishedIso,
      articleSection: "업데이트",
    }),
  ];

  return (
    <div className="min-h-screen bg-background">
      <Seo
        title={`${release.tag_name} 업데이트 안내 | 공지사항 | SSMaker`}
        description={releaseDescription}
        path={detailPath}
        type="article"
        keywords={[...SITE_KEYWORDS, "SSMaker 업데이트", release.tag_name]}
        publishedTime={publishedIso}
        modifiedTime={publishedIso}
        articleSection="업데이트"
        articleTags={["SSMaker", "업데이트", release.tag_name]}
        structuredData={structuredData}
      />
      <Navigation />
      <div className="container mx-auto px-4 pb-20 pt-28 sm:px-6 sm:pt-32">
        <FadeIn>
          <button
            onClick={() => navigate(NOTICE_LIST_PATH)}
            className="mb-8 flex min-h-11 items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            목록으로 돌아가기
          </button>

          <div className="glass-card rounded-xl p-5 sm:p-8 md:p-12">
            <div className="mb-6 flex items-center gap-3">
              <span className="inline-flex items-center gap-1 rounded bg-green-500/10 px-2 py-0.5 text-xs font-medium text-green-600 dark:text-green-400">
                <Package className="h-3 w-3" />
                업데이트
              </span>
              <span className="text-sm text-muted-foreground">{formatDate(release.published_at)}</span>
            </div>

            <h1 className="mb-8 text-2xl font-bold text-foreground md:text-3xl">
              {release.tag_name} 업데이트 안내
            </h1>

            <div className="border-t border-border/50 pt-8">
              <ReleaseBodyContent body={cleanReleaseBody(release.body)} />
            </div>
          </div>
        </FadeIn>
      </div>
      <Footer />
    </div>
  );
}

/* ──────────────────────────── Notice list view ───────────────── */

function NoticeList() {
  const navigate = useNavigate();
  const setupManualNotices = notices.filter((n) => SETUP_MANUAL_SLUGS.includes(n.slug));
  const otherNotices = notices.filter((n) => !SETUP_MANUAL_SLUGS.includes(n.slug));

  const {
    data: releases,
    isLoading: releasesLoading,
  } = useQuery({
    queryKey: ["github-releases"],
    queryFn: fetchReleases,
    staleTime: 5 * 60 * 1000,
  });

  const releaseList = (releases ?? []).slice(0, 20);
  const staticCount = notices.length;
  const staticNoticePaths = notices.map((notice) => noticeDetailPath(notice.slug));
  const releasePaths = releaseList.map((release) => releaseDetailPath(release.tag_name));
  const noticePaths = [NOTICE_LIST_PATH, ...staticNoticePaths, ...releasePaths];
  const structuredData = [
    buildOrganizationSchema(),
    buildBreadcrumbSchema([
      { name: "홈", path: "/" },
      { name: "공지사항", path: NOTICE_LIST_PATH },
    ]),
    buildCollectionPageSchema({
      name: "SSMaker 공지사항",
      description: "SSMaker의 업데이트, 공지, 가이드 정보를 모아둔 공지사항 목록 페이지",
      path: NOTICE_LIST_PATH,
      itemPaths: noticePaths,
    }),
    buildWebPageSchema({
      name: "공지사항 | SSMaker",
      description: "SSMaker 업데이트, 공지, 이벤트, 가이드 목록",
      path: NOTICE_LIST_PATH,
      breadcrumbPaths: [
        { name: "홈", path: "/" },
        { name: "공지사항", path: NOTICE_LIST_PATH },
      ],
    }),
  ];

  return (
    <div className="min-h-screen bg-background">
      <Seo
        title="공지사항 | SSMaker"
        description="SSMaker의 업데이트, 이벤트, 무료 이용권 안내 등 공지사항을 확인하세요."
        path={NOTICE_LIST_PATH}
        keywords={[...SITE_KEYWORDS, "공지사항", "업데이트", "릴리즈 노트"]}
        structuredData={structuredData}
      />
      <Navigation />
      <div className="container mx-auto px-4 pb-20 pt-28 sm:px-6 sm:pt-32">
        <FadeIn>
          <Link
            to="/"
            className="mb-6 inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            홈으로 돌아가기
          </Link>

          <h1 className="mb-8 text-3xl font-bold text-foreground">공지사항</h1>

          <div className="mb-10">
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <h2 className="text-xl font-semibold text-foreground">초기 세팅 매뉴얼</h2>
              <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {setupManualNotices.length}개 개별 게시물
              </span>
            </div>
            <div className="glass-card overflow-hidden rounded-xl">
              <div className="hidden items-center gap-4 border-b border-border/50 bg-muted/20 px-4 py-3 sm:px-6 md:grid md:grid-cols-[auto_minmax(0,1fr)_minmax(7rem,auto)]">
                <span className="w-20 text-center text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  단계
                </span>
                <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">제목</span>
                <span className="text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  날짜
                </span>
              </div>

              {setupManualNotices.map((notice, index) => (
                <button
                  key={`setup-${notice.id}`}
                  data-notice-slug={notice.slug}
                  onClick={() => navigate(noticeDetailPath(notice.slug))}
                  className={`group grid min-h-11 w-full grid-cols-1 items-center gap-2 bg-primary/[0.03] px-4 py-4 text-left transition-colors hover:bg-primary/[0.06] sm:px-6 md:grid-cols-[auto_minmax(0,1fr)_minmax(7rem,auto)] md:gap-4 ${
                    index < setupManualNotices.length - 1 ? "border-b border-border/50" : ""
                  }`}
                >
                  <span className="flex w-20 justify-start md:justify-center">
                    <span className="inline-flex items-center rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                      {index + 1}단계
                    </span>
                  </span>
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="font-medium text-foreground transition-colors group-hover:text-primary">
                      {notice.title}
                    </span>
                    <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                  </span>
                  <span className="text-sm text-muted-foreground md:text-right">{notice.date}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="mb-3 flex items-center gap-3">
            <h2 className="text-xl font-semibold text-foreground">일반 공지 및 업데이트</h2>
          </div>

          <div className="glass-card overflow-hidden rounded-xl">
            <div className="hidden items-center gap-4 border-b border-border/50 bg-muted/20 px-4 py-3 sm:px-6 md:grid md:grid-cols-[auto_minmax(0,1fr)_minmax(7rem,auto)]">
              <span className="w-16 text-center text-xs font-medium uppercase tracking-wider text-muted-foreground">
                분류
              </span>
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">제목</span>
              <span className="text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                날짜
              </span>
            </div>

            {otherNotices.map((notice, index) => (
              <button
                key={`list-${notice.id}`}
                data-notice-slug={notice.slug}
                onClick={() => navigate(noticeDetailPath(notice.slug))}
                className={`group grid min-h-11 w-full grid-cols-1 items-center gap-2 px-4 py-4 text-left transition-colors hover:bg-muted/30 sm:px-6 md:grid-cols-[auto_minmax(0,1fr)_minmax(7rem,auto)] md:gap-4 ${
                  index < otherNotices.length - 1 || releaseList.length > 0 ? "border-b border-border/50" : ""
                }`}
              >
                <span className="flex w-16 justify-center">
                  <span className="text-sm text-muted-foreground">{notice.id}</span>
                </span>
              <span className="flex min-w-0 items-center gap-2">
                <span className="font-medium text-foreground transition-colors group-hover:text-primary">
                  {notice.title}
                </span>
                {getNoticeStatusLabel(notice) && (
                  <span
                    className={`inline-flex rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                      getPromotionStatus() === "closed"
                        ? "bg-muted text-muted-foreground"
                        : "bg-primary text-primary-foreground"
                    }`}
                  >
                    {getNoticeStatusLabel(notice)}
                  </span>
                )}
                {notice.pinned && (
                  <span className="inline-flex items-center gap-1 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                      <Pin className="h-2.5 w-2.5" />
                    </span>
                  )}
                  <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                </span>
                <span className="text-sm text-muted-foreground md:text-right">{notice.date}</span>
              </button>
            ))}

            {releasesLoading && (
              <div className="space-y-3 p-6">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="flex items-center gap-4">
                    <Skeleton className="h-5 w-16" />
                    <Skeleton className="h-5 flex-1" />
                    <Skeleton className="h-5 w-24" />
                  </div>
                ))}
              </div>
            )}

            {releaseList.map((release, idx) => (
              <button
                key={`release-${release.id}`}
                onClick={() => navigate(releaseDetailPath(release.tag_name))}
                className={`group grid min-h-11 w-full grid-cols-1 items-center gap-2 px-4 py-4 text-left transition-colors hover:bg-muted/30 sm:px-6 md:grid-cols-[auto_minmax(0,1fr)_minmax(7rem,auto)] md:gap-4 ${
                  idx < releaseList.length - 1 ? "border-b border-border/50" : ""
                }`}
              >
                <span className="flex w-16 justify-center">
                  <span className="text-sm text-muted-foreground">{staticCount + idx + 1}</span>
                </span>
                <span className="flex min-w-0 items-center gap-2">
                  <span className="font-medium text-foreground transition-colors group-hover:text-primary">
                    {release.tag_name} 업데이트 안내
                  </span>
                  <span className="inline-flex items-center gap-1 rounded bg-green-500/10 px-1.5 py-0.5 text-[10px] font-medium text-green-600 dark:text-green-400">
                    <Package className="h-2.5 w-2.5" />
                  </span>
                  <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
                </span>
                <span className="text-sm text-muted-foreground md:text-right">{formatDate(release.published_at)}</span>
              </button>
            ))}
          </div>
        </FadeIn>
      </div>
      <Footer />
    </div>
  );
}

/* ──────────────────────────── Main export ────────────────────── */

export default function Notice() {
  const { slug } = useParams();

  if (slug && slug.startsWith("release-")) {
    const tagName = decodeURIComponent(slug.replace("release-", ""));
    return <ReleaseDetail tagName={tagName} />;
  }

  const selectedNotice = slug ? (notices.find((n) => n.slug === slug) ?? null) : null;
  if (selectedNotice) return <NoticeDetail notice={selectedNotice} />;
  return <NoticeList />;
}
