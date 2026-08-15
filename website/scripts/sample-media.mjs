import fs from "node:fs";
import path from "node:path";

const OCR_MEDIA_BASE =
  "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/ocr-showcase-20260815";
const AUTOMATION_MEDIA_BASE =
  "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/website-samples-20260815";
const UPLOAD_DATE = "2026-08-15T00:00:00+09:00";

const catalogPath = path.join(process.cwd(), "src", "data", "samples.catalog.json");
const catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));

export const SAMPLE_MEDIA = catalog.map((sample) => {
  const number = String(sample.id).padStart(2, "0");
  const isOcr = sample.category === "ocr";
  const base = isOcr ? OCR_MEDIA_BASE : AUTOMATION_MEDIA_BASE;
  const categoryLabel = isOcr ? "OCR 자막 블러" : "풀자동 실렌더";
  const description = isOcr
    ? "원본 중국 상품 영상의 자막 위치와 노출 시간을 감지해 필요한 구간에 블러를 적용한 비교입니다."
    : "쿠팡 상품을 기준으로 소스를 매칭하고 세로 편집, 한국어 음성·자막까지 SSMaker가 완성한 실제 결과입니다.";

  return {
    ...sample,
    categoryLabel,
    description,
    uploadDate: UPLOAD_DATE,
    beforeVideo: isOcr
      ? `${base}/source_${number}_first35s.mp4`
      : `${base}/source_${number}_${sample.slug}.mp4`,
    afterVideo: `${base}/${number}_${sample.slug}.mp4`,
    beforePoster: isOcr
      ? `${base}/poster_${number}_before.jpg`
      : `${base}/poster_${number}_source.jpg`,
    afterPoster: `${base}/poster_${number}_after.jpg`,
  };
});

export function durationToSeconds(duration) {
  const match = /^PT(?:(\d+)M)?(\d+(?:\.\d+)?)S$/.exec(duration);
  if (!match) throw new Error(`Unsupported ISO 8601 duration: ${duration}`);
  return Math.max(1, Math.round(Number(match[1] || 0) * 60 + Number(match[2])));
}
