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
};

const OCR_MEDIA_BASE =
  "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/ocr-showcase-20260815";
const AUTOMATION_MEDIA_BASE =
  "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/website-samples-20260815";

const ocrSample = (id: number, slug: string, title: string): VideoSample => {
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
  };
};

const automationSample = (id: number, slug: string, title: string): VideoSample => {
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
  };
};

export const VIDEO_SAMPLES: VideoSample[] = [
  ocrSample(1, "milk_frother", "전동 우유 거품기"),
  ocrSample(2, "mosquito_swatter", "충전식 전기 모기채"),
  ocrSample(3, "bathroom_scrubber", "무선 욕실 청소기"),
  ocrSample(4, "electric_whisk", "무선 전동 거품기"),
  ocrSample(5, "pepper_grinder", "전동 후추 그라인더"),
  automationSample(6, "air_cooler", "휴대용 미니 냉풍기"),
  automationSample(7, "uv_parasol", "UV 차단 미니 양산"),
  automationSample(8, "mosquito_trap", "태양광 모기 퇴치기"),
  automationSample(9, "aqua_shoes", "여름 아쿠아슈즈"),
  automationSample(10, "beach_towel", "대형 비치타월"),
];

export const SAMPLE_VIDEO_COUNT = VIDEO_SAMPLES.length * 2;
