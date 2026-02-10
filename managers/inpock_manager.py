"""
Inpock Link Manager
인포크링크 자동화 및 링크 관리자 (Selenium 기반)
"""

import os
import time
from typing import Optional, Dict

from utils.logging_config import get_logger
from managers.settings_manager import get_settings_manager

logger = get_logger(__name__)

class InpockManager:
    """
    Manages Inpock Link automation using Selenium.
    Handles login via cookies and adding new links.
    """
    
    BASE_URL = "https://inpock.co.kr"
    LOGIN_URL = "https://inpock.co.kr/login"
    ADMIN_URL = "https://inpock.co.kr/admin/link" # 추후 확인 필요, 일반적인 관리 페이지

    def __init__(self):
        self.settings = get_settings_manager()
        self.driver = None

    def _init_driver(self, headless: bool = False):
        """Initialize Selenium WebDriver"""
        if self.driver:
            return

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager
        except Exception as e:
            raise RuntimeError(
                "브라우저 자동화를 사용하려면 Selenium이 필요합니다.\n"
                "프로그램을 최신 버전으로 업데이트해도 동일하면, 관리자에게 문의해주세요."
            ) from e

        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        
        # Anti-detection options
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        chrome_options.add_argument("--start-maximized")
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Load cookies if available
            self._load_cookies()
            
        except Exception as e:
            logger.error(f"[Inpock] Failed to init driver: {e}")
            raise e

    def _load_cookies(self):
        """Load Inpock cookies from settings"""
        cookies = self.settings.get_inpock_cookies()
        if not cookies:
            return
            
        # Domain must match cookie domain
        if self.driver.current_url == "data:,":
            self.driver.get(self.BASE_URL)
            
        time.sleep(1)
        
        for name, value in cookies.items():
            self.driver.add_cookie({"name": name, "value": value, "domain": "inpock.co.kr"})
            
        self.driver.refresh()

    def _save_current_cookies(self):
        """Save current session cookies to settings"""
        if not self.driver:
            return
            
        cookies = self.driver.get_cookies()
        cookie_dict = {}
        for cookie in cookies:
            if "inpock.co.kr" in cookie.get("domain", ""):
                cookie_dict[cookie["name"]] = cookie["value"]
                
        self.settings.set_inpock_cookies(cookie_dict)
        logger.info("[Inpock] Cookies saved")

    def login_manual(self):
        """
        Open browser for manual login and save cookies.
        """
        self._init_driver(headless=False)
        self.driver.get(self.LOGIN_URL)
        
        logger.info("[Inpock] Please login manually in the opened browser.")
        
        # Wait for user to navigate away from login page or just wait for improved signal
        # For now, simplistic loop waiting for URL change or timeout
        max_wait = 300 # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            current_url = self.driver.current_url
            # If user is logged in, URL usually changes to main or admin
            if "login" not in current_url and self.BASE_URL in current_url:
                logger.info("[Inpock] Login detected (URL changed)")
                time.sleep(3) # Wait for redirects
                self._save_current_cookies()
                break
            time.sleep(1)

    def add_link(self, title: str, url: str) -> bool:
        """
        Add a new link to Inpock Link profile.
        NOTE: This is a placeholder implementation. The exact DOM structure 
        needs to be verified as Inpock doesn't verify public API docs.
        """
        if not self.settings.get_inpock_cookies():
            logger.warning("[Inpock] Login required first")
            return False
            
        try:
            self._init_driver(headless=False) # Headless might trigger security checks
            self.driver.get(self.ADMIN_URL)
            
            # TODO: Implement actual element interaction
            # 1. Find "Add Link" button
            # 2. Input Title
            # 3. Input URL
            # 4. Save
            
            # Mock success for now until we can inspect the page
            logger.info(f"[Inpock] (Mock) Adding link: {title} -> {url}")
            time.sleep(2)
            
            return True
            
        except Exception as e:
            logger.error(f"[Inpock] Failed to add link: {e}")
            return False
        finally:
            # Keep browser open for debugging if needed, or close
            # self.close()
            pass

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

# Global instance
_inpock_manager: Optional[InpockManager] = None

def get_inpock_manager() -> InpockManager:
    global _inpock_manager
    if _inpock_manager is None:
        _inpock_manager = InpockManager()
    return _inpock_manager
