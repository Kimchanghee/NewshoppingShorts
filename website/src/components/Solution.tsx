import { FadeIn } from "@/components/FadeIn";
import { ArrowRight, X, Check } from "lucide-react";

const beforeSteps = [
  "영상 선택 및 다운로드",
  "대본 추출 (또는 대본이 없으면 직접 생성)",
  "추출한 대본 번역",
  "대본으로 TTS 음성 생성",
  "자막 생성 및 편집",
  "외국어 자막 블러 처리",
  "TTS 오디오에 맞춰 자막 싱크 작업",
  "최종 확인",
  "내보내기",
];

const afterSteps = ["영상 선택", "클릭 한 번", "완성"];

export default function Solution() {
  return (
    <section className="relative py-16 sm:py-20 lg:py-28">
      <div className="container mx-auto px-4 sm:px-6">
        <FadeIn>
          <div className="text-center">
            <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">
              <span className="text-gradient">SSMaker</span>가 다 해결합니다
            </h2>
            <p className="mt-4 text-muted-foreground">
              복잡한 과정을 하나로 줄였습니다
            </p>
            <p className="mt-2 text-xs text-muted-foreground/60">
              ※ 작업 성능은 사용하시는 컴퓨터 성능에 따라 차이가 있을 수 있습니다.
            </p>
          </div>
        </FadeIn>

        <div className="mx-auto mt-10 grid max-w-5xl gap-6 sm:mt-12 md:grid-cols-[1fr,auto,1fr] lg:mt-16 lg:gap-8">
          {/* Before */}
          <FadeIn delay={0.1}>
            <div className="glass-card rounded-2xl p-5 sm:p-7 lg:p-8">
              <div className="mb-6 flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-destructive/10">
                  <X className="h-4 w-4 text-destructive" />
                </div>
                <span className="text-sm font-semibold uppercase tracking-wider text-destructive">
                  Before
                </span>
              </div>

              <div className="space-y-3">
                {beforeSteps.map((step, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 rounded-lg bg-background/50 px-4 py-3"
                  >
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
                      {i + 1}
                    </span>
                    <span className="text-sm text-foreground/70">{step}</span>
                  </div>
                ))}
              </div>

              <div className="mt-6 rounded-lg border border-destructive/20 bg-destructive/5 px-4 py-3 text-center">
                <span className="text-sm font-medium text-destructive">
                  1시간 또는 그 이상 / 건
                </span>
              </div>
            </div>
          </FadeIn>

          {/* Arrow */}
          <FadeIn delay={0.2} className="hidden items-center md:flex">
            <div className="flex flex-col items-center gap-2">
              <ArrowRight className="h-8 w-8 text-primary" />
            </div>
          </FadeIn>

          {/* Mobile arrow */}
          <FadeIn delay={0.2} className="flex justify-center md:hidden">
            <ArrowRight className="h-8 w-8 rotate-90 text-primary" />
          </FadeIn>

          {/* After */}
          <FadeIn delay={0.3}>
            <div className="glass-card rounded-2xl border-primary/20 p-5 shadow-glow-sm sm:p-7 lg:p-8">
              <div className="mb-6 flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                  <Check className="h-4 w-4 text-primary" />
                </div>
                <span className="text-sm font-semibold uppercase tracking-wider text-primary">
                  After
                </span>
              </div>

              <div className="space-y-3">
                {afterSteps.map((step, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-3 rounded-lg bg-primary/5 px-4 py-3"
                  >
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/20 text-xs font-medium text-primary">
                      {i + 1}
                    </span>
                    <span className="text-sm font-medium text-foreground/90">
                      {step}
                    </span>
                  </div>
                ))}
              </div>

              <div className="mt-6 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-center">
                <span className="text-sm font-medium text-primary">
                  3~5분 / 건
                </span>
              </div>
            </div>
          </FadeIn>
        </div>
      </div>
    </section>
  );
}
