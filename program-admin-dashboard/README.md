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
대시보드는 이 주소의 다음 백엔드 계약을 사용합니다.

- `POST /user/admin/session/login` — `{ "password": "..." }`로 로그인
- `GET /user/admin/session/verify` — Bearer 세션 검증
- `POST /user/admin/session/logout` — Bearer 세션 종료
- `/user/admin/*` — Bearer 세션을 전달하는 관리자 API

`ADMIN_API_KEY`는 대시보드 환경변수나 브라우저에 두지 않습니다. 백엔드가 발급한 짧은 수명의 관리자 세션만 HTTP-only 쿠키에 저장합니다.

## 검증

```bash
npm run verify
```
