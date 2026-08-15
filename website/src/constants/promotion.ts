export const PROMOTION_NOTICE_SLUG = "spring-2026-new-subscriber-extra-month";
export const PROMOTION_NOTICE_PATH = `/notice/${PROMOTION_NOTICE_SLUG}/index.html`;

export const PROMOTION = {
  id: "spring-2026-new-subscriber-extra-month",
  title: "신규 구독 1개월 추가 제공 이벤트",
  periodLabel: "2026.04.30 - 2026.05.14",
  startsAt: "2026-04-30T00:00:00+09:00",
  endsAtExclusive: "2026-05-15T00:00:00+09:00",
  endsAtLabel: "2026년 5월 14일 23:59 KST",
  bonusMonths: 1,
  bonusDays: 30,
} as const;

export type PromotionStatus = "upcoming" | "active" | "closed";

export function getPromotionStatus(now = new Date()): PromotionStatus {
  const start = new Date(PROMOTION.startsAt).getTime();
  const endExclusive = new Date(PROMOTION.endsAtExclusive).getTime();
  const current = now.getTime();

  if (current < start) return "upcoming";
  if (current < endExclusive) return "active";
  return "closed";
}

export function getPromotionStatusLabel(status = getPromotionStatus()) {
  if (status === "active") return "진행중";
  if (status === "closed") return "마감";
  return "예정";
}

export function getPromotionDescription(status = getPromotionStatus()) {
  if (status === "active") {
    return "신규 가입 후 이벤트 기간 안에 구독이 확정되면 구독 기간이 1개월 자동 추가됩니다.";
  }
  if (status === "closed") {
    return "이벤트 기간이 종료되어 신규 구독 1개월 추가 혜택은 더 이상 적용되지 않습니다.";
  }
  return "이벤트 시작 전입니다. 시작 후 신규 가입 및 구독 확정 계정에 혜택이 적용됩니다.";
}
