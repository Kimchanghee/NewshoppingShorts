import fs from "node:fs";
import path from "node:path";

const OCR_MEDIA_BASE =
  "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/ocr-showcase-20260815";
const AUTOMATION_SOURCE_MEDIA_BASE =
  "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/website-samples-20260815";
const AUTOMATION_AFTER_MEDIA_BASE =
  "https://github.com/Kimchanghee/NewshoppingShorts/releases/download/website-samples-scripted-20260816";
const OCR_UPLOAD_DATE = "2026-08-15T00:00:00+09:00";
const AUTOMATION_UPLOAD_DATE = "2026-08-16T00:00:00+09:00";

const catalogPath = path.join(process.cwd(), "src", "data", "samples.catalog.json");
const catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));

export const SAMPLE_MEDIA = catalog.map((sample) => {
  const number = String(sample.id).padStart(2, "0");
  const isOcr = sample.category === "ocr";
  const sourceBase = isOcr ? OCR_MEDIA_BASE : AUTOMATION_SOURCE_MEDIA_BASE;
  const afterBase = isOcr ? OCR_MEDIA_BASE : AUTOMATION_AFTER_MEDIA_BASE;
  const categoryLabel = isOcr ? "자막 정리" : "쇼핑 숏폼";
  const description = isOcr
    ? "원본 영상에 포함된 화면 자막을 자연스럽게 정리해 제품 장면에 집중할 수 있도록 다듬은 결과입니다."
    : "상품이 사용되는 장면을 바탕으로 세로 화면과 한국어 음성·자막을 더해 소개 영상으로 완성한 결과입니다.";

  return {
    ...sample,
    categoryLabel,
    description,
    uploadDate: isOcr ? OCR_UPLOAD_DATE : AUTOMATION_UPLOAD_DATE,
    beforeVideo: isOcr
      ? `${sourceBase}/source_${number}_first35s.mp4`
      : `${sourceBase}/source_${number}_${sample.slug}.mp4`,
    afterVideo: `${afterBase}/${number}_${sample.slug}.mp4`,
    beforePoster: isOcr
      ? `${sourceBase}/poster_${number}_before.jpg`
      : `${sourceBase}/poster_${number}_source.jpg`,
    afterPoster: `${afterBase}/poster_${number}_after.jpg`,
  };
});

export function durationToSeconds(duration) {
  const match = /^PT(?:(\d+)M)?(\d+(?:\.\d+)?)S$/.exec(duration);
  if (!match) throw new Error(`Unsupported ISO 8601 duration: ${duration}`);
  return Math.max(1, Math.round(Number(match[1] || 0) * 60 + Number(match[2])));
}
