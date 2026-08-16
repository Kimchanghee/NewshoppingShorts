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
const AUTOMATION_SOURCE_MEDIA_BASE =
  "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/website-samples-20260815";
const AUTOMATION_AFTER_MEDIA_BASE =
  "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/website-samples-scripted-20260816";

const OCR_UPLOAD_DATE = "2026-08-15T00:00:00+09:00";
const AUTOMATION_UPLOAD_DATE = "2026-08-16T00:00:00+09:00";

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
    uploadDate: OCR_UPLOAD_DATE,
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
    description: "10초 이상 실제 상품 영상을 장면별로 읽고, 단어 나열이 아닌 완전한 한국어 상품 소개 대본·음성·자막과 세로 편집을 SSMaker가 완성한 결과입니다.",
    beforeVideo: `${AUTOMATION_SOURCE_MEDIA_BASE}/source_${number}_${slug}.mp4`,
    afterVideo: `${AUTOMATION_AFTER_MEDIA_BASE}/${number}_${slug}.mp4`,
    beforePoster: `${AUTOMATION_SOURCE_MEDIA_BASE}/poster_${number}_source.jpg`,
    afterPoster: `${AUTOMATION_AFTER_MEDIA_BASE}/poster_${number}_after.jpg`,
    beforeDuration,
    afterDuration,
    uploadDate: AUTOMATION_UPLOAD_DATE,
  };
};

export const VIDEO_SAMPLES: VideoSample[] = sampleCatalog.map((sample) => {
  const factory = sample.category === "ocr" ? ocrSample : automationSample;
  return factory(sample.id, sample.slug, sample.title, sample.beforeDuration, sample.afterDuration);
});

export const SAMPLE_VIDEO_COUNT = VIDEO_SAMPLES.length * 2;
