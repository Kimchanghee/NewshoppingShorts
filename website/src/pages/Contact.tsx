import Navigation from "@/components/Navigation";
import Footer from "@/components/Footer";
import { FadeIn } from "@/components/FadeIn";
import { ArrowLeft, MessageCircle } from "lucide-react";
import { Link } from "react-router-dom";
import Seo from "@/components/Seo";
import { SITE_KAKAO_OPENCHAT_URL, SITE_KEYWORDS } from "@/constants/site";
import { buildBreadcrumbSchema, buildContactPageSchema, buildOrganizationSchema, buildWebPageSchema } from "@/lib/structuredData";
import { gaEvent } from "@/lib/ga4";

export default function Contact() {
  const contactPath = "/contact/index.html";
  const structuredData = [
    buildOrganizationSchema(),
    buildContactPageSchema(contactPath),
    buildBreadcrumbSchema([
      { name: "홈", path: "/" },
      { name: "문의하기", path: contactPath },
    ]),
    buildWebPageSchema({
      name: "문의하기 | SSMaker",
      description: "SSMaker 문의 접수 페이지. 카카오톡 오픈채팅으로 문의할 수 있습니다.",
      path: contactPath,
      breadcrumbPaths: [
        { name: "홈", path: "/" },
        { name: "문의하기", path: contactPath },
      ],
    }),
  ];

  return (
    <div className="min-h-screen bg-background">
      <Seo
        title="문의하기 | SSMaker"
        description="SSMaker 사용 중 궁금한 점, 제안, 파트너십 문의를 카카오톡으로 접수하세요."
        path={contactPath}
        keywords={[...SITE_KEYWORDS, "SSMaker 문의", "카카오톡 문의"]}
        structuredData={structuredData}
      />
      <Navigation />

      <div className="container mx-auto px-4 pb-16 pt-24 sm:px-6 sm:pb-20 sm:pt-32">
        <FadeIn>
          <Link
            to="/"
            className="mb-6 inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            홈으로 돌아가기
          </Link>
        </FadeIn>

        <div className="mx-auto max-w-4xl">
          <div className="mb-8 text-center sm:mb-12">
            <h1 className="mb-4 text-3xl font-bold text-foreground md:text-4xl">문의하기</h1>
            <p className="text-muted-foreground">SSMaker에 대한 궁금한 점이나 제안사항을 보내주세요</p>
          </div>

          <FadeIn delay={0.1}>
            <div className="mx-auto max-w-lg">
              <div className="glass-card rounded-xl p-5 text-center sm:p-8">
                <div className="mb-6 flex justify-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-yellow-400/20">
                    <MessageCircle className="h-8 w-8 text-yellow-400" />
                  </div>
                </div>

                <h2 className="mb-4 text-xl font-semibold text-foreground">카카오톡 문의하기</h2>
                <p className="mb-6 text-sm text-muted-foreground">
                  아래 버튼을 클릭하시면 카카오톡 오픈채팅으로 연결됩니다.
                </p>

                <a
                  href={SITE_KAKAO_OPENCHAT_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => gaEvent("contact_click", { placement: "contact_page", channel: "kakao" })}
                  className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-lg bg-yellow-400 px-5 py-3 font-semibold text-black transition-colors hover:bg-yellow-500 sm:w-auto sm:px-8"
                >
                  <MessageCircle className="h-5 w-5" />
                  카카오톡으로 문의하기
                </a>
              </div>

              <div className="mt-8 rounded-lg border border-border/50 bg-secondary/20 p-4">
                <p className="text-sm text-muted-foreground">
                  <strong className="text-foreground">운영 시간:</strong> 평일 09:00 - 18:00 (주말 및 공휴일 제외)
                  <br />
                  문의 응답은 영업일 기준 1-2일 소요됩니다.
                </p>
              </div>
            </div>
          </FadeIn>
        </div>
      </div>

      <Footer />
    </div>
  );
}
