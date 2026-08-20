import Navigation from "@/components/Navigation";
import Hero from "@/components/Hero";
import PromotionBanner from "@/components/PromotionBanner";
import PainPoints from "@/components/PainPoints";
import Solution from "@/components/Solution";
import Features from "@/components/Features";
import Efficiency from "@/components/Efficiency";
import Testimonials from "@/components/Testimonials";
import DemoVideo from "@/components/DemoVideo";
import HowItWorks from "@/components/HowItWorks";
import SetupGuide from "@/components/SetupGuide";
import Pricing from "@/components/Pricing";
import AnswerEngineSection from "@/components/AnswerEngineSection";
import FAQSection from "@/components/FAQSection";
import FinalCTA from "@/components/FinalCTA";
import Footer from "@/components/Footer";
import Seo from "@/components/Seo";
import { SITE_KEYWORDS } from "@/constants/site";
import { ANSWER_ENGINE_QAS } from "@/data/answerEngine";
import { FAQS } from "@/data/faqs";
import {
  buildBreadcrumbSchema,
  buildFaqSchema,
  buildHowToSchema,
  buildItemListSchema,
  buildOrganizationSchema,
  buildSoftwareApplicationSchema,
  buildSpeakableSchema,
  buildWebPageSchema,
  buildWebsiteSchema,
} from "@/lib/structuredData";

const HOME_STRUCTURED_DATA = [
  buildOrganizationSchema(),
  buildWebsiteSchema(),
  buildSoftwareApplicationSchema(),
  buildFaqSchema([...ANSWER_ENGINE_QAS, ...FAQS]),
  buildBreadcrumbSchema([{ name: "홈", path: "/" }]),
  buildWebPageSchema({
    name: "SSMaker 홈 | 쇼핑 숏폼 자동화",
    description: "중국 쇼핑 영상을 한국어 쇼핑 숏폼으로 자동 변환하고 쿠팡 파트너스, YouTube Shorts, Linktree 흐름을 연결하는 AI 솔루션 소개 페이지",
    path: "/",
    breadcrumbPaths: [{ name: "홈", path: "/" }],
  }),
  buildHowToSchema({
    name: "중국 쇼핑 영상을 한국어 숏폼으로 자동 변환하는 방법",
    description: "SSMaker로 다운로드한 상품 영상을 한국어 쇼핑 숏폼 콘텐츠로 만드는 기본 절차",
    path: "/",
    steps: [
      "SSMaker를 설치하고 실행합니다.",
      "타오바오/알리익스프레스 등에서 원본 영상을 불러옵니다.",
      "AI 자막 감지와 번역, 블러 처리를 실행합니다.",
      "한국어 스크립트 생성 후 TTS 음성을 합성합니다.",
      "완성된 세일즈 숏폼을 검토하고 내보냅니다.",
    ],
  }),
  buildHowToSchema({
    name: "쿠팡 파트너스 링크로 쇼핑 숏폼을 풀자동 제작하는 방법",
    description: "쿠팡 파트너스 단축 링크를 SSMaker에 넣어 상품 분석, 영상 제작, YouTube Shorts 업로드, Linktree 검수까지 진행하는 절차",
    path: "/",
    steps: [
      "쿠팡 파트너스에서 link.coupang.com/a/... 단축 링크를 생성합니다.",
      "SSMaker 풀자동 화면에 단축 링크를 붙여넣습니다.",
      "영상 소싱과 상품 설명 생성을 확인합니다.",
      "품질 검수 가능한 영상이면 YouTube Shorts 업로드와 Linktree 등록을 진행합니다.",
      "업로드 후 댓글의 상품 설명, 구매 링크, Linktree 링크를 확인합니다.",
    ],
  }),
  buildItemListSchema({
    name: "SSMaker 주요 노출 키워드와 사용 사례",
    description: "검색과 AI 답변 엔진이 SSMaker를 분류할 때 참고할 핵심 사용 사례",
    path: "/",
    items: [
      "중국 쇼핑 영상 한국어 숏폼 변환",
      "구매대행 쇼핑 숏폼 자동 제작",
      "쿠팡 파트너스 링크 기반 영상 자동화",
      "YouTube Shorts 쇼핑 채널 자동 업로드",
      "Linktree 상품 링크 번호 관리",
      "중국어 자막 감지와 블러 처리",
    ],
  }),
  buildSpeakableSchema("/", [
    "meta[name='description']",
    "[aria-label='서비스 요약 정보'] h2",
    "[aria-label='서비스 요약 정보'] p",
    "#answer-engine [data-speakable]",
  ]),
];

const Index = () => {
  return (
    <main className="min-h-screen bg-background">
      <Seo
        title="SSMaker - 쇼핑 숏폼 자동 변환 | AI 영상 편집 솔루션"
        description="SSMaker는 중국 쇼핑 영상을 한국어 쇼핑 숏폼으로 자동 변환하고 쿠팡 파트너스 단축 링크, YouTube Shorts 업로드, Linktree 검수 흐름까지 연결하는 Windows용 AI 영상 자동화 프로그램입니다."
        path="/"
        keywords={SITE_KEYWORDS}
        modifiedTime="2026-08-20"
        structuredData={HOME_STRUCTURED_DATA}
      />
      <Navigation />
      <Hero />
      <PromotionBanner />
      <PainPoints />
      <Solution />
      <Features />
      <Efficiency />
      <Testimonials />
      <DemoVideo />
      <HowItWorks />
      <SetupGuide />
      <Pricing />
      <AnswerEngineSection />
      <FAQSection />
      <FinalCTA />
      {/* GEO/AEO: LLM/검색엔진이 문맥을 쉽게 파악하도록 핵심 답변을 텍스트로 노출 */}
      <section className="sr-only" aria-label="서비스 요약 정보">
        <h2>SSMaker란 무엇인가요?</h2>
        <p>
          SSMaker는 중국 쇼핑 영상을 AI가 자동으로 한국어 숏폼 콘텐츠로 변환하는 Windows 프로그램입니다. 로그인 계정 기준
          매월 5회 무료로 사용할 수 있습니다.
        </p>
        <h2>SSMaker 무료 다운로드 방법</h2>
        <p>
          SSMaker는 공식 웹사이트에서 Microsoft Store 설치와 일반 설치 파일 다운로드를 모두 제공합니다. 자동 업데이트를 원하는
          사용자는 Microsoft Store 방식을 권장하며, 기존 일반 설치판 사용자는 일반 설치 파일을 이용할 수 있습니다. 두 방식은 업데이트
          경로가 다르므로 한 PC에서는 하나만 선택해야 합니다.
        </p>
        <h2>중국 쇼핑 영상을 한국어로 변환하는 방법</h2>
        <p>
          SSMaker를 사용하면 쿠팡 파트너스 단축 링크 또는 원본 쇼핑 영상을 바탕으로 한국어 숏폼 영상 제작 흐름을 자동화할 수
          있습니다. AI 자막 감지, 자동 블러, 번역, TTS 음성 합성까지 한 화면에서 처리합니다.
        </p>
        <h2>구매대행 쇼핑 숏폼 자동 제작 도구</h2>
        <p>
          SSMaker는 구매대행, 스마트스토어, 쿠팡 로켓그로스 셀러들이 중국 상품 영상을 한국어 쇼핑 숏폼으로 대량 생산할
          수 있도록 설계된 AI 자동화 솔루션입니다. 영상 링크 하나로 제작하거나 링크 2~5개를 한 영상으로 섞을 수 있고,
          대기 작업은 한 번에 하나씩 순서대로 처리합니다.
        </p>
        <h2>쿠팡 파트너스 API Key는 필수인가요?</h2>
        <p>
          아닙니다. 쿠팡 파트너스에서 생성한 link.coupang.com/a/... 단축 링크를 SSMaker 풀자동 화면에 넣는다면 쿠팡 API Key는
          필요하지 않습니다. API Key는 원본 coupang.com 상품 URL을 자동 제휴 링크로 변환하고 싶을 때만 선택적으로 사용합니다.
        </p>
        <h2>Linktree 자동 등록은 무엇이 필요한가요?</h2>
        <p>
          처음에는 Linktree 공개 프로필 URL만 저장해도 YouTube 설명과 댓글 검수에 사용할 수 있습니다. Linktree에 상품 카드를
          완전 자동으로 추가하려면 Make, Zapier, n8n, Cloudflare Worker 같은 Webhook 중계 주소가 필요합니다.
        </p>
        <h2>SSMaker 주요 기능</h2>
        <p>
          AI 자막 감지(OCR), 자동 자막 블러 처리, AI 세일즈 스크립트 생성, 한국어 TTS 음성 합성, NVIDIA GPU 가속 처리,
          링크 기반 단일 제작과 영상 링크 2~5개 믹스 제작을 지원합니다. 대기 목록의 작업은 순서대로 처리됩니다.
        </p>
        <h2>SSMaker 가격 및 요금제</h2>
        <p>
          무료 체험은 로그인 계정 기준 매월 5회 제공되며 모든 기능을 동일하게 사용할 수 있습니다. 프로 월 정액은 월 149,000원으로
          무제한 제작, GPU 가속, 링크 기반 단일·믹스 제작, 우선 고객 지원이 포함됩니다. 라이선스는 1인 1PC 기준입니다.
        </p>
        <h2>신규 구독 1개월 추가 제공 이벤트</h2>
        <p>
          2026년 4월 30일부터 2026년 5월 14일까지 신규 가입 후 구독이 확정된 계정에는 구독 기간 1개월이 자동으로 추가됩니다.
          이벤트 종료 후에는 공지 상태가 마감으로 표시되고 추가 1개월 혜택도 자동으로 적용되지 않습니다.
        </p>
        <h2>SSMaker vs 수작업 영상 편집 비교</h2>
        <p>
          수작업으로 쇼핑 영상을 편집할 때 반복되는 자막 감지, 블러, 번역, 음성 합성, 내보내기 단계를 SSMaker에서 한 흐름으로
          처리할 수 있습니다. 작업 시간과 외주 의존도를 줄이고, YouTube Shorts와 Linktree 검수까지 같은 운영 루틴으로 관리할 수 있습니다.
        </p>
        <h2>초보자용 초기 세팅 가이드</h2>
        <p>
          처음 사용하는 분도 4단계로 시작할 수 있습니다. ① 쿠팡 파트너스(쿠파스)에 유튜브 채널과 Linktree URL을 등록하고,
          ② Linktree 계정을 만들어 공개 프로필 URL을 준비합니다. ③ 쿠팡 파트너스에서 상품 단축 링크(link.coupang.com/a/...)를
          생성한 뒤, ④ SSMaker 풀자동 화면에 링크를 붙여넣으면 영상 생성·YouTube Shorts 업로드·Linktree 등록·고정 댓글까지
          자동으로 처리됩니다. 자세한 단계는 홈 화면의 "초기 세팅 가이드" 섹션에서 캡처 예시와 함께 확인할 수 있습니다.
        </p>
        <h2>SSMaker에 GPU가 필요한가요?</h2>
        <p>
          GPU 없이도 CPU 모드로 원활하게 동작합니다. NVIDIA CUDA GPU가 있으면 약 3배 더 빠른 처리 속도를
          경험할 수 있습니다.
        </p>
      </section>
      <Footer />
    </main>
  );
};

export default Index;
