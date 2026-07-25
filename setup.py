"""Root package entrypoint used by Vercel's Python dependency builder."""

from pathlib import Path

from setuptools import find_packages, setup


ROOT = Path(__file__).parent


def read_backend_requirements() -> list[str]:
    return [
        line.strip()
        for line in (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


setup(
    name="ssmaker-auth-api",
    version="0.1.0",
    description="SSMaker authentication API",
    package_dir={"": "backend"},
    packages=find_packages(where="backend"),
    install_requires=read_backend_requirements(),
    python_requires=">=3.10",
)
