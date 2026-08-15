"""Canonical catalog for every bundled, user-selectable font.

The downloader, integrity verifier, UI, settings, and video renderer all use
this module.  Asset checks describe the decoded TTF bytes (not merely the
download container), so an upstream response cannot silently change what is
shipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from types import MappingProxyType
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FONTS_DIR = PROJECT_ROOT / "fonts"
DEFAULT_LICENSES_DIR = PROJECT_ROOT / "resources" / "licenses"

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Verify representative common Korean syllables.  Do not use the final codepoint
# of the full modern Hangul block: some officially distributed display fonts
# intentionally ship a smaller, curated Korean character set.
HANGUL_SENTINELS = (0xAC00, 0xD55C, 0xAE00)  # 가, 한, 글


@dataclass(frozen=True)
class ArchiveSource:
    url: str
    size: int
    sha256: str
    member: str


@dataclass(frozen=True)
class FontAsset:
    filename: str
    size: int
    sha256: str
    family: str
    style: str
    url: str | None = None
    archive: ArchiveSource | None = None
    browser_user_agent: bool = False
    hangul_codepoints: tuple[int, ...] = HANGUL_SENTINELS

    def __post_init__(self) -> None:
        if (self.url is None) == (self.archive is None):
            raise ValueError(f"{self.filename} must have exactly one download source")


@dataclass(frozen=True)
class FontChoice:
    id: str
    display_name: str
    description: str
    compact_description: str
    asset: FontAsset
    license_name: str
    license_files: tuple[str, ...]
    source_page: str


@dataclass(frozen=True)
class LicenseNotice:
    filename: str
    size: int
    sha256: str


FONT_CHOICES = (
    FontChoice(
        id="seoul_hangang",
        display_name="서울 한강체",
        description="모던하고 깔끔한 서울시 공식 폰트",
        compact_description="모던하고 깔끔한",
        asset=FontAsset(
            filename="SeoulHangangB.ttf",
            size=7_344_552,
            sha256="c33bab9596c0b60ada7ea9b3456e00e1cfd8ee63c599db2f0ef71a84ba54769b",
            family="SeoulHangang",
            style="B",
            archive=ArchiveSource(
                url="https://www.seoul.go.kr/upload/seoul/font/seoul_font3.zip",
                size=50_350_440,
                sha256="7ab485b98f5b1a1b05cfd04484dd49a62f856be8506223cd99e5ea1a33e400a7",
                member="seoul_font/서울한강/SeoulHangangB.ttf",
            ),
        ),
        license_name="KOGL Type 1 (attribution)",
        license_files=("FONT-NOTICES.md", "KOGL-TYPE-1-Seoul-Typeface.txt"),
        source_page="https://www.seoul.go.kr/seoul/font.do",
    ),
    FontChoice(
        id="pretendard",
        display_name="프리텐다드",
        description="세련된 현대적 고딕체",
        compact_description="세련된 현대적",
        asset=FontAsset(
            filename="Pretendard-ExtraBold.ttf",
            size=2_669_648,
            sha256="eedbd2877218242323bdff816684f7f5c325e54ae820d5b78eec9a5e5c7edef6",
            family="Pretendard",
            style="ExtraBold",
            archive=ArchiveSource(
                url="https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip",
                size=47_304_526,
                sha256="04be351a74d6bf7d60c480a3087e51d185485d35a52023142af1df19eb8c428a",
                member="public/static/alternative/Pretendard-ExtraBold.ttf",
            ),
        ),
        license_name="SIL Open Font License 1.1",
        license_files=("FONT-NOTICES.md", "OFL-1.1.txt"),
        source_page="https://github.com/orioncactus/pretendard/releases/tag/v1.3.9",
    ),
    FontChoice(
        id="noto_sans_kr",
        display_name="Noto Sans KR",
        description="상업 이용 가능한 구글 Noto 한글 폰트",
        compact_description="깔끔한 범용",
        asset=FontAsset(
            filename="NotoSansKR-Variable.ttf",
            size=10_414_588,
            sha256="194018e6b2b293a7964f037b25c0249ce1418bc9ab3c971060a03aa57861e252",
            family="Noto Sans KR",
            style="Thin",
            url="https://raw.githubusercontent.com/google/fonts/4efc2774c63917927efe769ca845def6bd6debae/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf",
        ),
        license_name="SIL Open Font License 1.1",
        license_files=("FONT-NOTICES.md", "OFL-1.1.txt"),
        source_page="https://github.com/google/fonts/tree/4efc2774c63917927efe769ca845def6bd6debae/ofl/notosanskr",
    ),
    FontChoice(
        id="suit",
        display_name="SUIT",
        description="요즘 서비스 UI에 잘 맞는 모던 고딕체",
        compact_description="요즘 UI 감성",
        asset=FontAsset(
            filename="SUIT-Heavy.ttf",
            size=583_792,
            sha256="9dbd449ccaeb26bc154d66fa6a8d8a9089a00abdf4f556707031c710ab1b46f9",
            family="SUIT",
            style="Heavy",
            url="https://raw.githubusercontent.com/sun-typeface/SUIT/3183ae8a6024b526c2ba98fb877154743770a305/fonts/static/ttf/SUIT-Heavy.ttf",
        ),
        license_name="SIL Open Font License 1.1",
        license_files=("FONT-NOTICES.md", "OFL-1.1.txt"),
        source_page="https://github.com/sun-typeface/SUIT/tree/3183ae8a6024b526c2ba98fb877154743770a305",
    ),
    FontChoice(
        id="gmarketsans",
        display_name="G마켓 산스",
        description="인기 있는 고품질 무료 폰트",
        compact_description="인기 있는 고품질",
        asset=FontAsset(
            filename="GmarketSansTTFBold.ttf",
            size=2_511_976,
            sha256="ff7c354dd1a324e4cecc1223c4f71e74fa81be7027e0c7f6324c475909cacefc",
            family="Gmarket Sans TTF",
            style="Bold",
            archive=ArchiveSource(
                url="https://corp.gmarket.com/fonts/GmarketSansTTF.zip",
                size=2_640_278,
                sha256="a2cc0ab9eb3bc868a6f2affd89fa1d4718cb6e1226dcb695b05d0d2ff417ae02",
                member="GmarketSansTTFBold.ttf",
            ),
        ),
        license_name="SIL Open Font License 1.1",
        license_files=("FONT-NOTICES.md", "OFL-1.1.txt"),
        source_page="https://corp.gmarket.com/fonts/",
    ),
    FontChoice(
        id="paperlogy",
        display_name="페이퍼로지",
        description="부드러운 곡선이 매력적인 폰트",
        compact_description="부드러운 곡선",
        asset=FontAsset(
            filename="Paperlogy-9Black.ttf",
            size=1_305_192,
            sha256="9a2149095d72ae268abb3acf6a3a6ab4adcae8c0ebb98999bd2d607f22149bc0",
            family="Paperlogy",
            style="9 Black",
            archive=ArchiveSource(
                url="https://raw.githubusercontent.com/Freesentation/paperlogy/8ef35f53b318c7ca914c52b1b382b9a8bad07a61/Paperlogy-1.001.zip",
                size=5_609_426,
                sha256="6ffa5c8fc7539c61f419dcd2c4dd714556412f2455d26399e83792968c7b23d6",
                member="Paperlogy-9Black.ttf",
            ),
        ),
        license_name="SIL Open Font License 1.1",
        license_files=("FONT-NOTICES.md", "OFL-1.1.txt"),
        source_page="https://freesentation.blog/paperlogyfont",
    ),
    FontChoice(
        id="unpeople_gothic",
        display_name="유앤피플",
        description="부드럽고 가독성 좋은 고딕체",
        compact_description="부드럽고 가독성",
        asset=FontAsset(
            filename="UnPeople.ttf",
            size=2_495_412,
            sha256="eed9c46a5e5627d5c837facb8eae2c246489f1995edf5e4d02ba54c4bc0fff58",
            family="UNPEOPLE Gothic UNI",
            style="Regular",
            url="https://gongu.copyright.or.kr/gongu/wrt/cmmn/wrtFileDownload.do?wrtSn=13210384&fileSn=4",
            browser_user_agent=True,
        ),
        license_name="SIL Open Font License 1.1",
        license_files=("FONT-NOTICES.md", "OFL-1.1.txt"),
        source_page="https://www.unpl.co.kr/portal/main/contents.do?menuNo=200011",
    ),
)

FONT_BY_ID: Mapping[str, FontChoice] = MappingProxyType(
    {choice.id: choice for choice in FONT_CHOICES}
)
LICENSE_NOTICES: Mapping[str, LicenseNotice] = MappingProxyType(
    {
        notice.filename: notice
        for notice in (
            LicenseNotice(
                "FONT-NOTICES.md",
                2_038,
                "35eeae9498081a03b9189e09435aef5aa7fae6f28f0edb30831625f83b91aea3",
            ),
            LicenseNotice(
                "KOGL-TYPE-1-Seoul-Typeface.txt",
                737,
                "bfb9aa5028015fbe1817114b0b8084a4b9d07900f1ff231d34d33c0a26ade89e",
            ),
            LicenseNotice(
                "OFL-1.1.txt",
                4_008,
                "71801033d3c6353ba9400dc14791eecdd6a40dea827a557b2e2c22e36a997ff7",
            ),
        )
    }
)
FONT_IDS = tuple(FONT_BY_ID)
DEFAULT_FONT_ID = "seoul_hangang"
DEFAULT_WATERMARK_FONT_ID = "pretendard"

_LEGACY_FONT_ID_ALIASES = MappingProxyType(
    {
        "gmarket_sans": "gmarketsans",
        "unpeople": "unpeople_gothic",
    }
)
_RUNTIME_FALLBACK_IDS = (
    "pretendard",
    "noto_sans_kr",
    "suit",
    "gmarketsans",
    "paperlogy",
    "unpeople_gothic",
    "seoul_hangang",
)


def normalize_font_id(font_id: object, fallback: str = DEFAULT_FONT_ID) -> str:
    """Return a current catalog ID, migrating known legacy spellings."""
    if isinstance(font_id, str):
        candidate = _LEGACY_FONT_ID_ALIASES.get(font_id.strip(), font_id.strip())
        if candidate in FONT_BY_ID:
            return candidate
    return fallback if fallback in FONT_BY_ID else DEFAULT_FONT_ID


def font_candidate_paths(
    font_id: object,
    fonts_dir: str | Path,
    *,
    include_fallbacks: bool = False,
    fallback: str = DEFAULT_FONT_ID,
) -> list[str]:
    """Resolve a selected font, optionally followed by catalog fallbacks."""
    selected_id = normalize_font_id(font_id, fallback)
    ids = [selected_id]
    if include_fallbacks:
        ids.extend(item for item in _RUNTIME_FALLBACK_IDS if item != selected_id)
    base = Path(fonts_dir)
    return [str(base / FONT_BY_ID[item].asset.filename) for item in ids]


def runtime_fonts_dir() -> Path:
    """Locate bundled fonts in source, one-folder, or one-file app layouts."""
    if getattr(sys, "frozen", False):
        beside_executable = Path(sys.executable).resolve().parent / "fonts"
        if beside_executable.is_dir():
            return beside_executable
        return Path(getattr(sys, "_MEIPASS", beside_executable.parent)) / "fonts"
    return DEFAULT_FONTS_DIR


def ui_font_options(fonts_dir: str | Path = DEFAULT_FONTS_DIR) -> list[dict[str, object]]:
    """Return UI-ready dictionaries without duplicating catalog content."""
    base = Path(fonts_dir)
    return [
        {
            "name": choice.display_name,
            "id": choice.id,
            "preview": "쇼핑 숏폼 자막",
            "description": choice.description,
            "compact_description": choice.compact_description,
            "font_paths": [str(base / choice.asset.filename)],
        }
        for choice in FONT_CHOICES
    ]
