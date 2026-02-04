"""
Token Cost Calculator for Gemini API
터미널 로그에만 토큰 사용량과 비용을 출력합니다.
"""

from typing import Dict, Optional, Any

from utils.logging_config import get_logger

logger = get_logger(__name__)


class TokenCostCalculator:
    """Gemini API 토큰 사용량 및 비용 계산기"""

    # 모델별 가격 정보 (USD per 1M tokens)
    PRICING = {
        # Gemini 3.0 Pro Preview
        "gemini-3-pro-preview": {
            "input_small": 2.00,   # <= 200k tokens
            "input_large": 4.00,   # > 200k tokens
            "output_small": 12.00, # <= 200k tokens
            "output_large": 18.00, # > 200k tokens
            "threshold": 200000
        },

        # Gemini 3.0 Pro
        "gemini-3-pro": {
            "input_small": 2.00,   # <= 200k tokens
            "input_large": 4.00,   # > 200k tokens
            "output_small": 12.00, # <= 200k tokens
            "output_large": 18.00, # > 200k tokens
            "threshold": 200000
        },

        # Gemini 2.5 Flash
        "gemini-2.5-flash": {
            "input_text": 0.30,
            "input_image": 0.30,
            "input_video": 0.30,
            "input_audio": 1.00,
            "output": 2.50
        },

        # Gemini 3.0 Flash
        "gemini-3-flash": {
            "input_text": 0.50,
            "input_image": 0.50,
            "input_video": 0.50,
            "input_audio": 1.00,
            "output": 3.00
        },

        # Gemini 2.5 Pro
        "gemini-2.5-pro": {
            "input_small": 1.25,   # <= 200k tokens
            "input_large": 2.50,   # > 200k tokens
            "output_small": 10.00, # <= 200k tokens
            "output_large": 15.00, # > 200k tokens
            "threshold": 200000
        },

        # Gemini 2.5 Flash TTS
        "gemini-2.5-flash-preview-tts": {
            "input": 0.50,
            "output": 10.00
        },

        # Gemini 2.5 Flash TTS
        "gemini-2.5-flash-tts": {
            "input": 0.50,
            "output": 10.00
        },

        # Gemini 2.5 Pro TTS
        "gemini-2.5-pro-preview-tts": {
            "input": 1.00,
            "output": 20.00
        },

        # Gemini 2.0 Flash (backup)
        "gemini-2.0-flash": {
            "input_text": 0.10,
            "input_image": 0.10,
            "input_video": 0.10,
            "input_audio": 0.70,
            "output": 0.40
        }
    }

    def __init__(self):
        """초기화"""
        self.total_cost = 0.0
        self.session_costs = []

    def calculate_cost(
        self,
        model: str,
        usage_metadata: Any,
        media_type: str = "text"
    ) -> Dict[str, float]:
        """
        토큰 사용량을 기반으로 비용 계산

        Args:
            model: 모델 이름 (예: "gemini-3-pro-preview")
            usage_metadata: API 응답의 usage_metadata
                {
                    "prompt_token_count": int,
                    "candidates_token_count": int,
                    "total_token_count": int
                }
            media_type: 미디어 타입 ("text", "image", "video", "audio")

        Returns:
            {
                "input_tokens": int,
                "output_tokens": int,
                "input_cost": float,
                "output_cost": float,
                "total_cost": float
            }
        """
        usage = _normalize_usage_metadata(usage_metadata)

        input_tokens = usage["prompt_token_count"]
        output_tokens = usage["candidates_token_count"]

        # 둘 다 0이면 그냥 0원 처리
        if input_tokens == 0 and output_tokens == 0:
            return self._zero_cost()

        # 모델 가격 정보 가져오기
        pricing = self.PRICING.get(model)
        if not pricing:
            logger.warning("[비용 계산] 알 수 없는 모델: %s", model)
            return self._zero_cost()

        # 입력 비용 계산
        input_cost = self._calculate_input_cost(
            model, pricing, input_tokens, media_type
        )

        # 출력 비용 계산
        output_cost = self._calculate_output_cost(
            model, pricing, output_tokens, input_tokens
        )

        total_cost = input_cost + output_cost

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost
        }
        

    def _calculate_input_cost(
        self,
        model: str,
        pricing: Dict,
        tokens: int,
        media_type: str
    ) -> float:
        """입력 토큰 비용 계산"""
        if tokens == 0:
            return 0.0

        # 모델에 따라 다른 가격 로직 적용
        if "threshold" in pricing:
            # 프롬프트 크기에 따라 가격이 다른 모델 (Pro, 3.0 Pro)
            if tokens <= pricing["threshold"]:
                rate = pricing["input_small"]
            else:
                rate = pricing["input_large"]
        elif f"input_{media_type}" in pricing:
            # 미디어 타입에 따라 가격이 다른 모델 (Flash)
            rate = pricing.get(f"input_{media_type}", pricing.get("input_text", 0))
        else:
            # 단일 입력 가격 (TTS)
            rate = pricing.get("input", 0)

        return (tokens / 1_000_000) * rate

    def _calculate_output_cost(
        self,
        model: str,
        pricing: Dict,
        output_tokens: int,
        input_tokens: int
    ) -> float:
        """출력 토큰 비용 계산"""
        if output_tokens == 0:
            return 0.0

        # 프롬프트 크기에 따라 출력 가격이 다른 모델
        if "threshold" in pricing:
            if input_tokens <= pricing["threshold"]:
                rate = pricing["output_small"]
            else:
                rate = pricing["output_large"]
        else:
            # 단일 출력 가격
            rate = pricing.get("output", 0)

        return (output_tokens / 1_000_000) * rate

    def _zero_cost(self) -> Dict[str, float]:
        """비용 0 반환"""
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "input_cost": 0.0,
            "output_cost": 0.0,
            "total_cost": 0.0
        }

    def log_cost(
        self,
        step_name: str,
        model: str,
        cost_info: Dict[str, float],
        print_immediately: bool = False
    ):
        """
        비용 정보를 추적하고 선택적으로 출력

        Args:
            step_name: 단계 이름 (예: "비디오 분석", "TTS 생성")
            model: 모델 이름
            cost_info: calculate_cost()의 반환값
            print_immediately: True면 즉시 출력, False면 추적만 함 (기본값: False)
        """
        if cost_info["total_cost"] == 0:
            return

        # print_immediately=True일 때만 즉시 출력
        if print_immediately:
            logger.info("=" * 70)
            logger.info("[비용 계산] %s", step_name)
            logger.info("=" * 70)
            logger.info("모델: %s", model)
            logger.info("입력 토큰: %s개 -> $%.6f", f"{cost_info['input_tokens']:,}", cost_info['input_cost'])
            logger.info("출력 토큰: %s개 -> $%.6f", f"{cost_info['output_tokens']:,}", cost_info['output_cost'])
            logger.info("총 비용: $%.6f", cost_info['total_cost'])
            logger.info("=" * 70)

        # 세션 비용에 추가 (항상 추적)
        self.session_costs.append({
            "step": step_name,
            "model": model,
            "cost": cost_info["total_cost"]
        })
        self.total_cost += cost_info["total_cost"]

    def log_session_summary(self, title: str = "영상 1개 완성"):
        """세션 전체 비용 요약 출력

        Args:
            title: 요약 제목 (기본값: "영상 1개 완성")
        """
        if not self.session_costs:
            return

        logger.info("=" * 70)
        logger.info("[최종 비용 계산] %s", title)
        logger.info("=" * 70)

        for item in self.session_costs:
            # 모델명 간소화
            model_short = item['model'].replace('gemini-', '').replace('-preview', '')
            logger.info("  - %s: $%8.6f", item['step'].ljust(25), item['cost'])

        logger.info("-" * 70)
        logger.info("  총 비용: $%.6f", self.total_cost)
        logger.info("=" * 70)

    def reset_session(self):
        """세션 비용 초기화"""
        self.total_cost = 0.0
        self.session_costs = []

def _normalize_usage_metadata(usage_metadata: Any) -> Dict[str, int]:
    if usage_metadata is None:
        return {
            "prompt_token_count": 0,
            "candidates_token_count": 0,
            "total_token_count": 0,
        }

    if isinstance(usage_metadata, dict):
        return {
            "prompt_token_count": int(usage_metadata.get("prompt_token_count", 0) or 0),
            "candidates_token_count": int(usage_metadata.get("candidates_token_count", 0) or 0),
            "total_token_count": int(usage_metadata.get("total_token_count", 0) or 0),
        }

    try:
        prompt = getattr(usage_metadata, "prompt_token_count", None)
        if prompt is None:
            prompt = getattr(usage_metadata, "input_token_count", 0)

        candidates = getattr(usage_metadata, "candidates_token_count", 0)
        total = getattr(usage_metadata, "total_token_count", 0)

        return {
            "prompt_token_count": int(prompt or 0),
            "candidates_token_count": int(candidates or 0),
            "total_token_count": int(total or 0),
        }
    except Exception as e:
        logger.debug("Failed to normalize usage metadata: %s", e)
        return {
            "prompt_token_count": 0,
            "candidates_token_count": 0,
            "total_token_count": 0,
        }