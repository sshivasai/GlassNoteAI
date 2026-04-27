"""
GlassNote GUI Package

This __init__.py sets up the package path once so individual modules
don't need to insert paths manually.
"""

import sys
import os

# Add GUI root to path once for the entire package
_gui_root = os.path.dirname(os.path.abspath(__file__))
if _gui_root not in sys.path:
    sys.path.insert(0, _gui_root)
