# SSMaker Program Admin

수익형 웹사이트 대시보드와 분리된 프로그램 사용자 DB 운영 콘솔입니다.

## 기능

- 운영 관리자 비밀번호 로그인 및 HTTP-only 세션
- 프로그램별 사용자 검색, 필터, 페이지 이동
- 사용자 상세 정보와 로그인 이력
- 구독 연장, 축소, 회수
- 계정 활성/비활성 전환
- 사용자 삭제(사용자명 재입력 확인)
- 사용자·구독·온라인·작업 통계

## 로컬 실행

```bash
npm install
copy .env.example .env.local
npm run dev
```

`AUTH_API_BASE_URL`은 서버 전용 환경변수이며 브라우저 번들에 포함되지 않습니다.
