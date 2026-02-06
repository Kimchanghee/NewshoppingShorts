"""
임시 폴더에 남아있는 완성된 영상 파일을 바탕화면으로 복구하는 스크립트
"""
import logging
import os
import glob
import shutil
import json
from datetime import datetime
from caller import ui_controller

logger = logging.getLogger(__name__)

def recover_temp_videos():
    # 세션 데이터 로드
    session_file = "session_data.json"
    if not os.path.exists(session_file):
        logger.error("[Error] session_data.json file not found.")
        return

    with open(session_file, 'r', encoding='utf-8') as f:
        session_data = json.load(f)

    # 출력 폴더 경로
    output_folder = session_data.get('output_folder_path', os.path.join(os.path.expanduser('~'), 'Desktop'))
    logger.info("[Recovery] Output folder: %s", output_folder)

    # URL 타임스탬프 로드
    url_timestamps = session_data.get('url_timestamps', {})
    logger.info("[Recovery] Found %d URL timestamps", len(url_timestamps))

    # 임시 폴더에서 비디오 파일 찾기
    temp_pattern = os.path.join(os.environ['TEMP'], 'batch_video_*')
    temp_folders = glob.glob(temp_pattern)

    logger.info("[Recovery] Found %d temp folders", len(temp_folders))

    if not temp_folders:
        logger.info("[Complete] No files to recover.")
        return

    recovered_count = 0

    for temp_folder in temp_folders:
        # 폴더 내 mp4 파일 찾기
        video_files = glob.glob(os.path.join(temp_folder, '*.mp4'))

        if not video_files:
            continue

        for video_file in video_files:
            filename = os.path.basename(video_file)

            # 파일명에서 날짜 추출 (예: 003_20251121_231912_voice_callirrhoe_1.2x.mp4)
            # -> 20251121_231912
            parts = filename.split('_')
            if len(parts) >= 3:
                date_str = parts[1]  # 20251121
                time_str = parts[2]  # 231912
                timestamp_str = f"{date_str}_{time_str}"
            else:
                # 파일명 형식이 다르면 현재 시각 사용
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 폴더명 생성 (상품명은 추출 불가하므로 'video'로 대체)
            folder_name = f"{timestamp_str}_video"
            target_folder = os.path.join(output_folder, folder_name)

            # 폴더 생성
            os.makedirs(target_folder, exist_ok=True)

            # 파일 이동
            target_path = os.path.join(target_folder, filename)

            try:
                if os.path.exists(target_path):
                    logger.info("[Skipped] Already exists: %s", filename)
                else:
                    shutil.move(video_file, target_path)
                    logger.info("[Recovered] %s -> %s", filename, folder_name)
                    recovered_count += 1
            except (OSError, shutil.Error) as e:
                logger.error("[Error] Recovery failed for %s: %s", filename, e)
                ui_controller.write_error_log(e)

    logger.info("[Complete] Total %d files recovered", recovered_count)
    logger.info("[Location] %s", output_folder)

if __name__ == "__main__":
    # Configure basic logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger.info("=" * 60)
    logger.info("Video File Recovery Script")
    logger.info("=" * 60)

    recover_temp_videos()

    logger.info("=" * 60)
    input("Press Enter to exit...")
