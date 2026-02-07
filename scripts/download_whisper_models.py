"""
Faster-Whisper 모델 사전 다운로드 및 로컬 패키징 스크립트
Build Preparation Script

1. Faster-Whisper 모델을 미리 다운로드합니다.
2. 다운로드된 모델을 프로젝트 로컬 폴더(faster_whisper_models)로 복사합니다.
3. 이 폴더는 PyInstaller 빌드 시 포함되어 오프라인에서도 작동합니다.
"""

import logging
import os
import sys
import shutil
from pathlib import Path

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _find_model_files(model_dir: Path):
    """모델 디렉토리에서 model.bin 위치를 찾는다 (플랫 / HF 캐시 구조 모두 지원)."""
    if (model_dir / "model.bin").exists():
        return model_dir
    for entry in model_dir.iterdir():
        if entry.name.startswith("models--") and entry.is_dir():
            snapshots = entry / "snapshots"
            if snapshots.is_dir():
                for snap in snapshots.iterdir():
                    if snap.is_dir() and (snap / "model.bin").exists():
                        return snap
    return None


def download_and_bundle_models():
    """Faster-Whisper 모델들을 다운로드하고 로컬로 복사"""
    logger.info("=" * 60)
    logger.info("Faster-Whisper 모델 준비 시작 (Build Preparation)")
    logger.info("=" * 60)

    try:
        from faster_whisper import WhisperModel
        logger.info("[OK] faster_whisper 모듈 확인됨")
    except ImportError:
        logger.error("[오류] faster-whisper 패키지가 없습니다. 설치하세요: pip install faster-whisper")
        return False

    # 다운로드할 모델 목록 (base는 필수)
    models_to_download = ["tiny", "base"]
    
    # 프로젝트 루트 내 모델 저장 경로
    bundled_base_dir = Path("faster_whisper_models")
    bundled_base_dir.mkdir(exist_ok=True)

    for model_name in models_to_download:
        logger.info(f"\n[작업] {model_name} 모델 처리 중...")
        
        try:
            # 1. 모델 다운로드 (캐시 사용)
            # download_root를 지정하여 해당 폴더에 바로 다운로드되게 시도
            local_model_path = bundled_base_dir / model_name
            
            logger.info(f"  - 모델 다운로드/로드 중: {model_name}")
            model = WhisperModel(
                model_name,
                device="cpu",
                compute_type="int8",
                download_root=str(local_model_path)
            )
            
            # 2. 파일 확인 (플랫 구조 또는 HuggingFace 캐시 구조)
            resolved_path = _find_model_files(local_model_path)
            if resolved_path:
                logger.info(f"  ✅ {model_name} 모델 확인됨: {resolved_path}")
            else:
                logger.warning(f"  ⚠️ {model_name} 모델 파일(model.bin)을 찾을 수 없습니다.")
                
            del model

        except Exception as e:
            logger.error(f"  ❌ {model_name} 모델 처리 실패: {e}")
            return False

    logger.info("\n" + "=" * 60)
    logger.info("모든 모델 준비 완료! (faster_whisper_models/)")
    logger.info("=" * 60)
    return True

if __name__ == "__main__":
    success = download_and_bundle_models()
    sys.exit(0 if success else 1)
