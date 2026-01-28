from utils import DriverConfig
from utils import Tool
from core.api import ApiKeyManager
from caller import ui_controller
from utils.logging_config import get_logger

logger = get_logger(__name__)


def _async_load_and_init(self):
    """비동기 API 키 로드 및 초기화"""
    try:
        # API 키 로드
        self.load_saved_api_keys()
        
        # API 매니저 초기화
        self.api_key_manager = ApiKeyManager.APIKeyManager()
        
        # Gemini 클라이언트 초기화
        self.init_client()
        
        logger.info("[비동기 초기화] API 키 로드 및 초기화 완료")

    except Exception as e:
        logger.error(f"[비동기 초기화 오류] {str(e)}")
        ui_controller.write_error_log(e)