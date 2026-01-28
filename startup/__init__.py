# -*- coding: utf-8 -*-
"""
Qt application startup and initialization.
Handles package installation, system checks, OCR loading, and user authentication.
"""
from .app_controller import AppController
from .initializer import Initializer

__all__ = ["AppController", "Initializer"]
