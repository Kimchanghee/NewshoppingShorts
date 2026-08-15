import { FadeIn } from "@/components/FadeIn";
import { Clock, Languages, Monitor, Wallet } from "lucide-react";

const painPoints = [
  {
    icon: Clock,
    text: "중국어 영상 하나 한국어로 바꾸는데 30분 이상 걸림",
  },
  {
    icon: Languages,
    text: "자막 하나하나 수동으로 번역하고, 음성 따로 녹음하고...",
  },
  {
    icon: Monitor,
    text: "영상 10개 만들려면 하루 종일 모니터 앞에 앉아야 함",
  },
  {
    icon: Wallet,
    text: "외주 맡기면 영상 하나에 2~5만원, 수익이 남지 않음",
  },
];

export default function PainPoints() {
  return (
    <section className="relative py-24 md:py-32">
      <div className="section-glow absolute inset-0" />
      <div className="container relative mx-auto px-6">
        <FadeIn>
          <div className="text-center">
            <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">
              이런 경험, 있지 않으세요?
            </h2>
            <p className="mt-4 text-muted-foreground">
              쇼핑 숏폼 제작의 현실
            </p>
          </div>
        </FadeIn>

        <div className="mx-auto mt-16 grid max-w-4xl gap-4 sm:grid-cols-2">
          {painPoints.map((item, i) => (
            <FadeIn key={i} delay={i * 0.1}>
              <div className="glass-card group flex items-start gap-4 rounded-xl p-6 transition-all duration-300 hover:border-destructive/30">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-destructive/10">
                  <item.icon className="h-5 w-5 text-destructive" />
                </div>
                <p className="text-[15px] leading-relaxed text-foreground/80">
                  {item.text}
                </p>
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}
