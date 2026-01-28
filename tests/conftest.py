"""
Pytest Configuration and Shared Fixtures

Common test fixtures and setup for all tests.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture
def sample_video_path(tmp_path):
    """Provide path to sample video (for testing)"""
    # For actual tests, you would copy a real sample video here
    video_path = tmp_path / "sample.mp4"
    return str(video_path)


@pytest.fixture
def mock_gui():
    """Mock GUI object for testing processors"""
    class MockGUI:
        def __init__(self):
            self.ocr_reader = None
            self.local_file_path = "test.mp4"
            self.video_source = MockVar()
            self._temp_downloaded_file = None

        def update_progress_state(self, *args, **kwargs):
            pass

        def update_step_progress(self, *args, **kwargs):
            pass

    class MockVar:
        def get(self):
            return 'local'

    return MockGUI()


@pytest.fixture
def temp_output_dir(tmp_path):
    """Temporary output directory for test artifacts"""
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)
    return output_dir
