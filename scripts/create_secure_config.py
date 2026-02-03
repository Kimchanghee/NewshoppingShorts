#!/usr/bin/env python3
"""
보안 설정 파일 생성 스크립트

exe 빌드 전에 실행하여 API 키를 암호화된 파일로 저장합니다.
이 파일은 .gitignore에 추가되어 있어 저장소에 포함되지 않습니다.

Usage:
    python scripts/create_secure_config.py

    또는 대화형으로:
    python scripts/create_secure_config.py --interactive
"""

import argparse
import os
import sys

# 프로젝트 루트를 path에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def main():
    parser = argparse.ArgumentParser(description="Create encrypted config for exe build")
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Interactive mode - prompt for API key"
    )
    parser.add_argument(
        "--key",
        type=str,
        help="GLM-OCR API key (or use GLM_OCR_API_KEY env var)"
    )
    args = parser.parse_args()

    # API 키 가져오기
    api_key = args.key or os.getenv("GLM_OCR_API_KEY")

    if args.interactive and not api_key:
        print("=" * 60)
        print("GLM-OCR API Key 설정")
        print("=" * 60)
        print("\nZ.ai에서 발급받은 API 키를 입력하세요.")
        print("(입력 내용은 화면에 표시되지 않습니다)\n")

        import getpass
        api_key = getpass.getpass("API Key: ").strip()

    if not api_key:
        print("Error: API key not provided!")
        print("\n사용 방법:")
        print("  1. 환경변수 설정: set GLM_OCR_API_KEY=your-key")
        print("  2. 또는 인자로 전달: python create_secure_config.py --key your-key")
        print("  3. 또는 대화형 모드: python create_secure_config.py -i")
        sys.exit(1)

    # 설정 생성
    config = {
        "GLM_OCR_API_KEY": api_key
    }

    # 암호화 및 저장
    from utils.secure_config import create_encrypted_config

    output_path = os.path.join(project_root, "utils", ".secure_config.enc")
    create_encrypted_config(config, output_path)

    print("\n" + "=" * 60)
    print("설정 파일 생성 완료!")
    print("=" * 60)
    print(f"\n생성된 파일: {output_path}")
    print("\nPyInstaller 빌드 시 다음 옵션을 추가하세요:")
    print(f'  --add-data "{output_path};."')
    print("\n또는 .spec 파일의 datas에 추가:")
    print(f"  ('{output_path}', '.')")
    print("\n주의: .secure_config.enc 파일은 git에 커밋하지 마세요!")


if __name__ == "__main__":
    main()
