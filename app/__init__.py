"""
Application Package

This package contains the modularized components of the main application.
Split from the monolithic main.py for better maintainability.

Structure:
- mixins/: Mixin classes for VideoAnalyzerGUI
  - state_bridge: State alias mixin for backward compatibility
  - logging_mixin: Thread-safe logging mixin
  - progress_mixin: Progress state management mixin
  - window_events_mixin: Window event handlers mixin
  - delegation_mixin: Manager delegation stubs mixin
- state: Application state container
- ui_initializer: UI construction logic
- video_helpers: Video processing utility methods
- api_handler: API key management UI and logic
- batch_handler: Batch processing control logic
- login_handler: Login watch thread logic
- exit_handler: Application exit and cleanup logic
"""

__all__ = [
    'mixins',
    'state',
    'ui_initializer',
    'video_helpers',
    'api_handler',
    'batch_handler',
    'login_handler',
    'exit_handler',
]
