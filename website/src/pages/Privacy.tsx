import Footer from "@/components/Footer";
import { FadeIn } from "@/components/FadeIn";
import Navigation from "@/components/Navigation";
import Seo from "@/components/Seo";
import { SITE_KEYWORDS, SITE_SUPPORT_EMAIL } from "@/constants/site";
import { buildBreadcrumbSchema, buildOrganizationSchema, buildWebPageSchema } from "@/lib/structuredData";
import { ArrowLeft, Mail } from "lucide-react";
import { Link } from "react-router-dom";

const sections = [
  {
    title: "1. 처리하는 정보",
    items: [
      "회원가입 및 인증: 이름, 아이디, 비밀번호의 단방향 해시, 연락처, 선택 입력 이메일, 가입·접속 IP, 로그인 및 앱 버전 기록",
      "구독 및 결제: 구독 상태, 결제 식별자와 처리 결과. 정기 결제용 키가 필요한 경우 암호화하여 보관하며 카드 원문 전체를 직접 저장하지 않습니다.",
      "앱 기능: 이용자가 직접 입력한 상품 URL, API 설정, 영상·음성·자막 파일과 작업 결과. 대부분의 제작 데이터와 외부 서비스 인증 정보는 이용자의 PC에 저장됩니다.",
      "선택적 소식 수신: 이용자가 별도로 동의한 경우 이메일 주소와 동의 기록",
    ],
  },
  {
    title: "2. 이용 목적",
    paragraphs: [
      "계정 생성과 본인 인증, 중복 로그인 방지, 무료 체험·구독 및 작업량 관리, 결제 처리, 고객 지원, 오류·보안 대응, 앱 업데이트 제공에 사용합니다.",
    ],
  },
  {
    title: "3. 외부 서비스와 제공",
    paragraphs: [
      "이용자가 해당 기능을 실행할 때 YouTube, Instagram, TikTok, Threads, Linktree, 쿠팡 파트너스, 생성형 AI 및 음성·영상 처리 서비스의 API로 이용자가 선택한 콘텐츠나 인증 정보가 전송될 수 있습니다. 각 서비스의 처리는 해당 사업자의 개인정보처리방침을 따릅니다. 서버 운영·결제·보안에 필요한 범위에서 클라우드 호스팅 및 결제 처리 사업자가 수탁 처리할 수 있습니다.",
    ],
  },
  {
    title: "4. 보유 및 삭제",
    paragraphs: [
      "개인정보는 서비스 제공과 법적 의무 이행에 필요한 기간 동안만 보유하고 목적이 끝나면 안전하게 삭제하거나 익명화합니다. 이용자는 앱 설정에서 로컬 데이터와 외부 서비스 연결 정보를 삭제할 수 있으며, 계정 정보의 열람·정정·삭제는 아래 문의처로 요청할 수 있습니다.",
    ],
  },
  {
    title: "5. 보호 조치",
    paragraphs: [
      "전송 구간 암호화(HTTPS), 비밀번호 해시, 민감한 결제 키 암호화, 접근 권한 제한, 요청 속도 제한과 보안 로그 최소화를 적용합니다.",
    ],
  },
  {
    title: "6. 이용자의 선택과 권리",
    paragraphs: [
      "선택 정보 제공과 마케팅 수신을 거부할 수 있으며, 거부해도 핵심 앱 기능 이용에는 영향을 주지 않습니다. 외부 플랫폼 연결은 이용자가 직접 설정하고 언제든 해제할 수 있습니다.",
    ],
  },
  {
    title: "7. 아동의 개인정보",
    paragraphs: [
      "SSMaker는 아동을 대상으로 설계된 서비스가 아니며, 법정대리인의 동의 없이 아동의 개인정보를 의도적으로 수집하지 않습니다.",
    ],
  },
  {
    title: "8. 방침 변경 및 문의",
    paragraphs: [
      "중요한 변경은 앱 또는 공식 웹사이트를 통해 알립니다. 개인정보 관련 문의나 권리 행사는 아래 고객 지원 이메일 또는 문의 페이지로 접수해 주세요.",
    ],
  },
];

export default function Privacy() {
  const privacyPath = "/privacy/index.html";
  const structuredData = [
    buildOrganizationSchema(),
    buildBreadcrumbSchema([
      { name: "홈", path: "/" },
      { name: "개인정보처리방침", path: privacyPath },
    ]),
    buildWebPageSchema({
      name: "개인정보처리방침 | SSMaker",
      description: "SSMaker 데스크톱 앱과 인증·구독 서비스의 개인정보 처리 기준을 안내합니다.",
      path: privacyPath,
      breadcrumbPaths: [
        { name: "홈", path: "/" },
        { name: "개인정보처리방침", path: privacyPath },
      ],
    }),
  ];

  return (
    <div className="min-h-screen bg-background">
      <Seo
        title="개인정보처리방침 | SSMaker"
        description="SSMaker 데스크톱 앱과 인증·구독 서비스의 개인정보 처리 기준, 보유 및 삭제, 이용자 권리를 안내합니다."
        path={privacyPath}
        keywords={[...SITE_KEYWORDS, "SSMaker 개인정보처리방침", "개인정보 보호"]}
        structuredData={structuredData}
      />
      <Navigation />

      <main className="container mx-auto px-6 pb-20 pt-32">
        <FadeIn>
          <Link
            to="/"
            className="mb-6 inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            홈으로 돌아가기
          </Link>
        </FadeIn>

        <div className="mx-auto max-w-4xl">
          <FadeIn delay={0.05}>
            <header className="mb-10 border-b border-border/70 pb-8">
              <p className="mb-3 text-sm font-semibold text-primary">PRIVACY</p>
              <h1 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">SSMaker 개인정보처리방침</h1>
              <p className="mt-4 text-sm text-muted-foreground">시행일: 2026년 8월 6일</p>
              <p className="mt-5 leading-7 text-muted-foreground">
                YMcompany(이하 “회사”)는 SSMaker 데스크톱 앱과 인증·구독 서비스를 제공하면서 이용자의 개인정보를
                안전하게 처리합니다.
              </p>
            </header>
          </FadeIn>

          <div className="space-y-5">
            {sections.map((section, index) => (
              <FadeIn key={section.title} delay={0.08 + index * 0.025}>
                <section className="glass-card rounded-2xl p-6 md:p-8">
                  <h2 className="mb-4 text-xl font-semibold text-foreground">{section.title}</h2>
                  {section.paragraphs?.map((paragraph) => (
                    <p key={paragraph} className="leading-7 text-muted-foreground">
                      {paragraph}
                    </p>
                  ))}
                  {section.items && (
                    <ul className="space-y-3 pl-5 text-muted-foreground">
                      {section.items.map((item) => (
                        <li key={item} className="list-disc leading-7 marker:text-primary">
                          {item}
                        </li>
                      ))}
                    </ul>
                  )}
                  {section.title.startsWith("8.") && (
                    <div className="mt-5 flex flex-col gap-3 sm:flex-row">
                      <a
                        href={`mailto:${SITE_SUPPORT_EMAIL}`}
                        className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
                      >
                        <Mail className="h-4 w-4" aria-hidden="true" />
                        {SITE_SUPPORT_EMAIL}
                      </a>
                      <Link
                        to="/contact/index.html"
                        className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border px-5 py-3 text-sm font-semibold text-foreground transition-colors hover:bg-secondary"
                      >
                        고객 지원 페이지
                      </Link>
                    </div>
                  )}
                </section>
              </FadeIn>
            ))}
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
