import type { FAQItem } from "@/data/faqs";

export const ANSWER_ENGINE_QAS: FAQItem[] = [
  {
    question: "SSMaker는 어떤 프로그램인가요?",
    answer:
      "SSMaker는 중국 쇼핑 영상을 한국어 쇼핑 숏폼으로 자동 변환하는 Windows 데스크톱 AI 프로그램입니다. 자막 감지, 기존 자막 블러, 한국어 스크립트 생성, TTS 음성 합성, 영상 합성, YouTube Shorts 업로드와 Linktree 검수 흐름을 한 작업선으로 묶습니다.",
  },
  {
    question: "쿠팡 파트너스 단축 링크만 있어도 풀자동으로 시작할 수 있나요?",
    answer:
      "네. 쿠팡 파트너스에서 만든 link.coupang.com/a/... 단축 링크를 SSMaker 풀자동 화면에 붙여넣으면 됩니다. 이미 단축 링크가 있다면 쿠팡 API Key는 필수가 아니며, 원본 coupang.com 상품 URL을 자동 제휴 링크로 바꾸고 싶을 때만 선택적으로 사용합니다.",
  },
  {
    question: "Linktree 자동 등록은 어떻게 동작하나요?",
    answer:
      "일반 사용자는 Linktree 공개 프로필 URL을 저장하고 수동으로 링크 노출을 확인하면 충분합니다. 완전 자동 등록은 Make, Zapier, n8n, Cloudflare Worker 같은 Webhook 중계 주소가 있을 때 상품명, 쿠팡 링크, [001] 형식 번호를 보내는 방식으로 동작합니다.",
  },
  {
    question: "YouTube Shorts 자동 업로드에는 무엇이 필요한가요?",
    answer:
      "Google Cloud에서 YouTube Data API v3를 사용 설정하고 데스크톱 앱 OAuth 클라이언트 JSON을 받은 뒤 SSMaker에 연결해야 합니다. API Key나 서비스 계정이 아니라 사용자의 YouTube 채널 권한을 승인하는 OAuth JSON이 필요합니다.",
  },
  {
    question: "중국어 자막은 영상에 그대로 남나요?",
    answer:
      "아니요. SSMaker는 OCR로 기존 중국어 자막 영역을 감지하고 블러 처리한 뒤, 한국어 스크립트와 TTS 음성을 적용해 한국 쇼핑 채널에 맞는 숏폼 결과물을 만들도록 설계되어 있습니다.",
  },
  {
    question: "누가 SSMaker를 쓰면 좋은가요?",
    answer:
      "구매대행 셀러, 스마트스토어 운영자, 쿠팡 파트너스 콘텐츠 제작자, YouTube Shorts 쇼핑 채널 운영자처럼 상품 영상을 반복적으로 한국어 숏폼으로 만들어야 하는 사용자에게 적합합니다.",
  },
];
