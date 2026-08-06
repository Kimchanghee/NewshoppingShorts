"""Public, unauthenticated pages required by desktop distribution channels."""

from html import escape


PRIVACY_EFFECTIVE_DATE = "2026년 8월 6일"
PRIVACY_CONTACT_URL = "https://github.com/Kimchanghee/NewshoppingShorts/issues"


def render_privacy_policy() -> str:
    """Return the Korean SSMaker privacy policy as a standalone HTML page."""
    contact_url = escape(PRIVACY_CONTACT_URL, quote=True)
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SSMaker 개인정보처리방침</title>
  <style>
    :root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
    body {{ max-width: 800px; margin: 0 auto; padding: 32px 20px 64px; line-height: 1.7; }}
    h1, h2 {{ line-height: 1.3; }}
    h2 {{ margin-top: 2rem; }}
    .meta {{ color: #666; }}
    a {{ color: #1769aa; }}
    @media (prefers-color-scheme: dark) {{ .meta {{ color: #aaa; }} a {{ color: #70b7ff; }} }}
  </style>
</head>
<body>
  <main>
    <h1>SSMaker 개인정보처리방침</h1>
    <p class="meta">시행일: {PRIVACY_EFFECTIVE_DATE}</p>
    <p>YMcompany(이하 “회사”)는 SSMaker 데스크톱 앱과 인증·구독 서비스를 제공하면서 이용자의 개인정보를 안전하게 처리합니다.</p>

    <h2>1. 처리하는 정보</h2>
    <ul>
      <li>회원가입 및 인증: 이름, 아이디, 비밀번호의 단방향 해시, 연락처, 선택 입력 이메일, 가입·접속 IP, 로그인 및 앱 버전 기록</li>
      <li>구독 및 결제: 구독 상태, 결제 식별자와 처리 결과. 정기 결제용 키가 필요한 경우 암호화하여 보관하며 카드 원문 전체를 직접 저장하지 않습니다.</li>
      <li>앱 기능: 이용자가 직접 입력한 상품 URL, API 설정, 영상·음성·자막 파일과 작업 결과. 대부분의 제작 데이터와 외부 서비스 인증 정보는 이용자의 PC에 저장됩니다.</li>
      <li>선택적 소식 수신: 이용자가 별도로 동의한 경우 이메일 주소와 동의 기록</li>
    </ul>

    <h2>2. 이용 목적</h2>
    <p>계정 생성과 본인 인증, 중복 로그인 방지, 무료 체험·구독 및 작업량 관리, 결제 처리, 고객 지원, 오류·보안 대응, 앱 업데이트 제공에 사용합니다.</p>

    <h2>3. 외부 서비스와 제공</h2>
    <p>이용자가 해당 기능을 실행할 때 YouTube, Instagram, TikTok, Threads, Linktree, 쿠팡 파트너스, 생성형 AI 및 음성·영상 처리 서비스의 API로 이용자가 선택한 콘텐츠나 인증 정보가 전송될 수 있습니다. 각 서비스의 처리는 해당 사업자의 개인정보처리방침을 따릅니다. 서버 운영·결제·보안에 필요한 범위에서 클라우드 호스팅 및 결제 처리 사업자가 수탁 처리할 수 있습니다.</p>

    <h2>4. 보유 및 삭제</h2>
    <p>개인정보는 서비스 제공과 법적 의무 이행에 필요한 기간 동안만 보유하고 목적이 끝나면 안전하게 삭제하거나 익명화합니다. 이용자는 앱 설정에서 로컬 데이터와 외부 서비스 연결 정보를 삭제할 수 있으며, 계정 정보의 열람·정정·삭제는 아래 문의처로 요청할 수 있습니다.</p>

    <h2>5. 보호 조치</h2>
    <p>전송 구간 암호화(HTTPS), 비밀번호 해시, 민감한 결제 키 암호화, 접근 권한 제한, 요청 속도 제한과 보안 로그 최소화를 적용합니다.</p>

    <h2>6. 이용자의 선택과 권리</h2>
    <p>선택 정보 제공과 마케팅 수신을 거부할 수 있으며, 거부해도 핵심 앱 기능 이용에는 영향을 주지 않습니다. 외부 플랫폼 연결은 이용자가 직접 설정하고 언제든 해제할 수 있습니다.</p>

    <h2>7. 아동의 개인정보</h2>
    <p>SSMaker는 아동을 대상으로 설계된 서비스가 아니며, 법정대리인의 동의 없이 아동의 개인정보를 의도적으로 수집하지 않습니다.</p>

    <h2>8. 방침 변경 및 문의</h2>
    <p>중요한 변경은 앱 또는 배포 페이지를 통해 알립니다. 개인정보 관련 문의나 권리 행사는 <a href="{contact_url}">SSMaker 고객 지원</a>으로 접수해 주세요.</p>
  </main>
</body>
</html>"""
