import { FadeIn } from "@/components/FadeIn";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";
import { DOWNLOAD_URL } from "@/constants/release";
import { gaEvent } from "@/lib/ga4";

export default function FinalCTA() {
  const downloadUrl = DOWNLOAD_URL;
  return (
    <section className="relative overflow-hidden py-24 md:py-32">
      <div className="container relative mx-auto px-6 text-center">
        <FadeIn>
          <h2 className="mx-auto max-w-2xl text-4xl font-extrabold tracking-tight text-foreground md:text-5xl">
            지금 바로 <span className="text-gradient">시작하세요</span>
          </h2>
          <p className="mx-auto mt-6 max-w-lg text-lg text-muted-foreground">
            로그인 계정 기준 매월 5회 무료 체험 · 설치 후 바로 사용 가능
          </p>

          <div className="mt-10">
            <Button variant="hero" size="xl" asChild>
              <a
                href={downloadUrl}
                className="gap-2"
                rel="noopener noreferrer"
                onClick={() => gaEvent("download_click", { placement: "final_cta" })}
              >
                <Download className="h-5 w-5" />
                Microsoft Store에서 받기
              </a>
            </Button>
          </div>

          <p className="mt-4 text-sm text-muted-foreground">Windows 전용 · Microsoft Store 공식 배포</p>
        </FadeIn>
      </div>
    </section>
  );
}
