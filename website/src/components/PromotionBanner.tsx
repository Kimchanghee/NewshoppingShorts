import { CalendarDays, Gift } from "lucide-react";
import { Link } from "react-router-dom";
import {
  PROMOTION,
  PROMOTION_NOTICE_PATH,
  getPromotionDescription,
  getPromotionStatus,
  getPromotionStatusLabel,
} from "@/constants/promotion";
import { gaEvent } from "@/lib/ga4";

export default function PromotionBanner() {
  const status = getPromotionStatus();
  const statusLabel = getPromotionStatusLabel(status);
  const isClosed = status === "closed";

  return (
    <section id="event" className="border-y border-primary/15 bg-primary/[0.04] py-5">
      <div className="container mx-auto flex flex-col gap-4 px-6 md:flex-row md:items-center md:justify-between">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Gift className="h-4 w-4" />
          </span>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`rounded px-2 py-0.5 text-xs font-semibold ${
                  isClosed ? "bg-muted text-muted-foreground" : "bg-primary text-primary-foreground"
                }`}
              >
                {statusLabel}
              </span>
              <h2 className="text-base font-semibold text-foreground">{PROMOTION.title}</h2>
            </div>
            <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{getPromotionDescription(status)}</p>
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="inline-flex items-center gap-2 text-sm font-medium text-foreground">
            <CalendarDays className="h-4 w-4 text-primary" />
            {PROMOTION.periodLabel}
          </div>
          <Link
            to={PROMOTION_NOTICE_PATH}
            className="inline-flex items-center justify-center rounded-md border border-primary/30 px-4 py-2 text-sm font-semibold text-primary transition-colors hover:bg-primary/10"
            onClick={() => gaEvent("guide_click", { placement: "promotion_banner", guide: PROMOTION.id })}
          >
            이벤트 조건 보기
          </Link>
        </div>
      </div>
    </section>
  );
}
