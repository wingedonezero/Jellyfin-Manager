#!/usr/bin/env python3
"""
Simple run script for development.

Usage:
    python run.py
"""

import sys
from pathlib import Path

# Add src to path for development
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from main import main

if __name__ == "__main__":
    sys.exit(main())
