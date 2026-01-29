# -*- coding: utf-8 -*-
"""
Shopping Shorts Maker - 자동 빌드 스크립트

이 스크립트는 PyInstaller를 사용하여 자동으로 exe를 빌드합니다.
의존성 체크 → PyInstaller 설치 → 빌드 → 완료 메시지까지 자동으로 처리합니다.

사용법:
  python build.py           # 기본 빌드 (콘솔 모드)
  python build.py --clean   # 이전 빌드 파일 삭제 후 빌드
  python build.py --debug   # 디버그 모드 빌드
"""

import os
import sys
import subprocess
import shutil
from datetime import datetime

# UTF-8 인코딩 강제 설정 (한글 지원)
import sys
import io

# Windows 콘솔에서 UTF-8 사용
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    else:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )


class Colors:
    """콘솔 색상"""

    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"


def print_header(text):
    """헤더 출력"""
    print(f"{Colors.CYAN}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.CYAN}{text}{Colors.RESET}")
    print(f"{Colors.CYAN}{'=' * 70}{Colors.RESET}")


def print_step(text, icon="ℹ️"):
    """단계 출력"""
    print(f"{icon} {text}")


def print_success(text):
    """성공 메시지"""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")


def print_warning(text):
    """경고 메시지"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")


def print_error(text):
    """오류 메시지"""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")


def check_python_version():
    """Python 버전 체크 (최소 3.14 필요)"""
    major, minor, micro = sys.version_info[:3]
    min_version = (3, 14, 0)

    if (major, minor, micro) < min_version:
        print_error(
            f"Python 버전이 낮습니다. 현재: {major}.{minor}.{micro}, "
            f"필요: {'.'.join(map(str, min_version))}"
        )
        return False

    print_success(f"Python 버전 확인 완료: {major}.{minor}.{micro}")
    return True


def check_spec_file():
    """spec 파일 존재 체크"""
    spec_file = "ssmaker.spec"

    if not os.path.exists(spec_file):
        print_error(f"spec 파일이 없습니다: {spec_file}")
        return False

    print_success(f"spec 파일 확인 완료: {spec_file}")
    return True


def install_pyinstaller():
    """PyInstaller 설치 체크 및 설치"""
    try:
        import PyInstaller

        print_success("PyInstaller가 이미 설치되어 있습니다")
        return True
    except ImportError:
        print_step("PyInstaller가 설치되어 있지 않습니다. 설치 중...", icon="📦")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "pyinstaller"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print_success("PyInstaller 설치 완료")
            return True
        except subprocess.CalledProcessError as e:
            print_error(f"PyInstaller 설치 실패: {e}")
            return False


def check_build_dir():
    """빌드 디렉토리 준비"""
    build_dir = "build"
    dist_dir = "dist"

    # 빌드가 성공하면 dist 디렉토리에 exe가 생성됨

    print_step("빌드 디렉토리 확인 중...")

    # build 디렉토리 체크 (기존 빌드 파일)
    if os.path.exists(build_dir):
        print_warning(f"build 디렉토리가 존재합니다: {build_dir}")

    print_success("빌드 디렉토리 확인 완료")


def clean_build():
    """이전 빌드 파일 삭제"""
    dirs_to_clean = ["build", "dist"]

    print_step("이전 빌드 파일 삭제 중...", icon="🧹")

    for dir_name in dirs_to_clean:
        dir_path = os.path.join(os.getcwd(), dir_name)

        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                print_success(f"{dir_name}/ 삭제 완료")
            except Exception as e:
                print_error(f"{dir_name}/ 삭제 실패: {e}")
        else:
            print(f"  {dir_name}/ 존재하지 않음")


def build_exe(clean=False, debug=False):
    """exe 빌드 실행"""

    print_header("빌드 시작")

    # 1. Python 버전 체크
    if not check_python_version():
        return False

    # 2. spec 파일 체크
    if not check_spec_file():
        return False

    # 3. 이전 빌드 파일 삭제
    if clean:
        clean_build()
    else:
        check_build_dir()

    # 4. PyInstaller 설치 체크
    if not install_pyinstaller():
        return False

    # 5. 빌드 명령어 구성
    print_step("PyInstaller 빌드 시작...", icon="⚙️")

    # 빌드 옵션
    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "ssmaker.spec",
    ]

    # 디버그 모드 옵션 추가
    if debug:
        pyinstaller_cmd.insert(4, "--debug")
        pyinstaller_cmd.remove("--clean")  # 디버그 모드에서는 clean 제거
        print_step("디버그 모드로 빌드합니다", icon="🐛")
    else:
        print_step("릴리스 모드로 빌드합니다", icon="🚀")

    # 6. 빌드 실행
    try:
        start_time = datetime.now()

        result = subprocess.run(
            pyinstaller_cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        # 빌드 시간 계산
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # 빌드 완료 메시지
        if result.returncode == 0:
            print_success(f"빌드 완료! (소요 시간: {duration:.1f}초)")

            # 생성된 exe 파일 경로
            exe_path = os.path.join(os.getcwd(), "dist", "ssmaker.exe")

            if os.path.exists(exe_path):
                file_size_mb = os.path.getsize(exe_path) / (1024 * 1024)
                print_success(f"생성된 exe: dist/ssmaker.exe ({file_size_mb:.1f} MB)")

                print_header("빌드 완료")
                print(
                    f"{Colors.GREEN}┌────────────────────────────────────────┐{Colors.RESET}"
                )
                print(
                    f"{Colors.GREEN}│  exe 파일: dist/ssmaker.exe         │{Colors.RESET}"
                )
                print(
                    f"{Colors.GREEN}│  파일 크기: {file_size_mb:.1f} MB              │{Colors.RESET}"
                )
                print(
                    f"{Colors.GREEN}│  빌드 시간: {duration:.1f}초                  │{Colors.RESET}"
                )
                print(
                    f"{Colors.GREEN}└────────────────────────────────────────┘{Colors.RESET}"
                )
                print()
                print(f"{Colors.CYAN}💡 다음 명령어로 실행하세요:{Colors.RESET}")
                print(f"{Colors.YELLOW}   cd dist{Colors.RESET}")
                print(f"{Colors.YELLOW}   .\\ssmaker.exe{Colors.RESET}")
                print()

            else:
                print_error("exe 파일이 생성되지 않았습니다")

            return True

        else:
            print_error(f"빌드 실패 (코드: {result.returncode})")
            if result.stderr:
                print(f"{Colors.RED}에러 로그:{Colors.RESET}")
                print(result.stderr)
            return False

    except subprocess.CalledProcessError as e:
        print_error(f"빌드 중 예외 발생: {e}")
        return False


def main():
    """메인 함수"""

    print()
    print(f"{Colors.MAGENTA}{'=' * 70}{Colors.RESET}")
    print(
        f"{Colors.MAGENTA}  Shopping Shorts Maker - 자동 빌드 스크립트  {Colors.RESET}"
    )
    print(f"{Colors.MAGENTA}{'=' * 70}{Colors.RESET}")
    print()

    # 커맨드 라인 인자 파싱
    clean = "--clean" in sys.argv
    debug = "--debug" in sys.argv
    help_flag = "--help" in sys.argv or "-h" in sys.argv

    # 도움말 표시
    if help_flag:
        print_header("사용법")
        print("python build.py [옵션]")
        print()
        print("옵션:")
        print("  --clean   이전 빌드 파일 (build/, dist/) 삭제 후 빌드")
        print("  --debug   디버그 모드로 빌드 (콘솔 창 표시)")
        print("  --help, -h 도움말 표시")
        print()
        print("예시:")
        print("  python build.py           # 기본 빌드")
        print("  python build.py --clean   # 이전 빌드 삭제 후 빌드")
        print("  python build.py --debug   # 디버그 모드 빌드")
        print()
        return

    # 빌드 옵션 표시
    if clean:
        print_step("빌드 옵션: --clean (이전 빌드 파일 삭제)")
    if debug:
        print_step("빌드 옵션: --debug (디버그 모드)")

    print()

    # 빌드 실행
    success = build_exe(clean=clean, debug=debug)

    # 종료 코드 설정
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
