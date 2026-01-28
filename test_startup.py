#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
프로그램 시작 메시지 테스트 스크립트
"""

import subprocess
import sys
import time

def test_startup():
    """프로그램을 시작하고 5초 후 종료하면서 출력 캡처"""
    print("=" * 60)
    print("프로그램 시작 테스트 중...")
    print("=" * 60)

    try:
        # main.py를 subprocess로 실행
        process = subprocess.Popen(
            [sys.executable, "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        # 5초 대기
        time.sleep(5)

        # 프로세스 종료
        process.terminate()

        # 출력 읽기
        output, _ = process.communicate(timeout=2)

        print("\n" + "=" * 60)
        print("캡처된 출력:")
        print("=" * 60)
        print(output)
        print("=" * 60)

        # 메시지 카운트
        lines = output.split('\n')
        print_count = sum(1 for line in lines if line.strip())

        print(f"\n총 {print_count}줄의 출력이 있습니다.")

        # 특정 메시지 체크
        unwanted_messages = [
            "[DPI]", "[OCR]", "[GPU", "[ICON", "[설정", "[초기화]",
            "[세션]", "[테마]", "[폰트", "[CTA", "[API]", "[비동기"
        ]

        found_unwanted = []
        for msg in unwanted_messages:
            if msg in output:
                found_unwanted.append(msg)

        if found_unwanted:
            print("\n⚠️  발견된 불필요한 메시지:")
            for msg in found_unwanted:
                count = output.count(msg)
                print(f"  - {msg}: {count}개")
        else:
            print("\n✅ 모든 초기화 메시지가 제거되었습니다!")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_startup()
