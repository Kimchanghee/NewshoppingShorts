"""Release-order and credential-boundary regression tests."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_cloud_run_deploy_migrates_before_traffic_switch():
    for relative in ("backend/deploy.sh", "backend/deploy_to_cloudrun.bat"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "--no-traffic" in text
        assert "alembic,upgrade,head" in text
        assert "jobs execute" in text
        assert "update-traffic" in text
        assert text.index("jobs execute") < text.index("update-traffic")
        assert "ADMIN_PASSWORD_HASH" in text
        assert "ADMIN_SESSION_PEPPER" in text


def test_vercel_build_fails_closed_on_migration_error():
    text = (ROOT / "vercel.json").read_text(encoding="utf-8")
    assert '"buildCommand": "cd backend && python -m alembic upgrade head"' in text


def test_vercel_function_requirements_match_backend_requirements():
    def normalized(relative: str) -> list[str]:
        return [
            line.strip()
            for line in (ROOT / relative).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

    assert normalized("api/requirements.txt") == normalized("backend/requirements.txt")


def test_version_update_workflows_never_forward_full_admin_key():
    for relative in (
        ".github/workflows/build-and-deploy.yml",
        ".github/workflows/update-app-version-api.yml",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        update_section = text[text.index("Update server version API"):]
        assert "secrets.ADMIN_API_KEY" not in update_section
        assert "token_candidates" not in update_section
        assert "RejectRedirects" in update_section
