# 관리자 대시보드 운영 경계

## 권위 소스

- 관리자 UI와 BFF 프록시: 이 저장소의 `program-admin-dashboard/`
- 실제 운영 인증·사용자·관리자 API: private `project-user-dashboard` 저장소의 `backend/`
- 이 저장소의 `backend/`는 데스크톱 애플리케이션용 코드이며 운영 관리자 API의 권위 소스가 아니다.

운영 API 계약을 바꿀 때는 `project-user-dashboard/backend`를 먼저 수정하고 해당 API의 회귀 테스트를 통과시킨다. 그 다음 이 저장소의 관리자 BFF allowlist와 UI를 같은 계약에 맞춘다. 운영 API 코드를 두 저장소에 복사하지 않는다.

## Vercel 연결

| 역할 | Vercel 프로젝트 | 프로젝트 ID | 소스 경로 |
| --- | --- | --- | --- |
| 운영 API | `newshopping-shorts-auth` | `prj_cXggAHaOeD3jld6iKz3tNDsOTA56` | `project-user-dashboard/backend` |
| 관리자 UI | `ssmaker-program-admin-dashboard` | `prj_0Ggbf0uhy4lRXIt4z20tEvYlIT1l` | `program-admin-dashboard/` |

관리자 UI의 `AUTH_API_BASE_URL`은 반드시 Vercel 환경변수로 명시하며 production 코드에 기본 운영 URL을 두지 않는다.

현재 관리자 UI production 주소는 `https://ssmaker-program-admin-dashboard-esk931103.vercel.app`이다.

## 인증·프록시 계약

- `/api/session/login`, `/api/session/verify`, `/api/session/logout`은 짧은 TTL의 폐기 가능한 관리자 세션을 사용한다.
- UI의 `/api/admin/*` BFF는 사용자 조회·통계·허용된 구독 및 상태 변경만 전달한다.
- 변경 요청은 운영자와 request ID를 전달하며 운영 API는 변경 전후 값을 감사 로그에 저장한다.
- IP 주소는 관리자 API 응답에서 기본 마스킹한다.

## 안전한 배포 순서

1. 운영 API와 UI 테스트를 로컬에서 통과시킨다.
2. 운영 API preview를 배포하고 health, 로그인, 통계 및 읽기 전용 조회를 확인한다.
3. UI preview가 API preview를 보도록 연결해 로그인과 서버 필터를 확인한다.
4. diff와 배포 대상을 재검토한 뒤 API production, UI production 순서로 배포한다.
5. production에서 health, 로그인, 프로그램 전환, 통계, 상세 조회를 비파괴 방식으로 검증한다.
