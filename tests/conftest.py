"""Pytest configuration - add services directories to Python path."""
import sys
from pathlib import Path

# Add services directory to Python path for shared module imports
services_dir = Path(__file__).parent.parent / "services"
if str(services_dir) not in sys.path:
    sys.path.insert(0, str(services_dir))

# Add hallucination-detector services directory for cascade test module imports
hd_dir = services_dir / "hallucination-detector"
if str(hd_dir) not in sys.path:
    sys.path.insert(0, str(hd_dir))
