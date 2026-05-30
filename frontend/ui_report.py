"""
PDF and Excel report generation.
==================================
Builds downloadable engineering reports from a SizingResult.
Returns BytesIO objects consumed by st.download_button().
"""

"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

import streamlit as st

from backend.models import SizingResult


# ---------------------------------------------------------------------------
# UNICODE → ASCII SAFETY FILTER  (fpdf2 Helvetica is Latin-1 only)
# ---------------------------------------------------------------------------

def _pdf_safe(text: str) -> str:
    """
    Replace every character outside the Latin-1 range (U+0000 – U+00FF)
    with a clean ASCII engineering equivalent.

    fpdf2 core fonts (Helvetica, Times, Courier) use Latin-1 encoding.
    Any character above U+00FF raises:
      "Character X is outside the range of characters supported by the font."

    Parameters
    ----------
    text : str   Any string that will be rendered to a PDF cell.

    Returns
    -------
    str   Safe ASCII string suitable for fpdf2 core fonts.
    """
    if not isinstance(text, str):
        text = str(text)

    _TABLE: dict[str, str] = {
        # ── Dashes ────────────────────────────────────────────────────────
        "\u2014": "-",      # — em dash
        "\u2013": "-",      # – en dash
        "\u2012": "-",      # ‒ figure dash
        "\u2015": "-",      # ― horizontal bar
        "\u2212": "-",      # − minus sign

        # ── Greek letters (engineering notation) ─────────────────────────
        "\u0394": "Delta ", # Δ
        "\u03c1": "rho",    # ρ
        "\u03c3": "sigma",  # σ
        "\u03b7": "eta",    # η
        "\u03b3": "gamma",  # γ
        "\u03bc": "mu",     # μ
        "\u03bd": "nu",     # ν
        "\u03be": "xi",     # ξ
        "\u03c6": "phi",    # φ
        "\u03c0": "pi",     # π
        "\u03b1": "alpha",  # α
        "\u03b2": "beta",   # β
        "\u03b5": "eps",    # ε
        "\u03ba": "kappa",  # κ
        "\u03b8": "theta",  # θ
        "\u03c7": "chi",    # χ
        "\u03c4": "tau",    # τ
        "\u03c9": "omega",  # ω
        "\u03a9": "Omega",  # Ω
        "\u03a3": "Sigma",  # Σ
        "\u0393": "Gamma",  # Γ

        # ── Subscript digits ──────────────────────────────────────────────
        "\u2080": "0",      # ₀
        "\u2081": "1",      # ₁
        "\u2082": "2",      # ₂
        "\u2083": "3",      # ₃
        "\u2084": "4",      # ₄
        "\u2085": "5",      # ₅

        # ── Superscript digits / symbols (note: ² ³ ARE in Latin-1) ──────
        # These are in Latin-1 (U+00B2, U+00B3) and technically safe,
        # but some font variants still reject them — replacing for safety.
        "\u00b2": "2",      # ²
        "\u00b3": "3",      # ³
        "\u00b9": "1",      # ¹
        "\u2070": "0",      # ⁰
        "\u2074": "4",      # ⁴

        # ── Mathematical symbols ──────────────────────────────────────────
        "\u00d7": "x",      # × multiplication sign
        "\u00b7": ".",      # · middle dot / interpunct
        "\u221a": "sqrt",   # √
        "\u2265": ">=",     # ≥
        "\u2264": "<=",     # ≤
        "\u2260": "!=",     # ≠
        "\u00b1": "+/-",    # ±
        "\u221e": "inf",    # ∞
        "\u2192": "->",     # →
        "\u2190": "<-",     # ←
        "\u2248": "~=",     # ≈
        "\u00b0": "deg",    # ° degree sign

        # ── Fractions ─────────────────────────────────────────────────────
        "\u00bc": "1/4",    # ¼
        "\u00bd": "1/2",    # ½
        "\u00be": "3/4",    # ¾

        # ── Typographic quotes (common in copy-pasted text) ───────────────
        "\u2018": "'",      # '
        "\u2019": "'",      # '
        "\u201c": '"',      # "
        "\u201d": '"',      # "

        # ── Bullets and misc ──────────────────────────────────────────────
        "\u2022": "*",      # •
        "\u00b6": "P",      # ¶ pilcrow
        "\u00a9": "(c)",    # ©
        "\u00ae": "(R)",    # ®
        "\u2122": "(TM)",   # ™
    }

    for char, replacement in _TABLE.items():
        text = text.replace(char, replacement)

    # Final safety net: drop any remaining non-Latin-1 characters
    return text.encode("latin-1", errors="replace").decode("latin-1")


# ---------------------------------------------------------------------------
# NONE-SAFE FORMATTER
# ---------------------------------------------------------------------------

def _fmt(value: Optional[float], decimals: int = 3) -> str:
    """Format a float for PDF output, returning '-' (ASCII) for None."""
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"


# ---------------------------------------------------------------------------
# PDF REPORT  (fpdf2)
# ---------------------------------------------------------------------------

def build_pdf_bytes(result: SizingResult) -> bytes:
    """
    Generate a professional engineering sizing report as PDF bytes.

    All text is passed through _pdf_safe() before rendering to avoid
    the "character outside Latin-1 range" fpdf2 error.

    Returns
    -------
    bytes   Raw PDF bytes for st.download_button().
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise ImportError(
            "fpdf2 is required for PDF export.  Run: pip install fpdf2>=2.7.9"
        )

    class _Report(FPDF):
        """Custom FPDF subclass with engineering report styling."""

        def header(self) -> None:
            self.set_fill_color(27, 108, 168)
            self.rect(0, 0, 210, 16, "F")
            self.set_font("Helvetica", "B", 13)
            self.set_text_color(255, 255, 255)
            self.cell(0, 16, "Control Valve Sizing Report", align="C", ln=True)
            self.set_text_color(0, 0, 0)

        def footer(self) -> None:
            self.set_y(-12)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            # Footer uses ASCII only — no _pdf_safe needed
            self.cell(
                0, 10,
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC"
                f"   |   Standard: IEC 60534-2-1:2011 / ISA-75.01.01-2012"
                f"   |   Page {self.page_no()}",
                align="C",
            )

        def section_title(self, title: str) -> None:
            """Render a blue section header bar."""
            self.set_fill_color(27, 108, 168)
            self.set_text_color(255, 255, 255)
            self.set_font("Helvetica", "B", 10)
            # Apply safety filter to section title
            self.cell(0, 7, f"  {_pdf_safe(title)}", fill=True, ln=True)
            self.set_text_color(0, 0, 0)
            self.ln(2)

        def data_row(self, label: str, value: str, unit: str = "") -> None:
            """
            Render one labelled data row.

            _pdf_safe() is applied to ALL three fields here — this means
            build_pdf_bytes() can pass raw engineering strings (with Greek
            letters, em dashes, superscripts, etc.) and they will always
            be sanitised before hitting the font renderer.
            """
            safe_label = _pdf_safe(label)
            safe_value = _pdf_safe(value)
            safe_unit  = _pdf_safe(unit)

            even = (int(self.get_y()) // 6) % 2 == 0
            self.set_fill_color(248, 249, 250)

            # Label column
            self.set_font("Helvetica", "", 9)
            self.set_text_color(0, 0, 0)
            self.cell(80, 6, safe_label, border="B", fill=even)

            # Value column (blue, bold)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(27, 108, 168)
            self.cell(60, 6, safe_value, border="B", fill=even)

            # Unit column (grey, italic)
            self.set_text_color(100, 100, 100)
            self.set_font("Helvetica", "I", 9)
            self.cell(50, 6, safe_unit, border="B", fill=even, ln=True)

            # Reset colour
            self.set_text_color(0, 0, 0)

    # ── Build document ─────────────────────────────────────────────────────
    pdf = _Report()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Title block
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(
        0, 6,
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
        f"Revision: A  |  Status: Preliminary",
        align="C", ln=True,
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # ── Section 1: Primary Sizing Results ─────────────────────────────────
    pdf.section_title("1. PRIMARY SIZING RESULTS")
    # Use _fmt() for None-safe formatting (returns "-" not "—")
    pdf.data_row("Cv Required",              _fmt(result.Cv_required),  "[-]")
    pdf.data_row("Cv Design (with margin)",  _fmt(result.Cv_design),    "[-]")
    pdf.data_row("Kv Required",              _fmt(result.Kv_required),  "m3/h/bar^0.5")
    if result.sizing_ratio is not None:
        pdf.data_row("Sizing Ratio",
                     f"{result.sizing_ratio * 100:.1f}%", "[-]")
    if result.opening_pct is not None:
        pdf.data_row("Estimated Opening",
                     f"{result.opening_pct:.1f}%", "%")
    if result.velocity_ms is not None:
        pdf.data_row("Downstream Velocity",
                     _fmt(result.velocity_ms, 2), "m/s")
    pdf.ln(4)

    # ── Section 2: Process Conditions ─────────────────────────────────────
    pdf.section_title("2. PROCESS CONDITIONS (SI Internal Values)")
    pdf.data_row("Inlet Pressure P1",   _fmt(result.P1_bar, 4),  "bar abs")
    pdf.data_row("Outlet Pressure P2",  _fmt(result.P2_bar, 4),  "bar abs")
    if result.P1_bar and result.P2_bar:
        pdf.data_row("Differential dP",
                     _fmt(result.P1_bar - result.P2_bar, 4), "bar")
    pdf.data_row("Inlet Temperature T1",
                 _fmt(result.T1_K - 273.15 if result.T1_K else None, 1), "deg C")
    pdf.data_row("Mass Flow W",         _fmt(result.W_kgh, 3),  "kg/h")
    pdf.data_row("Inlet Density rho1",  _fmt(result.rho1_kgm3, 4), "kg/m3")
    pdf.ln(4)

    # ── Section 3: Intermediate Values ────────────────────────────────────
    pdf.section_title("3. INTERMEDIATE COMPUTED VALUES")
    pdf.data_row("Fluid Phase",
                 result.fluid_phase.value if result.fluid_phase else "-", "")
    pdf.data_row("Piping Factor Fp",    _fmt(result.Fp, 4),  "[-]")
    pdf.data_row("FF Factor",           _fmt(result.FF, 4),  "[-]")
    pdf.data_row("dP max (choked)",     _fmt(result.delta_P_max_bar, 4), "bar")
    pdf.data_row("dP eff (used in Cv)", _fmt(result.delta_P_eff_bar, 4), "bar")
    pdf.data_row("Expansion Factor Y",  _fmt(result.Y, 4),  "[-]")
    pdf.data_row("Fgamma",             _fmt(result.Fgamma, 4), "[-]")
    pdf.data_row("x (dP/P1)",          _fmt(result.x, 4),  "[-]")
    pdf.data_row("Reynolds Number Rev", _fmt(result.Rev, 0) if result.Rev else "-", "[-]")
    pdf.data_row("FR Factor",           _fmt(result.FR, 4),  "[-]")
    if result.FLP is not None:
        pdf.data_row("FLP (with fittings)", _fmt(result.FLP, 4), "[-]")
    if result.xTP is not None:
        pdf.data_row("xTP (with fittings)", _fmt(result.xTP, 4), "[-]")
    pdf.ln(4)

    # ── Section 4: Cavitation Analysis ────────────────────────────────────
    if result.cavitation:
        pdf.section_title("4. CAVITATION / FLASHING ANALYSIS (IEC 60534-8-4)")
        cav = result.cavitation
        pdf.data_row("Cavitation Regime",   cav.regime.value.upper(), "")
        pdf.data_row("Sigma (sigma)",        _fmt(cav.sigma, 4),            "[-]")
        pdf.data_row("Vena Contracta Pvc",   _fmt(cav.P_vc, 4),             "bar abs")
        pdf.data_row("dP Incipient",         _fmt(cav.delta_P_incipient, 4),"bar")
        pdf.data_row("dP Max (choked)",      _fmt(cav.delta_P_max, 4),      "bar")
        pdf.data_row("FF Factor",            _fmt(cav.FF, 4),               "[-]")
        pdf.data_row("Is Choked",            str(cav.is_choked),            "")
        pdf.data_row("Is Flashing",          str(cav.is_flashing),          "")
        pdf.ln(4)

    # ── Section 5: Noise Prediction ───────────────────────────────────────
    if result.noise:
        pdf.section_title("5. NOISE PREDICTION (IEC 60534-8-3 / 8-4)")
        noise = result.noise
        pdf.data_row("External SPL Lpe",     f"{noise.Lpe_dba:.1f}", "dBA at 1 m")
        pdf.data_row("Internal LWi",         f"{noise.LWi_db:.1f}",  "dB re 1 pW")
        pdf.data_row("Pipe Wall TL",         f"{noise.TL_db:.1f}",   "dB")
        pdf.data_row("Peak Frequency f_p",   f"{noise.f_peak_hz:.0f}", "Hz")
        # eta uses scientific notation — _pdf_safe handles the 'e' notation fine
        pdf.data_row("Acoustic Efficiency eta",
                     f"{noise.eta:.2e}",    "[-]")
        pdf.data_row("Flow Regime",          noise.regime, "")
        pdf.data_row("Exceeds Site Limit",   str(noise.exceeds_limit), "")
        pdf.ln(4)

    # ── Section 6: Engineering Messages ───────────────────────────────────
    if result.messages:
        pdf.section_title("6. ENGINEERING WARNINGS AND NOTES")
        for msg in result.messages:
            level_str  = f"[{msg.level.value.upper()}]"
            code_str   = _pdf_safe(f"[{msg.code}]")
            msg_str    = _pdf_safe(msg.message)

            # Colour the level indicator
            if msg.level.value == "error":
                pdf.set_text_color(220, 53, 69)
            elif msg.level.value == "warning":
                pdf.set_text_color(200, 100, 4)
            else:
                pdf.set_text_color(13, 110, 253)

            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(30, 6, level_str)

            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 6, f"{code_str} {msg_str}")

    return pdf.output()


# ---------------------------------------------------------------------------
# EXCEL REPORT  (openpyxl)
# ---------------------------------------------------------------------------

def build_excel_bytes(result: SizingResult) -> bytes:
    """
    Generate a structured Excel workbook with sizing results.

    Excel handles Unicode natively — no character filtering required.

    Returns
    -------
    bytes   Raw .xlsx bytes for st.download_button().
    """
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    except ImportError:
        raise ImportError(
            "openpyxl is required for Excel export. "
            "Run: pip install openpyxl>=3.1.4"
        )

    wb = openpyxl.Workbook()

    # ── Style helpers ──────────────────────────────────────────────────────
    hdr_font    = Font(bold=True, color="FFFFFF", size=10)
    hdr_fill    = PatternFill("solid", fgColor="1B6CA8")
    val_font    = Font(bold=True, color="1B6CA8", size=10)
    lbl_font    = Font(size=10)
    thin_border = Border(bottom=Side(style="thin", color="DEE2E6"))
    center      = Alignment(horizontal="center", vertical="center")

    def write_section(ws, row: int, title: str) -> int:
        cell = ws.cell(row=row, column=1, value=title)
        cell.font      = hdr_font
        cell.fill      = hdr_fill
        cell.alignment = center
        ws.merge_cells(
            start_row=row, start_column=1,
            end_row=row,   end_column=3,
        )
        return row + 1

    def write_row(ws, row: int, label: str, value: str, unit: str = "") -> int:
        # Excel supports full Unicode — use raw strings (no sanitisation)
        ws.cell(row=row, column=1, value=label).font = lbl_font
        ws.cell(row=row, column=2, value=value).font = val_font
        ws.cell(row=row, column=3, value=unit).font  = Font(
            color="6C757D", italic=True
        )
        for col in range(1, 4):
            ws.cell(row=row, column=col).border = thin_border
        return row + 1

    # ── Sheet 1: Sizing Results ────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Sizing Results"
    ws1.column_dimensions["A"].width = 38
    ws1.column_dimensions["B"].width = 22
    ws1.column_dimensions["C"].width = 22

    r = 1
    ws1.cell(r, 1, "CONTROL VALVE SIZING REPORT").font = Font(
        bold=True, size=14, color="1B6CA8"
    )
    ws1.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    r += 1
    ws1.cell(r, 1,
             f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}").font = Font(
        color="6C757D", size=9
    )
    r += 2

    r = write_section(ws1, r, "PRIMARY RESULTS")
    r = write_row(ws1, r, "Cv Required",
                  _fmt(result.Cv_required), "—")
    r = write_row(ws1, r, "Cv Design (with margin)",
                  _fmt(result.Cv_design), "—")
    r = write_row(ws1, r, "Kv Required",
                  _fmt(result.Kv_required), "m³/h/bar^0.5")
    r = write_row(ws1, r, "Sizing Ratio",
                  f"{result.sizing_ratio*100:.1f}%" if result.sizing_ratio else "—", "—")
    r = write_row(ws1, r, "Estimated Opening %",
                  f"{result.opening_pct:.1f}%" if result.opening_pct else "—", "%")
    r = write_row(ws1, r, "Downstream Velocity",
                  _fmt(result.velocity_ms, 2) if result.velocity_ms else "—", "m/s")
    r += 1

    r = write_section(ws1, r, "PROCESS CONDITIONS (SI)")
    r = write_row(ws1, r, "Inlet Pressure P1",  _fmt(result.P1_bar, 4), "bar abs")
    r = write_row(ws1, r, "Outlet Pressure P2",  _fmt(result.P2_bar, 4), "bar abs")
    r = write_row(ws1, r, "Inlet Temperature T1",
                  _fmt(result.T1_K - 273.15 if result.T1_K else None, 1), "°C")
    r = write_row(ws1, r, "Mass Flow W",         _fmt(result.W_kgh, 3),  "kg/h")
    r = write_row(ws1, r, "Inlet Density ρ₁",    _fmt(result.rho1_kgm3, 4), "kg/m³")
    r += 1

    r = write_section(ws1, r, "INTERMEDIATE VALUES")
    r = write_row(ws1, r, "Piping Factor Fp", _fmt(result.Fp, 4), "—")
    r = write_row(ws1, r, "FF Factor",        _fmt(result.FF, 4), "—")
    r = write_row(ws1, r, "ΔP max",           _fmt(result.delta_P_max_bar, 4), "bar")
    r = write_row(ws1, r, "Expansion Factor Y", _fmt(result.Y, 4), "—")
    r = write_row(ws1, r, "Reynolds Number Rev",
                  _fmt(result.Rev, 0) if result.Rev else "—", "—")
    r = write_row(ws1, r, "FR Factor", _fmt(result.FR, 4), "—")
    r += 1

    # ── Sheet 2: Cavitation ────────────────────────────────────────────────
    if result.cavitation:
        ws2 = wb.create_sheet("Cavitation Analysis")
        ws2.column_dimensions["A"].width = 38
        ws2.column_dimensions["B"].width = 22
        ws2.column_dimensions["C"].width = 22
        cav = result.cavitation
        r2  = write_section(ws2, 1, "CAVITATION ANALYSIS (IEC 60534-8-4)")
        r2  = write_row(ws2, r2, "Cavitation Regime",  cav.regime.value.upper(), "")
        r2  = write_row(ws2, r2, "Sigma σ",            _fmt(cav.sigma, 4), "—")
        r2  = write_row(ws2, r2, "Vena Contracta Pvc", _fmt(cav.P_vc, 4), "bar abs")
        r2  = write_row(ws2, r2, "ΔP Incipient",       _fmt(cav.delta_P_incipient, 4), "bar")
        r2  = write_row(ws2, r2, "ΔP Max (choked)",    _fmt(cav.delta_P_max, 4), "bar")
        r2  = write_row(ws2, r2, "Is Choked",          str(cav.is_choked), "")
        r2  = write_row(ws2, r2, "Is Flashing",        str(cav.is_flashing), "")

    # ── Sheet 3: Noise ────────────────────────────────────────────────────
    if result.noise:
        ws3 = wb.create_sheet("Noise Analysis")
        ws3.column_dimensions["A"].width = 38
        ws3.column_dimensions["B"].width = 22
        ws3.column_dimensions["C"].width = 22
        noise = result.noise
        r3    = write_section(ws3, 1, "NOISE PREDICTION (IEC 60534-8-3/8-4)")
        r3    = write_row(ws3, r3, "External SPL Lpe",  f"{noise.Lpe_dba:.1f}", "dBA at 1 m")
        r3    = write_row(ws3, r3, "Internal LWi",      f"{noise.LWi_db:.1f}",  "dB re 1 pW")
        r3    = write_row(ws3, r3, "Pipe Wall TL",      f"{noise.TL_db:.1f}",   "dB")
        r3    = write_row(ws3, r3, "Peak Frequency f_p",f"{noise.f_peak_hz:.0f}", "Hz")
        r3    = write_row(ws3, r3, "Acoustic Eff. η",   f"{noise.eta:.2e}",     "—")
        r3    = write_row(ws3, r3, "Flow Regime",        noise.regime, "")
        r3    = write_row(ws3, r3, "Exceeds Limit",      str(noise.exceeds_limit), "")

    # ── Sheet 4: Warnings ─────────────────────────────────────────────────
    if result.messages:
        ws4 = wb.create_sheet("Warnings")
        ws4.column_dimensions["A"].width = 12
        ws4.column_dimensions["B"].width = 30
        ws4.column_dimensions["C"].width = 80
        r4 = write_section(ws4, 1, "ENGINEERING MESSAGES")
        for msg in result.messages:
            ws4.cell(r4, 1, msg.level.value.upper())
            ws4.cell(r4, 2, msg.code)
            ws4.cell(r4, 3, msg.message)
            r4 += 1

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# STREAMLIT RENDER PANEL
# ---------------------------------------------------------------------------

def render_report_panel(result: SizingResult) -> None:
    """
    Render the report download panel inside the Report tab.

    Parameters
    ----------
    result : SizingResult   Completed sizing result to export.
    """
    from frontend.ui_styles import section_header_html

    if not result.success:
        st.info("ℹ Run a successful calculation to generate a report.")
        return

    st.markdown(
        section_header_html("Export Sizing Report"),
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    # ── PDF Download ──────────────────────────────────────────────────────
    with col1:
        st.markdown("#### 📄 PDF Report")
        st.caption(
            "Professional engineering sizing report. "
            "Includes all inputs, results, intermediate values, "
            "cavitation analysis, noise prediction, and warnings."
        )
        try:
            pdf_bytes = build_pdf_bytes(result)
            fname = f"valve_sizing_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            st.download_button(
                label="⬇ Download PDF Report",
                data=pdf_bytes,
                file_name=fname,
                mime="application/pdf",
                use_container_width=True,
            )
        except ImportError as e:
            st.warning(f"PDF export unavailable: {e}")
        except Exception as e:
            st.error(f"PDF generation failed: {e}")

    # ── Excel Download ────────────────────────────────────────────────────
    with col2:
        st.markdown("#### 📊 Excel Workbook")
        st.caption(
            "Structured Excel workbook with separate sheets for "
            "sizing results, noise analysis, and engineering warnings."
        )
        try:
            xlsx_bytes = build_excel_bytes(result)
            fname = f"valve_sizing_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            st.download_button(
                label="⬇ Download Excel Workbook",
                data=xlsx_bytes,
                file_name=fname,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        except ImportError as e:
            st.warning(f"Excel export unavailable: {e}")
        except Exception as e:
            st.error(f"Excel generation failed: {e}")

    # ── Contents table ────────────────────────────────────────────────────
    st.divider()
    st.markdown(
        section_header_html("Report Contents"),
        unsafe_allow_html=True,
    )
    st.markdown("""
| Section | Content |
|---|---|
| **1. Primary Results** | Cv required, Cv design, Kv, sizing ratio, opening %, velocity |
| **2. Process Conditions** | P1, P2, T1, flow rate, density (SI internal) |
| **3. Intermediate Values** | FF, Fp, FL, Y, Fgamma, x, Rev, FR, dP_max, dP_eff |
| **4. Cavitation Analysis** | Regime, sigma, Pvc, dP_incipient, dP_max (liquid only) |
| **5. Noise Prediction** | Lpe, LWi, TL, f_peak, eta, regime (IEC 60534-8-3/8-4) |
| **6. Engineering Warnings** | All constraint messages with codes and severity levels |
    """)
