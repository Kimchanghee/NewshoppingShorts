from app.public_pages import (
    PRIVACY_CONTACT_EMAIL,
    render_privacy_policy,
    render_terms_of_service,
)


def test_privacy_policy_is_public_html_page():
    html = render_privacy_policy()

    assert "<!doctype html>" in html
    assert "SSMaker 개인정보처리방침" in html
    assert "비밀번호의 단방향 해시" in html
    assert "카드 원문 전체를 직접 저장하지 않습니다" in html
    assert PRIVACY_CONTACT_EMAIL in html
    assert "개인정보의 처리 및 보유 기간" in html
    assert "개인정보 처리의 위탁" in html
    assert "국외 이전" in html
    assert "정보주체의 권리" in html


def test_terms_of_service_is_public_html_page():
    html = render_terms_of_service()

    assert "<!doctype html>" in html
    assert "SSMaker 서비스 이용약관" in html
    assert "서비스의 제공 및 변경" in html
    assert "회원의 의무" in html
    assert "유료서비스" in html
    assert PRIVACY_CONTACT_EMAIL in html
    assert "2026년 8월 13일" in html
    assert "조회수·판매·제휴 수익을 보장하지 않습니다" in html
    assert "연결한 계정과 게시물은 회원이 직접 확인" in html
    assert "외부 서비스의 정책·심사·장애" in html
    assert "고의 또는 과실로 회원에게 발생한 손해" in html
    assert 'aria-labelledby="service-result-notice"' in html
