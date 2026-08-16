import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
WEBSITE_ROOT = REPOSITORY_ROOT / "website"


def test_landing_site_is_repository_owned_and_provider_independent():
    required_files = {
        "index.html",
        "package.json",
        "package-lock.json",
        "vite.config.ts",
        "src/App.tsx",
        "src/pages/Index.tsx",
        "public/favicon.ico",
        "public/favicon.svg",
        "public/og.jpg",
        "public/robots.txt",
        "public/sitemap.xml",
        "public/site.webmanifest",
    }

    for relative_path in required_files:
        assert (WEBSITE_ROOT / relative_path).is_file(), relative_path

    text_files = [
        WEBSITE_ROOT / "index.html",
        WEBSITE_ROOT / "package.json",
        WEBSITE_ROOT / "package-lock.json",
        WEBSITE_ROOT / "vite.config.ts",
        *WEBSITE_ROOT.joinpath("src").rglob("*.ts"),
        *WEBSITE_ROOT.joinpath("src").rglob("*.tsx"),
    ]
    content = "\n".join(path.read_text(encoding="utf-8") for path in text_files).lower()
    assert "lovable" not in content
    assert "gpteng" not in content
    assert "/~flock.js" not in content
    assert "/~api/analytics" not in content


def test_vercel_serves_landing_routes_before_the_fastapi_fallback():
    config = json.loads((REPOSITORY_ROOT / "vercel.json").read_text(encoding="utf-8"))
    routes = config["routes"]

    assert config["outputDirectory"] == "website/dist"
    assert "cd ../website && npm ci" in config["buildCommand"]
    assert "npm audit --audit-level=low" in config["buildCommand"]
    assert "npm run check" in config["buildCommand"]
    assert "npm run build" in config["buildCommand"]
    assert routes[0] == {"src": "^/$", "dest": "/index.html"}
    filesystem_index = routes.index({"handle": "filesystem"})
    landing_fallback_index = next(
        index
        for index, route in enumerate(routes)
        if index > filesystem_index and route.get("dest") == "/index.html"
    )
    assert filesystem_index < landing_fallback_index < len(routes) - 1
    assert routes[-1] == {"src": "^/(.*)$", "dest": "/api/index.py"}


def test_desktop_guides_use_the_independent_custom_domain():
    settings_source = (REPOSITORY_ROOT / "ui/panels/settings_tab.py").read_text(
        encoding="utf-8"
    )

    assert 'SETUP_NOTICE_BASE_URL = "https://shoppingshorts.store/notice"' in settings_source
    assert "ssmaker.lovable.app" not in settings_source
