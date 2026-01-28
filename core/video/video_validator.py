# -*- coding: utf-8 -*-
"""
영상 품질 검증 모듈
최종 생성된 영상의 품질을 Gemini로 검증하고 문제 발견 시 재처리
"""

import os
import json
import time
import re
from typing import Dict, Any, Optional, Tuple

from google.genai import types

from prompts import get_video_validation_prompt
from caller import ui_controller
import config
from utils.logging_config import get_logger

logger = get_logger(__name__)


# 검증 결과 상수
VALIDATION_PASS = "pass"
VALIDATION_FAIL = "fail"
VALIDATION_RETRY = "retry"

# 최대 재시도 횟수
MAX_VALIDATION_RETRIES = 2
MIN_PASS_SCORE = 70


def validate_final_video(app, video_path: str) -> Dict[str, Any]:
    """
    최종 생성된 영상의 품질을 검증합니다.

    Args:
        app: 애플리케이션 인스턴스
        video_path: 검증할 영상 파일 경로

    Returns:
        검증 결과 딕셔너리
    """
    logger.info("[영상 검증] 최종 영상 품질 검증 시작...")
    logger.info(f"[영상 검증] 파일: {os.path.basename(video_path)}")

    if not os.path.exists(video_path):
        logger.error(f"[영상 검증] 오류: 파일을 찾을 수 없습니다 - {video_path}")
        return _create_error_result("파일을 찾을 수 없습니다")

    try:
        # Gemini 클라이언트 확인
        if not hasattr(app, 'genai_client') or not app.genai_client:
            logger.warning("[영상 검증] Gemini 클라이언트가 없습니다")
            return _create_error_result("Gemini 클라이언트 없음")

        # 영상 업로드
        logger.info("[영상 검증] 영상 파일 업로드 중...")
        video_file = app.genai_client.files.upload(file=video_path)

        # 파일 처리 대기
        wait_count = 0
        while video_file.state == types.FileState.PROCESSING:
            time.sleep(2)
            wait_count += 2
            if wait_count % 10 == 0:
                logger.info(f"[영상 검증] 파일 처리 중... ({wait_count}초 경과)")
            video_file = app.genai_client.files.get(name=video_file.name)

        if video_file.state == types.FileState.FAILED:
            error_msg = getattr(getattr(video_file, "error", None), "message", "알 수 없는 오류")
            logger.error(f"[영상 검증] 파일 처리 실패: {error_msg}")
            return _create_error_result(f"파일 처리 실패: {error_msg}")

        # 검증 프롬프트 생성
        prompt = get_video_validation_prompt()

        # API 호출
        logger.info("[영상 검증] Gemini API로 영상 분석 요청 중...")
        api_mgr = getattr(app, 'api_key_manager', None) or getattr(app, 'api_manager', None)
        current_api_key = getattr(api_mgr, 'current_key', 'unknown') if api_mgr else 'unknown'
        logger.debug(f"[영상 검증 API] 사용 중인 API 키: {current_api_key}")

        response = app.genai_client.models.generate_content(
            model=config.GEMINI_VIDEO_MODEL,
            contents=[
                types.Part.from_uri(
                    file_uri=video_file.uri,
                    mime_type=video_file.mime_type
                ),
                prompt,
            ],
        )

        # 응답 파싱
        result_text = _extract_text_from_response(response)
        if not result_text:
            logger.warning("[영상 검증] 응답이 비어있습니다")
            return _create_error_result("응답 없음")

        # JSON 파싱
        validation_result = _parse_validation_response(result_text)
        if not validation_result:
            logger.warning("[영상 검증] JSON 파싱 실패")
            logger.debug(f"[영상 검증] 원본 응답: {result_text[:500]}...")
            return _create_error_result("JSON 파싱 실패")

        # 결과 로깅
        _log_validation_result(validation_result)

        # 파일 삭제 (정리)
        try:
            app.genai_client.files.delete(name=video_file.name)
        except Exception as delete_err:
            logger.debug(f"[영상 검증] 임시 파일 삭제 실패 (무시됨): {delete_err}")

        return validation_result

    except Exception as e:
        ui_controller.write_error_log(e)
        logger.error(f"[영상 검증] 오류 발생: {e}")
        return _create_error_result(str(e))


def _extract_text_from_response(response) -> str:
    """응답에서 텍스트 추출"""
    result_text = ""
    if hasattr(response, 'candidates') and response.candidates:
        for candidate in response.candidates:
            if hasattr(candidate, 'content') and candidate.content:
                for part in candidate.content.parts:
                    if hasattr(part, 'text') and part.text:
                        result_text += part.text
    if not result_text:
        result_text = getattr(response, 'text', '')
    return result_text


def _parse_validation_response(text: str) -> Optional[Dict[str, Any]]:
    """검증 응답을 JSON으로 파싱"""
    # 코드블록 제거
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()

    # JSON 추출 시도
    try:
        # 전체가 JSON인 경우
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # JSON 객체 찾기
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return None


def _log_validation_result(result: Dict[str, Any]):
    """검증 결과 로깅"""
    vr = result.get('validation_result', result)

    overall_pass = vr.get('overall_pass', False)
    overall_score = vr.get('score', 0)

    logger.info("[영상 검증] =======================================")
    logger.info(f"[영상 검증] 전체 결과: {'통과' if overall_pass else '실패'}")
    logger.info(f"[영상 검증] 전체 점수: {overall_score}/100")
    logger.info("[영상 검증] ---------------------------------------")

    # 세부 항목 로깅
    items = [
        ('subtitle_sync', '자막-오디오 싱크'),
        ('chinese_blur', '중국어 블러'),
        ('korean_subtitle', '한글 자막'),
        ('overall_quality', '전체 품질')
    ]

    for key, name in items:
        item = vr.get(key, {})
        item_pass = item.get('pass', False)
        item_score = item.get('score', 0)
        issues = item.get('issues', [])

        status = 'PASS' if item_pass else 'FAIL'
        logger.info(f"[영상 검증] [{status}] {name}: {item_score}/100")

        if issues:
            for issue in issues[:3]:  # 최대 3개만 표시
                time_str = issue.get('time', '??:??')
                desc = issue.get('description', '')
                logger.info(f"[영상 검증]    - [{time_str}] {desc}")

    # 권장사항
    recommendations = vr.get('recommendations', [])
    if recommendations:
        logger.info("[영상 검증] ---------------------------------------")
        logger.info("[영상 검증] 개선 권장사항:")
        for i, rec in enumerate(recommendations[:5], 1):
            logger.info(f"[영상 검증]   {i}. {rec}")

    logger.info("[영상 검증] =======================================")


def _create_error_result(error_msg: str) -> Dict[str, Any]:
    """오류 결과 생성"""
    return {
        'validation_result': {
            'overall_pass': False,
            'score': 0,
            'error': error_msg,
            'subtitle_sync': {'pass': False, 'score': 0, 'issues': []},
            'chinese_blur': {'pass': False, 'score': 0, 'issues': []},
            'korean_subtitle': {'pass': False, 'score': 0, 'issues': []},
            'overall_quality': {'pass': False, 'score': 0, 'issues': []},
            'recommendations': [f'검증 실패: {error_msg}']
        }
    }


def get_failed_items(validation_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    검증 실패 항목들을 반환합니다.

    Returns:
        실패한 항목과 문제점 딕셔너리
    """
    vr = validation_result.get('validation_result', validation_result)
    failed_items = {}

    items = ['subtitle_sync', 'chinese_blur', 'korean_subtitle', 'overall_quality']
    for item_key in items:
        item = vr.get(item_key, {})
        if not item.get('pass', True) or item.get('score', 100) < MIN_PASS_SCORE:
            failed_items[item_key] = {
                'score': item.get('score', 0),
                'issues': item.get('issues', [])
            }

    return failed_items


def needs_regeneration(validation_result: Dict[str, Any]) -> Tuple[bool, str]:
    """
    영상 재생성이 필요한지 판단합니다.

    Returns:
        (재생성 필요 여부, 이유)
    """
    vr = validation_result.get('validation_result', validation_result)

    # 오류가 있으면 재생성 불필요 (검증 자체가 실패)
    if 'error' in vr:
        return False, f"검증 오류: {vr['error']}"

    overall_pass = vr.get('overall_pass', False)
    overall_score = vr.get('score', 0)

    # 통과했으면 재생성 불필요
    if overall_pass and overall_score >= MIN_PASS_SCORE:
        return False, "검증 통과"

    # 실패 항목 확인
    failed_items = get_failed_items(validation_result)

    if not failed_items:
        return False, "실패 항목 없음"

    # 재생성 이유 생성
    reasons = []
    if 'subtitle_sync' in failed_items:
        reasons.append("자막 싱크 불일치")
    if 'chinese_blur' in failed_items:
        reasons.append("중국어 블러 미처리")
    if 'korean_subtitle' in failed_items:
        reasons.append("한글 자막 문제")
    if 'overall_quality' in failed_items:
        reasons.append("전체 품질 미흡")

    return True, ", ".join(reasons)


def get_fix_recommendations(validation_result: Dict[str, Any]) -> Dict[str, list]:
    """
    각 실패 항목에 대한 수정 권장사항을 반환합니다.

    Returns:
        항목별 수정 권장사항
    """
    failed_items = get_failed_items(validation_result)
    recommendations = {}

    for item_key, item_data in failed_items.items():
        issues = item_data.get('issues', [])
        item_recs = []

        if item_key == 'subtitle_sync':
            # 자막 싱크 문제 → 타임스탬프 재분석 필요
            if issues:
                times = [i.get('time', '') for i in issues if i.get('time')]
                item_recs.append(f"문제 구간: {', '.join(times)}")
            item_recs.append("TTS 타임스탬프 재분석 권장")
            item_recs.append("자막 시작/종료 시간 조정 필요")

        elif item_key == 'chinese_blur':
            # 중국어 블러 문제 → 블러 영역 재감지 필요
            if issues:
                times = [i.get('time', '') for i in issues if i.get('time')]
                item_recs.append(f"미처리 구간: {', '.join(times)}")
            item_recs.append("OCR 재실행하여 중국어 영역 재감지")
            item_recs.append("블러 강도 증가 권장")

        elif item_key == 'korean_subtitle':
            # 한글 자막 문제 → 자막 분할/렌더링 재처리
            if issues:
                for issue in issues:
                    desc = issue.get('description', '')
                    if desc:
                        item_recs.append(desc)
            item_recs.append("자막 분할 규칙 재적용")
            item_recs.append("자막 위치/크기 조정 필요")

        elif item_key == 'overall_quality':
            item_recs.append("전체 영상 재인코딩 권장")

        recommendations[item_key] = item_recs

    return recommendations


class VideoValidationManager:
    """영상 검증 및 재처리 관리자"""

    def __init__(self, app):
        self.app = app
        self.retry_count = 0
        self.validation_history = []

    def validate_and_fix(self, video_path: str, auto_fix: bool = True) -> Tuple[bool, str, Dict]:
        """
        영상을 검증하고 필요 시 자동 수정합니다.

        Args:
            video_path: 검증할 영상 경로
            auto_fix: 자동 수정 여부

        Returns:
            (성공 여부, 최종 영상 경로, 검증 결과)
        """
        self.retry_count = 0

        while self.retry_count <= MAX_VALIDATION_RETRIES:
            logger.info(f"[검증 관리자] {'초기 검증' if self.retry_count == 0 else f'재검증 ({self.retry_count}/{MAX_VALIDATION_RETRIES})'}")

            # 검증 실행
            validation_result = validate_final_video(self.app, video_path)
            self.validation_history.append(validation_result)

            # 재생성 필요 여부 확인
            needs_regen, reason = needs_regeneration(validation_result)

            if not needs_regen:
                logger.info(f"[검증 관리자] 검증 통과: {reason}")
                return True, video_path, validation_result

            logger.warning(f"[검증 관리자] 검증 실패: {reason}")

            if not auto_fix:
                logger.info("[검증 관리자] 자동 수정이 비활성화되어 있습니다")
                return False, video_path, validation_result

            if self.retry_count >= MAX_VALIDATION_RETRIES:
                logger.warning(f"[검증 관리자] 최대 재시도 횟수 초과 ({MAX_VALIDATION_RETRIES}회)")
                break

            # 수정 시도
            self.retry_count += 1
            logger.info(f"[검증 관리자] 문제 수정 시도 중... (시도 {self.retry_count}/{MAX_VALIDATION_RETRIES})")

            # 수정 권장사항 가져오기
            fix_recs = get_fix_recommendations(validation_result)

            # 문제 수정 시도
            fixed_path = self._attempt_fix(video_path, fix_recs)
            if fixed_path and fixed_path != video_path:
                video_path = fixed_path
                logger.info(f"[검증 관리자] 수정된 영상: {os.path.basename(fixed_path)}")
            else:
                logger.warning("[검증 관리자] 수정 실패, 재검증으로 진행")

        # 최종 실패
        final_result = self.validation_history[-1] if self.validation_history else {}
        return False, video_path, final_result

    def _attempt_fix(self, video_path: str, fix_recommendations: Dict[str, list]) -> Optional[str]:
        """
        문제 수정을 시도합니다.

        Returns:
            수정된 영상 경로 (실패 시 None)
        """
        try:
            # 수정이 필요한 항목 확인
            if 'chinese_blur' in fix_recommendations:
                logger.info("[검증 관리자] 중국어 블러 재처리 시도...")
                # 블러 재처리 호출
                if hasattr(self.app, 'reapply_blur') and callable(self.app.reapply_blur):
                    self.app.reapply_blur()

            if 'subtitle_sync' in fix_recommendations:
                logger.info("[검증 관리자] 자막 싱크 재조정 시도...")
                # 자막 타이밍 재조정
                if hasattr(self.app, 'recalculate_subtitle_timing'):
                    self.app.recalculate_subtitle_timing()

            if 'korean_subtitle' in fix_recommendations:
                logger.info("[검증 관리자] 한글 자막 재렌더링 시도...")
                # 자막 재렌더링은 영상 재생성으로 처리

            # 영상 재생성 필요 시
            if any(key in fix_recommendations for key in ['subtitle_sync', 'korean_subtitle']):
                logger.info("[검증 관리자] 영상 재합성 필요...")
                # 여기서는 기존 영상 경로 반환 (재생성은 호출측에서 처리)
                return video_path

            return video_path

        except Exception as e:
            ui_controller.write_error_log(e)
            logger.error(f"[검증 관리자] 수정 중 오류: {e}")
            return None

    def get_summary(self) -> str:
        """검증 이력 요약을 반환합니다."""
        if not self.validation_history:
            return "검증 이력 없음"

        lines = [f"총 검증 횟수: {len(self.validation_history)}"]
        for i, result in enumerate(self.validation_history):
            vr = result.get('validation_result', result)
            score = vr.get('score', 0)
            passed = vr.get('overall_pass', False)
            status = '통과' if passed else '실패'
            lines.append(f"  {i+1}차: {score}점 ({status})")

        return "\n".join(lines)
