import { FadeIn } from "@/components/FadeIn";
import { FileVideo, Settings, Play } from "lucide-react";

const steps = [
  {
    icon: FileVideo,
    number: "01",
    title: "영상 파일 선택",
    description: "영상 파일을 선택하거나 URL을 입력하세요.",
  },
  {
    icon: Settings,
    number: "02",
    title: "옵션 설정",
    description:
      "자막 블러, TTS, 스크립트 생성 등 원하는 옵션을 ON/OFF 하세요.",
  },
  {
    icon: Play,
    number: "03",
    title: "처리 시작",
    description:
      '"영상 처리 시작" 클릭 한 번이면 완성된 한국어 숏폼 영상이 출력됩니다.',
  },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="relative py-24 md:py-32">
      <div className="section-glow absolute inset-0" />
      <div className="container relative mx-auto px-6">
        <FadeIn>
          <div className="text-center">
            <p className="mb-3 text-sm font-medium uppercase tracking-widest text-primary">
              How it works
            </p>
            <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">
              복잡한 과정은 AI가 해결합니다
            </h2>
            <p className="mt-4 text-muted-foreground max-w-2xl mx-auto">
              영상 다운로드부터 번역, 편집, 자막, 더빙까지. SSMaker는 이 모든 과정을 단 3단계로 압축했습니다.
            </p>
          </div>
        </FadeIn>

        <div className="mx-auto mt-16 grid max-w-4xl gap-8 md:grid-cols-3">
          {steps.map((step, i) => (
            <FadeIn key={i} delay={i * 0.15}>
              <div className="relative text-center">
                {/* Connector line */}
                {i < steps.length - 1 && (
                  <div className="absolute left-[calc(50%+40px)] right-[calc(-50%+40px)] top-10 hidden border-t border-dashed border-border md:block" />
                )}

                <div className="relative mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-2xl glass-card">
                  <step.icon className="h-8 w-8 text-primary" />
                  <span className="absolute -right-2 -top-2 flex h-7 w-7 items-center justify-center rounded-full bg-gradient-primary text-xs font-bold text-primary-foreground">
                    {step.number}
                  </span>
                </div>

                <h3 className="mb-2 text-lg font-semibold text-foreground">
                  {step.title}
                </h3>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {step.description}
                </p>
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}
