"""
pytest configuration and fixtures for the weather API tests.
"""

import sys
from pathlib import Path

# Add the project root to Python path for test imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import pytest fixtures
import pytest
