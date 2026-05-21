# Computer Use Provider Comparison (2026-05-21)

비교 대상: **OpenAI Codex (CLI + computer-use MCP)** vs **Google Gemini Computer Use**  
평가 기준: (1) 실사용 안정성 신호 (2) 정확도/성능 공개 수치 (3) 우리 앱 적용 난이도

## 1) 공개 성능/정확도 지표

- OpenAI는 GPT-5.4 발표에서 OSWorld-Verified 벤치마크 점수 **74.9**를 공개함.
  - 출처: https://openai.com/index/introducing-gpt-5-4/
- OpenAI API 문서에서 `computer-use-preview`는 deprecated 되었고, `computer` tool + `gpt-5.5` 사용을 권장함.
  - 출처: https://platform.openai.com/docs/guides/tools-computer-use
- Google Gemini 문서의 Computer Use는 여전히 **preview** 모델 계열을 중심으로 제공되며(예: `gemini-3-flash-preview`), 프로덕션 사용 시 제약/변동 리스크가 명시됨.
  - 출처: https://ai.google.dev/gemini-api/docs/computer-use
  - 출처: https://ai.google.dev/gemini-api/docs/changelog

## 2) 실사용 신호(후기/현장 이슈)

- Google 공식 포럼에서 Computer Use 관련 할당량/가용성 이슈 리포트가 지속적으로 보임.
  - 예: https://discuss.ai.google.dev/t/computer-use-model-runs-out-of-capacity-immediately/85882
  - 예: https://discuss.ai.google.dev/t/persistent-429-errors-for-computer-use-preview-models/100183
- OpenAI Codex 측도 이슈가 존재하지만, 본 프로젝트 환경에서는 CLI 로그인 + MCP 활성화 검증이 즉시 가능했고 `computer-use` 서버 감지가 성공함.

## 3) 우리 앱 기준 결론

2026-05-21 기준으로, 우리 앱(설정 탭 자동 셋업 보조)에서는 **Codex CLI 연동이 우선**이 합리적:

1. 로컬 macOS 앱 + 브라우저 혼합 워크플로우에 직접 연결 가능  
2. 현재 머신에서 `codex login status`, `codex mcp list`로 즉시 상태 점검 가능  
3. Setup Assistant에 단계별 프롬프트를 자동 생성해 사람 개입(로그인/2FA/캡차/키 발급)만 남기는 운용이 가능

> 정책: 로그인/2FA/캡차/법적 동의/API 키 발급은 사용자 수행, 나머지 탐색/입력/이동은 Codex가 수행.
