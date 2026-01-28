"""
Application Package

This package contains the modularized components of the main application.
Split from the monolithic main.py for better maintainability.

Modules:
- state: Application state container
- api_handler: API key management UI and logic
- batch_handler: Batch processing control logic
- login_handler: Login watch thread logic
- exit_handler: Application exit and cleanup logic
"""

__all__ = ['api_handler', 'batch_handler', 'login_handler', 'state', 'exit_handler']
