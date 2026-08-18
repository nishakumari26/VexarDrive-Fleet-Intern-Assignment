"""Build the Google Form pack: technical report PDF + dashboard images."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
PACK = ROOT / "submission"
IMG = PACK / "dashboard_images"
REPO = "https://github.com/nishakumari26/VexarDrive-Fleet-Intern-Assignment"

NAVY = colors.HexColor("#0B3D5C")
TEAL = colors.HexColor("#1B6B7A")
LIGHT = colors.HexColor("#F4F7F9")
LINE = colors.HexColor("#D5DEE5")
BAND = {
    "Safe": "#2E7D32",
    "Moderate": "#EF6C00",
    "Risky": "#C62828",
    "Healthy": "#2E7D32",
    "Needs Attention": "#EF6C00",
    "Maintenance Required": "#C62828",
}


def styles():
    base = getSampleStyleSheet()
    s = {
        "cover_kicker": ParagraphStyle(
            "cover_kicker", parent=base["Normal"], fontName="Times-Bold",
            fontSize=10, textColor=TEAL, alignment=TA_CENTER, tracking=1.2,
        ),
        "cover_title": ParagraphStyle(
            "cover_title", parent=base["Title"], fontName="Times-Bold",
            fontSize=22, leading=26, textColor=NAVY, alignment=TA_CENTER, spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=base["Normal"], fontName="Times-Roman",
            fontSize=12, leading=16, textColor=colors.HexColor("#334"),
            alignment=TA_CENTER, spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="Times-Bold",
            fontSize=14, leading=18, textColor=NAVY, spaceBefore=14, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="Times-Bold",
            fontSize=12, leading=15, textColor=TEAL, spaceBefore=10, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontName="Times-Roman",
            fontSize=10, leading=14, alignment=TA_JUSTIFY, spaceAfter=7,
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"], fontName="Times-Italic",
            fontSize=8.5, leading=11, textColor=colors.HexColor("#445"),
            alignment=TA_CENTER, spaceBefore=3, spaceAfter=10,
        ),
        "cell": ParagraphStyle(
            "cell", parent=base["Normal"], fontName="Times-Roman",
            fontSize=7.5, leading=10,
        ),
        "cell_h": ParagraphStyle(
            "cell_h", parent=base["Normal"], fontName="Times-Bold",
            fontSize=7.5, leading=10, textColor=colors.white,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"], fontName="Times-Roman",
            fontSize=8, textColor=colors.HexColor("#556"), alignment=TA_CENTER,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"], fontName="Times-Roman",
            fontSize=10, leading=13, leftIndent=4, spaceAfter=2,
        ),
    }
    return s


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Times-Roman", 8)
    canvas.drawString(18 * mm, A4[1] - 8 * mm, "VexarDrive  |  Data Scientist Intern Assignment")
    canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 8 * mm, "Technical Report")
    canvas.setFillColor(LINE)
    canvas.rect(0, 0, A4[0], 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#445"))
    canvas.setFont("Times-Roman", 8)
    canvas.drawString(18 * mm, 5 * mm, "Candidate workbook week: 31 Jul - 6 Aug 2026  |  Bengaluru hubs")
    canvas.drawRightString(A4[0] - 18 * mm, 5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def cover_header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 28 * mm, A4[0], 28 * mm, fill=1, stroke=0)
    canvas.setFillColor(TEAL)
    canvas.rect(0, 0, A4[0], 18 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Times-Roman", 9)
    canvas.drawCentredString(A4[0] / 2, 8 * mm, "Confidential candidate submission  |  VexarDrive Technologies")
    canvas.restoreState()


def p(text, style):
    return Paragraph(text.replace("\n", "<br/>"), style)


def table(headers, rows, col_widths, s):
    head = [p(h, s["cell_h"]) for h in headers]
    body = [[p(str(c), s["cell"]) for c in row] for row in rows]
    t = Table([head] + body, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    return t


def save_dashboard_images(drv: pd.DataFrame, veh: pd.DataFrame) -> dict[str, Path]:
    IMG.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "axes.titlesize": 13,
        "axes.labelsize": 10,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    })
    paths = {}

    def bar_panel(ax, df, id_col, name_col, score_col, band_col, xlabel, title):
        plot = df.sort_values(score_col, ascending=True)
        labels = plot[id_col] + "  " + plot[name_col].astype(str)
        colors_ = [BAND[b] for b in plot[band_col]]
        ax.barh(labels, plot[score_col], color=colors_, height=0.72)
        ax.set_xlabel(xlabel)
        ax.set_title(title, loc="left", pad=8, color="#0B3D5C", fontweight="bold")
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(axis="x", linestyle=":", alpha=0.4)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig, axes = plt.subplots(2, 1, figsize=(12.5, 16.5), gridspec_kw={"height_ratios": [2.4, 1]})
    fig.suptitle(
        "VexarDrive  |  Driver Behaviour Dashboard",
        fontsize=16, fontweight="bold", color="#0B3D5C", y=0.995,
    )
    fig.text(
        0.06, 0.965,
        "Risk is relative to this 30-driver week. Green = Safe, amber = Moderate, red = Risky. "
        "Thresholds are empirical P95 of moving telemetry (speed 42.4 km/h, horiz. IMU 0.460 g, |Gyro_Z| 5.01 deg/s).",
        fontsize=8.5, color="#445",
    )
    bar_panel(
        axes[0], drv, "Driver_ID", "Driver_Name", "risk_score", "risk_band",
        "Risk score (0 = safest vs peers this week)",
        "Overall driver risk score",
    )
    axes[1].scatter(
        drv["overspeed_per_100km"], drv["harsh_horiz_per_100km"],
        c=[BAND[b] for b in drv["risk_band"]], s=55, zorder=3,
    )
    for _, r in drv.iterrows():
        axes[1].annotate(r["Driver_ID"], (r["overspeed_per_100km"], r["harsh_horiz_per_100km"]),
                         textcoords="offset points", xytext=(4, 3), fontsize=7)
    axes[1].set_xlabel("Overspeed minutes per 100 km")
    axes[1].set_ylabel("Harsh horizontal IMU minutes per 100 km")
    axes[1].set_title("Overspeed rate vs harsh IMU rate", loc="left", color="#0B3D5C", fontweight="bold")
    axes[1].grid(True, linestyle=":", alpha=0.4)
    axes[1].spines["top"].set_visible(False)
    axes[1].spines["right"].set_visible(False)
    legend = [
        Patch(facecolor=BAND["Safe"], label="Safe (n=10)"),
        Patch(facecolor=BAND["Moderate"], label="Moderate (n=10)"),
        Patch(facecolor=BAND["Risky"], label="Risky (n=10)"),
    ]
    axes[0].legend(handles=legend, loc="lower right", frameon=False, fontsize=8)
    fig.tight_layout(rect=[0, 0.01, 1, 0.96])
    paths["driver"] = IMG / "01_driver_behaviour_dashboard.png"
    fig.savefig(paths["driver"], dpi=160)
    plt.close(fig)

    veh = veh.copy()
    veh["label"] = veh["Make"] + " " + veh["Model"]
    fig, axes = plt.subplots(2, 1, figsize=(12.5, 16.5), gridspec_kw={"height_ratios": [2.4, 1]})
    fig.suptitle(
        "VexarDrive  |  Vehicle Health Status Dashboard",
        fontsize=16, fontweight="bold", color="#0B3D5C", y=0.995,
    )
    fig.text(
        0.06, 0.965,
        "Health mixes workshop fields (odometer, days since service, age) with speed-controlled IMU (cruise 15-35 km/h). "
        "Green = Healthy, amber = Needs Attention, red = Maintenance Required.",
        fontsize=8.5, color="#445",
    )
    bar_panel(
        axes[0], veh, "Vehicle_ID", "label", "maintenance_risk", "health_band",
        "Maintenance risk (0 = healthiest vs peers this week)",
        "Overall vehicle maintenance risk",
    )
    sizes = (veh["Odometer_KM_Start_of_Week"] / 900).clip(28, 180)
    axes[1].scatter(
        veh["days_since_service"], veh["cruise_vibration_g"],
        c=[BAND[b] for b in veh["health_band"]], s=sizes, zorder=3, alpha=0.9,
    )
    for _, r in veh.iterrows():
        axes[1].annotate(r["Vehicle_ID"], (r["days_since_service"], r["cruise_vibration_g"]),
                         textcoords="offset points", xytext=(4, 3), fontsize=7)
    axes[1].set_xlabel("Days since last service")
    axes[1].set_ylabel("Mean |accel magnitude - 1 g| while cruising")
    axes[1].set_title("Days since service vs cruise vibration (marker size proportional to odometer)",
                      loc="left", color="#0B3D5C", fontweight="bold")
    axes[1].grid(True, linestyle=":", alpha=0.4)
    axes[1].spines["top"].set_visible(False)
    axes[1].spines["right"].set_visible(False)
    legend = [
        Patch(facecolor=BAND["Healthy"], label="Healthy (n=10)"),
        Patch(facecolor=BAND["Needs Attention"], label="Needs Attention (n=10)"),
        Patch(facecolor=BAND["Maintenance Required"], label="Maintenance Required (n=10)"),
    ]
    axes[0].legend(handles=legend, loc="lower right", frameon=False, fontsize=8)
    fig.tight_layout(rect=[0, 0.01, 1, 0.96])
    paths["vehicle"] = IMG / "02_vehicle_health_dashboard.png"
    fig.savefig(paths["vehicle"], dpi=160)
    plt.close(fig)
    return paths


def build_pdf(drv: pd.DataFrame, veh: pd.DataFrame, images: dict[str, Path]) -> Path:
    PACK.mkdir(parents=True, exist_ok=True)
    pdf_path = PACK / "VexarDrive_Technical_Report.pdf"
    s = styles()
    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        leftMargin=17 * mm, rightMargin=17 * mm,
        topMargin=20 * mm, bottomMargin=18 * mm,
        title="VexarDrive Data Scientist Intern - Technical Report",
        author="Nisha Kumari",
    )
    story = []
    usable = A4[0] - 34 * mm

    story.append(Spacer(1, 38 * mm))
    story.append(p("DATA SCIENTIST INTERN ASSIGNMENT", s["cover_kicker"]))
    story.append(Spacer(1, 6 * mm))
    story.append(p("Technical Report", s["cover_title"]))
    story.append(p("Driver Behaviour and Vehicle Health Dashboards<br/>from One Week of Two-Wheeler Fleet Telemetry", s["cover_sub"]))
    story.append(Spacer(1, 8 * mm))
    meta = [
        ["Candidate organisation", "VexarDrive Technologies"],
        ["Dataset", "VEXAR_Fleet_Dataset_CANDIDATE_VERSION.xlsx"],
        ["Observation window", "31 July 2026 - 6 August 2026"],
        ["Scope", "30 drivers, 30 two-wheelers, 450 trips, 12,987 per-minute GPS + IMU rows"],
        ["Geography", "Bengaluru hubs (Rajajinagar, HSR Layout, Bellandur, and others)"],
        ["Code and dashboards", REPO],
        ["Interactive HTML", "dashboards/driver_behaviour.html and dashboards/vehicle_health.html"],
    ]
    mt = Table(
        [[p(f"<b>{a}</b>", s["cell"]), p(b, s["cell"])] for a, b in meta],
        colWidths=[45 * mm, usable - 45 * mm],
    )
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.3, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(mt)
    story.append(Spacer(1, 10 * mm))
    story.append(p(
        "This report documents how every KPI, threshold, score and band on the two required dashboards "
        "was derived from the candidate workbook. No synthetic rows were added. Cut-offs are empirical "
        "percentiles of this week's moving telemetry, not textbook automotive constants or legal speed limits.",
        s["body"],
    ))
    story.append(PageBreak())

    story.append(p("1. Problem and required outputs", s["h1"]))
    story.append(p(
        "VexarDrive operates a two-wheeler delivery fleet. The candidate brief asks for two explainable "
        "dashboards built only from the supplied week of trip and phone-sensor data:",
        s["body"],
    ))
    story.append(ListFlowable([
        ListItem(p("<b>Driver Behaviour Dashboard</b> - score every driver, separate risky vs safe patterns, "
                   "and show why each score exists.", s["bullet"])),
        ListItem(p("<b>Vehicle Health Status Dashboard</b> - flag vehicles whose IMU / GPS / trip patterns "
                   "suggest wear or a workshop visit, and show what triggered the flag.", s["bullet"])),
    ], bulletType="1", leftIndent=12, start="1"))
    story.append(p(
        "The brief also requires a methodology for every displayed number, explicit assumptions, and "
        "additional uses of the same columns. Labels such as Safe / Risky or Healthy / Maintenance Required "
        "are used only where the data can support a relative ranking of the current 30-unit roster.",
        s["body"],
    ))

    story.append(p("2. Data loading, joins and validation", s["h1"]))
    story.append(p(
        "Sheets are read with <b>header=2</b> because row 0 is a title (for example \"Drivers (Master Data)\"), "
        "row 1 is blank, and row 2 holds column names. Joins follow the brief:",
        s["body"],
    ))
    story.append(p(
        "Telemetry.Trip_ID &rarr; Trips.Trip_ID &nbsp;|&nbsp; Trips.Driver_ID &rarr; Drivers.Driver_ID "
        "&nbsp;|&nbsp; Trips.Vehicle_ID &rarr; Vehicles.Vehicle_ID",
        s["caption"],
    ))
    story.append(p("Quality checks written to outputs/qa_report.json:", s["body"]))
    story.append(table(
        ["Check", "Result"],
        [
            ["Rows", "30 drivers, 30 vehicles, 450 trips, 12,987 telemetry minutes"],
            ["Null cells", "0 on all four tables"],
            ["Orphan keys", "0 (every trip driver/vehicle exists in master data)"],
            ["Telemetry coverage", "Every trip has telemetry; row count = Duration_Min"],
            ["ID consistency", "Telemetry Driver_ID and Vehicle_ID match the parent trip"],
            ["Balance", "Exactly 15 trips per driver"],
        ],
        [55 * mm, usable - 55 * mm], s,
    ))
    story.append(p(
        "Two data-quality notes were recorded and then excluded from scoring: two people share the name "
        "Kavya Pillai (D07 and D23), so analysis keys on Driver_ID; Gender sometimes disagrees with the "
        "given name, so gender is not an input to any KPI.",
        s["body"],
    ))

    story.append(p("3. Why thresholds are empirical", s["h1"]))
    story.append(p(
        "The phone IMU is one sample per minute. A literature harsh-brake cut-off of about 0.4 g lasting "
        "about one second cannot be applied honestly: a 60-second average hides the spike. Accel_Z has mean "
        "1.007 g (gravity on Z). One-minute change in speed is uncorrelated with the accel axes, so speed "
        "delta is not used as a harsh-event detector.",
        s["body"],
    ))
    story.append(p(
        "Event lines are the 95th percentile of <b>moving</b> minutes (speed at least 5 km/h; n = 11,891). "
        "Five km/h is only an idle/crawl gate, not a safety limit.",
        s["body"],
    ))
    story.append(table(
        ["Signal", "Event line (P95)", "Notes"],
        [
            ["Speed_kmph", "42.4 km/h", "P99 = 52.1 km/h. Not a posted legal limit (none in the file)."],
            ["Horizontal accel sqrt(X^2+Y^2)", "0.460 g", "Phone-plane jerks; Z is gravity-dominated."],
            ["|Gyro_Z|", "5.01 deg/s", "Heavy tail (P99 about 39.7 deg/s)."],
            ["|Accel_Z - 1 g|", "0.087 g", "Vertical bump / suspension proxy."],
        ],
        [50 * mm, 35 * mm, usable - 85 * mm], s,
    ))
    story.append(p(
        "Counts are converted to rates per 100 km using Trips.Distance_KM so a longer trip is not punished "
        "only for lasting more minutes.",
        s["body"],
    ))

    story.append(p("4. Driver Behaviour Dashboard", s["h1"]))
    story.append(p("4.1 Metrics", s["h2"]))
    story.append(table(
        ["KPI", "Columns", "Calculation", "Why it is relevant"],
        [
            ["Overspeed min / 100 km", "Speed_kmph, Distance_KM",
             "Minutes with speed > 42.4 km/h, divided by km, times 100; mean of 15 trips.",
             "Only direct collision-energy / speed signal in the workbook."],
            ["Harsh horizontal IMU / 100 km", "Accel_X_g, Accel_Y_g",
             "sqrt(X^2+Y^2) > 0.460 g, exposure-adjusted.",
             "Proxy for aggressive start/stop or swerve when 1-minute speed deltas are too smooth."],
            ["Yaw events / 100 km", "Gyro_Z_dps",
             "|Gyro_Z| > 5.01 deg/s, exposure-adjusted.",
             "Abrupt heading change on a two-wheeler."],
            ["Mean trip max speed", "Max_Speed_kmph",
             "Average of trip maxima.",
             "Captures a short peak that may not dominate the overspeed-minute share."],
        ],
        [38 * mm, 32 * mm, 55 * mm, usable - 125 * mm], s,
    ))
    story.append(p("4.2 Overall risk score", s["h2"]))
    story.append(p(
        "Each metric is converted to a percentile rank among the 30 drivers (0-100). The composite is:",
        s["body"],
    ))
    story.append(p(
        "<b>risk_score = 0.30 x overspeed rank + 0.25 x harsh IMU rank + 0.25 x yaw rank + 0.20 x max-speed rank</b>",
        s["caption"],
    ))
    story.append(p(
        "Ranks avoid arbitrary 0-1 scaling. Weights put slightly more mass on overspeed because it is the "
        "most interpretable safety signal here; IMU components are equal. Changing the weights reorders the "
        "middle of the pack more than the extremes. This weighting is an assumption and is stated as such.",
        s["body"],
    ))
    story.append(p("4.3 Bands (Safe / Moderate / Risky)", s["h2"]))
    story.append(p(
        "There are no labelled crashes or insurance events. With n = 30, the only classification justified "
        "by the data is a relative split of this week's scores. Tertiles give a 10 / 10 / 10 split:",
        s["body"],
    ))
    story.append(table(
        ["Band", "Rule on risk_score", "Meaning"],
        [
            ["Safe", "score &lt;= 37.0", "Safer than peers this week, not 'legal'."],
            ["Moderate", "37.0 &lt; score &lt;= 64.3", "Typical for this roster."],
            ["Risky", "score &gt; 64.3", "Riskier than peers this week, not 'illegal'."],
        ],
        [32 * mm, 45 * mm, usable - 77 * mm], s,
    ))
    story.append(p(
        "The dashboard table includes a full 'why' sentence: the four rates, kilometres, trips, and the "
        "largest contributing rank, so a reviewer can see why a driver received a particular score.",
        s["body"],
    ))
    story.append(p("4.4 Findings this week", s["h2"]))
    top_r = drv.head(5)
    bot_r = drv.sort_values("risk_score").head(5)
    story.append(table(
        ["ID", "Driver", "Risk", "Band", "Largest contributor", "Overspeed /100km"],
        [[r.Driver_ID, r.Driver_Name, f"{r.risk_score:.1f}", r.risk_band,
          r.top_contributor, f"{r.overspeed_per_100km:.1f}"] for r in top_r.itertuples()],
        [16 * mm, 38 * mm, 18 * mm, 22 * mm, 52 * mm, usable - 146 * mm], s,
    ))
    story.append(p("Table 1. Highest-risk drivers this week.", s["caption"]))
    story.append(table(
        ["ID", "Driver", "Risk", "Band", "Largest contributor"],
        [[r.Driver_ID, r.Driver_Name, f"{r.risk_score:.1f}", r.risk_band, r.top_contributor]
         for r in bot_r.itertuples()],
        [16 * mm, 42 * mm, 18 * mm, 22 * mm, usable - 98 * mm], s,
    ))
    story.append(p("Table 2. Lowest-risk (safest vs peers) drivers this week.", s["caption"]))
    story.append(p(
        "Headline: D19 Senthil Pillai scores 95.0 (Risky) because overspeed is 53.1 minutes per 100 km "
        "(fleet-worst). D28 is at the other end of the same relative scale (9.5, Safe).",
        s["body"],
    ))
    story.append(Image(str(images["driver"]), width=usable, height=usable * 16.5 / 12.5 * 0.42))
    story.append(p("Figure 1. Driver Behaviour Dashboard (static image of the interactive HTML).", s["caption"]))

    story.append(p("5. Vehicle Health Status Dashboard", s["h1"]))
    story.append(p(
        "The workbook has no OBD, DTCs, tyre pressure or workshop job cards. Health is inferred from "
        "master-data wear plus speed-controlled IMU. GPS is used as Speed_kmph (dictionary: instantaneous "
        "speed). Latitude / longitude are not in the health score because there is no planned route or "
        "road-quality layer; they remain a pothole-heatmap extra use case.",
        s["body"],
    ))
    story.append(p(
        "Cruise window 15-35 km/h matches this fleet's typical urban speed (trip average about 24 km/h) "
        "and reduces stop-go riding style so vibration is closer to a machine signal.",
        s["body"],
    ))
    story.append(p("5.1 Metrics", s["h2"]))
    story.append(table(
        ["KPI", "Columns", "Calculation", "Why it is relevant"],
        [
            ["Days since service", "Last_Service_Date vs 6 Aug 2026",
             "Days late, then fleet percentile rank.",
             "No OEM interval in the file; lateness is relative."],
            ["Odometer", "Odometer_KM_Start_of_Week", "Percentile rank.",
             "Only mileage field; wear accumulates with distance."],
            ["Age (years)", "Manufacture_Year", "2026 minus year, then rank.",
             "Older two-wheelers typically need more shop time."],
            ["Cruise vibration", "Accel X/Y/Z at 15-35 km/h",
             "Mean |accel magnitude - 1 g|, then rank.",
             "Persistent shake at steady speed (engine / wheel / suspension)."],
            ["Cruise gyro", "Gyro X/Y/Z at 15-35 km/h",
             "Median gyro magnitude, then rank.",
             "Median used because gyro has a heavy tail; rotational shake."],
            ["Vertical bumps / 100 km", "Accel_Z_g, Distance_KM",
             "|Z-1| > 0.087 g, exposure-adjusted.",
             "Pothole or worn-suspension proxy."],
        ],
        [38 * mm, 38 * mm, 50 * mm, usable - 126 * mm], s,
    ))
    story.append(p("5.2 Health / maintenance score", s["h2"]))
    story.append(p(
        "<b>maintenance_risk = 0.22 service + 0.18 odometer + 0.12 age + 0.22 vibration + 0.12 cruise gyro + 0.14 bumps</b><br/>"
        "<b>health_score = 100 - maintenance_risk</b>",
        s["caption"],
    ))
    story.append(p(
        "Workshop fields (service, odometer, age) do not depend on riding style. IMU terms are speed-controlled. "
        "Weights are assumptions: slightly more mass on service recency and cruise vibration.",
        s["body"],
    ))
    story.append(p("5.3 Bands", s["h2"]))
    story.append(table(
        ["Band", "Rule on maintenance_risk", "Meaning"],
        [
            ["Healthy", "risk &lt;= 36.0", "Healthier than peers this week."],
            ["Needs Attention", "36.0 &lt; risk &lt;= 65.4", "Typical for this roster."],
            ["Maintenance Required", "risk &gt; 65.4", "Priority workshop queue vs peers, not a DTC."],
        ],
        [42 * mm, 48 * mm, usable - 90 * mm], s,
    ))
    story.append(p("5.4 Findings and confounding", s["h2"]))
    top_v = veh.head(5)
    story.append(table(
        ["ID", "Vehicle", "Health", "Band", "Odo km", "Days since service", "Largest contributor"],
        [[r.Vehicle_ID, f"{r.Make} {r.Model}", f"{r.health_score:.1f}", r.health_band,
          f"{int(r.Odometer_KM_Start_of_Week):,}", str(int(r.days_since_service)), r.top_contributor]
         for r in top_v.itertuples()],
        [16 * mm, 32 * mm, 18 * mm, 38 * mm, 22 * mm, 28 * mm, usable - 154 * mm], s,
    ))
    story.append(p("Table 3. Highest maintenance-risk vehicles (shop first).", s["caption"]))
    story.append(p(
        "Priority unit: V02 TVS Raider, health 4.8, 46,601 km, 92 days since service. "
        "Nineteen vehicles have a single rider this week, so IMU can still mix style with machine. "
        "Mitigation: (1) service / odometer / age are rider-independent; (2) vibration is cruise-only; "
        "(3) V02's usual rider D02 is only Moderate on behaviour while V02 is the worst health unit - "
        "evidence that the vehicle metrics are not a copy of the driver score.",
        s["body"],
    ))
    story.append(Image(str(images["vehicle"]), width=usable, height=usable * 16.5 / 12.5 * 0.42))
    story.append(p("Figure 2. Vehicle Health Status Dashboard (static image of the interactive HTML).", s["caption"]))

    story.append(p("6. Assumptions", s["h1"]))
    story.append(ListFlowable([
        ListItem(p("One week is enough to <b>rank</b> the current roster, not to predict crashes.", s["bullet"])),
        ListItem(p("Phone orientation is stable enough that Z is approximately gravity (supported by mean Z about 1.0 g).", s["bullet"])),
        ListItem(p("P95 event lines mean 'unusual for this fleet', not physics constants.", s["bullet"])),
        ListItem(p("Tertile bands are the only classification justified by n = 30 and the absence of labelled accidents.", s["bullet"])),
        ListItem(p("Trips.Distance_KM is the exposure base (data dictionary: derived from per-minute speed).", s["bullet"])),
        ListItem(p("Score weights are stated assumptions, not estimated from a labelled loss function.", s["bullet"])),
    ], bulletType="1", leftIndent=12, start="1"))

    story.append(p("7. What this dataset cannot support", s["h1"]))
    story.append(p(
        "The following were not invented: fuel use, idling cost, engine temperature, brake-pad wear, "
        "crash probability, legal speeding against a posted limit (no speed-limit layer), or a 'safe' "
        "g-threshold copied from automotive literature. If a metric cannot be computed from the columns, "
        "it is omitted rather than fabricated.",
        s["body"],
    ))

    story.append(p("8. Additional use cases supported by the same columns", s["h1"]))
    story.append(ListFlowable([
        ListItem(p("<b>Hub workload</b> - trip counts and kilometres by Home_Hub / start coordinates.", s["bullet"])),
        ListItem(p("<b>Time-of-day risk</b> - Start_Time plus overspeed minutes (evening vs morning).", s["bullet"])),
        ListItem(p("<b>Rider-bike rotation</b> - 44 driver-vehicle pairs this week; V23 already has four riders, which helps isolate the bike.", s["bullet"])),
        ListItem(p("<b>Service scheduling</b> - rank days-since-service times odometer without IMU.", s["bullet"])),
        ListItem(p("<b>Route roughness map</b> - latitude/longitude of vertical-bump minutes (pothole heatmap).", s["bullet"])),
        ListItem(p("<b>Onboarding quality</b> - License_Experience_Years vs risk rank (exploratory only; not causal).", s["bullet"])),
        ListItem(p("<b>Coaching prototype</b> - the same event flags, if sampling later exceeds one sample per minute.", s["bullet"])),
    ], bulletType="1", leftIndent=12, start="1"))

    story.append(p("9. Reproducibility", s["h1"]))
    story.append(p(
        "From the repository root: <b>python -m pip install -r requirements.txt</b> then "
        "<b>python src/pipeline.py</b>. The script validates joins, derives P95 thresholds from this week's "
        "moving minutes, writes outputs/*.csv (including kpi_dictionary.csv with column / formula / why / "
        "threshold for every KPI) and rebuilds the HTML dashboards. Interactive dashboards: "
        f"<link href='{REPO}'>{REPO}</link>.",
        s["body"],
    ))
    story.append(p(
        "Static dashboard images for reviewers who cannot open HTML are in submission/dashboard_images/. "
        "They show the same 30 drivers, 30 vehicles, scores and colour bands as the HTML files.",
        s["body"],
    ))
    story.append(Spacer(1, 6 * mm))
    story.append(p(
        "End of report. All numbers above are computed from VEXAR_Fleet_Dataset_CANDIDATE_VERSION.xlsx.",
        s["caption"],
    ))

    doc.build(story, onFirstPage=cover_header_footer, onLaterPages=header_footer)
    return pdf_path


def main() -> None:
    drv = pd.read_csv(OUT / "driver_scores.csv")
    veh = pd.read_csv(OUT / "vehicle_scores.csv")
    images = save_dashboard_images(drv, veh)
    pdf = build_pdf(drv, veh, images)
    readme = PACK / "README_FOR_REVIEWERS.txt"
    readme.write_text(
        "VexarDrive intern assignment - Google Form pack\n"
        "==============================================\n\n"
        "1) Technical Report\n"
        "   VexarDrive_Technical_Report.pdf\n\n"
        "2) Dashboard images (HTML dashboards are in the GitHub repo; these PNGs are for reviewers who need pictures)\n"
        "   dashboard_images/01_driver_behaviour_dashboard.png\n"
        "   dashboard_images/02_vehicle_health_dashboard.png\n\n"
        f"Code and interactive HTML: {REPO}\n",
        encoding="utf-8",
    )
    print("Wrote", pdf)
    print("Wrote", images["driver"])
    print("Wrote", images["vehicle"])


if __name__ == "__main__":
    main()
