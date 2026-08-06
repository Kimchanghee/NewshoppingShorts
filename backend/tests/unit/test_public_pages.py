from app.public_pages import PRIVACY_CONTACT_URL, render_privacy_policy


def test_privacy_policy_is_public_html_page():
    html = render_privacy_policy()

    assert "<!doctype html>" in html
    assert "SSMaker 개인정보처리방침" in html
    assert "비밀번호의 단방향 해시" in html
    assert "카드 원문 전체를 직접 저장하지 않습니다" in html
    assert PRIVACY_CONTACT_URL in html
