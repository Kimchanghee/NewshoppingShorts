# -*- coding: utf-8 -*-
"""
System requirements checking and validation.
"""
import os
import sys
import struct
import platform
import subprocess
import ctypes
from typing import Tuple, List, Dict, Any

from PyQt5.QtWidgets import QMessageBox

from .constants import (
    MIN_RAM_GB,
    RECOMMENDED_RAM_GB,
    MIN_DISK_GB,
    RECOMMENDED_DISK_GB,
)


def check_system_requirements() -> Tuple[bool, List[str], List[str], Dict[str, Any]]:
    """
    Check system specifications and return results.

    Returns:
        Tuple of (can_run, issues, warnings, specs)
        - can_run: Whether the program can run
        - issues: List of critical issues (blocking)
        - warnings: List of warnings (non-blocking)
        - specs: Dictionary of system specifications
    """
    issues: List[str] = []
    warnings: List[str] = []
    specs: Dict[str, Any] = {}

    # 1. 64-bit check
    is_64bit = struct.calcsize("P") * 8 == 64
    specs['architecture'] = '64bit' if is_64bit else '32bit'
    if not is_64bit:
        issues.append("32비트 시스템에서는 실행할 수 없습니다. 64비트 Windows가 필요합니다.")

    # 2. Windows version check
    os_version = platform.version()
    os_release = platform.release()
    specs['os'] = f"Windows {os_release} ({os_version})"
    try:
        major_version = int(os_release) if os_release.isdigit() else 10
        if major_version < 10:
            issues.append(f"Windows {os_release}은 지원되지 않습니다. Windows 10 이상이 필요합니다.")
    except (ValueError, AttributeError):
        pass  # Version parsing failed, assume compatible

    # 3. RAM check
    try:
        kernel32 = ctypes.windll.kernel32
        c_ulonglong = ctypes.c_ulonglong

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ('dwLength', ctypes.c_ulong),
                ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', c_ulonglong),
                ('ullAvailPhys', c_ulonglong),
                ('ullTotalPageFile', c_ulonglong),
                ('ullAvailPageFile', c_ulonglong),
                ('ullTotalVirtual', c_ulonglong),
                ('ullAvailVirtual', c_ulonglong),
                ('ullAvailExtendedVirtual', c_ulonglong),
            ]

        mem_status = MEMORYSTATUSEX()
        mem_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        kernel32.GlobalMemoryStatusEx(ctypes.byref(mem_status))

        total_ram_gb = mem_status.ullTotalPhys / (1024 ** 3)
        avail_ram_gb = mem_status.ullAvailPhys / (1024 ** 3)
        specs['ram_total'] = f"{total_ram_gb:.1f}GB"
        specs['ram_available'] = f"{avail_ram_gb:.1f}GB"

        if total_ram_gb < MIN_RAM_GB:
            issues.append(
                f"RAM이 {total_ram_gb:.1f}GB로 부족합니다. "
                f"최소 {RECOMMENDED_RAM_GB}GB 이상 필요합니다."
            )
        elif total_ram_gb < RECOMMENDED_RAM_GB:
            warnings.append(
                f"RAM이 {total_ram_gb:.1f}GB입니다. "
                f"{RECOMMENDED_RAM_GB}GB 이상 권장됩니다. (느릴 수 있음)"
            )
    except Exception:
        specs['ram_total'] = "확인 불가"
        warnings.append("RAM 용량을 확인할 수 없습니다.")

    # 4. CPU check
    cpu_count = os.cpu_count() or 1
    specs['cpu_cores'] = cpu_count
    specs['cpu_name'] = platform.processor() or "알 수 없음"

    if cpu_count < 2:
        warnings.append(f"CPU 코어가 {cpu_count}개입니다. 4코어 이상 권장됩니다.")
    elif cpu_count < 4:
        warnings.append(f"CPU 코어가 {cpu_count}개입니다. 처리 속도가 느릴 수 있습니다.")

    # 5. Disk space check
    try:
        import shutil
        total, used, free = shutil.disk_usage(os.getcwd())
        free_gb = free / (1024 ** 3)
        specs['disk_free'] = f"{free_gb:.1f}GB"

        if free_gb < MIN_DISK_GB:
            issues.append(
                f"디스크 여유 공간이 {free_gb:.1f}GB로 부족합니다. "
                f"최소 {RECOMMENDED_DISK_GB}GB 필요."
            )
        elif free_gb < RECOMMENDED_DISK_GB:
            warnings.append(
                f"디스크 여유 공간이 {free_gb:.1f}GB입니다. "
                f"{RECOMMENDED_DISK_GB}GB 이상 권장."
            )
    except OSError:
        specs['disk_free'] = "확인 불가"

    # 6. ffmpeg check
    try:
        ffmpeg_found = False
        ffprobe_found = False

        # Check ffmpeg
        try:
            creationflags = (
                subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, 'CREATE_NO_WINDOW')
                else 0
            )
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=creationflags
            )
            if result.returncode == 0:
                ffmpeg_found = True
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            # System ffmpeg not found, check imageio_ffmpeg
            try:
                import imageio_ffmpeg
                ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
                if ffmpeg_path and os.path.exists(ffmpeg_path):
                    ffmpeg_found = True
            except (ImportError, AttributeError, OSError):
                pass

        # Check ffprobe
        try:
            creationflags = (
                subprocess.CREATE_NO_WINDOW
                if hasattr(subprocess, 'CREATE_NO_WINDOW')
                else 0
            )
            subprocess.run(
                ['ffprobe', '-version'],
                capture_output=True,
                timeout=5,
                creationflags=creationflags
            )
            ffprobe_found = True
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass

        if ffmpeg_found:
            if ffprobe_found:
                specs['ffmpeg'] = "완전 (ffmpeg + ffprobe)"
            else:
                specs['ffmpeg'] = "설치됨"
        else:
            specs['ffmpeg'] = "없음"
            warnings.append("ffmpeg가 설치되지 않았습니다. 영상 처리 기능을 사용할 수 없습니다.")
    except Exception as e:
        specs['ffmpeg'] = "확인 실패"
        warnings.append(f"ffmpeg 확인 중 오류: {e}")

    can_run = len(issues) == 0
    return can_run, issues, warnings, specs


def show_system_check_dialog() -> bool:
    """
    Show system check results in a popup dialog.

    Returns:
        True if program can continue, False otherwise
    """
    can_run, issues, warnings, specs = check_system_requirements()

    # Build specification text
    spec_text = (
        f"[시스템 사양]\n"
        f"• OS: {specs.get('os', '알 수 없음')}\n"
        f"• 아키텍처: {specs.get('architecture', '알 수 없음')}\n"
        f"• CPU: {specs.get('cpu_name', '알 수 없음')} ({specs.get('cpu_cores', '?')}코어)\n"
        f"• RAM: {specs.get('ram_total', '알 수 없음')} (사용 가능: {specs.get('ram_available', '?')})\n"
        f"• 디스크 여유: {specs.get('disk_free', '알 수 없음')}\n"
        f"• FFmpeg: {specs.get('ffmpeg', '확인 불가')}"
    )

    if not can_run:
        # Cannot run - show error and exit
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("시스템 요구사항 미충족")
        msg.setText("이 컴퓨터에서는 프로그램을 실행할 수 없습니다.")

        detail = spec_text + "\n\n[문제점]\n"
        for issue in issues:
            detail += f"  {issue}\n"
        if warnings:
            detail += "\n[경고]\n"
            for warn in warnings:
                detail += f"  {warn}\n"

        msg.setDetailedText(detail)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        return False

    elif warnings:
        # Warnings but can run - confirm continuation
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("시스템 사양 확인")
        msg.setText(
            "프로그램을 실행할 수 있지만, 일부 제한이 있을 수 있습니다.\n"
            "계속 진행하시겠습니까?"
        )

        detail = spec_text + "\n\n[경고]\n"
        for warn in warnings:
            detail += f"  {warn}\n"

        msg.setDetailedText(detail)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)

        result = msg.exec_()
        return result == QMessageBox.Yes

    else:
        # No issues - continue silently
        return True
