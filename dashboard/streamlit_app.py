"""RMS dashboard — Streamlit.

Five pages, selected from the sidebar:
    1. Today / Tomorrow  — hourly covers + staffing
    2. Order Sheet       — ingredient orders
    3. Corrections       — submit predicted-vs-actual feedback
    4. Model Health      — MAE / bias / retrain controls
    5. Coefficient Inspector — LGBM importance + SGD coefficients
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="RMS", layout="wide")

PAGES = (
    "Today / Tomorrow",
    "Order Sheet",
    "Corrections",
    "Model Health",
    "Coefficient Inspector",
)


def main() -> None:
    page = st.sidebar.radio("Page", PAGES)
    st.title(page)
    st.info("Stub — implementation pending. See PLANNING.md §10 and AGENTS.md.")


if __name__ == "__main__":
    main()
