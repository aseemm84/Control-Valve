"""
PDF and Excel report generation.
==================================
Builds downloadable engineering reports from a SizingResult.
Returns BytesIO objects consumed by st.download_button().
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

import streamlit as st

from backend.models import FluidPhase, SizingResult


# ---------------------------------------------------------------------------
# PDF REPORT  (fpdf2)
# ---------------------------------------------------------------------------

def build_pdf_bytes(result: SizingResult) -> bytes:
    """
    Generate a professional engineering sizing report as PDF bytes.

    Returns
    -------
    bytes
        Raw PDF bytes suitable for st.download_button().
    """
    try:
        from fpdf import FPDF
    except ImportError:
        raise ImportError("fpdf2 is required for PDF export.  Run: pip install fpdf2>=2.7.8")

    class _Report(FPDF):
        def header(self):
            self.set_fill_color(27, 108, 168)
            self.rect(0, 0, 210, 16, "F")
            self.set_font("Helvetica", "B", 13)
            self.set_text_color(255, 255, 255)
            self.cell(0, 16, "Control Valve Sizing Report", align="C", ln=True)
            self.set_text_color(0, 0, 0)

        def footer(self):
            self.set_y(-12)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(
                0, 10,
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC   |   "
                f"Standard: IEC 60534-2-1:2011 / ISA-75.01.01-2012   |   "
                f"Page {self.page_no()}",
                align="C",
            )

        def section_title(self, title: str) -> None:
            self.set_fill_color(27, 108, 168)
            self.set_text_color(255, 255, 255)
            self.set_font("Helvetica", "B", 10)
            self.cell(0, 7, f"  {title}", fill=True, ln=True)
            self.set_text_color(0, 0, 0)
            self.ln(2)

        def data_row(self, label: str, value: str, unit: str = "") -> None:
            self.set_font("Helvetica", "", 9)
            self.set_fill_color(248, 249, 250)
            even = (self.get_y() // 6) % 2 == 0
            fill = even
            self.cell(80, 6, label, border="B", fill=fill)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(27, 108, 168)
            self.cell(60, 6, value, border="B", fill=fill)
            self.set_text_color(100, 100, 100)
            self.set_font("Helvetica", "I", 9)
            self.cell(50, 6, unit, border="B", fill=fill, ln=True)
            self.set_text_color(0, 0, 0)

    pdf = _Report()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # ── Title block ─────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}   |   "
             f"Revision: A   |   Status: Preliminary", align="C", ln=True)
    pdf.ln(4)

    # ── Section 1: Sizing Results ─────────────────────────────────────
    pdf.section_title("1. PRIMARY SIZING RESULTS")
    if result.Cv_required:
        pdf.data_row("Cv Required", f"{result.Cv_required:.3f}", "—")
        pdf.data_row("Cv Design (with margin)", f"{result.Cv_design:.3f}", "—")
        pdf.data_row("Kv Required", f"{result.Kv_required:.3f}", "m³/h/bar^0.5")
    if result.sizing_ratio:
        pdf.data_row("Sizing Ratio", f"{result.sizing_ratio * 100:.1f}%", "—")
    if result.opening_pct:
        pdf.data_row("Estimated Opening %", f"{result.opening_pct:.1f}%", "—")
    if result.velocity_ms:
        pdf.data_row("Downstream Velocity", f"{result.velocity_ms:.2f}", "m/s")
    pdf.ln(4)

    # ── Section 2: Process Conditions ─────────────────────────────────
    pdf.section_title("2. PROCESS CONDITIONS (SI Internal Values)")
    if result.P1_bar:
        pdf.data_row("Inlet Pressure P1", f"{result.P1_bar:.4f}", "bar abs")
    if result.P2_bar:
        pdf.data_row("Outlet Pressure P2", f"{result.P2_bar:.4f}", "bar abs")
        pdf.data_row("Differential ΔP", f"{result.P1_bar - result.P2_bar:.4f}", "bar")
    if result.T1_K:
        pdf.data_row("Inlet Temperature T1", f"{result.T1_K - 273.15:.1f}", "°C")
    if result.W_kgh:
        pdf.data_row("Mass Flow W", f"{result.W_kgh:.3f}", "kg/h")
    if result.rho1_kgm3:
        pdf.data_row("Inlet Density ρ₁", f"{result.rho1_kgm3:.4f}", "kg/m³")
    pdf.ln(4)

    # ── Section 3: Intermediate Values ────────────────────────────────
    pdf.section_title("3. INTERMEDIATE COMPUTED VALUES")
    pdf.data_row("Fluid Phase", result.fluid_phase.value if result.fluid_phase else "—", "")
    if result.Fp is not None:
        pdf.data_row("Piping Factor Fp", f"{result.Fp:.4f}", "—")
    if result.FF is not None:
        pdf.data_row("Critical Pressure Ratio FF", f"{result.FF:.4f}", "—")
    if result.delta_P_max_bar is not None:
        pdf.data_row("ΔP max (choked)", f"{result.delta_P_max_bar:.4f}", "bar")
    if result.delta_P_eff_bar is not None:
        pdf.data_row("ΔP eff (used in Cv)", f"{result.delta_P_eff_bar:.4f}", "bar")
    if result.Y is not None:
        pdf.data_row("Expansion Factor Y", f"{result.Y:.4f}", "—")
    if result.Fgamma is not None:
        pdf.data_row("Specific Heat Ratio Factor Fγ", f"{result.Fgamma:.4f}", "—")
    if result.x is not None:
        pdf.data_row("Pressure Differential Ratio x", f"{result.x:.4f}", "—")
    if result.FR is not None:
        pdf.data_row("Reynolds Number Factor FR", f"{result.FR:.4f}", "—")
    if result.Rev is not None:
        pdf.data_row("Valve Reynolds Number Rev", f"{result.Rev:.0f}", "—")
    pdf.ln(4)

    # ── Section 4: Cavitation Analysis ────────────────────────────────
    if result.cavitation:
        pdf.section_title("4. CAVITATION / FLASHING ANALYSIS (IEC 60534-8-4)")
        cav = result.cavitation
        pdf.data_row("Cavitation Regime", cav.regime.value.upper(), "")
        pdf.data_row("Cavitation Index σ", f"{cav.sigma:.4f}", "—")
        pdf.data_row("Vena Contracta Pressure Pvc", f"{cav.P_vc:.4f}", "bar abs")
        pdf.data_row("Incipient ΔP", f"{cav.delta_P_incipient:.4f}", "bar")
        pdf.data_row("Maximum ΔP (choked)", f"{cav.delta_P_max:.4f}", "bar")
        pdf.data_row("FF Factor", f"{cav.FF:.4f}", "—")
        pdf.data_row("Is Choked", str(cav.is_choked), "")
        pdf.data_row("Is Flashing", str(cav.is_flashing), "")
        pdf.ln(4)

    # ── Section 5: Noise ──────────────────────────────────────────────
    if result.noise:
        pdf.section_title("5. NOISE PREDICTION (IEC 60534-8-3 / 8-4)")
        noise = result.noise
        pdf.data_row("External SPL Lpe", f"{noise.Lpe_dba:.1f}", "dBA at 1 m")
        pdf.data_row("Internal Sound Power LWi", f"{noise.LWi_db:.1f}", "dB re 1 pW")
        pdf.data_row("Pipe Wall TL", f"{noise.TL_db:.1f}", "dB")
        pdf.data_row("Peak Frequency f_p", f"{noise.f_peak_hz:.0f}", "Hz")
        pdf.data_row("Acoustic Efficiency η", f"{noise.eta:.2e}", "—")
        pdf.data_row("Flow Regime", noise.regime, "")
        pdf.data_row("Exceeds Limit", str(noise.exceeds_limit), "")
        pdf.ln(4)

    # ── Section 6: Warnings ───────────────────────────────────────────
    if result.messages:
        pdf.section_title("6. ENGINEERING WARNINGS & NOTES")
        for msg in result.messages:
            pdf.set_font("Helvetica", "B", 9)
            level_str = f"[{msg.level.value.upper()}]"
            pdf.set_text_color(
                220 if msg.level.value == "error" else
                200 if msg.level.value == "warning" else 13,
                53 if msg.level.value == "error" else
                100 if msg.level.value == "warning" else 110,
                69 if msg.level.value == "error" else
                4 if msg.level.value == "warning" else 253,
            )
            pdf.cell(30, 6, level_str)
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 6, f"[{msg.code}] {msg.message}")

    return pdf.output()


# ---------------------------------------------------------------------------
# EXCEL REPORT  (openpyxl)
# ---------------------------------------------------------------------------

def build_excel_bytes(result: SizingResult) -> bytes:
    """
    Generate a structured Excel workbook with sizing results.

    Returns
    -------
    bytes
        Raw .xlsx bytes suitable for st.download_button().
    """
    try:
        import openpyxl
        from openpyxl.styles import (
            Alignment, Border, Font, PatternFill, Side,
        )
    except ImportError:
        raise ImportError(
            "openpyxl is required for Excel export.  Run: pip install openpyxl>=3.1.2"
        )

    wb = openpyxl.Workbook()

    # ── Style helpers ──────────────────────────────────────────────────
    hdr_font   = Font(bold=True, color="FFFFFF", size=10)
    hdr_fill   = PatternFill("solid", fgColor="1B6CA8")
    val_font   = Font(bold=True, color="1B6CA8", size=10)
    lbl_font   = Font(size=10)
    thin_border= Border(
        bottom=Side(style="thin", color="DEE2E6"),
    )
    center     = Alignment(horizontal="center", vertical="center")

    def write_section(ws, row: int, title: str) -> int:
        cell = ws.cell(row=row, column=1, value=title)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = center
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
        return row + 1

    def write_row(ws, row: int, label: str, value: str, unit: str = "") -> int:
        ws.cell(row=row, column=1, value=label).font  = lbl_font
        ws.cell(row=row, column=2, value=value).font  = val_font
        ws.cell(row=row, column=3, value=unit).font   = Font(color="6C757D", italic=True)
        for col in range(1, 4):
            ws.cell(row=row, column=col).border = thin_border
        return row + 1

    # ── Sheet 1: Sizing Results ─────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Sizing Results"
    ws1.column_dimensions["A"].width = 38
    ws1.column_dimensions["B"].width = 22
    ws1.column_dimensions["C"].width = 22

    r = 1
    ws1.cell(r, 1, "CONTROL VALVE SIZING REPORT").font = Font(bold=True, size=14, color="1B6CA8")
    ws1.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
    r += 1
    ws1.cell(r, 1, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}").font = Font(color="6C757D", size=9)
    r += 2

    r = write_section(ws1, r, "PRIMARY RESULTS")
    r = write_row(ws1, r, "Cv Required", f"{result.Cv_required:.3f}" if result.Cv_required else "—", "—")
    r = write_row(ws1, r, "Cv Design (with margin)", f"{result.Cv_design:.3f}" if result.Cv_design else "—", "—")
    r = write_row(ws1, r, "Kv Required", f"{result.Kv_required:.3f}" if result.Kv_required else "—", "m³/h/bar^0.5")
    r = write_row(ws1, r, "Sizing Ratio", f"{result.sizing_ratio*100:.1f}%" if result.sizing_ratio else "—", "—")
    r = write_row(ws1, r, "Estimated Opening %", f"{result.opening_pct:.1f}%" if result.opening_pct else "—", "%")
    r = write_row(ws1, r, "Downstream Velocity", f"{result.velocity_ms:.2f}" if result.velocity_ms else "—", "m/s")
    r += 1

    r = write_section(ws1, r, "PROCESS CONDITIONS (SI)")
    r = write_row(ws1, r, "Inlet Pressure P1", f"{result.P1_bar:.4f}" if result.P1_bar else "—", "bar abs")
    r = write_row(ws1, r, "Outlet Pressure P2", f"{result.P2_bar:.4f}" if result.P2_bar else "—", "bar abs")
    r = write_row(ws1, r, "Inlet Temperature T1", f"{result.T1_K - 273.15:.1f}" if result.T1_K else "—", "°C")
    r = write_row(ws1, r, "Mass Flow W", f"{result.W_kgh:.3f}" if result.W_kgh else "—", "kg/h")
    r = write_row(ws1, r, "Inlet Density ρ₁", f"{result.rho1_kgm3:.4f}" if result.rho1_kgm3 else "—", "kg/m³")
    r += 1

    r = write_section(ws1, r, "INTERMEDIATE VALUES")
    r = write_row(ws1, r, "Piping Factor Fp", f"{result.Fp:.4f}" if result.Fp else "—", "—")
    r = write_row(ws1, r, "FF Factor", f"{result.FF:.4f}" if result.FF else "—", "—")
    r = write_row(ws1, r, "ΔP max", f"{result.delta_P_max_bar:.4f}" if result.delta_P_max_bar else "—", "bar")
    r = write_row(ws1, r, "Expansion Factor Y", f"{result.Y:.4f}" if result.Y else "—", "—")
    r = write_row(ws1, r, "Reynolds Number Rev", f"{result.Rev:.0f}" if result.Rev else "—", "—")
    r = write_row(ws1, r, "FR Factor", f"{result.FR:.4f}" if result.FR else "—", "—")
    r += 1

    # Cavitation
    if result.cavitation:
        cav = result.cavitation
        r = write_section(ws1, r, "CAVITATION ANALYSIS")
        r = write_row(ws1, r, "Regime", cav.regime.value.upper(), "")
        r = write_row(ws1, r, "Sigma σ", f"{cav.sigma:.4f}", "—")
        r = write_row(ws1, r, "Pvc", f"{cav.P_vc:.4f}", "bar abs")
        r = write_row(ws1, r, "ΔP incipient", f"{cav.delta_P_incipient:.4f}", "bar")
        r = write_row(ws1, r, "ΔP max", f"{cav.delta_P_max:.4f}", "bar")
        r += 1

    # ── Sheet 2: Noise ──────────────────────────────────────────────
    if result.noise:
        ws2 = wb.create_sheet("Noise Analysis")
        ws2.column_dimensions["A"].width = 38
        ws2.column_dimensions["B"].width = 22
        ws2.column_dimensions["C"].width = 22
        noise = result.noise
        r2 = 1
        r2 = write_section(ws2, r2, "NOISE PREDICTION (IEC 60534-8-3/8-4)")
        r2 = write_row(ws2, r2, "External SPL Lpe", f"{noise.Lpe_dba:.1f}", "dBA at 1 m")
        r2 = write_row(ws2, r2, "Internal LWi", f"{noise.LWi_db:.1f}", "dB re 1 pW")
        r2 = write_row(ws2, r2, "Pipe Wall TL", f"{noise.TL_db:.1f}", "dB")
        r2 = write_row(ws2, r2, "Peak Frequency f_p", f"{noise.f_peak_hz:.0f}", "Hz")
        r2 = write_row(ws2, r2, "Acoustic Efficiency η", f"{noise.eta:.2e}", "—")
        r2 = write_row(ws2, r2, "Flow Regime", noise.regime, "")
        r2 = write_row(ws2, r2, "Exceeds Limit", str(noise.exceeds_limit), "")

    # ── Sheet 3: Warnings ───────────────────────────────────────────
    if result.messages:
        ws3 = wb.create_sheet("Warnings")
        ws3.column_dimensions["A"].width = 15
        ws3.column_dimensions["B"].width = 30
        ws3.column_dimensions["C"].width = 80
        r3 = write_section(ws3, 1, "ENGINEERING MESSAGES")
        for msg in result.messages:
            ws3.cell(r3, 1, msg.level.value.upper())
            ws3.cell(r3, 2, msg.code)
            ws3.cell(r3, 3, msg.message)
            r3 += 1

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
        section_header_html("Export Sizing Report"), unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    # ── PDF Download ──────────────────────────────────────────────────
    with col1:
        st.markdown("#### 📄 PDF Report")
        st.caption(
            "Professional engineering sizing report in PDF format.  "
            "Includes all inputs, results, intermediate values, cavitation "
            "analysis, noise prediction, and engineering warnings."
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

    # ── Excel Download ────────────────────────────────────────────────
    with col2:
        st.markdown("#### 📊 Excel Workbook")
        st.caption(
            "Structured Excel workbook with separate sheets for sizing results, "
            "noise analysis, and engineering warnings.  Suitable for integration "
            "into project design packages."
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

    # ── Report metadata ───────────────────────────────────────────────
    st.divider()
    st.markdown(
        section_header_html("Report Contents"), unsafe_allow_html=True
    )
    st.markdown("""
| Section | Content |
|---|---|
| **1. Primary Results** | Cv_required, Cv_design, Kv, sizing ratio, opening %, velocity |
| **2. Process Conditions** | P1, P2, T1, flow rate, density (SI) |
| **3. Intermediate Values** | FF, Fp, FL, Y, Fγ, x, Rev, FR, ΔP_max, ΔP_eff |
| **4. Cavitation Analysis** | Regime, σ, P_vc, ΔP_incipient, ΔP_max (liquid only) |
| **5. Noise Prediction** | Lpe, LWi, TL, f_peak, η, regime (IEC 60534-8-3/8-4) |
| **6. Engineering Warnings** | All hard constraint errors and soft warnings with codes |
    """)