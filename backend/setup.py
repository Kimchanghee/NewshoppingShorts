"""Package definition for deploying the authentication API as a Python dependency."""

from pathlib import Path

from setuptools import find_packages, setup


ROOT = Path(__file__).parent


def read_requirements() -> list[str]:
    return [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


setup(
    name="ssmaker-auth-api",
    version="0.1.0",
    description="SSMaker authentication API",
    packages=find_packages(),
    install_requires=read_requirements(),
    python_requires=">=3.10",
)
