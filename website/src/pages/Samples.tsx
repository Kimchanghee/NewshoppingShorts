import { useRef, useState } from "react";
import { Download, Pause, Play, ScanText, Sparkles, WandSparkles } from "lucide-react";

import Footer from "@/components/Footer";
import Navigation from "@/components/Navigation";
import Seo from "@/components/Seo";
import { Button } from "@/components/ui/button";
import { DOWNLOAD_URL } from "@/constants/release";
import { SITE_KEYWORDS } from "@/constants/site";
import { SAMPLE_VIDEO_COUNT, VIDEO_SAMPLES, type SampleCategory, type VideoSample } from "@/data/samples";
import { gaEvent } from "@/lib/ga4";
import { buildBreadcrumbSchema, buildItemListSchema, buildWebPageSchema } from "@/lib/structuredData";

type Filter = "all" | SampleCategory;

const SAMPLE_STRUCTURED_DATA = [
  buildBreadcrumbSchema([
    { name: "홈", path: "/" },
    { name: "샘플", path: "/samples/index.html" },
  ]),
  buildWebPageSchema({
    name: "SSMaker Before / After 영상 샘플 10개",
    description: "SSMaker가 실제로 처리한 OCR 자막 블러 5건과 풀자동 쇼핑 숏폼 제작 5건의 원본·완성본 비교 페이지",
    path: "/samples/index.html",
    breadcrumbPaths: [
      { name: "홈", path: "/" },
      { name: "샘플", path: "/samples/index.html" },
    ],
  }),
  buildItemListSchema({
    name: "SSMaker Before / After 영상 샘플",
    description: "원본 10개와 SSMaker 제작본 10개를 나란히 확인하는 실제 처리 샘플",
    path: "/samples/index.html",
    items: VIDEO_SAMPLES.map((sample) => `${sample.title} ${sample.categoryLabel} Before / After`),
  }),
];

const FILTERS: Array<{ value: Filter; label: string; count: number }> = [
  { value: "all", label: "전체", count: 10 },
  { value: "ocr", label: "OCR 자막 블러", count: 5 },
  { value: "automation", label: "풀자동 제작", count: 5 },
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
      <div className="relative mx-auto aspect-[9/16] max-h-[680px] bg-[#080808]">
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
      <div className="flex flex-col gap-5 border-b border-white/10 px-5 py-6 sm:px-7 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-red-400/25 bg-red-500/10 text-sm font-bold text-red-300">
            {String(sample.id).padStart(2, "0")}
          </span>
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-white/60">
                {sample.categoryLabel}
              </span>
              {sample.id > 5 ? (
                <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs font-medium text-emerald-300">
                  신규 추가
                </span>
              ) : null}
            </div>
            <h2 className="text-xl font-bold tracking-tight text-white sm:text-2xl">{sample.title}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-white/50">{sample.description}</p>
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          className="shrink-0 border-white/15 bg-white/5 text-white hover:bg-white/10 hover:text-white"
          onClick={togglePair}
          aria-label={`${sample.title} Before/After ${isPlaying ? "동시에 일시정지" : "동시에 재생"}`}
        >
          {isPlaying ? <Pause className="mr-2 h-4 w-4" /> : <Play className="mr-2 h-4 w-4" />}
          {isPlaying ? "함께 일시정지" : "두 영상 함께 재생"}
        </Button>
      </div>

      <div className="grid gap-px bg-white/10 p-px lg:grid-cols-2">
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
        title="영상 샘플 10개 Before / After | SSMaker"
        description="SSMaker 실제 프로그램으로 처리한 원본 10개와 제작본 10개를 나란히 재생해 보세요. OCR 자막 블러 5건과 풀자동 쇼핑 숏폼 제작 5건을 공개합니다."
        path="/samples/index.html"
        keywords={[...SITE_KEYWORDS, "SSMaker 샘플", "Before After 영상", "OCR 자막 블러 예시"]}
        modifiedTime="2026-08-15"
        structuredData={SAMPLE_STRUCTURED_DATA}
      />
      <Navigation />

      <section className="relative border-b border-white/10 pb-20 pt-32 sm:pb-24 sm:pt-40">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_20%,rgba(220,38,38,0.18),transparent_46%)]" />
        <div className="container relative mx-auto px-6 text-center">
          <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-red-400/20 bg-red-500/10 px-4 py-2 text-sm font-medium text-red-200">
            <Sparkles className="h-4 w-4" />
            실제 프로그램 처리 결과
          </div>
          <h1 className="text-balance text-4xl font-extrabold tracking-[-0.04em] text-white sm:text-6xl lg:text-7xl">
            원본과 제작본을
            <br />
            <span className="text-gradient">직접 비교해 보세요</span>
          </h1>
          <p className="mx-auto mt-6 max-w-3xl text-balance text-base leading-7 text-white/55 sm:text-lg">
            기존 OCR 자막 블러 5건에 실제 풀자동 제작 5건을 더했습니다. Before 10개와 After 10개, 총 {SAMPLE_VIDEO_COUNT}개 영상을 같은 화면에서 확인할 수 있습니다.
          </p>

          <div className="mx-auto mt-10 grid max-w-3xl grid-cols-1 gap-3 sm:grid-cols-3">
            {[
              { icon: ScanText, value: "5건", label: "OCR 자막 블러" },
              { icon: WandSparkles, value: "5건", label: "풀자동 실렌더" },
              { icon: Play, value: "20개", label: "실제 재생 영상" },
            ].map((item) => (
              <div key={item.label} className="glass-card rounded-2xl px-5 py-5 text-left sm:text-center">
                <item.icon className="mb-3 h-5 w-5 text-red-400 sm:mx-auto" />
                <div className="text-2xl font-bold text-white">{item.value}</div>
                <div className="mt-1 text-xs text-white/45">{item.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="container mx-auto px-4 py-16 sm:px-6 sm:py-20" aria-label="Before After 영상 샘플 목록">
        <div className="mb-10 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-red-400">10 Before · 10 After</p>
            <h2 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">처리 유형별 샘플</h2>
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
                className={`rounded-full border px-4 py-2 text-sm transition-colors ${
                  filter === item.value
                    ? "border-red-400/40 bg-red-500/15 text-red-200"
                    : "border-white/10 bg-white/[0.03] text-white/50 hover:border-white/20 hover:text-white"
                }`}
              >
                {item.label} <span className="ml-1 text-xs opacity-60">{item.count}</span>
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

      <section className="border-t border-white/10 py-20">
        <div className="container mx-auto px-6 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">내 상품 영상도 같은 흐름으로</h2>
          <p className="mx-auto mt-4 max-w-2xl text-white/50">SSMaker를 설치하고 상품 링크 또는 원본 영상으로 직접 결과를 만들어 보세요.</p>
          <Button variant="hero" size="lg" asChild className="mt-8">
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
