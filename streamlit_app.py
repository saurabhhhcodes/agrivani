"""Streamlit Community Cloud entrypoint for AgriVani.

The full local stack can still be launched with start.py. Streamlit Cloud runs
this file as a single process, and frontend.streamlit_app falls back to
in-process services when the FastAPI backend is not available.
"""

from frontend.streamlit_app import *  # noqa: F401,F403
