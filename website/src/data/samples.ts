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
    categoryLabel: "자막 정리",
    description: "원본 영상에 포함된 화면 자막을 자연스럽게 정리해 제품 장면에 집중할 수 있도록 다듬은 결과입니다.",
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
    categoryLabel: "쇼핑 숏폼",
    description: "상품이 사용되는 장면을 바탕으로 세로 화면과 한국어 음성·자막을 더해 소개 영상으로 완성한 결과입니다.",
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
