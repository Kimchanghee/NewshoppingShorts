"""
1688 Sourcing Manager
1688.com 이미지 검색 및 동영상 소싱 관리자 (Selenium 기반)
"""

import os
import time
import json
import requests
from typing import Optional, Dict, List
from urllib.parse import quote

from utils.logging_config import get_logger
from managers.settings_manager import get_settings_manager

logger = get_logger(__name__)

class SourcingManager:
    """
    Manages 1688.com product sourcing using Selenium.
    Handles image search, product selection, and video extraction.
    """
    
    BASE_URL = "https://www.1688.com/"
    IMAGE_SEARCH_URL = "https://s.1688.com/youyuan/index.htm?tab=imageSearch&imageAddress="

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
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
        except Exception as e:
            raise RuntimeError(
                "1688 소싱 기능을 사용하려면 Selenium이 필요합니다.\n"
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
            logger.error(f"[Sourcing] Failed to init driver: {e}")
            raise e

    def _load_cookies(self):
        """Load 1688 cookies from settings"""
        cookies = self.settings.get_1688_cookies()
        if not cookies:
            return
            
        self.driver.get(self.BASE_URL)
        time.sleep(2)
        
        for name, value in cookies.items():
            self.driver.add_cookie({"name": name, "value": value, "domain": ".1688.com"})
            
        self.driver.refresh()

    def _save_current_cookies(self):
        """Save current session cookies to settings"""
        if not self.driver:
            return
            
        cookies = self.driver.get_cookies()
        cookie_dict = {}
        for cookie in cookies:
            if "1688.com" in cookie.get("domain", ""):
                cookie_dict[cookie["name"]] = cookie["value"]
                
        self.settings.set_1688_cookies(cookie_dict)
        logger.info("[Sourcing] Cookies saved")

    def login_manual(self):
        """
        Open browser for manual login and save cookies.
        This blocks until user closes the browser or presses Enter in console (if adapted).
        For GUI, this should be called in a way that waits for a signal.
        """
        self._init_driver(headless=False)
        self.driver.get("https://login.1688.com/member/signin.htm")
        
        logger.info("[Sourcing] Please login manually in the opened browser.")
        # In a real GUI app, we might want to pop up a message box here 
        # or have a "Save Cookies" button in the UI. 
        # For now, we'll wait for a specific URL change or timeout loop.
        
        max_wait = 300 # 5 minutes
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            if "login.1688.com" not in self.driver.current_url:
                logger.info("[Sourcing] Login detected (URL changed)")
                time.sleep(3) # Wait for redirects
                self._save_current_cookies()
                break
            time.sleep(1)

    def search_by_image(self, image_url: str) -> List[Dict[str, str]]:
        """
        Perform image search on 1688.
        
        Args:
            image_url: URL of the product image (e.g. from Coupang)
            
        Returns:
            List of found products (title, url, price, image)
        """
        # Visual search is better with head for debugging
        self._init_driver(headless=False)
        
        # 1688 Image Search requires uploading or passing URL. 
        # Passing URL via query param is tricky, often requires upload.
        # However, `s.1688.com/youyuan/index.htm?tab=imageSearch&imageAddress=` works for some.
        
        target_url = f"{self.IMAGE_SEARCH_URL}{quote(image_url)}"
        self.driver.get(target_url)
        
        # Wait for results
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".sm-offer-item"))
            )
        except Exception:
            logger.warning("[Sourcing] No results or timeout")
            return []

        products = []
        from selenium.webdriver.common.by import By
        items = self.driver.find_elements(By.CSS_SELECTOR, ".sm-offer-item")
        
        for item in items[:5]: # Top 5 results
            try:
                link_tag = item.find_element(By.TAG_NAME, "a")
                url = link_tag.get_attribute("href")
                
                # Title might be in differnet places depending on layout
                try:
                    title = item.find_element(By.CSS_SELECTOR, ".desc").text
                except:
                    title = "Unknown Product"
                    
                try:
                    price = item.find_element(By.CSS_SELECTOR, ".price").text
                except:
                    price = "0"
                    
                products.append({
                    "title": title,
                    "url": url,
                    "price": price
                })
            except Exception as e:
                continue
                
        return products

    def extract_video_info(self, product_url: str) -> Optional[str]:
        """
        Extract video URL from product detail page.
        
        Args:
            product_url: 1688 Product Detail URL
            
        Returns:
            Video URL or None
        """
        self._init_driver(headless=True)
        self.driver.get(product_url)
        
        video_url = None
        
        try:
            # Method 1: Look for <video> tag
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "video"))
            )
            video_tag = self.driver.find_element(By.TAG_NAME, "video")
            video_url = video_tag.get_attribute("src")
            
        except Exception:
            logger.debug("[Sourcing] Video tag not found immediately, checking page source")
            
        # Method 2: Regex search in page source (often in JSON data)
        if not video_url:
            import re
            page_source = self.driver.page_source
            # Look for typical cloud video URLs (alicdn, etc)
            # "videoUrl":"https://cloud.video.taobao.com/..."
            match = re.search(r'"videoUrl":"(https?://[^"]+\.mp4[^"]*)"', page_source)
            if match:
                video_url = match.group(1).replace("\\u002F", "/")
        
        return video_url

    def download_video(self, video_url: str, output_path: str) -> bool:
        """Download video content to file"""
        try:
            response = requests.get(video_url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"[Sourcing] Video downloaded: {output_path}")
            return True
        except Exception as e:
            logger.error(f"[Sourcing] Download failed: {e}")
            return False

    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

# Global instance
_sourcing_manager: Optional[SourcingManager] = None

def get_sourcing_manager() -> SourcingManager:
    global _sourcing_manager
    if _sourcing_manager is None:
        _sourcing_manager = SourcingManager()
    return _sourcing_manager
