import { FadeIn } from "@/components/FadeIn";
import { Button } from "@/components/ui/button";
import { Check, Download, Zap } from "lucide-react";
import { DOWNLOAD_URL } from "@/constants/release";
import { gaEvent } from "@/lib/ga4";

const plans = [
  {
    name: "무료 체험",
    price: "₩0",
    description: "SSMaker의 모든 기능을 무료로 체험해 보세요",
    features: [
      "매월 5회 무료 영상 생성",
      "모든 핵심 기능 체험",
      "자막 감지 + 자막 블러",
      "AI 스크립트 생성",
      "TTS 음성 합성",
    ],
    cta: "Microsoft Store에서 무료 설치",
    ctaIcon: Download,
    href: DOWNLOAD_URL,
    popular: false,
  },
  {
    name: "프로 월 정액",
    price: "₩149,000",
    period: "/월",
    description: "제한 없이 대량 콘텐츠를 생산하세요",
    features: [
      "무제한 영상 생성",
      "GPU 가속 지원",
      "링크 기반 단일·믹스 제작",
      "우선 기술 지원",
      "이벤트 기간 신규 구독 시 1개월 추가",
    ],
    cta: "구독 문의하기",
    ctaIcon: Zap,
    href: "/contact/index.html",
    popular: true,
  },
];

export default function Pricing() {
  const downloadUrl = DOWNLOAD_URL;
  return (
    <section id="pricing" className="relative py-24 md:py-32">
      <div className="section-glow absolute inset-0" />
      <div className="container relative mx-auto px-6">
        <FadeIn>
          <div className="text-center">
            <p className="mb-3 text-sm font-medium uppercase tracking-widest text-primary">Pricing</p>
            <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">합리적인 요금제</h2>
            <p className="mt-4 text-muted-foreground">필요에 맞는 플랜을 선택하세요</p>
          </div>
        </FadeIn>

        <div className="mx-auto mt-16 grid max-w-4xl gap-8 md:grid-cols-2">
          {plans.map((plan, i) => (
            <FadeIn key={i} delay={i * 0.15}>
              <div
                className={`glass-card relative flex h-full flex-col rounded-2xl p-8 transition-all duration-300 ${
                  plan.popular ? "border-primary/30 shadow-glow" : "hover:border-primary/20"
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                    <span className="rounded-full bg-primary px-4 py-1 text-xs font-semibold text-primary-foreground">
                      이벤트 적용
                    </span>
                  </div>
                )}

                <div className="mb-6">
                  <h3 className="text-lg font-semibold text-foreground">{plan.name}</h3>
                  <div className="mt-3 flex items-baseline gap-1">
                    <span className="text-4xl font-bold text-foreground">{plan.price}</span>
                    {plan.period && <span className="text-muted-foreground">{plan.period}</span>}
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{plan.description}</p>
                </div>

                <ul className="mb-8 flex-1 space-y-3">
                  {plan.features.map((feature, j) => (
                    <li key={j} className="flex items-center gap-3">
                      <Check className="h-4 w-4 shrink-0 text-primary" />
                      <span className="text-sm text-muted-foreground">{feature}</span>
                    </li>
                  ))}
                </ul>

                <Button
                  asChild
                  variant={plan.popular ? "default" : "outline"}
                  className={plan.popular ? "bg-gradient-primary-hover w-full shadow-glow-sm" : "w-full"}
                >
                  <a
                    href={plan.href === DOWNLOAD_URL ? downloadUrl : plan.href}
                    rel="noopener noreferrer"
                    onClick={() =>
                      gaEvent(plan.href === DOWNLOAD_URL ? "download_click" : "contact_click", {
                        placement: "pricing",
                        plan: plan.name,
                      })
                    }
                  >
                    <plan.ctaIcon className="mr-2 h-4 w-4" />
                    {plan.cta}
                  </a>
                </Button>
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}
