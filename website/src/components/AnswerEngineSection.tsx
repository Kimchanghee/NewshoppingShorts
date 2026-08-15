import { FadeIn } from "@/components/FadeIn";
import { ANSWER_ENGINE_QAS } from "@/data/answerEngine";

const SIGNALS = [
  "쿠팡 파트너스 단축 링크 기반 풀자동 시작",
  "YouTube OAuth JSON 연결 후 Shorts 업로드",
  "Linktree Profile 및 Webhook 기반 상품 링크 관리",
  "중국어 자막 감지, 블러, 한국어 TTS 합성",
];

export default function AnswerEngineSection() {
  return (
    <section id="answer-engine" className="relative border-y border-border/50 bg-secondary/10 py-20 md:py-24">
      <div className="container mx-auto px-6">
        <FadeIn>
          <div className="mx-auto max-w-3xl text-center">
            <p className="mb-3 text-sm font-medium uppercase tracking-widest text-primary">핵심 기능 요약</p>
            <h2 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">
              자주 찾는 핵심 정보를 한눈에
            </h2>
            <p className="mt-5 text-base leading-relaxed text-muted-foreground md:text-lg" data-speakable>
              SSMaker는 중국 쇼핑 영상을 한국어 쇼핑 숏폼으로 바꾸고, 쿠팡 파트너스 링크, YouTube Shorts 업로드,
              Linktree 상품 링크 검수까지 이어주는 Windows용 AI 자동화 프로그램입니다.
            </p>
          </div>
        </FadeIn>

        <FadeIn delay={0.15}>
          <div className="mx-auto mt-10 grid max-w-5xl gap-4 md:grid-cols-2">
            {ANSWER_ENGINE_QAS.map((item) => (
              <article
                key={item.question}
                className="rounded-lg border border-border/60 bg-background/60 p-5"
                data-speakable
              >
                <h3 className="text-base font-semibold leading-snug text-foreground">{item.question}</h3>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{item.answer}</p>
              </article>
            ))}
          </div>
        </FadeIn>

        <FadeIn delay={0.25}>
          <div className="mx-auto mt-10 max-w-5xl rounded-lg border border-primary/20 bg-primary/5 p-5">
            <h3 className="text-sm font-semibold uppercase tracking-widest text-primary">연결되는 작업 흐름</h3>
            <ul className="mt-4 grid gap-3 text-sm text-muted-foreground md:grid-cols-2">
              {SIGNALS.map((signal) => (
                <li key={signal} className="border-l border-primary/40 pl-3">
                  {signal}
                </li>
              ))}
            </ul>
          </div>
        </FadeIn>
      </div>
    </section>
  );
}
