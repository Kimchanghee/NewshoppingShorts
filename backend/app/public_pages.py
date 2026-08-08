"""Public, unauthenticated legal pages for the SSMaker desktop service."""

from html import escape


LEGAL_EFFECTIVE_DATE = "2026년 8월 8일"
PRIVACY_EFFECTIVE_DATE = LEGAL_EFFECTIVE_DATE
PRIVACY_CONTACT_EMAIL = "k931103@gmail.com"
PRIVACY_CONTACT_URL = f"mailto:{PRIVACY_CONTACT_EMAIL}"
PRIVACY_URL = "https://newshopping-shorts-auth.vercel.app/privacy"
TERMS_URL = "https://newshopping-shorts-auth.vercel.app/terms"
LEGAL_TEMPLATE_SOURCE = "https://github.com/kimlawtech/korean-privacy-terms"


def _render_page(*, title: str, label: str, body: str) -> str:
    privacy_url = escape(PRIVACY_URL, quote=True)
    terms_url = escape(TERMS_URL, quote=True)
    source_url = escape(LEGAL_TEMPLATE_SOURCE, quote=True)
    privacy_current = 'aria-current="page"' if label == "PRIVACY" else ""
    terms_current = 'aria-current="page"' if label == "TERMS" else ""
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{escape(title)}</title>
  <style>
    :root {{ font-family: Pretendard, "Malgun Gothic", system-ui, sans-serif; color:#171717; background:#f7f7f8; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; line-height:1.75; word-break:keep-all; }}
    header {{ position:sticky; top:0; z-index:1; background:rgba(255,255,255,.94); border-bottom:1px solid #e7e7ea; backdrop-filter:blur(10px); }}
    nav {{ max-width:920px; margin:0 auto; padding:15px 24px; display:flex; align-items:center; gap:20px; }}
    .brand {{ margin-right:auto; color:#171717; font-weight:800; text-decoration:none; letter-spacing:-.02em; }}
    nav a:not(.brand) {{ color:#5f6368; font-size:14px; text-decoration:none; }}
    nav a[aria-current="page"] {{ color:#e31639; font-weight:700; }}
    main {{ max-width:920px; margin:32px auto 72px; padding:44px 56px 56px; background:#fff; border:1px solid #e7e7ea; border-radius:20px; box-shadow:0 12px 40px rgba(20,20,25,.05); }}
    .eyebrow {{ margin:0 0 8px; color:#e31639; font-size:13px; font-weight:800; letter-spacing:.08em; }}
    h1 {{ margin:0; font-size:36px; line-height:1.3; letter-spacing:-.045em; }}
    h2 {{ margin:42px 0 12px; padding-top:4px; font-size:21px; line-height:1.45; letter-spacing:-.025em; }}
    h3 {{ margin:24px 0 8px; font-size:16px; }}
    p, li, td, th {{ font-size:15px; }}
    .meta {{ margin:12px 0 32px; color:#73757b; font-size:14px; }}
    .summary {{ padding:18px 20px; background:#fff5f6; border:1px solid #ffd8df; border-radius:12px; }}
    ul, ol {{ padding-left:23px; }}
    li + li {{ margin-top:6px; }}
    table {{ width:100%; border-collapse:collapse; margin:14px 0 20px; display:block; overflow-x:auto; }}
    th, td {{ padding:12px 13px; border:1px solid #dedee3; text-align:left; vertical-align:top; min-width:140px; }}
    th {{ background:#f6f6f8; font-weight:700; }}
    a {{ color:#c51232; }}
    footer {{ margin-top:48px; padding-top:24px; border-top:1px solid #e7e7ea; color:#777a80; font-size:12px; }}
    @media (max-width:680px) {{
      nav {{ padding:13px 18px; gap:14px; }}
      main {{ margin:0; padding:32px 20px 48px; border:0; border-radius:0; }}
      h1 {{ font-size:29px; }}
      h2 {{ font-size:19px; }}
    }}
  </style>
</head>
<body>
  <header>
    <nav aria-label="법적 고지">
      <a class="brand" href="/">SSMaker</a>
      <a href="{privacy_url}" {privacy_current}>개인정보처리방침</a>
      <a href="{terms_url}" {terms_current}>이용약관</a>
    </nav>
  </header>
  <main>
    <p class="eyebrow">SSMAKER · {escape(label)}</p>
    {body}
    <footer>
      <p>문서 구조 참고: <a href="{source_url}" rel="noreferrer">kimlawtech/korean-privacy-terms</a> (Apache-2.0). 서비스 사실관계에 맞게 별도로 작성했습니다.</p>
      <p>본 공개 문서는 서비스 운영 정책을 설명하며, 개별 사안에 대한 법률 자문을 대신하지 않습니다.</p>
    </footer>
  </main>
</body>
</html>"""


def render_privacy_policy() -> str:
    """Return a service-specific Korean privacy policy."""
    email = escape(PRIVACY_CONTACT_EMAIL)
    mailto = escape(PRIVACY_CONTACT_URL, quote=True)
    body = f"""
    <h1>SSMaker 개인정보처리방침</h1>
    <p class="meta">시행일 및 최종 개정일: {LEGAL_EFFECTIVE_DATE}</p>
    <p class="summary">YMcompany(이하 “회사”)는 「개인정보 보호법」 제30조에 따라 SSMaker 이용자의 개인정보를 보호하고 관련 고충을 신속하게 처리하기 위해 이 방침을 공개합니다.</p>

    <h2>제1조 개인정보의 처리 목적</h2>
    <ul>
      <li>회원가입, 본인 식별, 로그인 및 계정 보안</li>
      <li>무료 체험, 구독 상태, 작업 가능 횟수 및 결제 처리</li>
      <li>중복 로그인 방지, 비정상 이용 탐지, 장애·보안 사고 대응</li>
      <li>고객 문의 처리, 서비스 품질 개선, 앱 버전 확인 및 업데이트 제공</li>
      <li>별도 선택 동의가 있는 경우 YM 프로그램 소식 제공</li>
    </ul>

    <h2>제2조 처리하는 개인정보의 항목</h2>
    <table>
      <thead><tr><th>구분</th><th>항목</th><th>처리 근거</th></tr></thead>
      <tbody>
        <tr><td>회원가입 필수</td><td>이름, 아이디, 비밀번호의 단방향 해시, 이메일, 연락처, 이용약관·개인정보 동의 여부·문서 버전·동의 일시</td><td>회원가입 시 동의 및 계약 이행</td></tr>
        <tr><td>선택</td><td>YM 프로그램 소식 수신 여부</td><td>별도 선택 동의</td></tr>
        <tr><td>자동 생성</td><td>가입·접속 IP, 접속 일시, 세션 식별자, 앱 버전, 로그인·이용·오류 기록, 구독 및 작업 횟수</td><td>서비스 보안 및 운영상 정당한 이익</td></tr>
        <tr><td>결제 시</td><td>결제 식별자, 상품·금액, 결제 상태와 처리 결과, 암호화된 정기결제 키(해당 시)</td><td>유료서비스 계약 이행 및 법적 의무</td></tr>
      </tbody>
    </table>
    <p>영상·음성·자막, 외부 플랫폼 OAuth 토큰과 API 키 등 제작 자료는 원칙적으로 이용자의 PC에 저장됩니다. 이용자가 특정 외부 기능을 실행하면 선택한 자료가 해당 플랫폼으로 직접 전송될 수 있습니다. 회사는 카드 원문 전체를 직접 저장하지 않습니다. 비밀번호 원문도 보관하지 않습니다.</p>

    <h2>제3조 개인정보의 처리 및 보유 기간</h2>
    <table>
      <thead><tr><th>업무</th><th>보유 기간</th></tr></thead>
      <tbody>
        <tr><td>계정·구독 정보</td><td>회원 탈퇴 또는 서비스 종료 시까지. 다만 관계 법령상 보존 의무가 있으면 해당 기간까지 분리 보관</td></tr>
        <tr><td>계약·청약철회·대금결제 기록</td><td>전자상거래 등에서의 소비자보호에 관한 법률에 따라 5년</td></tr>
        <tr><td>소비자 불만·분쟁처리 기록</td><td>동 법률에 따라 3년</td></tr>
        <tr><td>접속 기록</td><td>통신비밀보호법 등 적용 법령에서 요구하는 기간</td></tr>
        <tr><td>선택적 소식 수신 동의 기록</td><td>동의 철회 또는 회원 탈퇴 시까지, 법적 분쟁 대응에 필요한 경우 관련 기간</td></tr>
      </tbody>
    </table>

    <h2>제4조 개인정보의 제3자 제공</h2>
    <p>회사는 원칙적으로 이용자의 개인정보를 제3자에게 판매하거나 제공하지 않습니다. 다만 이용자의 별도 동의가 있거나 법령에 근거가 있는 경우, 또는 이용자가 YouTube·Google·Instagram·TikTok·Threads·Linktree·쿠팡 파트너스·생성형 AI·음성 및 영상 처리 기능을 직접 실행한 경우 선택한 콘텐츠와 인증 정보가 해당 서비스에 전송될 수 있습니다. 이때 해당 사업자의 정책이 함께 적용됩니다.</p>

    <h2>제5조 개인정보 처리의 위탁</h2>
    <table>
      <thead><tr><th>수탁자</th><th>위탁 업무</th><th>보유 기간</th></tr></thead>
      <tbody>
        <tr><td>Vercel Inc.</td><td>인증 API 및 공개 웹페이지 호스팅</td><td>위탁계약 및 서비스 이용 기간</td></tr>
        <tr><td>Supabase Inc.</td><td>계정·구독 데이터베이스 인프라</td><td>위탁계약 및 서비스 이용 기간</td></tr>
        <tr><td>PAYAPP 운영사</td><td>결제 승인, 정기결제 및 결과 통지</td><td>결제 및 관계 법령상 보존 기간</td></tr>
      </tbody>
    </table>
    <p>수탁자 또는 업무가 변경되면 이 방침을 통해 공개합니다.</p>

    <h2>제6조 개인정보의 국외 이전</h2>
    <p>클라우드 호스팅과 이용자가 선택한 외부 플랫폼 기능은 국외에 위치한 서버를 이용할 수 있습니다. Vercel·Supabase 및 각 외부 플랫폼에 필요한 정보가 서비스 이용 시 암호화된 네트워크를 통해 이전되며, 계정·인증·콘텐츠 처리 목적이 끝나거나 해당 사업자의 정책상 보유 기간이 종료될 때까지 처리될 수 있습니다. 이용자는 외부 플랫폼 연결을 하지 않거나 연결을 해제해 해당 이전을 거부할 수 있으나 관련 기능은 이용할 수 없습니다.</p>

    <h2>제7조 개인정보의 파기 절차 및 방법</h2>
    <p>보유 목적과 기간이 끝난 정보는 지체 없이 파기합니다. 전자 파일은 복구가 어렵도록 삭제하고, 법령상 보존 대상은 별도 분리한 뒤 기간 종료 후 파기합니다. 이용자 PC의 로컬 자료와 외부 플랫폼 토큰은 앱의 연결 해제·삭제 기능 또는 해당 플랫폼 계정에서 직접 삭제할 수 있습니다.</p>

    <h2>제8조 정보주체의 권리, 법정대리인 및 행사 방법</h2>
    <p>이용자는 개인정보 열람, 정정, 삭제, 처리정지, 동의 철회 및 관계 법령상 전송 요구를 요청할 수 있습니다. 본인 확인이 필요한 경우 최소한의 확인 절차를 거치며, 대리인을 통한 요청도 관계 법령에 따라 처리합니다. 요청은 <a href="{mailto}">{email}</a>로 접수해 주세요.</p>

    <h2>제9조 안전성 확보 조치</h2>
    <ul>
      <li>HTTPS 전송 암호화와 운영 데이터 접근 권한 제한</li>
      <li>비밀번호 단방향 해시 및 민감 결제 키 암호화</li>
      <li>세션 만료·강제 로그아웃, 요청 속도 제한, 보안 로그 최소화</li>
      <li>OAuth 토큰·API 키의 사용자별 보안 저장소 사용</li>
    </ul>

    <h2>제10조 개인정보 자동 수집 장치</h2>
    <p>현재 공개 법적 고지 페이지는 맞춤형 광고 쿠키를 사용하지 않습니다. 호스팅 사업자가 보안과 장애 대응을 위한 최소 접속 기록을 생성할 수 있습니다.</p>

    <h2>제11조 만 14세 미만 아동</h2>
    <p>SSMaker는 만 14세 미만 아동을 대상으로 하지 않으며 법정대리인의 확인 없는 아동 회원가입을 받지 않습니다. 관련 사실을 확인하면 필요한 확인과 삭제 조치를 합니다.</p>

    <h2>제12조 개인정보 보호책임자 및 문의</h2>
    <p>운영 주체: YMcompany<br>개인정보 보호 및 고객 문의: <a href="{mailto}">{email}</a></p>

    <h2>제13조 방침의 변경</h2>
    <p>법령 또는 서비스 변경으로 이 방침이 달라지면 시행 전에 앱 또는 이 페이지를 통해 알립니다. 중요한 변경은 필요한 경우 별도 동의를 받습니다.</p>
    """
    return _render_page(title="SSMaker 개인정보처리방침", label="PRIVACY", body=body)


def render_terms_of_service() -> str:
    """Return Korean terms tailored to the desktop subscription service."""
    email = escape(PRIVACY_CONTACT_EMAIL)
    mailto = escape(PRIVACY_CONTACT_URL, quote=True)
    privacy = escape(PRIVACY_URL, quote=True)
    body = f"""
    <h1>SSMaker 서비스 이용약관</h1>
    <p class="meta">시행일 및 최종 개정일: {LEGAL_EFFECTIVE_DATE}</p>
    <p class="summary">이 약관은 YMcompany(이하 “회사”)가 제공하는 SSMaker 데스크톱 앱, 인증·구독 및 관련 서비스의 이용 조건과 회사와 회원의 권리·의무를 정합니다.</p>

    <h2>제1조 목적 및 적용</h2>
    <p>회원이 회원가입 화면에서 이 약관을 확인하고 개별 동의한 뒤 가입을 완료하면 약관에 동의한 것으로 봅니다. 개인정보 처리에는 별도의 <a href="{privacy}">개인정보처리방침</a>이 적용됩니다.</p>

    <h2>제2조 용어의 정의</h2>
    <ul>
      <li>“서비스”란 SSMaker 앱과 계정·구독·업데이트 및 고객지원 기능을 말합니다.</li>
      <li>“회원”이란 계정을 만들고 서비스를 이용하는 자를 말합니다.</li>
      <li>“콘텐츠”란 회원이 입력·생성·편집·업로드하는 영상, 이미지, 음성, 자막, 링크와 관련 자료를 말합니다.</li>
      <li>“외부 서비스”란 YouTube, Google, 소셜 플랫폼, 쇼핑·AI·음성·영상 API 등 회사가 직접 운영하지 않는 서비스를 말합니다.</li>
    </ul>

    <h2>제3조 약관의 게시 및 변경</h2>
    <p>회사는 약관을 가입 화면과 웹사이트에서 확인할 수 있게 합니다. 관련 법령을 위반하지 않는 범위에서 약관을 변경할 수 있으며, 적용일과 주요 사유를 시행 전에 앱 또는 웹사이트에 알립니다. 회원에게 불리한 중요한 변경은 관계 법령에 따른 기간과 방법으로 고지하고 필요한 경우 다시 동의를 받습니다.</p>

    <h2>제4조 회원가입과 계정</h2>
    <ol>
      <li>회원은 정확한 정보를 제공하고 변경 시 최신 상태로 유지해야 합니다.</li>
      <li>계정과 비밀번호를 안전하게 관리해야 하며 타인에게 양도·대여할 수 없습니다.</li>
      <li>만 14세 미만은 법정대리인 확인 없이 가입할 수 없습니다.</li>
      <li>도용, 허위 정보, 서비스 방해 또는 법령 위반이 확인되면 가입을 거절하거나 이용을 제한할 수 있습니다.</li>
    </ol>

    <h2>제5조 서비스의 제공 및 변경</h2>
    <p>회사는 영상 제작 보조, 외부 플랫폼 연결·업로드, 계정·구독 관리와 업데이트 기능을 제공합니다. 보안, 기술 개선, 외부 API 정책 변경 또는 운영상 필요에 따라 기능을 변경할 수 있으며 중요한 변경은 가능한 범위에서 사전 안내합니다. 유지보수·장애·천재지변·외부 사업자 중단 등 불가피한 사유가 있으면 일시 중단할 수 있습니다.</p>

    <h2>제6조 무료 체험과 유료서비스</h2>
    <ol>
      <li>무료 체험의 기간·횟수·범위는 가입 화면이나 앱에 표시된 정책을 따릅니다.</li>
      <li>유료서비스의 가격, 기간, 자동결제 여부와 제공 내용은 결제 전에 표시합니다.</li>
      <li>청약철회·해지·환불은 전자상거래 등에서의 소비자보호에 관한 법률 등 관계 법령과 결제 화면에 고지된 조건을 따릅니다. 법령상 권리를 부당하게 제한하지 않습니다.</li>
      <li>결제 오류나 부당 과금이 확인되면 회사 또는 결제 사업자에게 정정을 요청할 수 있습니다.</li>
    </ol>

    <h2>제7조 회원의 의무</h2>
    <p>회원은 다음 행위를 해서는 안 됩니다.</p>
    <ul>
      <li>타인의 계정·개인정보·결제수단 또는 저작물을 무단 사용하는 행위</li>
      <li>악성코드 배포, 역공학, 자동화된 과도한 요청 등 서비스 안정성을 해치는 행위</li>
      <li>외부 플랫폼의 약관, 광고·전자상거래·저작권·표시 의무 등 관계 법령을 위반하는 행위</li>
      <li>불법·유해·기만적 콘텐츠를 제작·배포하거나 회사 또는 제3자의 권리를 침해하는 행위</li>
    </ul>

    <h2>제8조 콘텐츠와 지식재산권</h2>
    <p>회원이 적법하게 보유한 원본 콘텐츠의 권리는 회원에게 있습니다. 회원은 서비스 처리와 자신이 선택한 외부 플랫폼 전송에 필요한 범위에서만 회사와 해당 사업자가 콘텐츠를 처리하도록 허용합니다. 앱, UI, 문서, 상표와 회사가 제공한 소프트웨어의 권리는 회사 또는 정당한 권리자에게 있습니다.</p>

    <h2>제9조 외부 서비스</h2>
    <p>외부 서비스 연결은 회원이 직접 승인하며 해당 사업자의 약관·정책·API 할당량과 심사 기준이 적용됩니다. 외부 사업자의 정책 변경, 계정 제한, API 중단 또는 콘텐츠 심사 결과는 회사가 통제할 수 없습니다. 회원은 업로드 전에 콘텐츠, 공개 범위, 링크와 표시 내용을 확인해야 합니다.</p>

    <h2>제10조 이용 제한 및 계약 해지</h2>
    <p>회사는 약관·법령 위반이나 보안 위험이 확인되면 사전 통지 후 이용을 제한할 수 있습니다. 긴급한 보안 침해나 타인 피해 방지를 위해 먼저 제한한 뒤 알릴 수 있습니다. 회원은 고객 문의를 통해 탈퇴 또는 유료서비스 해지를 요청할 수 있으며, 회사는 법적 보존 의무가 없는 정보를 처리 목적 종료 후 삭제합니다.</p>

    <h2>제11조 회사의 의무</h2>
    <p>회사는 관계 법령과 이 약관을 준수하고 서비스를 안정적으로 제공하기 위해 합리적인 보안·운영 조치를 취합니다. 회원의 정당한 문의와 불만을 처리하고 개인정보를 개인정보처리방침에 따라 보호합니다.</p>

    <h2>제12조 책임의 범위</h2>
    <p>회사는 고의 또는 과실로 회원에게 발생한 손해에 대해 관계 법령에 따라 책임을 부담합니다. 회원의 귀책, 불가항력, 외부 서비스 장애 또는 회원이 검토하지 않은 자동 생성 결과로 발생한 손해에 대해서는 회사의 책임 없는 범위에서 책임을 지지 않습니다. 이 조항은 소비자보호법상 배제할 수 없는 권리를 제한하지 않습니다.</p>

    <h2>제13조 준거법 및 분쟁 해결</h2>
    <p>이 약관은 대한민국 법률을 따릅니다. 분쟁이 발생하면 상호 협의하여 해결하며, 해결되지 않으면 민사소송법 등 관계 법령이 정한 관할 법원에서 처리합니다. 소비자는 관계 기관의 분쟁조정 절차를 이용할 수 있습니다.</p>

    <h2>제14조 문의</h2>
    <p>운영 주체: YMcompany<br>서비스·결제·약관 문의: <a href="{mailto}">{email}</a></p>
    """
    return _render_page(title="SSMaker 서비스 이용약관", label="TERMS", body=body)
