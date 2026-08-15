"""Public before-and-after showcase for SSmaker's OCR subtitle blur."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape


MEDIA_BASE_URL = (
    "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/"
    "ocr-showcase-20260815"
)


@dataclass(frozen=True)
class ShowcaseSample:
    number: str
    title: str
    category: str
    source_filename: str
    result_filename: str
    duration: str
    blur_regions: int


SAMPLES = (
    ShowcaseSample(
        "01",
        "전동 우유 거품기",
        "Kitchen",
        "source_01_first35s.mp4",
        "01_milk_frother.mp4",
        "25.5초",
        70,
    ),
    ShowcaseSample(
        "02",
        "전기 모기채",
        "Living",
        "source_02_first35s.mp4",
        "02_mosquito_swatter.mp4",
        "22.6초",
        49,
    ),
    ShowcaseSample(
        "03",
        "전동 욕실 청소솔",
        "Home care",
        "source_03_first35s.mp4",
        "03_bathroom_scrubber.mp4",
        "21.4초",
        75,
    ),
    ShowcaseSample(
        "04",
        "전동 거품기",
        "Kitchen",
        "source_04_first35s.mp4",
        "04_electric_whisk.mp4",
        "23.0초",
        18,
    ),
    ShowcaseSample(
        "05",
        "전동 후추 그라인더",
        "Kitchen",
        "source_05_first35s.mp4",
        "05_pepper_grinder.mp4",
        "21.1초",
        68,
    ),
)


def _asset_url(filename: str) -> str:
    return f"{MEDIA_BASE_URL}/{escape(filename, quote=True)}"


def _render_sample(sample: ShowcaseSample) -> str:
    title = escape(sample.title)
    source_url = _asset_url(sample.source_filename)
    result_url = _asset_url(sample.result_filename)
    source_poster_url = _asset_url(f"poster_{sample.number}_before.jpg")
    result_poster_url = _asset_url(f"poster_{sample.number}_after.jpg")
    return f"""
      <article class="sample-card" id="sample-{sample.number}">
        <div class="sample-heading">
          <div class="sample-index" aria-hidden="true">{sample.number}</div>
          <div class="sample-title-block">
            <p class="sample-category">{escape(sample.category)}</p>
            <h3>{title}</h3>
          </div>
          <div class="sample-facts" aria-label="샘플 검증 정보">
            <span>{escape(sample.duration)}</span>
            <span>{sample.blur_regions}개 영역 처리</span>
          </div>
        </div>

        <div class="media-grid">
          <figure class="media-panel media-source">
            <figcaption>
              <span class="media-kicker">Before</span>
              <strong>원본 영상</strong>
            </figcaption>
            <div class="phone-frame">
              <video controls playsinline preload="metadata" poster="{source_poster_url}"
                     aria-label="{title} 원본 영상">
                <source src="{source_url}" type="video/mp4">
                브라우저가 MP4 재생을 지원하지 않습니다.
              </video>
            </div>
            <a class="download-link" href="{source_url}" download>
              원본 내려받기 <span aria-hidden="true">↗</span>
            </a>
          </figure>

          <div class="process-rail" aria-hidden="true">
            <span></span>
            <svg viewBox="0 0 24 24" focusable="false">
              <path d="M5 12h14M14 7l5 5-5 5"/>
            </svg>
            <span></span>
          </div>

          <figure class="media-panel media-result">
            <figcaption>
              <span class="media-kicker">After</span>
              <strong>SSmaker 제작본</strong>
              <span class="verified-badge">
                <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m5 10 3 3 7-7"/></svg>
                OCR 검증 완료
              </span>
            </figcaption>
            <div class="phone-frame result-frame">
              <video controls playsinline preload="metadata" poster="{result_poster_url}"
                     aria-label="{title} SSmaker 제작 영상">
                <source src="{result_url}" type="video/mp4">
                브라우저가 MP4 재생을 지원하지 않습니다.
              </video>
            </div>
            <a class="download-link result-download" href="{result_url}" download>
              제작본 내려받기 <span aria-hidden="true">↗</span>
            </a>
          </figure>
        </div>

        <div class="pair-actions">
          <button type="button" class="pair-button pair-play">
            <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m7 5 7 5-7 5Z"/></svg>
            두 영상 함께 재생
          </button>
          <button type="button" class="pair-button pair-reset">
            <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 7V3m0 0h4M4 3l3 3a6 6 0 1 1-1.4 6"/></svg>
            처음부터
          </button>
        </div>
      </article>
    """


def render_ocr_showcase() -> str:
    """Render the self-contained public OCR showcase page."""
    sample_markup = "".join(_render_sample(sample) for sample in SAMPLES)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0b1715">
  <meta name="description" content="SSmaker OCR 자막 블러 기술의 원본과 제작본 5개를 직접 비교해 보세요.">
  <meta property="og:title" content="SSmaker OCR Blur — Before & After">
  <meta property="og:description" content="중국어 자막의 위치와 시간만 정교하게 추적한 실제 제작 샘플 5개">
  <meta property="og:type" content="website">
  <meta property="og:url" content="https://newshopping-shorts-auth.vercel.app/ocr-showcase">
  <title>OCR Blur Showcase | SSmaker</title>
  <link rel="stylesheet" href="/static/ocr_showcase.css">
  <script src="/static/ocr_showcase.js" defer></script>
</head>
<body data-view="pair">
  <a class="skip-link" href="#samples">샘플 목록으로 건너뛰기</a>
  <header class="site-header">
    <a class="brand" href="/ocr-showcase" aria-label="SSmaker OCR 쇼케이스 홈">
      <span class="brand-mark">S</span>
      <span>SSmaker</span>
    </a>
    <div class="header-label"><span></span> OCR BLUR LAB</div>
    <a class="header-cta" href="#samples">샘플 보기</a>
  </header>

  <main>
    <section class="hero">
      <div class="hero-glow" aria-hidden="true"></div>
      <div class="hero-copy">
        <p class="eyebrow"><span>Release test</span> 2026.08.15</p>
        <h1>원본의 몰입감은 그대로.<br><em>불필요한 자막만 정교하게.</em></h1>
        <p class="hero-description">
          프레임마다 달라지는 중국어 자막의 위치와 시간을 추적해 필요한 범위만 블러합니다.
          실제 원본과 SSmaker 제작본을 직접 재생해 차이를 확인하세요.
        </p>
        <div class="hero-actions">
          <a class="primary-button" href="#samples">
            5개 비교 영상 보기
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14m-6-6 6 6 6-6"/></svg>
          </a>
          <span class="hero-note">이어폰으로 음성·원음을 함께 비교할 수 있습니다.</span>
        </div>
      </div>

      <aside class="proof-panel" aria-label="OCR 검증 결과">
        <div class="proof-orbit" aria-hidden="true"><span></span></div>
        <p class="proof-label">Independent OCR audit</p>
        <strong class="proof-score">0</strong>
        <p class="proof-caption">잔존 중국어 자막</p>
        <div class="proof-stats">
          <div><strong>3,408</strong><span>전체 프레임 검사</span></div>
          <div><strong>100%</strong><span>블러 적용 범위</span></div>
          <div><strong>5/5</strong><span>샘플 검증 통과</span></div>
        </div>
      </aside>
    </section>

    <section class="method-strip" aria-label="처리 과정">
      <p>영상 입력</p><span>01</span>
      <p>프레임별 OCR</p><span>02</span>
      <p>위치·시간 추적</p><span>03</span>
      <p>정밀 블러·전수 검증</p>
    </section>

    <section class="samples-section" id="samples">
      <div class="section-heading">
        <div>
          <p class="eyebrow dark">Before / After</p>
          <h2>다섯 가지 실제 영상으로<br>처리 결과를 확인하세요.</h2>
        </div>
        <div class="view-switcher" role="group" aria-label="영상 배치 선택">
          <button type="button" data-view="source" aria-pressed="false">원본</button>
          <button type="button" data-view="pair" aria-pressed="true">나란히</button>
          <button type="button" data-view="result" aria-pressed="false">제작본</button>
        </div>
      </div>

      <div class="samples-list">
        {sample_markup}
      </div>
    </section>

    <section class="quality-note">
      <div class="quality-icon" aria-hidden="true">
        <svg viewBox="0 0 28 28"><path d="M14 3 24 7v7c0 6-4.3 9.5-10 11-5.7-1.5-10-5-10-11V7Z"/><path d="m9 14 3 3 7-7"/></svg>
      </div>
      <div>
        <p class="eyebrow dark">Quality protocol</p>
        <h2>‘처리 완료’가 아니라<br>‘잔존 자막 0건’까지 확인합니다.</h2>
      </div>
      <p>
        모든 제작본은 GLM-OCR 검출 후 별도의 RapidOCR 전체 프레임 검사까지 통과했습니다.
        영상 전환, 다중 위치, 이동 자막을 시간축과 좌표축에서 함께 검증한 결과입니다.
      </p>
    </section>
  </main>

  <footer>
    <div class="brand footer-brand"><span class="brand-mark">S</span><span>SSmaker</span></div>
    <p>AI product video automation, refined frame by frame.</p>
    <p class="footer-meta">OCR Showcase · 2026 SSmaker</p>
  </footer>
</body>
</html>"""
