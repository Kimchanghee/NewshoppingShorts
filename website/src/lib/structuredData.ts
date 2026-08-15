import {
  DEFAULT_DOWNLOAD_URL,
  DEFAULT_OG_IMAGE_URL,
  BUSINESS_ADDRESS,
  BUSINESS_NAME,
  BUSINESS_REGISTRATION_NUMBER,
  BUSINESS_TYPE,
  SITE_DESCRIPTION,
  SITE_AREA_SERVED,
  SITE_KAKAO_OPENCHAT_URL,
  SITE_LANGUAGE,
  SITE_NAME,
  SITE_REPOSITORY_URL,
  SITE_SUPPORT_EMAIL,
  SITE_URL,
} from "@/constants/site";
import type { FAQItem } from "@/data/faqs";

type SchemaObject = Record<string, unknown>;

type BreadcrumbItem = {
  name: string;
  path: string;
};

type ArticleSchemaInput = {
  headline: string;
  description: string;
  path: string;
  datePublished?: string;
  dateModified?: string;
  articleSection?: string;
};

type CollectionPageInput = {
  name: string;
  description: string;
  path: string;
  itemPaths?: string[];
};

type WebPageInput = {
  name: string;
  description: string;
  path: string;
  breadcrumbPaths?: BreadcrumbItem[];
};

type HowToInput = {
  name: string;
  description: string;
  path: string;
  steps: string[];
};

type ItemListInput = {
  name: string;
  description?: string;
  path: string;
  items: string[];
};

export function toAbsoluteUrl(path = "/") {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

export function buildOrganizationSchema(): SchemaObject {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${SITE_URL}#organization`,
    name: SITE_NAME,
    legalName: BUSINESS_NAME,
    url: SITE_URL,
    email: SITE_SUPPORT_EMAIL,
    taxID: BUSINESS_REGISTRATION_NUMBER,
    description: SITE_DESCRIPTION,
    address: {
      "@type": "PostalAddress",
      ...BUSINESS_ADDRESS,
    },
    areaServed: SITE_AREA_SERVED.map((country) => ({
      "@type": "Country",
      name: country,
    })),
    knowsAbout: [
      "AI video automation",
      "Korean short-form commerce video",
      "Coupang Partners affiliate workflow",
      "YouTube Shorts upload automation",
      "Linktree product link operations",
      "Chinese subtitle detection and blur",
    ],
    contactPoint: [
      {
        "@type": "ContactPoint",
        contactType: "customer support",
        email: SITE_SUPPORT_EMAIL,
        availableLanguage: ["Korean", "English"],
      },
    ],
    logo: DEFAULT_OG_IMAGE_URL,
    slogan: "중국 쇼핑 영상을 한국어 쇼핑 숏폼으로 자동 변환",
    additionalProperty: [
      {
        "@type": "PropertyValue",
        name: "업태",
        value: BUSINESS_TYPE,
      },
    ],
    sameAs: [SITE_REPOSITORY_URL, SITE_KAKAO_OPENCHAT_URL],
  };
}

export function buildWebsiteSchema(): SchemaObject {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${SITE_URL}#website`,
    name: SITE_NAME,
    alternateName: ["Shopping Shorts Maker", "쇼핑 숏폼 메이커"],
    description: SITE_DESCRIPTION,
    url: SITE_URL,
    inLanguage: SITE_LANGUAGE,
    hasPart: [
      {
        "@type": "DataFeed",
        name: "SSMaker RSS feed",
        url: `${SITE_URL}/feed.xml`,
      },
      {
        "@type": "DataFeed",
        name: "SSMaker Atom feed",
        url: `${SITE_URL}/atom.xml`,
      },
      {
        "@type": "DataFeed",
        name: "SSMaker JSON feed",
        url: `${SITE_URL}/feed.json`,
      },
    ],
    publisher: {
      "@id": `${SITE_URL}#organization`,
    },
  };
}

export function buildSoftwareApplicationSchema(): SchemaObject {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "@id": `${SITE_URL}#software`,
    name: SITE_NAME,
    alternateName: ["Shopping Shorts Maker", "쇼핑 숏폼 메이커"],
    applicationCategory: "BusinessApplication",
    applicationSubCategory: "AI video editing automation",
    operatingSystem: "Windows",
    downloadUrl: DEFAULT_DOWNLOAD_URL,
    installUrl: DEFAULT_DOWNLOAD_URL,
    screenshot: DEFAULT_OG_IMAGE_URL,
    description:
      "중국 쇼핑 영상을 한국어 쇼핑 숏폼으로 자동 변환하는 Windows 데스크톱 AI 솔루션. 자막 감지, 중국어 자막 블러, 번역, 한국어 TTS 합성, 일괄 처리, YouTube Shorts 업로드, Linktree 상품 링크 검수 흐름을 제공합니다.",
    inLanguage: SITE_LANGUAGE,
    availableOnDevice: "Windows PC",
    countriesSupported: SITE_AREA_SERVED,
    softwareRequirements: "Windows 10 이상, 인터넷 연결, 선택 사항: NVIDIA CUDA GPU",
    featureList: [
      "중국 쇼핑 영상 자막 감지",
      "원본 중국어 자막 블러 처리",
      "한국어 쇼핑 스크립트 생성",
      "한국어 TTS 음성 합성",
      "쿠팡 파트너스 단축 링크 기반 풀자동 소싱",
      "YouTube Shorts 자동 업로드",
      "Linktree 상품 링크 번호 관리",
      "최대 4개 영상 병렬 처리",
    ],
    audience: {
      "@type": "Audience",
      audienceType: [
        "구매대행 셀러",
        "스마트스토어 운영자",
        "쿠팡 파트너스 콘텐츠 제작자",
        "YouTube Shorts 쇼핑 채널 운영자",
      ],
    },
    offers: [
      {
        "@type": "Offer",
        name: "무료 체험",
        price: "0",
        priceCurrency: "KRW",
        availability: "https://schema.org/InStock",
        url: DEFAULT_DOWNLOAD_URL,
      },
      {
        "@type": "Offer",
        name: "프로 월 정액",
        price: "149000",
        priceCurrency: "KRW",
        availability: "https://schema.org/InStock",
        url: `${SITE_URL}/contact/index.html`,
        priceSpecification: {
          "@type": "UnitPriceSpecification",
          price: "149000",
          priceCurrency: "KRW",
          billingDuration: 1,
          billingIncrement: 1,
          unitCode: "MON",
        },
      },
    ],
    potentialAction: {
      "@type": "DownloadAction",
      target: DEFAULT_DOWNLOAD_URL,
      name: "SSMaker 다운로드",
    },
    publisher: {
      "@id": `${SITE_URL}#organization`,
    },
  };
}

export function buildFaqSchema(faqs: FAQItem[]): SchemaObject {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: faq.answer,
      },
    })),
  };
}

export function buildBreadcrumbSchema(items: BreadcrumbItem[]): SchemaObject {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: toAbsoluteUrl(item.path),
    })),
  };
}

export function buildCollectionPageSchema(input: CollectionPageInput): SchemaObject {
  const itemListElement =
    input.itemPaths?.map((path, index) => ({
      "@type": "ListItem",
      position: index + 1,
      url: toAbsoluteUrl(path),
    })) ?? [];

  return {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: input.name,
    description: input.description,
    url: toAbsoluteUrl(input.path),
    inLanguage: SITE_LANGUAGE,
    isPartOf: {
      "@id": `${SITE_URL}#website`,
    },
    mainEntity: {
      "@type": "ItemList",
      itemListElement,
    },
  };
}

export function buildArticleSchema(input: ArticleSchemaInput): SchemaObject {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: input.headline,
    description: input.description,
    url: toAbsoluteUrl(input.path),
    datePublished: input.datePublished,
    dateModified: input.dateModified ?? input.datePublished,
    articleSection: input.articleSection,
    inLanguage: SITE_LANGUAGE,
    image: [DEFAULT_OG_IMAGE_URL],
    author: {
      "@id": `${SITE_URL}#organization`,
    },
    publisher: {
      "@id": `${SITE_URL}#organization`,
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": toAbsoluteUrl(input.path),
    },
  };
}

export function buildWebPageSchema(input: WebPageInput): SchemaObject {
  return {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: input.name,
    description: input.description,
    url: toAbsoluteUrl(input.path),
    inLanguage: SITE_LANGUAGE,
    breadcrumb: input.breadcrumbPaths
      ? {
          "@type": "BreadcrumbList",
          itemListElement: input.breadcrumbPaths.map((item, index) => ({
            "@type": "ListItem",
            position: index + 1,
            name: item.name,
            item: toAbsoluteUrl(item.path),
          })),
        }
      : undefined,
    isPartOf: {
      "@id": `${SITE_URL}#website`,
    },
  };
}

export function buildHowToSchema(input: HowToInput): SchemaObject {
  return {
    "@context": "https://schema.org",
    "@type": "HowTo",
    name: input.name,
    description: input.description,
    inLanguage: SITE_LANGUAGE,
    url: toAbsoluteUrl(input.path),
    step: input.steps.map((step, index) => ({
      "@type": "HowToStep",
      position: index + 1,
      text: step,
      url: `${toAbsoluteUrl(input.path)}#step-${index + 1}`,
    })),
  };
}

export function buildItemListSchema(input: ItemListInput): SchemaObject {
  return {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: input.name,
    description: input.description,
    url: toAbsoluteUrl(input.path),
    inLanguage: SITE_LANGUAGE,
    itemListElement: input.items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item,
    })),
  };
}

export function buildSpeakableSchema(
  path: string,
  cssSelectors: string[] = ["meta[name='description']", "[data-speakable]"],
): SchemaObject {
  return {
    "@context": "https://schema.org",
    "@type": "WebPage",
    "@id": toAbsoluteUrl(path),
    speakable: {
      "@type": "SpeakableSpecification",
      cssSelector: cssSelectors,
    },
  };
}

export function buildVideoObjectSchema(input: {
  name: string;
  description: string;
  thumbnailUrl: string;
  uploadDate: string;
  contentUrl?: string;
  embedUrl?: string;
  duration?: string;
}): SchemaObject {
  return {
    "@context": "https://schema.org",
    "@type": "VideoObject",
    name: input.name,
    description: input.description,
    thumbnailUrl: input.thumbnailUrl,
    uploadDate: input.uploadDate,
    ...(input.contentUrl && { contentUrl: input.contentUrl }),
    ...(input.embedUrl && { embedUrl: input.embedUrl }),
    ...(input.duration && { duration: input.duration }),
    publisher: {
      "@id": `${SITE_URL}#organization`,
    },
  };
}

export function buildAggregateRatingSchema(input: {
  ratingValue: number;
  reviewCount: number;
  bestRating?: number;
}): SchemaObject {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "@id": `${SITE_URL}#software`,
    name: SITE_NAME,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Windows",
    aggregateRating: {
      "@type": "AggregateRating",
      ratingValue: input.ratingValue,
      reviewCount: input.reviewCount,
      bestRating: input.bestRating ?? 5,
    },
  };
}

export function buildContactPageSchema(path = "/contact"): SchemaObject {
  return {
    "@context": "https://schema.org",
    "@type": "ContactPage",
    name: `${SITE_NAME} 문의하기`,
    description: "SSMaker 고객 문의 및 파트너십 문의 페이지",
    url: toAbsoluteUrl(path),
    inLanguage: SITE_LANGUAGE,
    mainEntity: {
      "@id": `${SITE_URL}#organization`,
    },
  };
}

export function parseKoreanDateToIso(dateText: string) {
  const match = dateText.match(/(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일/);
  if (!match) return undefined;

  const [, year, month, day] = match;
  return `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
}
