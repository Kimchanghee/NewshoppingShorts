import { Helmet } from "react-helmet-async";
import { useLocation } from "react-router-dom";
import {
  DEFAULT_OG_IMAGE_URL,
  SITE_AUTHOR,
  SITE_DESCRIPTION,
  SITE_KEYWORDS,
  SITE_LANGUAGE,
  SITE_LOCALE,
  SITE_NAME,
  SITE_URL,
} from "@/constants/site";

type SeoProps = {
  title: string;
  description?: string;
  path?: string;
  imageUrl?: string;
  noIndex?: boolean;
  type?: "website" | "article";
  keywords?: string[] | string;
  publishedTime?: string;
  modifiedTime?: string;
  articleSection?: string;
  articleTags?: string[];
  alternates?: Array<{ hrefLang: string; href: string }>;
  structuredData?: Record<string, unknown> | Array<Record<string, unknown>>;
};

function resolveAbsoluteUrl(pathname: string) {
  if (pathname.startsWith("http://") || pathname.startsWith("https://")) return pathname;
  return `${SITE_URL}${pathname.startsWith("/") ? pathname : `/${pathname}`}`;
}

export default function Seo({
  title,
  description = SITE_DESCRIPTION,
  path,
  imageUrl,
  noIndex = false,
  type = "website",
  keywords = SITE_KEYWORDS,
  publishedTime,
  modifiedTime,
  articleSection,
  articleTags,
  alternates,
  structuredData,
}: SeoProps) {
  const location = useLocation();
  const resolvedPath = path ?? `${location.pathname}${location.search}`;
  const url = resolveAbsoluteUrl(resolvedPath);
  const image = imageUrl ?? DEFAULT_OG_IMAGE_URL;
  const robotsContent = noIndex
    ? "noindex, nofollow, noarchive"
    : "index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1";
  const keywordString = Array.isArray(keywords) ? keywords.join(", ") : keywords;
  const structuredDataList = structuredData
    ? Array.isArray(structuredData)
      ? structuredData
      : [structuredData]
    : [];
  const alternateLinks = alternates ?? [
    { hrefLang: "ko-KR", href: url },
    { hrefLang: "x-default", href: url },
  ];

  return (
    <Helmet htmlAttributes={{ lang: SITE_LANGUAGE }}>
      <title>{title}</title>
      <meta name="description" content={description} />
      <meta name="keywords" content={keywordString} />
      <meta name="author" content={SITE_AUTHOR} />
      <meta name="application-name" content={SITE_NAME} />
      <meta name="language" content={SITE_LANGUAGE} />
      <meta name="subject" content="AI 쇼핑 숏폼 자동 제작, 쿠팡 파트너스, YouTube Shorts, Linktree 자동화" />
      <meta name="classification" content="Business software, AI video automation, ecommerce marketing" />
      <meta name="coverage" content="South Korea" />
      <meta name="distribution" content="global" />
      <meta name="rating" content="general" />
      <meta name="referrer" content="strict-origin-when-cross-origin" />
      <meta name="thumbnail" content={image} />
      <meta name="format-detection" content="telephone=no, email=no, address=no" />
      <link rel="canonical" href={url} />
      <link rel="alternate" type="text/plain" href="/llms.txt" title="SSMaker LLM summary" />
      <link rel="alternate" type="text/plain" href="/llms-full.txt" title="SSMaker full LLM context" />
      <link rel="alternate" type="application/rss+xml" href="/feed.xml" title="SSMaker RSS feed" />
      <link rel="alternate" type="application/atom+xml" href="/atom.xml" title="SSMaker Atom feed" />
      <link rel="alternate" type="application/feed+json" href="/feed.json" title="SSMaker JSON feed" />
      {alternateLinks.map((alternate) => (
        <link
          key={`alternate-${alternate.hrefLang}`}
          rel="alternate"
          hrefLang={alternate.hrefLang}
          href={resolveAbsoluteUrl(alternate.href)}
        />
      ))}

      <meta name="robots" content={robotsContent} />
      <meta name="googlebot" content={robotsContent} />

      <meta property="og:type" content={type} />
      <meta property="og:site_name" content={SITE_NAME} />
      <meta property="og:locale" content={SITE_LOCALE} />
      <meta property="og:url" content={url} />
      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      <meta property="og:image" content={image} />
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:image:type" content="image/jpeg" />
      <meta property="og:image:alt" content={title} />
      {modifiedTime ?? publishedTime ? <meta property="og:updated_time" content={modifiedTime ?? publishedTime} /> : null}
      {type === "article" && publishedTime ? <meta property="article:published_time" content={publishedTime} /> : null}
      {type === "article" && (modifiedTime ?? publishedTime) ? (
        <meta property="article:modified_time" content={modifiedTime ?? publishedTime} />
      ) : null}
      {type === "article" ? <meta property="article:author" content={SITE_NAME} /> : null}
      {type === "article" && articleSection ? <meta property="article:section" content={articleSection} /> : null}
      {type === "article" && articleTags?.length
        ? articleTags.map((tag) => <meta key={`article-tag-${tag}`} property="article:tag" content={tag} />)
        : null}

      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content="@SSMaker_kr" />
      <meta name="twitter:url" content={url} />
      <meta name="twitter:title" content={title} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={image} />

      {structuredDataList.map((schema, index) => (
        <script key={`schema-${index}`} type="application/ld+json">
          {JSON.stringify(schema)}
        </script>
      ))}
    </Helmet>
  );
}
