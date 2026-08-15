declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  }
}

const GA_MEASUREMENT_ID = "G-QD734BE7JN";

let initialized = false;

export function initGA4() {
  if (initialized) return;

  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`;
  document.head.appendChild(script);

  window.dataLayer = window.dataLayer ?? [];
  window.gtag =
    window.gtag ??
    function gtag(...args: unknown[]) {
      window.dataLayer!.push(args);
    };

  window.gtag("js", new Date());
  window.gtag("config", GA_MEASUREMENT_ID, { send_page_view: false });
  initialized = true;
}

export function gaPageView(pagePath: string, title?: string) {
  if (!window.gtag) return;
  window.gtag("event", "page_view", {
    page_path: pagePath,
    page_title: title,
  });
}

export function gaEvent(name: string, params?: Record<string, unknown>) {
  if (!window.gtag) return;
  window.gtag("event", name, params ?? {});
}
