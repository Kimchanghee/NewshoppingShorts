import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { gaEvent, gaPageView, initGA4 } from "@/lib/ga4";

const ENGAGED_MS = 60_000;

export default function Analytics() {
  const location = useLocation();
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    initGA4();
  }, []);

  useEffect(() => {
    const pagePath = `${location.pathname}${location.search}`;
    gaPageView(pagePath, document.title);

    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      gaEvent("engaged_60s", { page_path: pagePath });
    }, ENGAGED_MS);

    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
      timerRef.current = null;
    };
  }, [location.pathname, location.search]);

  return null;
}
