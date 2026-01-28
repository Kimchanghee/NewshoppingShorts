"""
URL 큐 관리 모듈
"""
import re
import tkinter as tk
from ui.components.custom_dialog import show_info, show_warning, show_error, show_question
from typing import List
from urllib.parse import urlparse
from datetime import datetime
from utils.logging_config import get_logger

logger = get_logger(__name__)

URL_PATTERN = re.compile(r'https?://[^\s\"\'<>]+')


class QueueManager:
    """URL 큐 관리 클래스"""

    def __init__(self, gui):
        """
        Args:
            gui: VideoAnalyzerGUI 인스턴스 (부모 GUI)
        """
        self.gui = gui

    def remove_selected_url(self):
        """선택된 URL을 큐에서 제거"""
        url_listbox = getattr(self.gui, "url_listbox", None)
        if url_listbox is None:
            return
        selection = url_listbox.selection()
        if not selection:
            return
        item_id = selection[0]
        values = url_listbox.item(item_id, "values")
        url_value = values[1] if values and len(values) > 1 else item_id
        status = self.gui.url_status.get(url_value)
        if status == "processing":
            show_warning(self.gui.root, "경고", "현재 작업 중 입니다")
            return
        if url_value in self.gui.url_queue:
            self.gui.url_queue.remove(url_value)
        self.gui.url_status.pop(url_value, None)
        self.update_url_listbox()
        self.update_queue_count()
        self.add_log(f"URL 삭제: {url_value[:60]}...")

    def clear_url_queue(self):
        """큐를 완전 초기화 (진행 중 항목 제외, 완료/실패 기록도 모두 삭제)"""
        if not self.gui.url_queue and not self.gui.url_status:
            return
        if not show_question(self.gui.root, "확인", "대기 중인 모든 URL을 삭제할까요?\n(완료/실패 기록도 모두 삭제됩니다)"):
            return

        # 진행 중인 URL만 보존
        processing = [url for url, status in self.gui.url_status.items() if status == 'processing']
        self.gui.url_queue = processing
        self.gui.url_status = {url: 'processing' for url in processing}

        # 완료/실패 URL의 타임스탬프도 삭제
        if hasattr(self.gui, 'url_timestamps'):
            self.gui.url_timestamps = {url: ts for url, ts in self.gui.url_timestamps.items() if url in processing}

        # URL별 상태 메시지도 삭제
        if hasattr(self.gui, 'url_status_message'):
            self.gui.url_status_message = {url: msg for url, msg in self.gui.url_status_message.items() if url in processing}

        # 생성된 영상 목록 초기화
        if hasattr(self.gui, 'generated_videos'):
            self.gui.generated_videos = []

        self.update_url_listbox()
        self.update_queue_count()
        self.add_log("URL 대기열 완전 초기화 (완료/실패 기록 포함)")

    def clear_waiting_only(self):
        """대기 상태 URL만 제거"""
        waiting_urls = [url for url, status in self.gui.url_status.items() if status == 'waiting']
        if not waiting_urls:
            show_info(self.gui.root, "안내", "대기 중인 URL이 없습니다.")
            return
        if not show_question(self.gui.root, "확인", "대기 상태 URL만 삭제할까요?"):
            return
        for url in waiting_urls:
            if url in self.gui.url_queue:
                self.gui.url_queue.remove(url)
            self.gui.url_status.pop(url, None)
        self.update_url_listbox()
        self.update_queue_count()
        self.add_log("대기 URL 삭제 완료")

    def update_url_listbox(self):
        """URL 리스트를 현재 상태에 맞게 갱신"""
        if not hasattr(self.gui, "url_listbox"):
            return
        tree = self.gui.url_listbox
        for item in tree.get_children():
            tree.delete(item)

        status_labels = {
            'waiting': '대기',
            'processing': '진행 중',
            'completed': '완료',
            'failed': '실패',
            'skipped': '건너뜀'
        }

        for idx, url in enumerate(self.gui.url_queue, 1):
            status = self.gui.url_status.get(url, 'waiting')
            order_label = '진행' if status == 'processing' else '대기'
            order_text = f"{order_label} {idx}"

            # 상태 텍스트: processing일 때는 상세 단계 표시
            # Status text: show detailed step for processing
            if status == 'processing':
                step_msg = self.gui.url_status_message.get(url, '')
                status_text = step_msg if step_msg else '진행 중'
            else:
                status_text = status_labels.get(status, status)

            # 비고란: 완료 시 제품 요약, 실패/건너뜀 시 오류 메시지
            remarks_text = ''
            if status == 'completed':
                remarks_text = self.gui.url_remarks.get(url, '')
            elif status in ('failed', 'skipped'):
                remarks_text = self.gui.url_status_message.get(url, '')

            # 상태 태그만 사용 (processing은 자체 배경색으로 강조)
            # 대기 상태일 때만 줄무늬 적용 (다른 상태는 자체 배경색 사용)
            if status == 'waiting':
                row_tag = 'oddrow' if idx % 2 == 1 else 'evenrow'
                tags = (status, row_tag)
            else:
                tags = (status,)
            tree.insert(
                '',
                'end',
                iid=url,
                values=(order_text, url, status_text, remarks_text),
                tags=tags
            )

        processed_items = [
            (url, status)
            for url, status in self.gui.url_status.items()
            if url not in self.gui.url_queue and status in ('completed', 'failed', 'skipped')
        ]
        for url, status in processed_items:
            if status == 'completed':
                order_text = '완료'
            elif status == 'skipped':
                order_text = '건너뜀'
            else:
                order_text = '실패'

            # 상태는 기본 라벨 사용
            status_text = status_labels.get(status, status)

            # 비고란: 완료 시 제품 요약, 실패/건너뜀 시 오류 메시지
            if status == 'completed':
                remarks_text = self.gui.url_remarks.get(url, '')
            else:
                remarks_text = self.gui.url_status_message.get(url, '')

            tree.insert(
                '',
                'end',
                iid=f"done_{hash(url)}",
                values=(order_text, url, status_text, remarks_text),
                tags=(status,)
            )

        self.update_queue_count()

    def update_queue_count(self):
        """Queue 상태 숫자 집계 및 개별 카운트 레이블 업데이트"""
        counts = {
            'waiting': 0,
            'processing': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0
        }
        for status in self.gui.url_status.values():
            if status in counts:
                counts[status] += 1

        # 개별 카운트 레이블 업데이트
        count_processing = getattr(self.gui, 'count_processing', None)
        if count_processing is not None:
            count_processing.config(text=f"🔄 진행 {counts['processing']}")

        count_waiting = getattr(self.gui, 'count_waiting', None)
        if count_waiting is not None:
            count_waiting.config(text=f"⏸ 대기 {counts['waiting']}")

        count_completed = getattr(self.gui, 'count_completed', None)
        if count_completed is not None:
            count_completed.config(text=f"✅ 완료 {counts['completed']}")

        count_skipped = getattr(self.gui, 'count_skipped', None)
        if count_skipped is not None:
            count_skipped.config(text=f"⏭ 건너뜀 {counts['skipped']}")

        count_failed = getattr(self.gui, 'count_failed', None)
        if count_failed is not None:
            count_failed.config(text=f"❌ 실패 {counts['failed']}")

        # 기존 레이블 호환성 (숨겨져 있음)
        queue_count_label = getattr(self.gui, 'queue_count_label', None)
        if queue_count_label is not None:
            text = (
                f"진행: {counts['processing']} | "
                f"대기: {counts['waiting']} | "
                f"완료: {counts['completed']} | "
                f"건너뜀: {counts['skipped']} | "
                f"실패: {counts['failed']}"
            )
            queue_count_label.config(text=text)

        update_overall_progress_display = getattr(self.gui, 'update_overall_progress_display', None)
        if update_overall_progress_display is not None:
            update_overall_progress_display()

    def extract_urls_from_text(self, text: str) -> List[str]:
        """텍스트에서 URL 추출"""
        if not text:
            return []
        candidates = URL_PATTERN.findall(text)
        if not candidates:
            candidates = [line.strip() for line in text.splitlines() if line.strip()]
        normalized = []
        for raw in candidates:
            cleaned = raw.strip().strip("[](){}<>\"'\n\r \t")
            if not cleaned:
                continue
            parsed = urlparse(cleaned)
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                continue
            normalized.append(parsed.geturl())
        return normalized

    def add_urls_to_queue(self, urls: List[str]) -> int:
        """URL을 큐에 추가 (중복 체크 포함)"""
        added = 0
        duplicates = []

        for url in urls:
            if url in self.gui.url_queue:
                duplicates.append(url)
                continue
            self.gui.url_queue.append(url)
            self.gui.url_status[url] = 'waiting'
            added += 1

        # 중복 URL 알림
        if duplicates:
            dup_count = len(duplicates)
            dup_preview = '\n'.join(duplicates[:3])
            if len(duplicates) > 3:
                dup_preview += f'\n... 외 {len(duplicates) - 3}개'

            show_warning(
                self.gui.root,
                "중복 URL 감지",
                f"{dup_count}개의 URL이 이미 대기열에 있습니다:\n\n{dup_preview}"
            )

        if added:
            preview = ', '.join(urls[:3])
            if len(urls) > 3:
                preview += ', ...'
            self.add_log(f"새 URL {added}개 추가: {preview}")
            self.update_url_listbox()
        else:
            self.update_queue_count()
        return added

    def add_url_from_entry(self, event=None):
        """입력란에서 URL 추가"""
        url_entry = getattr(self.gui, 'url_entry', None)
        if url_entry is None:
            return "break"
        raw_text = url_entry.get("1.0", tk.END)
        urls = self.extract_urls_from_text(raw_text)
        if not urls:
            # 빈 입력은 조용히 무시 (팝업 닫을 때 Enter 이벤트 중복 방지)
            return "break"
        added = self.add_urls_to_queue(urls)
        if added:
            url_entry.delete("1.0", tk.END)
            # 제작 대기열 추가 알림 팝업
            show_info(
                self.gui.root,
                "제작 대기열 추가 완료",
                f"{added}개의 URL이 제작 대기열에 추가되었습니다.\n\n분석 시작 버튼을 눌러 작업을 시작하세요."
            )
        return "break"

    def paste_and_extract(self, event=None):
        """클립보드에서 URL 추출 및 추가"""
        try:
            clipboard_text = self.gui.root.clipboard_get()
        except Exception as e:
            logger.error("[클립보드] 텍스트 가져오기 실패: %s", e)
            show_error(self.gui.root, "오류", "클립보드에서 텍스트를 가져오지 못했습니다.")
            return "break"
        urls = self.extract_urls_from_text(clipboard_text)
        if not urls:
            show_info(self.gui.root, "안내", "클립보드에 유효한 URL이 없습니다.")
            return "break"
        added = self.add_urls_to_queue(urls)
        if added:
            # 제작 대기열 추가 알림 팝업
            show_info(
                self.gui.root,
                "제작 대기열 추가 완료",
                f"{added}개의 URL이 제작 대기열에 추가되었습니다.\n\n분석 시작 버튼을 눌러 작업을 시작하세요."
            )
        return "break"

    def add_log(self, message: str):
        """로그 메시지 출력"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        logger.info('[%s] %s', timestamp, message)
