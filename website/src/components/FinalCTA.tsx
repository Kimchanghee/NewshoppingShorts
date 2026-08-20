import { FadeIn } from "@/components/FadeIn";
import { DownloadChoices } from "@/components/DownloadChoices";

export default function FinalCTA() {
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
            <DownloadChoices placement="final_cta" />
          </div>

          <p className="mt-5 text-sm text-muted-foreground">Windows 10/11 전용</p>
        </FadeIn>
      </div>
    </section>
  );
}
