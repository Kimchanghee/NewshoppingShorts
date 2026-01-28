"""
System Optimizer for Cross-Platform CPU/Memory Optimization

This module dynamically optimizes resource usage based on system hardware.
"""

import os
import sys
import platform
import multiprocessing
import psutil
import warnings
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

from utils.logging_config import get_logger

logger = get_logger(__name__)


def is_windows() -> bool:
    """Check if running on Windows"""
    return platform.system().lower() == 'windows'


def is_macos() -> bool:
    """Check if running on macOS"""
    return platform.system().lower() == 'darwin'


def is_linux() -> bool:
    """Check if running on Linux"""
    return platform.system().lower() == 'linux'


@dataclass
class SystemSpecs:
    """System specifications"""
    cpu_cores: int
    cpu_threads: int
    total_memory_gb: float
    available_memory_gb: float
    is_low_end: bool
    is_high_end: bool
    platform: str
    architecture: str
    has_gpu: bool
    gpu_memory_gb: Optional[float] = None


class SystemOptimizer:
    """
    Dynamic system optimizer for cross-platform compatibility
    """
    
    def __init__(self, app=None):
        self.app = app
        self.specs = self._detect_system_specs()
        self.optimization_settings = self._calculate_optimization_settings()
        
    def _detect_system_specs(self) -> SystemSpecs:
        """Detect system hardware specifications"""
        try:
            # CPU 정보
            cpu_cores = multiprocessing.cpu_count()
            
            # 물리적 코어 수 추정 (Windows/Linux/MacOS)
            physical_cores = cpu_cores
            try:
                if hasattr(psutil, 'cpu_count'):
                    physical_cores = psutil.cpu_count(logical=False) or cpu_cores
            except Exception as e:
                logger.debug("Failed to get physical core count: %s", e)
            
            # 메모리 정보
            memory = psutil.virtual_memory()
            total_memory_gb = memory.total / (1024**3)
            available_memory_gb = memory.available / (1024**3)
            
            # 플랫폼 정보
            current_platform = platform.system()
            architecture = platform.machine()
            
            # 하이엔드/로우엔드 판단
            is_low_end = total_memory_gb < 8.0 or cpu_cores < 4
            is_high_end = total_memory_gb >= 16.0 and cpu_cores >= 8
            
            # GPU 감지 (하드웨어 존재 + CUDA 사용 가능 여부)
            has_gpu = False
            gpu_memory_gb = None

            if is_windows():
                # Windows: GPU 감지 시도
                try:
                    import wmi
                    c = wmi.WMI()
                    for gpu in c.Win32_VideoController():
                        if gpu.AdapterRAM:
                            has_gpu = True
                            gpu_memory_gb = int(gpu.AdapterRAM) / (1024**3)
                            break
                except Exception as e:
                    logger.debug("Failed to detect GPU via WMI: %s", e)

            # CUDA 사용 가능 여부 확인 (GPU가 감지되었어도 torch CUDA 미지원이면 False)
            if has_gpu:
                try:
                    import torch
                    if not torch.cuda.is_available():
                        has_gpu = False
                        gpu_memory_gb = None
                except Exception as e:
                    # torch 없거나 import 실패 시 CPU로 간주
                    logger.debug("CUDA check failed, falling back to CPU: %s", e)
                    has_gpu = False
                    gpu_memory_gb = None
            
            return SystemSpecs(
                cpu_cores=cpu_cores,
                cpu_threads=physical_cores,
                total_memory_gb=total_memory_gb,
                available_memory_gb=available_memory_gb,
                is_low_end=is_low_end,
                is_high_end=is_high_end,
                platform=current_platform,
                architecture=architecture,
                has_gpu=has_gpu,
                gpu_memory_gb=gpu_memory_gb
            )
            
        except Exception as e:
            # 기본값 반환
            warnings.warn(f"System detection failed: {e}")
            return SystemSpecs(
                cpu_cores=4,
                cpu_threads=4,
                total_memory_gb=8.0,
                available_memory_gb=4.0,
                is_low_end=True,
                is_high_end=False,
                platform=platform.system(),
                architecture=platform.machine(),
                has_gpu=False
            )
    
    def _calculate_optimization_settings(self) -> Dict:
        """Calculate optimization settings based on system specs"""
        specs = self.specs

        # OCR 샘플링 간격: 시스템 성능에 따라 동적 조정 (더 보수적으로)
        if specs.is_low_end:
            ocr_sample_interval = 1.0  # 로우엔드: 1초 (부하 대폭 감소)
        elif specs.is_high_end:
            ocr_sample_interval = 0.5  # 하이엔드: 0.5초
        else:
            ocr_sample_interval = 0.7  # 중간: 0.7초

        # 병렬 워커 수: CPU 코어에 비례 (더 보수적으로)
        if specs.cpu_cores <= 4:
            max_parallel_workers = 1  # 4코어 이하: 직렬 처리
        elif specs.cpu_cores <= 8:
            max_parallel_workers = 2  # 8코어 이하: 2개
        else:
            max_parallel_workers = min(3, specs.cpu_cores // 4)  # 최대 3개

        # Faster-Whisper 모델 선택: 기본 base (가장 균형잡힘)
        if specs.total_memory_gb >= 16 and specs.cpu_cores >= 8 and specs.has_gpu:
            whisper_model = "small"  # GPU + 고사양만 small
        elif specs.total_memory_gb >= 8 and specs.cpu_cores >= 4:
            whisper_model = "base"  # 기본 권장 (모든 일반 PC)
        else:
            whisper_model = "tiny"  # 저사양: tiny

        # Faster-Whisper CPU 스레드 제한
        if specs.cpu_cores <= 2:
            whisper_threads = 1
        elif specs.cpu_cores <= 4:
            whisper_threads = 2
        elif specs.cpu_cores <= 8:
            whisper_threads = 4
        else:
            whisper_threads = min(8, specs.cpu_cores // 2)  # 최대 8개

        # Faster-Whisper 디바이스 선택
        # GPU 사용 가능 시 cuda, 아니면 cpu
        if specs.has_gpu and specs.gpu_memory_gb and specs.gpu_memory_gb >= 4:
            whisper_device = "cuda"
        else:
            whisper_device = "cpu"

        # Faster-Whisper compute_type 선택
        # GPU: float16, CPU: int8 (가장 빠름)
        if whisper_device == "cuda":
            whisper_compute_type = "float16"
        else:
            whisper_compute_type = "int8"  # CPU에서 가장 빠름

        # beam_size: Faster-Whisper에서 실제 사용
        if specs.has_gpu and specs.is_high_end:
            whisper_beam_size = 5  # GPU 하이엔드
        elif specs.is_high_end:
            whisper_beam_size = 5  # CPU 하이엔드
        else:
            whisper_beam_size = 3  # 로우/미드엔드: 속도 우선

        # 이미지 다운스케일링 (더 적극적으로)
        if specs.total_memory_gb < 4:
            image_downscale_target = 640  # 매우 낮은 메모리
        elif specs.total_memory_gb < 8:
            image_downscale_target = 720  # 낮은 메모리
        elif specs.is_high_end:
            image_downscale_target = 1080  # 높은 사양
        else:
            image_downscale_target = 960  # 기본

        # ROI 분석 영역 (더 좁게)
        if specs.is_low_end:
            roi_bottom_percent = 25  # 로우엔드: 하단 25%만
        elif specs.is_high_end:
            roi_bottom_percent = 35  # 하이엔드: 하단 35%
        else:
            roi_bottom_percent = 30  # 기본: 하단 30%
        
        # 메모리 사용 제한
        max_memory_usage_gb = min(4.0, specs.total_memory_gb * 0.5)
        
        return {
            'ocr_sample_interval': ocr_sample_interval,
            'max_parallel_workers': max_parallel_workers,
            'whisper_model': whisper_model,
            'whisper_threads': whisper_threads,
            'whisper_device': whisper_device,
            'whisper_compute_type': whisper_compute_type,
            'whisper_beam_size': whisper_beam_size,
            'image_downscale_target': image_downscale_target,
            'roi_bottom_percent': roi_bottom_percent,
            'max_memory_usage_gb': max_memory_usage_gb,
            'use_gpu_acceleration': specs.has_gpu and specs.total_memory_gb >= 8,
            'enable_caching': specs.total_memory_gb >= 4,
            'batch_size': 1 if specs.is_low_end else 2
        }
    
    def get_optimization_settings(self) -> Dict:
        """Get optimization settings"""
        return self.optimization_settings
    
    def get_system_specs(self) -> SystemSpecs:
        """Get system specifications"""
        return self.specs
    
    def print_system_info(self):
        """Print system information and optimization settings"""
        specs = self.specs
        settings = self.optimization_settings

        logger.info("=" * 60)
        logger.info("SYSTEM OPTIMIZATION REPORT")
        logger.info("=" * 60)
        logger.info("Platform: %s (%s)", specs.platform, specs.architecture)
        logger.info("CPU Cores: %d (Logical: %d)", specs.cpu_cores, specs.cpu_threads)
        logger.info("Total Memory: %.1f GB", specs.total_memory_gb)
        logger.info("Available Memory: %.1f GB", specs.available_memory_gb)
        logger.info("System Type: %s", 'Low-end' if specs.is_low_end else 'High-end' if specs.is_high_end else 'Mid-range')
        logger.info("Has GPU: %s", specs.has_gpu)
        if specs.gpu_memory_gb:
            logger.info("GPU Memory: %.1f GB", specs.gpu_memory_gb)

        logger.info("OPTIMIZATION SETTINGS:")
        logger.info("  OCR Sample Interval: %ss", settings['ocr_sample_interval'])
        logger.info("  Max Parallel Workers: %d", settings['max_parallel_workers'])
        logger.info("  Faster-Whisper Model: %s", settings['whisper_model'])
        logger.info("  Faster-Whisper Device: %s", settings['whisper_device'])
        logger.info("  Faster-Whisper Compute Type: %s", settings['whisper_compute_type'])
        logger.info("  CPU Threads: %d", settings['whisper_threads'])
        logger.info("  Whisper Beam Size: %d", settings['whisper_beam_size'])
        logger.info("  Image Downscale: %dpx", settings['image_downscale_target'])
        logger.info("  ROI Bottom Percent: %d%%", settings['roi_bottom_percent'])
        logger.info("  Max Memory Usage: %.1f GB", settings['max_memory_usage_gb'])
        logger.info("  GPU Acceleration: %s", settings['use_gpu_acceleration'])
        logger.info("  Caching Enabled: %s", settings['enable_caching'])
        logger.info("  Batch Size: %d", settings['batch_size'])
        logger.info("=" * 60)
    
    def apply_thread_limits(self):
        """Apply thread limits for Faster-Whisper (CTranslate2)"""
        # Faster-Whisper는 cpu_threads 파라미터를 직접 모델에 전달하므로
        # 별도의 전역 스레드 설정이 필요 없음
        logger.info("[SystemOptimizer] Faster-Whisper will use %d CPU threads", self.optimization_settings['whisper_threads'])
    
    def monitor_memory_usage(self, process_name="main"):
        """Monitor memory usage and warn if approaching limits"""
        try:
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_gb = memory_mb / 1024
            
            max_memory_gb = self.optimization_settings['max_memory_usage_gb']
            
            if memory_gb > max_memory_gb * 0.8:
                logger.warning("[Memory Warning] %s using %.1fGB (%.0f%% of limit)", process_name, memory_gb, memory_gb/max_memory_gb*100)
                return False

            return True
        except Exception as e:
            logger.debug("Failed to monitor memory usage: %s", e)
            return True
    
    def get_optimized_ocr_params(self) -> Dict:
        """Get optimized OCR parameters"""
        settings = self.optimization_settings
        return {
            'sample_interval': settings['ocr_sample_interval'],
            'max_workers': settings['max_parallel_workers'],
            'roi_bottom_percent': settings['roi_bottom_percent'],
            'downscale_target': settings['image_downscale_target'],
            'batch_size': settings['batch_size']
        }
    
    def get_optimized_whisper_params(self) -> Dict:
        """Get optimized Faster-Whisper parameters"""
        settings = self.optimization_settings
        return {
            'model_size': settings['whisper_model'],
            'device': settings['whisper_device'],
            'compute_type': settings['whisper_compute_type'],
            'cpu_threads': settings['whisper_threads'],
            'beam_size': settings['whisper_beam_size'],
        }


def get_system_optimizer(app=None):
    """Factory function to get system optimizer"""
    return SystemOptimizer(app)


if __name__ == "__main__":
    # 테스트 실행
    optimizer = SystemOptimizer()
    optimizer.print_system_info()