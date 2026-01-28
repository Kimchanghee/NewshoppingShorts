"""
Faster-Whisper 모델 사전 다운로드 스크립트

빌드 전에 실행하여 Faster-Whisper 모델을 미리 다운로드합니다.
빌드 시 이 모델들이 함께 포함되어 오프라인에서도 작동합니다.

Faster-Whisper는 CTranslate2 기반으로 PyTorch 없이 동작합니다.
"""

import logging
import os
import sys

logger = logging.getLogger(__name__)


def download_faster_whisper_models():
    """Faster-Whisper 모델들을 미리 다운로드"""
    logger.info("=" * 60)
    logger.info("Faster-Whisper 모델 다운로드 시작")
    logger.info("=" * 60)

    # Python 3.13+ 호환성 체크
    if sys.version_info >= (3, 13):
        logger.warning(
            f"[건너뜀] Python {sys.version_info.major}.{sys.version_info.minor}는 "
            "faster-whisper를 지원하지 않습니다."
        )
        logger.info("Python 3.13+에서는 글자 수 비례 타이밍이 자동으로 사용됩니다.")
        logger.info("Whisper STT가 필요하면 Python 3.12 이하를 사용하세요.")
        return True  # 성공으로 처리 (빌드 진행 가능)

    try:
        from faster_whisper import WhisperModel
        logger.info("[OK] faster_whisper 모듈 import 성공")
    except ImportError:
        logger.error("[오류] faster-whisper 패키지가 설치되지 않았습니다.")
        logger.error("다음 명령어로 설치하세요: pip install faster-whisper")
        return False

    # 다운로드할 모델 목록
    # Faster-Whisper 모델 크기 및 성능 비교 (CTranslate2 형식):
    # - tiny:     ~75MB   (가장 빠름, 정확도 낮음)
    # - base:     ~140MB  (균형잡힌 성능, 일반적으로 권장)
    # - small:    ~244MB  (좋은 정확도)
    # - medium:   ~769MB  (높은 정확도)
    # - large-v3: ~1.5GB+ (최고 정확도, 가장 느림)
    models_to_download = [
        "tiny",      # 저사양 PC용
        "base",      # 일반 PC용 (기본 권장)
        "small",     # 중간 사양 PC용
    ]

    logger.info(f"\n다운로드할 모델: {', '.join(models_to_download)}")
    logger.info("이 작업은 인터넷 연결이 필요하며, 몇 분 정도 걸릴 수 있습니다.")
    logger.info("모델은 HuggingFace Hub에서 다운로드됩니다.\n")

    for model_name in models_to_download:
        logger.info(f"[다운로드 중] {model_name} 모델...")
        try:
            # Faster-Whisper 모델 로드 (자동으로 HuggingFace에서 다운로드)
            # CPU + int8로 테스트 로드
            model = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
                download_root=None  # 기본 HuggingFace 캐시 사용
            )
            logger.info(f"[완료] {model_name} 모델 다운로드 및 로드 성공")

            # 모델 저장 위치 확인
            cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
            logger.info(f"  저장 위치: {cache_dir}")

            # 메모리 해제
            del model

        except (OSError, RuntimeError, ValueError) as e:
            logger.error(f"[오류] {model_name} 모델 다운로드 실패: {e}", exc_info=True)
            return False

    logger.info("\n" + "=" * 60)
    logger.info("모든 Faster-Whisper 모델 다운로드 완료!")
    logger.info("=" * 60)
    logger.info("\n이제 PyInstaller 빌드를 진행하세요.")
    logger.info("모델 파일들이 자동으로 포함됩니다.")
    logger.info("\n참고: Faster-Whisper는 PyTorch 없이 CTranslate2로 동작합니다.")
    logger.info("      빌드 크기가 OpenAI Whisper 대비 약 60% 감소합니다.\n")

    return True


if __name__ == "__main__":
    try:
        success = download_faster_whisper_models()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("\n\n다운로드가 중단되었습니다.")
        sys.exit(1)
    except (OSError, RuntimeError) as e:
        logger.error(f"\n\n다운로드 중 오류 발생: {e}", exc_info=True)
        sys.exit(1)
