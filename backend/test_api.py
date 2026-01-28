#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API 테스트 스크립트

로컬 또는 배포된 서버의 API를 테스트합니다.

사용법:
    python test_api.py [server_url]

예시:
    python test_api.py
    python test_api.py http://localhost:8000
    python test_api.py https://your-cloud-run-url.run.app
"""

import sys
import requests
import json


def test_api(base_url: str = "http://localhost:8000"):
    """API 엔드포인트를 테스트합니다."""
    print(f"🔍 서버 테스트: {base_url}\n")
    results = []

    # 1. 루트 엔드포인트 테스트
    print("1️⃣  루트 엔드포인트 테스트 (GET /)")
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                print(f"   ✅ 성공: {data}")
                results.append(("GET /", True))
            else:
                print(f"   ❌ 실패: 예상치 못한 응답 - {data}")
                results.append(("GET /", False))
        else:
            print(f"   ❌ 실패: HTTP {response.status_code}")
            results.append(("GET /", False))
    except Exception as e:
        print(f"   ❌ 오류: {str(e)}")
        results.append(("GET /", False))

    # 2. 헬스 체크 테스트
    print("\n2️⃣  헬스 체크 테스트 (GET /health)")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                print(f"   ✅ 성공: {data}")
                results.append(("GET /health", True))
            else:
                print(f"   ❌ 실패: 서버가 건강하지 않음 - {data}")
                results.append(("GET /health", False))
        else:
            print(f"   ❌ 실패: HTTP {response.status_code}")
            results.append(("GET /health", False))
    except Exception as e:
        print(f"   ❌ 오류: {str(e)}")
        results.append(("GET /health", False))

    # 3. 로그인 테스트 (잘못된 자격증명)
    print("\n3️⃣  로그인 실패 테스트 (POST /user/login/god - 잘못된 자격증명)")
    try:
        payload = {
            "id": "nonexistent_user",
            "pw": "wrong_password",
            "key": "ssmaker",
            "ip": "127.0.0.1",
            "force": False,
        }
        response = requests.post(
            f"{base_url}/user/login/god", json=payload, timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "EU001":
                print(f"   ✅ 성공: 올바르게 로그인 거부됨 - {data}")
                results.append(("POST /user/login/god (invalid)", True))
            else:
                print(f"   ⚠️  경고: 예상치 못한 응답 - {data}")
                results.append(("POST /user/login/god (invalid)", False))
        else:
            print(f"   ❌ 실패: HTTP {response.status_code}")
            results.append(("POST /user/login/god (invalid)", False))
    except Exception as e:
        print(f"   ❌ 오류: {str(e)}")
        results.append(("POST /user/login/god (invalid)", False))

    # 4. 로그인 테스트 (유효한 자격증명 - 선택사항)
    print(
        "\n4️⃣  로그인 성공 테스트 (POST /user/login/god - testuser/test123)"
    )
    print("   ⚠️  이 테스트는 testuser 계정이 존재해야 합니다.")
    print("   생성: python create_user.py testuser test123")

    try:
        payload = {
            "id": "testuser",
            "pw": "test123",
            "key": "ssmaker",
            "ip": "127.0.0.1",
            "force": False,
        }
        response = requests.post(
            f"{base_url}/user/login/god", json=payload, timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") is True:
                print(f"   ✅ 성공: 로그인 완료")
                print(f"      User ID: {data.get('data', {}).get('data', {}).get('id')}")
                token = data.get("data", {}).get("token")
                if token:
                    print(f"      JWT Token: {token[:20]}...")
                    results.append(("POST /user/login/god (valid)", True))

                    # 5. 세션 체크 테스트
                    print("\n5️⃣  세션 체크 테스트 (POST /user/login/god/check)")
                    try:
                        user_id = data.get("data", {}).get("data", {}).get("id")
                        check_payload = {
                            "id": user_id,
                            "key": token,
                            "ip": "127.0.0.1",
                        }
                        check_response = requests.post(
                            f"{base_url}/user/login/god/check",
                            json=check_payload,
                            timeout=10,
                        )
                        if check_response.status_code == 200:
                            check_data = check_response.json()
                            if check_data.get("status") is True:
                                print(f"   ✅ 성공: 세션 유효 - {check_data}")
                                results.append(("POST /user/login/god/check", True))
                            else:
                                print(
                                    f"   ❌ 실패: 세션 무효 - {check_data}"
                                )
                                results.append(("POST /user/login/god/check", False))
                    except Exception as e:
                        print(f"   ❌ 오류: {str(e)}")
                        results.append(("POST /user/login/god/check", False))

                    # 6. 로그아웃 테스트
                    print("\n6️⃣  로그아웃 테스트 (POST /user/logout/god)")
                    try:
                        logout_payload = {"id": user_id, "key": token}
                        logout_response = requests.post(
                            f"{base_url}/user/logout/god",
                            json=logout_payload,
                            timeout=10,
                        )
                        if logout_response.status_code == 200:
                            logout_data = logout_response.json()
                            if logout_data.get("status") is True:
                                print(f"   ✅ 성공: 로그아웃 완료 - {logout_data}")
                                results.append(("POST /user/logout/god", True))
                            else:
                                print(f"   ❌ 실패: 로그아웃 실패 - {logout_data}")
                                results.append(("POST /user/logout/god", False))
                    except Exception as e:
                        print(f"   ❌ 오류: {str(e)}")
                        results.append(("POST /user/logout/god", False))

                else:
                    print("   ❌ 실패: JWT 토큰 없음")
                    results.append(("POST /user/login/god (valid)", False))
            elif data.get("status") == "EU001":
                print("   ⚠️  건너뜀: testuser 계정이 존재하지 않거나 비밀번호가 틀립니다.")
                print("   생성: python create_user.py testuser test123")
                results.append(("POST /user/login/god (valid)", None))
            else:
                print(f"   ❌ 실패: {data}")
                results.append(("POST /user/login/god (valid)", False))
        else:
            print(f"   ❌ 실패: HTTP {response.status_code}")
            results.append(("POST /user/login/god (valid)", False))
    except Exception as e:
        print(f"   ❌ 오류: {str(e)}")
        results.append(("POST /user/login/god (valid)", False))

    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)

    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    skipped = sum(1 for _, result in results if result is None)
    total = len(results)

    for endpoint, result in results:
        status = "✅ 통과" if result is True else ("❌ 실패" if result is False else "⚠️  건너뜀")
        print(f"{status:12} {endpoint}")

    print("-" * 60)
    print(
        f"총 {total}개 테스트: {passed}개 통과, {failed}개 실패, {skipped}개 건너뜀"
    )

    if failed == 0 and passed > 0:
        print("\n🎉 모든 테스트 통과!")
        return 0
    elif failed > 0:
        print(f"\n⚠️  {failed}개 테스트 실패")
        return 1
    else:
        print("\n⚠️  실행된 테스트 없음")
        return 2


def main():
    base_url = "http://localhost:8000"

    if len(sys.argv) > 1:
        base_url = sys.argv[1].rstrip("/")

    print("=" * 60)
    print("🧪 SSMaker Auth API 테스트")
    print("=" * 60)

    exit_code = test_api(base_url)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
