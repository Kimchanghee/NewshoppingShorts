import { Button } from "@/components/ui/button";
import { Download, Play } from "lucide-react";
import { motion } from "framer-motion";
import heroBg from "@/assets/hero-bg.jpg";
import { DOWNLOAD_URL } from "@/constants/release";
import { gaEvent } from "@/lib/ga4";
export default function Hero() {
  const downloadUrl = DOWNLOAD_URL;
  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden">
      <div className="absolute inset-0 bg-cover bg-center opacity-40" style={{ backgroundImage: `url(${heroBg})` }} />
      <div className="hero-glow absolute inset-0" />
      <div className="absolute inset-0 bg-gradient-to-b from-background/30 via-transparent to-background" />

      <div className="container relative z-10 mx-auto px-6 pt-20 text-center">
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.8 }}
          className="mx-auto max-w-4xl text-balance text-5xl font-extrabold leading-tight tracking-tight text-foreground md:text-7xl"
        >
          쿠팡 파트너스 링크를 <br className="hidden md:block" /> <span className="text-gradient">쇼츠 영상</span>으로 자동 제작
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5, duration: 0.8 }}
          className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-muted-foreground md:text-xl"
        >
          link.coupang.com 단축 링크를 넣으면 상품 파악, 쇼핑 숏폼 생성,
          <br className="hidden md:block" />
          YouTube Shorts 업로드와 Linktree 링크 정리까지 한 흐름으로 이어집니다.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7, duration: 0.8 }}
          className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
        >
          <Button variant="hero" size="xl" asChild>
            <a
              href={downloadUrl}
              className="gap-2"
              rel="noopener noreferrer"
              onClick={() => gaEvent("download_click", { placement: "hero" })}
            >
              <Download className="h-5 w-5" />
              Microsoft Store에서 무료 설치
            </a>
          </Button>
          <Button variant="outline" size="xl" asChild className="border-primary/20 bg-primary/5 hover:bg-primary/10">
            <a href="#demo-video" className="gap-2">
              <Play className="h-5 w-5" />
              데모 영상 보기
            </a>
          </Button>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 1.0, duration: 0.8 }}
          className="mt-10 flex justify-center"
        >
          <div className="inline-flex flex-col items-center gap-3 rounded-2xl border border-primary/30 bg-primary/5 px-6 py-4 backdrop-blur-sm">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-primary">
              <span className="h-px w-8 bg-primary/50" />
              지원 플랫폼
              <span className="h-px w-8 bg-primary/50" />
            </div>
            <div className="flex flex-wrap items-center justify-center gap-3">
              <div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-sm font-medium text-foreground">
                <span className="text-base">🎵</span>
                <span>도우인</span>
                <span className="text-xs text-muted-foreground">抖音</span>
              </div>
              <div className="h-1 w-1 rounded-full bg-primary/40" />
              <div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-sm font-medium text-foreground">
                <span className="text-base">📕</span>
                <span>샤오홍수</span>
                <span className="text-xs text-muted-foreground">小红书</span>
              </div>
              <div className="h-1 w-1 rounded-full bg-primary/40" />
              <div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-sm font-medium text-foreground">
                <span className="text-base">⚡</span>
                <span>콰이쇼우</span>
                <span className="text-xs text-muted-foreground">快手</span>
              </div>
            </div>
            <p className="text-center text-sm text-muted-foreground">
              <span className="font-semibold text-primary">쿠팡 단축 링크</span>를 넣고{" "}
              <span className="font-semibold text-foreground">영상 제작 → 업로드 → 링크 정리</span>까지{" "}
              <span className="font-semibold text-primary">자동화</span>
            </p>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
