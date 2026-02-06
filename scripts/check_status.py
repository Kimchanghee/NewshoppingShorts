"""현재 세션 상태 확인"""
import json
import logging
import os
from collections import Counter

logger = logging.getLogger(__name__)

if not os.path.exists('session_data.json'):
    logger.info("세션 파일이 없습니다.")
else:
    with open('session_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    logger.info('='*60)
    logger.info('현재 세션 상태')
    logger.info('='*60)
    logger.info(f'저장 시각: {data.get("saved_at")}')

    url_queue = data.get('url_queue', [])
    url_status = data.get('url_status', {})
    url_status_message = data.get('url_status_message', {})

    logger.info(f'\n총 URL: {len(url_queue)}개')

    # 상태별 개수
    counts = Counter(url_status.values())
    logger.info(f'\n상태별 개수:')
    for status, count in counts.items():
        logger.info(f'  {status}: {count}개')

    # 대기 중인 URL
    waiting = [url for url in url_queue if url_status.get(url) == 'waiting']
    logger.info(f'\n대기 중인 URL ({len(waiting)}개):')
    for i, url in enumerate(waiting[:5], 1):
        logger.info(f'  {i}. {url[:60]}...')
    if len(waiting) > 5:
        logger.info(f'  ... 외 {len(waiting)-5}개')

    # 처리 중인 URL
    processing = [url for url in url_queue if url_status.get(url) == 'processing']
    if processing:
        logger.info(f'\n처리 중인 URL:')
        for url in processing:
            logger.info(f'  - {url[:60]}...')

    # 완료된 URL
    completed = [url for url, status in url_status.items() if status == 'completed']
    logger.info(f'\n완료된 URL: {len(completed)}개')

    # 실패/건너뜀 URL
    failed = [(url, url_status_message.get(url, '')) for url, status in url_status.items() if status == 'failed']
    if failed:
        logger.info(f'\n실패한 URL ({len(failed)}개):')
        for url, msg in failed[:3]:
            logger.info(f'  - {url[:50]}... ({msg})')

    skipped = [(url, url_status_message.get(url, '')) for url, status in url_status.items() if status == 'skipped']
    if skipped:
        logger.info(f'\n건너뜀 URL ({len(skipped)}개):')
        for url, msg in skipped[:3]:
            logger.info(f'  - {url[:50]}... ({msg})')

    logger.info('\n' + '='*60)
