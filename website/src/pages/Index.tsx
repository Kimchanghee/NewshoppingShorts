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
import {
  buildBreadcrumbSchema,
  buildItemListSchema,
  buildOrganizationSchema,
  buildSoftwareApplicationSchema,
  buildWebPageSchema,
  buildWebsiteSchema,
} from "@/lib/structuredData";

const HOME_STRUCTURED_DATA = [
  buildOrganizationSchema(),
  buildWebsiteSchema(),
  buildSoftwareApplicationSchema(),
  buildBreadcrumbSchema([{ name: "홈", path: "/" }]),
  buildWebPageSchema({
    name: "SSMaker 홈 | 쇼핑 숏폼 자동화",
    description: "중국 쇼핑 영상을 한국어 쇼핑 숏폼으로 자동 변환하고 쿠팡 파트너스, YouTube Shorts, Linktree 흐름을 연결하는 AI 솔루션 소개 페이지",
    path: "/",
    breadcrumbPaths: [{ name: "홈", path: "/" }],
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
];

const Index = () => {
  return (
    <main className="min-h-screen bg-background">
      <Seo
        title="SSMaker - 쇼핑 숏폼 자동 변환 | AI 영상 편집 솔루션"
        description="SSMaker는 중국 쇼핑 영상을 한국어 쇼핑 숏폼으로 자동 변환하고 쿠팡 파트너스 단축 링크, YouTube Shorts 업로드, Linktree 검수 흐름까지 연결하는 Windows용 AI 영상 자동화 프로그램입니다."
        path="/"
        keywords={SITE_KEYWORDS}
        modifiedTime="2026-08-16"
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
      <Footer />
    </main>
  );
};

export default Index;
