"""
Engineering warnings and validation message panel.
====================================================
Renders the list[ValidationMessage] from SizingResult.messages
with colour-coded severity boxes and clear action guidance.
"""

from __future__ import annotations

import streamlit as st

from backend.models import MessageLevel, SizingResult


def render_warning_panel(result: SizingResult) -> None:
    """
    Render all validation messages from a SizingResult.

    Groups messages by severity level (ERROR → WARNING → INFO).
    Renders a compact summary count at the top.

    Parameters
    ----------
    result : SizingResult   Full result including messages list.
    """
    if not result.messages:
        st.markdown(
            '<div class="ok-box">✅ <strong>No warnings.</strong> '
            'All engineering constraints are satisfied.</div>',
            unsafe_allow_html=True,
        )
        return

    errors   = [m for m in result.messages if m.level == MessageLevel.ERROR]
    warnings = [m for m in result.messages if m.level == MessageLevel.WARNING]
    infos    = [m for m in result.messages if m.level == MessageLevel.INFO]

    # Summary counts
    parts = []
    if errors:   parts.append(f"🔴 {len(errors)} Error{'s' if len(errors) > 1 else ''}")
    if warnings: parts.append(f"🟠 {len(warnings)} Warning{'s' if len(warnings) > 1 else ''}")
    if infos:    parts.append(f"🔵 {len(infos)} Info{'s' if len(infos) > 1 else ''}")
    st.caption("  ·  ".join(parts))

    # ── Errors ────────────────────────────────────────────────────────────
    if errors:
        st.markdown("#### 🔴 Errors")
        for msg in errors:
            st.markdown(
                f'<div class="err-box">'
                f'<strong>[{msg.code}]</strong> {msg.message}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Warnings ──────────────────────────────────────────────────────────
    if warnings:
        st.markdown("#### 🟠 Warnings")
        for msg in warnings:
            st.markdown(
                f'<div class="warn-box">'
                f'<strong>[{msg.code}]</strong> {msg.message}'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Info ──────────────────────────────────────────────────────────────
    if infos:
        with st.expander(f"ℹ {len(infos)} informational note(s)", expanded=False):
            for msg in infos:
                st.markdown(
                    f'<div class="info-box">'
                    f'<strong>[{msg.code}]</strong> {msg.message}'
                    f'</div>',
                    unsafe_allow_html=True,
                )