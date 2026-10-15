"""streamlit_app.py: Entrypoint for Streamlit Community Cloud.

Streamlit Cloud looks for streamlit_app.py at the repo root.
This simply delegates to the package dashboard.
"""
import sys
from pathlib import Path

# Add src to path so the package is importable without install
sys.path.insert(0, str(Path(__file__).parent / "src"))

from edge_ai.app.dashboard import main  # noqa: E402

main()
