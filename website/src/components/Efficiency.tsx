import { FadeIn } from "@/components/FadeIn";
import { useCountUp } from "@/hooks/useCountUp";
import ROICalculator from "@/components/ROICalculator";

function StatCard({
  value,
  suffix,
  label,
  sublabel,
  delay,
}: {
  value: number;
  suffix: string;
  label: string;
  sublabel: string;
  delay: number;
}) {
  const { count, ref } = useCountUp(value, 2000);

  return (
    <FadeIn delay={delay}>
      <div ref={ref} className="glass-card rounded-xl p-8 text-center">
        <div className="text-4xl font-extrabold text-gradient md:text-5xl">
          {count}
          {suffix}
        </div>
        <p className="mt-3 font-semibold text-foreground">{label}</p>
        <p className="mt-1 text-sm text-muted-foreground">{sublabel}</p>
      </div>
    </FadeIn>
  );
}

const stats = [
  {
    value: 6,
    suffix: "단계",
    label: "반복 작업 통합",
    sublabel: "자막 감지·블러·번역·TTS·업로드 검수",
  },
  {
    value: 4,
    suffix: "개",
    label: "병렬 처리 옵션",
    sublabel: "PC 성능에 따라 동시 처리",
  },
  {
    value: 1,
    suffix: "개",
    label: "상품 링크 기준",
    sublabel: "쿠팡 단축 링크에서 영상 루틴 시작",
  },
  {
    value: 1,
    suffix: "개",
    label: "필요 도구",
    sublabel: "제작·업로드·Linktree 검수를 한 화면에서",
  },
];

export default function Efficiency() {
  return (
    <section id="efficiency" className="relative py-24 md:py-32">
      <div className="container mx-auto px-6">
        <FadeIn>
          <div className="text-center">
            <p className="mb-3 text-sm font-medium uppercase tracking-widest text-primary">
              Efficiency
            </p>
            <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">
              반복 작업을 줄입니다
            </h2>
            <p className="mt-4 text-muted-foreground">
              쇼핑 숏폼 운영자가 매일 반복하는 제작·업로드·링크 정리 흐름에 맞췄습니다
            </p>
          </div>
        </FadeIn>

        <div className="mx-auto mt-16 grid max-w-5xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((stat, i) => (
            <StatCard key={i} {...stat} delay={i * 0.1} />
          ))}
        </div>

        <ROICalculator />
      </div>
    </section>
  );
}
