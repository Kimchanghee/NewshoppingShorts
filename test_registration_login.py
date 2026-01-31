#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Registration and login test script (Windows compatible)
"""

import requests
import json
import sys
import os

# API Configuration
API_SERVER = "https://ssmaker-auth-api-1049571775048.us-central1.run.app"
TIMEOUT = 30


def print_header(text: str):
    """Print header"""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def print_success(text: str):
    """Print success message"""
    print(f"OK   {text}")


def print_error(text: str):
    """Print error message"""
    print(f"FAIL {text}")


def print_info(text: str):
    """Print info message"""
    print(f"INFO {text}")


def print_response(response: requests.Response, title: str):
    """Print response details"""
    print(f"\n[{title}]")
    print(f"  Status: {response.status_code}")
    try:
        data = response.json()
        print(f"  Body: {json.dumps(data, indent=2, ensure_ascii=False)[:300]}")
        return data
    except:
        print(f"  Body: {response.text[:300]}")
        return None


def test_check_username(username: str) -> bool:
    """Test username availability check"""
    print_header(f"1. Username availability check: '{username}'")

    url = f"{API_SERVER}/user/check-username/{username}"
    print_info(f"GET {url}")

    try:
        response = requests.get(url, timeout=10)
        data = print_response(response, "Response")

        if data and data.get("available"):
            print_success(f"Username '{username}' is available")
            return True
        else:
            message = data.get("message", "Unknown error") if data else "Parse failed"
            print_error(f"Username '{username}' not available: {message}")
            return False
    except Exception as e:
        print_error(f"Request failed: {e}")
        return False


def test_registration(
    username: str,
    name: str = "Test User",
    password: str = "test1234",
    contact: str = "010-1234-5678",
):
    """Test registration"""
    print_header(f"2. Registration: '{username}'")

    url = f"{API_SERVER}/user/register/request"
    body = {
        "name": name,
        "username": username,
        "password": password,
        "contact": contact,
    }
    print_info(f"POST {url}")
    print_info(f"Body: {json.dumps(body, ensure_ascii=False)}")

    try:
        response = requests.post(url, json=body, timeout=TIMEOUT)
        data = print_response(response, "Response")

        if response.status_code == 429:
            print_error("Rate limit exceeded (too many requests)")
            print_info("Please try again in 1 hour")
            return {"success": False, "rate_limited": True}

        if data and data.get("success"):
            print_success("Registration successful")
            print_info(f"Trial count: {data.get('data', {}).get('work_count')}")
            token = data.get("data", {}).get("token")
            if token:
                print_info(f"JWT token received (length: {len(token)})")
            return {"success": True, "token": token}
        else:
            message = data.get("message", "Unknown error") if data else "Parse failed"
            print_error(f"Registration failed: {message}")
            return {"success": False, "error": message}
    except Exception as e:
        print_error(f"Request exception: {e}")
        return {"success": False, "error": str(e)}


def test_login(username: str, password: str = "test1234"):
    """Test login"""
    print_header(f"3. Login: '{username}'")

    url = f"{API_SERVER}/user/login/god"
    # API Key는 서버의 SSMAKER_API_KEY 환경변수와 일치해야 함
    # 배포 설정: SSMAKER_API_KEY=ssmaker
    api_key = os.environ.get("SSMAKER_API_KEY", "ssmaker")
    body = {
        "id": username,
        "pw": password,
        "key": api_key,
        "ip": "127.0.0.1",
        "force": False,
    }
    print_info(f"POST {url}")
    print_info(
        f"Body: {{'id': '{username}', 'pw': '***', 'key': '***', 'ip': '127.0.0.1', 'force': False}}"
    )

    try:
        response = requests.post(url, json=body, timeout=TIMEOUT)
        data = print_response(response, "Response")

        if data and data.get("status") is True:
            print_success("Login successful")
            user_data = data.get("data", {}).get("data", {})
            print_info(f"User ID: {user_data.get('id')}")
            print_info(f"Token: {data.get('data', {}).get('token', 'N/A')[:20]}...")
            return {"success": True, "login_data": data}
        elif data and (data.get("status") == "EU003" or data.get("message") == "EU003"):
            print_info("Duplicate login detected (EU003). Retrying with force=True...")
            
            # Retry with force=True
            body["force"] = True
            response = requests.post(url, json=body, timeout=TIMEOUT)
            data = print_response(response, "Retry Response")
            
            if data and data.get("status") is True:
                print_success("Login successful (Forced)")
                user_data = data.get("data", {}).get("data", {})
                print_info(f"User ID: {user_data.get('id')}")
                return {"success": True, "login_data": data}
            else:
                status = data.get("status") if data else response.status_code
                message = data.get("message", "Unknown error") if data else response.text[:100]
                print_error(f"Forced login failed: Status={status}, Message={message}")
                return {"success": False, "status": status, "message": message}
        else:
            status = data.get("status") if data else response.status_code
            message = (
                data.get("message", "Unknown error") if data else response.text[:100]
            )
            print_error(f"Login failed: Status={status}, Message={message}")
            return {"success": False, "status": status, "message": message}
    except Exception as e:
        print_error(f"Request exception: {e}")
        return {"success": False, "error": str(e)}


def main():
    """Main test flow"""
    print(f"\n{'=' * 60}")
    print(f"  Registration/Login Flow Test")
    print(f"{'=' * 60}")

    # Test username
    test_username = "testuser2026"

    # 1. Check username availability
    available = test_check_username(test_username)
    if not available:
        print_info("Username already exists. Testing with a new username.")
        import hashlib

        test_username = f"testuser{hash(test_username) % 10000}"
        available = test_check_username(test_username)
        if not available:
            print_error("Username check failed. Test aborted.")
            sys.exit(1)

    # 2. Register
    reg_result = test_registration(test_username)

    if reg_result.get("rate_limited"):
        print_info("Rate limit exceeded, skipping login test.")
        print_info(f"Username '{test_username}' passed availability check,")
        print_info("so registration was likely attempted already.")
        print_info("Please try again in 1 hour or with a different username.")
        return

    if not reg_result.get("success"):
        print_error("Registration failed. Skipping login test.")
        return

    # 3. Login
    login_result = test_login(test_username)

    # Summary
    print_header("Test Summary")
    print(f"  Username: {test_username}")
    print(f"  Availability check: OK")
    print(f"  Registration: {'OK' if reg_result.get('success') else 'FAIL'}")
    print(f"  Login: {'OK' if login_result.get('success') else 'FAIL'}")

    if login_result.get("success"):
        print(f"\n*** All tests PASSED! ***\n")
    else:
        print(f"\n*** Login failed. There may be an issue. ***\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\nTest interrupted\n")
    except Exception as e:
        print_error(f"Test error: {e}")
        import traceback

        traceback.print_exc()
