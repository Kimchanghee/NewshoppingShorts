import { FadeIn } from "@/components/FadeIn";
import { Quote } from "lucide-react";
import { useEffect, useRef, useState } from "react";

interface Testimonial {
  content: string;
  author: string;
  role: string;
  platform: "YouTube" | "Blog" | "Store" | "Cafe";
}

const testimonials: Testimonial[] = [
  {
    content:
      "쿠팡 파트너스 상품 링크를 기준으로 영상 제작과 업로드 흐름을 한 화면에서 관리해야 할 때 적합한 구성입니다.",
    author: "구매대행 셀러",
    role: "상품 소싱·쇼츠 운영",
    platform: "Store",
  },
  {
    content:
      "중국어 자막 감지, 블러, 한국어 스크립트와 TTS를 반복 작업해야 하는 운영자에게 시간을 줄여주는 방식입니다.",
    author: "스마트스토어 운영자",
    role: "중국 상품 영상 현지화",
    platform: "Blog",
  },
  {
    content:
      "YouTube Shorts 업로드 후 댓글에 상품 설명과 Linktree 링크를 남기는 검수 흐름까지 포함할 수 있습니다.",
    author: "쇼핑 채널 운영자",
    role: "유튜브 쇼핑 채널 운영",
    platform: "YouTube",
  },
  {
    content:
      "상품 링크 제목 앞에 번호를 붙여 Linktree를 정리하는 방식이라, 여러 상품을 연속 업로드할 때 관리가 쉽습니다.",
    author: "1인 셀러",
    role: "1인 셀러 · 쿠팡 로켓그로스",
    platform: "Cafe",
  },
  {
    content:
      "상품 특성을 기반으로 한국어 세일즈 문장을 만들고, 같은 규칙으로 댓글 설명까지 맞추는 운영 방식에 어울립니다.",
    author: "콘텐츠 담당자",
    role: "쇼핑 라이브 콘텐츠팀",
    platform: "YouTube",
  },
  {
    content:
      "반복 영상 제작이 많은 팀에서는 GPU 가속과 병렬 처리 옵션으로 작업 대기 시간을 줄일 수 있습니다.",
    author: "위탁판매 운영자",
    role: "도매꾹 · 위탁판매",
    platform: "Store",
  },
];

// Duplicate for seamless infinite scroll
const duplicated = [...testimonials, ...testimonials];

function TestimonialCard({ item }: { item: Testimonial }) {
  return (
    <div className="glass-card relative flex h-full min-h-[240px] w-[min(340px,calc(100vw-2rem))] shrink-0 flex-col rounded-2xl p-6 sm:min-h-[260px] sm:w-[380px] sm:p-8">
      <Quote className="absolute right-8 top-8 h-8 w-8 text-primary/10" />

      <p className="mb-6 flex-1 leading-relaxed text-foreground/90">{item.content}</p>

      <div className="mt-auto border-t border-border/50 pt-5">
        <div className="font-semibold text-foreground">{item.author}</div>
        <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
          <span>{item.role}</span>
          <span className="h-1 w-1 rounded-full bg-border" />
          <span className="text-primary">{item.platform}</span>
        </div>
      </div>
    </div>
  );
}

export default function Testimonials() {
  const trackRef = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return;

    let raf: number;
    let pos = 0;
    // Total width of the original set (first half)
    const halfWidth = () => track.scrollWidth / 2;

    const step = () => {
      if (!paused) {
        pos += 0.5; // px per frame
        if (pos >= halfWidth()) pos = 0;
        track.style.transform = `translateX(-${pos}px)`;
      }
      raf = requestAnimationFrame(step);
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [paused]);

  return (
    <section
      id="testimonials"
      className="relative overflow-hidden bg-secondary/20 py-16 sm:py-20 lg:py-28"
    >
      <div className="container mx-auto px-4 sm:px-6">
        <FadeIn>
          <div className="mb-10 text-center sm:mb-12 lg:mb-16">
            <p className="mb-3 text-sm font-medium uppercase tracking-widest text-primary">
              Use Cases
            </p>
            <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">
              쇼핑 숏폼 운영에 맞춘 활용 사례
            </h2>
            <p className="mt-4 text-muted-foreground">
              쿠팡 파트너스, YouTube Shorts, Linktree를 함께 쓰는 운영 흐름에 맞춰 설계했습니다
            </p>
          </div>
        </FadeIn>
      </div>

      {/* Infinite carousel */}
      <div
        className="relative"
        onMouseEnter={() => setPaused(true)}
        onMouseLeave={() => setPaused(false)}
      >
        {/* Fade edges */}
        <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-8 bg-gradient-to-r from-background to-transparent sm:w-24 md:w-40" />
        <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-8 bg-gradient-to-l from-background to-transparent sm:w-24 md:w-40" />

        <div
          ref={trackRef}
          className="flex gap-4 px-4 sm:gap-6 sm:px-6"
          style={{ willChange: "transform" }}
        >
          {duplicated.map((item, i) => (
            <TestimonialCard key={i} item={item} />
          ))}
        </div>
      </div>
    </section>
  );
}
