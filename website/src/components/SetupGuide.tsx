import { FadeIn } from "@/components/FadeIn";
import { Link } from "react-router-dom";
import { ArrowRight, BookOpen } from "lucide-react";
import { gaEvent } from "@/lib/ga4";

const setupNoticeLinks = [
  { label: "쿠파스 채널 등록", to: "/notice/coupang-partners-channel-setup/index.html" },
  { label: "Linktree 가입·세팅", to: "/notice/linktree-signup-link-setup/index.html" },
  { label: "상품 링크 가져오기", to: "/notice/coupang-partners-product-link/index.html" },
  { label: "YouTube OAuth 설정", to: "/notice/youtube-oauth-client-guide/index.html" },
  { label: "Google Cloud 실제 캡쳐", to: "/notice/youtube-google-cloud-oauth-screenshots/index.html" },
  { label: "업로드 후 검수", to: "/notice/youtube-linktree-upload-check/index.html" },
];

/**
 * 홈에 노출되는 가이드 안내 섹션.
 * 자세한 단계별 매뉴얼은 /notice 의 설정별 실제 캡쳐 공지로 이동합니다.
 */
export default function SetupGuide() {
  return (
    <section id="setup-guide" className="relative py-16 sm:py-20 lg:py-28">
      <div className="section-glow absolute inset-0" />
      <div className="container relative mx-auto px-4 sm:px-6">
        <FadeIn>
          <div className="mx-auto max-w-3xl rounded-2xl border border-border/60 bg-secondary/30 p-5 text-center sm:p-8 md:p-10">
            <span className="inline-flex items-center gap-2 rounded-full border border-border/60 bg-background/50 px-3 py-1 text-[11px] text-muted-foreground">
              <BookOpen className="h-3.5 w-3.5" />
              초기 세팅 매뉴얼
            </span>
            <p className="mt-4 text-sm font-medium uppercase tracking-widest text-primary">
              Setup Guide
            </p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight text-foreground md:text-4xl">
              실제 화면 캡쳐로 보는 초기 세팅
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
              쿠팡 파트너스(쿠파스) 채널 등록부터 Linktree 세팅, YouTube OAuth 연결, Google Cloud 실제 캡쳐, 상품 링크 생성, 쇼츠 검수까지
              실제 화면 캡쳐 기반의 단계별 매뉴얼을 설정별 공지사항으로 나눠 정리해 두었습니다.
            </p>
            <div className="mt-6 grid gap-2 sm:grid-cols-2">
              {setupNoticeLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  onClick={() => gaEvent("guide_click", { placement: "setup_guide", guide: link.to })}
                  className="inline-flex min-h-12 items-center justify-between gap-3 rounded-lg border border-border/70 bg-background/45 px-4 py-3 text-left text-sm font-semibold text-foreground transition-colors hover:border-primary/50 hover:text-primary"
                >
                  {link.label}
                  <ArrowRight className="h-4 w-4 shrink-0" />
                </Link>
              ))}
            </div>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}
