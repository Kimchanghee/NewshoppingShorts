import { useRef, useState } from "react";
import { ArrowRight, Download, Pause, Play, Sparkles } from "lucide-react";

import Footer from "@/components/Footer";
import Navigation from "@/components/Navigation";
import Seo from "@/components/Seo";
import { Button } from "@/components/ui/button";
import { DOWNLOAD_URL } from "@/constants/release";
import { SITE_KEYWORDS } from "@/constants/site";
import { VIDEO_SAMPLES, type SampleCategory, type VideoSample } from "@/data/samples";
import { gaEvent } from "@/lib/ga4";
import { buildBreadcrumbSchema, buildItemListSchema, buildVideoObjectSchema, buildWebPageSchema } from "@/lib/structuredData";

type Filter = "all" | SampleCategory;

const SAMPLE_STRUCTURED_DATA = [
  buildBreadcrumbSchema([
    { name: "홈", path: "/" },
    { name: "샘플", path: "/samples/index.html" },
  ]),
  buildWebPageSchema({
    name: "SSMaker Before / After 영상 갤러리",
    description: "원본 영상과 SSMaker로 완성한 결과를 나란히 재생하며 화면 구성, 음성, 자막의 변화를 확인하는 영상 갤러리",
    path: "/samples/index.html",
    breadcrumbPaths: [
      { name: "홈", path: "/" },
      { name: "샘플", path: "/samples/index.html" },
    ],
  }),
  buildItemListSchema({
    name: "SSMaker Before / After 영상 샘플",
    description: "원본 영상과 SSMaker 제작 결과를 나란히 확인하는 Before / After 갤러리",
    path: "/samples/index.html",
    items: VIDEO_SAMPLES.map((sample) => `${sample.title} ${sample.categoryLabel} Before / After`),
  }),
  ...VIDEO_SAMPLES.flatMap((sample) =>
    (["before", "after"] as const).map((kind) => {
      const isBefore = kind === "before";
      const label = isBefore ? "Before 원본" : "After SSMaker 제작본";
      const pageUrl = "https://shoppingshorts.store/samples/index.html";
      const watchUrl = `${pageUrl}#sample-${sample.id}`;
      return buildVideoObjectSchema({
        id: `${watchUrl}-${kind}`,
        name: `${sample.title} ${label}`,
        description: `${sample.description} ${label} 영상입니다.`,
        thumbnailUrl: isBefore ? sample.beforePoster : sample.afterPoster,
        uploadDate: sample.uploadDate,
        contentUrl: isBefore ? sample.beforeVideo : sample.afterVideo,
        duration: isBefore ? sample.beforeDuration : sample.afterDuration,
        pageUrl,
        watchUrl,
      });
    }),
  ),
];

const FILTERS: Array<{ value: Filter; label: string }> = [
  { value: "all", label: "전체" },
  { value: "ocr", label: "자막 정리" },
  { value: "automation", label: "쇼핑 숏폼" },
];

function VideoPanel({
  sample,
  kind,
  videoRef,
}: {
  sample: VideoSample;
  kind: "before" | "after";
  videoRef: React.RefObject<HTMLVideoElement>;
}) {
  const isBefore = kind === "before";
  const label = isBefore ? "Before · 원본" : "After · SSMaker 제작본";
  const video = isBefore ? sample.beforeVideo : sample.afterVideo;
  const poster = isBefore ? sample.beforePoster : sample.afterPoster;

  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-black/40">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <span className={`text-sm font-semibold ${isBefore ? "text-white/70" : "text-red-300"}`}>{label}</span>
        <span className="text-[11px] uppercase tracking-[0.18em] text-white/35">MP4</span>
      </div>
      <div className="relative mx-auto aspect-[9/16] max-h-[620px] bg-[#080808] sm:max-h-[680px] md:max-h-[600px] lg:max-h-[680px]">
        <video
          ref={videoRef}
          className="h-full w-full object-contain"
          controls
          playsInline
          preload="metadata"
          poster={poster}
          data-testid="sample-video"
          data-sample-id={sample.id}
          data-kind={kind}
          aria-label={`${sample.title} ${label} 영상`}
        >
          <source src={video} type="video/mp4" />
          브라우저가 MP4 영상 재생을 지원하지 않습니다.
        </video>
      </div>
    </div>
  );
}

function SampleCard({ sample }: { sample: VideoSample }) {
  const beforeRef = useRef<HTMLVideoElement>(null);
  const afterRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const togglePair = async () => {
    const before = beforeRef.current;
    const after = afterRef.current;
    if (!before || !after) return;

    if (isPlaying) {
      before.pause();
      after.pause();
      setIsPlaying(false);
      return;
    }

    before.currentTime = 0;
    after.currentTime = 0;
    before.muted = true;
    after.muted = false;
    const results = await Promise.allSettled([before.play(), after.play()]);
    const started = results.some((result) => result.status === "fulfilled");
    setIsPlaying(started);
    gaEvent("sample_pair_play", { sample_id: sample.id, category: sample.category });
  };

  const stopPair = () => {
    beforeRef.current?.pause();
    afterRef.current?.pause();
    setIsPlaying(false);
  };

  return (
    <article
      id={`sample-${sample.id}`}
      data-testid="sample-card"
      className="scroll-mt-24 overflow-hidden rounded-[28px] border border-white/10 bg-white/[0.035] shadow-2xl shadow-black/20"
    >
      <div className="flex flex-col gap-5 border-b border-white/10 px-5 py-6 sm:px-7 md:flex-row md:items-center md:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-red-400/25 bg-red-500/10 text-sm font-bold text-red-300">
            {String(sample.id).padStart(2, "0")}
          </span>
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-white/60">
                {sample.categoryLabel}
              </span>
            </div>
            <h2 className="text-xl font-bold tracking-tight text-white sm:text-2xl">{sample.title}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/50">{sample.description}</p>
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          className="min-h-11 w-full shrink-0 border-white/15 bg-white/5 text-white hover:bg-white/10 hover:text-white md:w-auto"
          onClick={togglePair}
          aria-label={`${sample.title} Before/After ${isPlaying ? "동시에 일시정지" : "동시에 재생"}`}
        >
          {isPlaying ? <Pause className="mr-2 h-4 w-4" /> : <Play className="mr-2 h-4 w-4" />}
          {isPlaying ? "함께 일시정지" : "두 영상 함께 재생"}
        </Button>
      </div>

      <div className="grid gap-px bg-white/10 p-px md:grid-cols-2">
        <VideoPanel sample={sample} kind="before" videoRef={beforeRef} />
        <div onEnded={stopPair}>
          <VideoPanel sample={sample} kind="after" videoRef={afterRef} />
        </div>
      </div>
    </article>
  );
}

export default function Samples() {
  const [filter, setFilter] = useState<Filter>("all");
  const visibleSamples = filter === "all" ? VIDEO_SAMPLES : VIDEO_SAMPLES.filter((sample) => sample.category === filter);

  return (
    <main className="min-h-screen overflow-hidden bg-background">
      <Seo
        title="Before / After 영상 갤러리 | SSMaker"
        description="원본 상품 영상과 SSMaker로 완성한 결과를 나란히 재생하며 화면 구성, 한국어 음성, 자막의 변화를 직접 비교해 보세요."
        path="/samples/index.html"
        keywords={[...SITE_KEYWORDS, "SSMaker 샘플", "Before After 영상", "영상 자막 정리 예시"]}
        modifiedTime="2026-08-16"
        structuredData={SAMPLE_STRUCTURED_DATA}
      />
      <Navigation />

      <section className="relative border-b border-white/10 pb-16 pt-28 sm:pb-20 sm:pt-36 lg:pb-24 lg:pt-40">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_20%,rgba(220,38,38,0.18),transparent_46%)]" />
        <div className="container relative mx-auto px-4 text-center sm:px-6">
          <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-red-400/20 bg-red-500/10 px-4 py-2 text-sm font-medium text-red-200">
            <Sparkles className="h-4 w-4" />
            SSMaker 영상 갤러리
          </div>
          <h1 className="text-balance text-[2.35rem] font-extrabold leading-[1.08] tracking-[-0.04em] text-white sm:text-5xl md:text-6xl lg:text-7xl">
            상품 영상이 달라지는 과정을
            <br />
            <span className="text-gradient">직접 비교해 보세요</span>
          </h1>
          <p className="mx-auto mt-6 max-w-3xl text-balance text-base leading-7 text-white/55 sm:text-lg">
            원본과 완성 영상을 나란히 재생하며 화면 구성과 음성, 자막이 어떻게 달라지는지 자연스럽게 확인해 보세요.
          </p>

          <div className="mx-auto mt-10 grid max-w-4xl items-stretch gap-3 text-left md:grid-cols-[minmax(0,1fr)_3.5rem_minmax(0,1fr)] md:gap-4">
            <div className="glass-card flex min-h-32 flex-col justify-center rounded-3xl px-6 py-6 sm:px-8">
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-white/40">Before</span>
              <strong className="mt-2 text-xl font-bold text-white sm:text-2xl">원본 영상</strong>
              <span className="mt-2 text-sm leading-6 text-white/45">편집 전 화면과 소리를 그대로 확인합니다.</span>
            </div>
            <div className="flex h-10 items-center justify-center self-center md:h-full">
              <span className="flex h-10 w-10 items-center justify-center rounded-full border border-red-400/25 bg-red-500/10 text-red-300">
                <ArrowRight className="h-5 w-5 rotate-90 md:rotate-0" aria-hidden="true" />
              </span>
            </div>
            <div className="glass-card flex min-h-32 flex-col justify-center rounded-3xl border-red-400/20 bg-red-500/[0.07] px-6 py-6 sm:px-8">
              <span className="text-xs font-semibold uppercase tracking-[0.2em] text-red-300/70">After</span>
              <strong className="mt-2 text-xl font-bold text-white sm:text-2xl">SSMaker 완성 영상</strong>
              <span className="mt-2 text-sm leading-6 text-white/45">쇼츠에 맞춘 화면과 음성, 자막을 함께 비교합니다.</span>
            </div>
          </div>
        </div>
      </section>

      <section className="container mx-auto px-4 py-16 sm:px-6 sm:py-20" aria-label="Before After 영상 샘플 목록">
        <div className="mb-10 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-red-400">Before · After</p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">완성 결과 살펴보기</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-white/50">
              각 영상의 기본 컨트롤로 따로 재생하거나, 카드 상단의 버튼으로 원본은 음소거하고 제작본 음성과 함께 동시에 재생할 수 있습니다.
            </p>
          </div>
          <div className="flex flex-wrap gap-2" role="group" aria-label="샘플 유형 필터">
            {FILTERS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setFilter(item.value)}
                aria-pressed={filter === item.value}
                className={`min-h-11 rounded-full border px-4 py-2 text-sm transition-colors ${
                  filter === item.value
                    ? "border-red-400/40 bg-red-500/15 text-red-200"
                    : "border-white/10 bg-white/[0.03] text-white/50 hover:border-white/20 hover:text-white"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-10">
          {visibleSamples.map((sample) => (
            <SampleCard key={sample.id} sample={sample} />
          ))}
        </div>
      </section>

      <section className="border-t border-white/10 py-16 sm:py-20">
        <div className="container mx-auto px-4 text-center sm:px-6">
          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">내 상품 영상도 같은 흐름으로</h2>
          <p className="mx-auto mt-4 max-w-2xl text-white/50">SSMaker를 설치하고 상품 링크 또는 원본 영상으로 직접 결과를 만들어 보세요.</p>
          <Button variant="hero" size="lg" asChild className="mt-8 min-h-12 w-full max-w-sm sm:w-auto">
            <a href={DOWNLOAD_URL} rel="noopener noreferrer" onClick={() => gaEvent("download_click", { placement: "samples_bottom" })}>
              <Download className="mr-2 h-5 w-5" />
              Microsoft Store에서 받기
            </a>
          </Button>
        </div>
      </section>

      <Footer />
    </main>
  );
}
