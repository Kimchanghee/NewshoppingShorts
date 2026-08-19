import { FadeIn } from "@/components/FadeIn";
import {
  ScanText,
  EyeOff,
  Sparkles,
  AudioLines,
  Cpu,
  Layers,
} from "lucide-react";

const features = [
  {
    icon: ScanText,
    title: "AI 자막 감지",
    description:
      "영상 속 외국어 자막을 자동으로 인식하여 빠르고 정확하게 추출합니다.",
  },
  {
    icon: EyeOff,
    title: "자동 자막 블러 처리",
    description:
      "원본 외국어 자막을 깔끔하게 제거하여 깨끗한 영상을 확보합니다.",
  },
  {
    icon: Sparkles,
    title: "AI 쇼핑 스크립트 생성",
    description:
      "AI가 상품의 특징을 파악하고 자연스러운 한국어 쇼핑 멘트를 자동 작성합니다.",
  },
  {
    icon: AudioLines,
    title: "한국어 TTS 음성 합성",
    description:
      "전문 성우 수준의 자연스러운 한국어 음성을 자동 생성합니다.",
  },
  {
    icon: Cpu,
    title: "GPU 가속 지원",
    description:
      "NVIDIA CUDA + CuPy로 2~3배 빠른 영상 처리 속도를 경험하세요.",
  },
  {
    icon: Layers,
    title: "링크 기반 단일·믹스 제작",
    description:
      "영상 링크 하나로 제작하거나 링크 2~5개를 한 영상으로 섞고, 대기 작업은 순서대로 안전하게 처리합니다.",
  },
];

export default function Features() {
  return (
    <section id="features" className="relative py-24 md:py-32">
      <div className="section-glow absolute inset-0" />
      <div className="container relative mx-auto px-6">
        <FadeIn>
          <div className="text-center">
            <p className="mb-3 text-sm font-medium uppercase tracking-widest text-primary">
              Features
            </p>
            <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">
              강력한 핵심 기능
            </h2>
            <p className="mt-4 text-muted-foreground">
              영상 변환에 필요한 모든 기능을 하나에 담았습니다
            </p>
          </div>
        </FadeIn>

        <div className="mx-auto mt-16 grid max-w-5xl gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature, i) => (
            <FadeIn key={i} delay={i * 0.08}>
              <div className="glass-card group h-full rounded-xl p-6 transition-all duration-300 hover:border-primary/20 hover:shadow-glow-sm">
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 transition-colors group-hover:bg-primary/15">
                  <feature.icon className="h-5 w-5 text-primary" />
                </div>
                <h3 className="mb-2 font-semibold text-foreground">
                  {feature.title}
                </h3>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {feature.description}
                </p>
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}
