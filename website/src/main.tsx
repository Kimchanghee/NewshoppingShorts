import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";

// Static HTML keeps schema/text available to non-JavaScript crawlers. Once the app
// starts, Helmet owns the live head so the same entities are not published twice.
const staticSeoSelectors = [
  "[data-static-seo]",
  "meta[name='description']",
  "meta[name='keywords']",
  "meta[name='author']",
  "meta[name='application-name']",
  "meta[name='language']",
  "meta[name='subject']",
  "meta[name='classification']",
  "meta[name='coverage']",
  "meta[name='distribution']",
  "meta[name='rating']",
  "meta[name='referrer']",
  "meta[name='thumbnail']",
  "meta[name='format-detection']",
  "meta[name='robots']",
  "meta[name='googlebot']",
  "meta[name^='twitter:']",
  "meta[property^='og:']",
  "meta[property^='article:']",
  "link[rel='canonical']",
  "link[rel='alternate'][hreflang]",
  "link[rel='alternate'][type='text/plain']",
  "link[rel='alternate'][type='application/rss+xml']",
  "link[rel='alternate'][type='application/atom+xml']",
  "link[rel='alternate'][type='application/feed+json']",
  "script[type='application/ld+json']",
];
document.querySelectorAll(staticSeoSelectors.join(",")).forEach((element) => element.remove());

createRoot(document.getElementById("root")!).render(<App />);
