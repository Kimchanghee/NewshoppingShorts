import sampleCatalog from "./samples.catalog.json";

export type SampleCategory = "ocr" | "automation";

export type VideoSample = {
  id: number;
  title: string;
  category: SampleCategory;
  categoryLabel: string;
  description: string;
  beforeVideo: string;
  afterVideo: string;
  beforePoster: string;
  afterPoster: string;
  beforeDuration: string;
  afterDuration: string;
  uploadDate: string;
};

const OCR_MEDIA_BASE =
  "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/ocr-showcase-20260815";
const AUTOMATION_MEDIA_BASE =
  "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/website-samples-20260815";

const SAMPLE_UPLOAD_DATE = "2026-08-15T00:00:00+09:00";

const ocrSample = (
  id: number,
  slug: string,
  title: string,
  beforeDuration: string,
  afterDuration: string,
): VideoSample => {
  const number = String(id).padStart(2, "0");
  return {
    id,
    title,
    category: "ocr",
    categoryLabel: "OCR 자막 블러",
    description: "원본 중국 상품 영상의 자막 위치와 노출 시간을 감지해 필요한 구간에 블러를 적용한 비교입니다.",
    beforeVideo: `${OCR_MEDIA_BASE}/source_${number}_first35s.mp4`,
    afterVideo: `${OCR_MEDIA_BASE}/${number}_${slug}.mp4`,
    beforePoster: `${OCR_MEDIA_BASE}/poster_${number}_before.jpg`,
    afterPoster: `${OCR_MEDIA_BASE}/poster_${number}_after.jpg`,
    beforeDuration,
    afterDuration,
    uploadDate: SAMPLE_UPLOAD_DATE,
  };
};

const automationSample = (
  id: number,
  slug: string,
  title: string,
  beforeDuration: string,
  afterDuration: string,
): VideoSample => {
  const number = String(id).padStart(2, "0");
  return {
    id,
    title,
    category: "automation",
    categoryLabel: "풀자동 실렌더",
    description: "쿠팡 상품을 기준으로 소스를 매칭하고 세로 편집, 한국어 음성·자막까지 SSMaker가 완성한 실제 결과입니다.",
    beforeVideo: `${AUTOMATION_MEDIA_BASE}/source_${number}_${slug}.mp4`,
    afterVideo: `${AUTOMATION_MEDIA_BASE}/${number}_${slug}.mp4`,
    beforePoster: `${AUTOMATION_MEDIA_BASE}/poster_${number}_source.jpg`,
    afterPoster: `${AUTOMATION_MEDIA_BASE}/poster_${number}_after.jpg`,
    beforeDuration,
    afterDuration,
    uploadDate: SAMPLE_UPLOAD_DATE,
  };
};

export const VIDEO_SAMPLES: VideoSample[] = sampleCatalog.map((sample) => {
  const factory = sample.category === "ocr" ? ocrSample : automationSample;
  return factory(sample.id, sample.slug, sample.title, sample.beforeDuration, sample.afterDuration);
});

export const SAMPLE_VIDEO_COUNT = VIDEO_SAMPLES.length * 2;
