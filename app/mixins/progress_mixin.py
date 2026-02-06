# -*- coding: utf-8 -*-
"""
Progress Mixin - Progress state delegation methods.

Extracted from main.py for cleaner separation of progress management.
"""


class ProgressMixin:
    """Provides progress state management delegation methods.

    Requires:
        - self.progress_manager: ProgressManager instance (optional, with fallback)
        - self.progress_states: dict (for fallback when manager not available)
    """

    def update_progress_state(
        self, step: str, status: str, progress: float = 0, message: str = None
    ):
        """Update progress state for a specific step.

        Args:
            step: Step identifier (e.g., 'download', 'analysis', 'tts')
            status: Status string ('waiting', 'processing', 'completed', 'error')
            progress: Progress value 0-100
            message: Optional status message
        """
        mgr = getattr(self, "progress_manager", None)
        if mgr:
            mgr.update_progress_state(step, status, progress, message)
        else:
            self.progress_states[step] = {
                "status": status,
                "progress": progress,
                "message": message,
            }

    def update_step_progress(self, step: str, value: float):
        """Update progress value for a specific step.

        Args:
            step: Step identifier
            value: Progress value 0-100
        """
        mgr = getattr(self, "progress_manager", None)
        if mgr:
            mgr.update_step_progress(step, value)

    def reset_progress_states(self):
        """Reset all progress states to initial values."""
        mgr = getattr(self, "progress_manager", None)
        if mgr:
            mgr.reset_progress_states()
        else:
            for step in self.progress_states:
                self.progress_states[step] = {
                    "status": "waiting",
                    "progress": 0,
                    "message": None,
                }

    def set_active_job(self, source: str, index: int = None, total: int = None):
        """Set the currently active job being processed.

        Args:
            source: Job source (URL or file path)
            index: Current job index (1-based)
            total: Total number of jobs
        """
        mgr = getattr(self, "progress_manager", None)
        if mgr:
            mgr.set_active_job(source, index, total)

    def set_active_voice(
        self, voice_id: str, voice_index: int = None, voice_total: int = None
    ):
        """Set the currently active voice being processed.

        Args:
            voice_id: Voice identifier
            voice_index: Current voice index (1-based)
            voice_total: Total number of voices
        """
        mgr = getattr(self, "progress_manager", None)
        if mgr:
            mgr.set_active_voice(voice_id, voice_index, voice_total)

    def update_all_progress_displays(self):
        """Update all progress display widgets."""
        mgr = getattr(self, "progress_manager", None)
        if mgr and hasattr(mgr, "update_all_progress_displays"):
            mgr.update_all_progress_displays()

    def update_overall_progress_display(self):
        """Update the overall progress display widget."""
        mgr = getattr(self, "progress_manager", None)
        if mgr and hasattr(mgr, "update_overall_progress_display"):
            mgr.update_overall_progress_display()
