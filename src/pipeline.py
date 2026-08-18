"""
VexarDrive fleet analysis — reproducible pipeline.

Reads the candidate Excel workbook, validates joins, derives empirical
thresholds from this week's telemetry (not generic industry cut-offs),
scores every driver and vehicle, and writes CSVs + HTML dashboards.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
DATA_XLSX = ROOT / "data" / "VEXAR_Fleet_Dataset_CANDIDATE_VERSION.xlsx"
SOURCE_XLSX = Path(r"C:\Users\NISHA KUMARI\Downloads\VEXAR_Fleet_Dataset_CANDIDATE_VERSION.xlsx")
OUT = ROOT / "outputs"
DASH = ROOT / "dashboards"

MOVING_SPEED_KMPH = 5.0  # exclude standstill / crawl; documented in README
CRUISE_LO, CRUISE_HI = 15.0, 35.0  # typical urban two-wheeler cruise in this fleet


def load_sheet(path: Path, sheet: str) -> pd.DataFrame:
    # Rows 0-1 are titles; row 2 is the column header (see data dictionary).
    return pd.read_excel(path, sheet_name=sheet, header=2)


def ensure_data() -> Path:
    DATA_XLSX.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_XLSX.exists():
        if not SOURCE_XLSX.exists():
            raise FileNotFoundError(f"Place the candidate workbook at {DATA_XLSX}")
        shutil.copy2(SOURCE_XLSX, DATA_XLSX)
    return DATA_XLSX


def validate(drivers: pd.DataFrame, vehicles: pd.DataFrame, trips: pd.DataFrame, tel: pd.DataFrame) -> dict:
    report = {
        "n_drivers": int(len(drivers)),
        "n_vehicles": int(len(vehicles)),
        "n_trips": int(len(trips)),
        "n_telemetry": int(len(tel)),
        "null_cells": {
            "drivers": int(drivers.isna().sum().sum()),
            "vehicles": int(vehicles.isna().sum().sum()),
            "trips": int(trips.isna().sum().sum()),
            "telemetry": int(tel.isna().sum().sum()),
        },
        "orphan_trip_drivers": sorted(set(trips["Driver_ID"]) - set(drivers["Driver_ID"])),
        "orphan_trip_vehicles": sorted(set(trips["Vehicle_ID"]) - set(vehicles["Vehicle_ID"])),
        "telemetry_trips_missing_from_trips": int(len(set(tel["Trip_ID"]) - set(trips["Trip_ID"]))),
        "trips_without_telemetry": int(len(set(trips["Trip_ID"]) - set(tel["Trip_ID"]))),
        "trips_per_driver_min": int(trips.groupby("Driver_ID").size().min()),
        "trips_per_driver_max": int(trips.groupby("Driver_ID").size().max()),
        "week_start": str(pd.to_datetime(trips["Trip_Date"]).min().date()),
        "week_end": str(pd.to_datetime(trips["Trip_Date"]).max().date()),
        "trips_duration_ne_telemetry_rows": int(
            (
                tel.groupby("Trip_ID").size().reindex(trips["Trip_ID"]).fillna(0).astype(int).to_numpy()
                != trips["Duration_Min"].astype(int).to_numpy()
            ).sum()
        ),
        "telemetry_driver_mismatch_vs_trips": int(
            tel.merge(trips[["Trip_ID", "Driver_ID"]], on="Trip_ID", suffixes=("_tel", "_trip"))
            .eval("Driver_ID_tel != Driver_ID_trip")
            .sum()
        ),
        "telemetry_vehicle_mismatch_vs_trips": int(
            tel.merge(trips[["Trip_ID", "Vehicle_ID"]], on="Trip_ID", suffixes=("_tel", "_trip"))
            .eval("Vehicle_ID_tel != Vehicle_ID_trip")
            .sum()
        ),
    }
    assert report["n_drivers"] == 30
    assert report["n_vehicles"] == 30
    assert report["n_trips"] == 450
    assert report["trips_per_driver_min"] == 15
    assert report["orphan_trip_drivers"] == []
    assert report["orphan_trip_vehicles"] == []
    assert report["telemetry_trips_missing_from_trips"] == 0
    assert report["trips_without_telemetry"] == 0
    assert report["null_cells"]["telemetry"] == 0
    assert report["trips_duration_ne_telemetry_rows"] == 0
    assert report["telemetry_driver_mismatch_vs_trips"] == 0
    assert report["telemetry_vehicle_mismatch_vs_trips"] == 0
    return report


def percentile_rank(series: pd.Series) -> pd.Series:
    """0-100 rank within the fleet. Higher = larger raw value."""
    return series.rank(method="average", pct=True) * 100.0


def band_from_tertile(score: float, p33: float, p67: float, labels: tuple[str, str, str]) -> str:
    if score <= p33:
        return labels[0]
    if score <= p67:
        return labels[1]
    return labels[2]


def load_all(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    drivers = load_sheet(path, "Drivers")
    vehicles = load_sheet(path, "Vehicles")
    trips = load_sheet(path, "Trips")
    tel = load_sheet(path, "Telemetry")
    trips["Trip_Date"] = pd.to_datetime(trips["Trip_Date"])
    vehicles["Last_Service_Date"] = pd.to_datetime(vehicles["Last_Service_Date"])
    vehicles["Registration_Date"] = pd.to_datetime(vehicles["Registration_Date"])
    drivers["Date_Joined_Fleet"] = pd.to_datetime(drivers["Date_Joined_Fleet"])
    tel["Timestamp"] = pd.to_datetime(tel["Timestamp"])
    return drivers, vehicles, trips, tel


def engineer_telemetry(tel: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    t = tel.sort_values(["Trip_ID", "Timestamp"]).copy()
    t["accel_mag_g"] = np.sqrt(t["Accel_X_g"] ** 2 + t["Accel_Y_g"] ** 2 + t["Accel_Z_g"] ** 2)
    t["horiz_accel_g"] = np.sqrt(t["Accel_X_g"] ** 2 + t["Accel_Y_g"] ** 2)
    t["gyro_mag_dps"] = np.sqrt(t["Gyro_X_dps"] ** 2 + t["Gyro_Y_dps"] ** 2 + t["Gyro_Z_dps"] ** 2)
    t["abs_gyro_z"] = t["Gyro_Z_dps"].abs()
    t["abs_z_dev"] = (t["Accel_Z_g"] - 1.0).abs()
    t["is_moving"] = t["Speed_kmph"] >= MOVING_SPEED_KMPH
    t["is_cruise"] = t["Speed_kmph"].between(CRUISE_LO, CRUISE_HI)

    moving = t.loc[t["is_moving"]]
    thr = {
        "moving_speed_kmph": MOVING_SPEED_KMPH,
        "overspeed_p95_kmph": float(moving["Speed_kmph"].quantile(0.95)),
        "severe_overspeed_p99_kmph": float(moving["Speed_kmph"].quantile(0.99)),
        "harsh_horiz_p95_g": float(moving["horiz_accel_g"].quantile(0.95)),
        "yaw_p95_dps": float(moving["abs_gyro_z"].quantile(0.95)),
        "z_dev_p95_g": float(moving["abs_z_dev"].quantile(0.95)),
        "n_moving_minutes": int(moving.shape[0]),
        "n_minutes": int(t.shape[0]),
        "why": (
            "Thresholds are empirical percentiles of THIS week's moving minutes "
            "(speed >= 5 km/h). Per-minute IMU is too coarse for physics-based "
            "g-cutoffs (e.g. 0.4g harsh brake), so tails of the observed "
            "distribution are used instead of textbook values."
        ),
    }
    t["evt_overspeed"] = t["is_moving"] & (t["Speed_kmph"] > thr["overspeed_p95_kmph"])
    t["evt_severe_overspeed"] = t["is_moving"] & (t["Speed_kmph"] > thr["severe_overspeed_p99_kmph"])
    t["evt_harsh_horiz"] = t["is_moving"] & (t["horiz_accel_g"] > thr["harsh_horiz_p95_g"])
    t["evt_yaw"] = t["is_moving"] & (t["abs_gyro_z"] > thr["yaw_p95_dps"])
    t["evt_z_bump"] = t["is_moving"] & (t["abs_z_dev"] > thr["z_dev_p95_g"])
    return t, thr


def trip_features(tel: pd.DataFrame, trips: pd.DataFrame) -> pd.DataFrame:
    g = tel.groupby("Trip_ID").agg(
        minutes=("Timestamp", "size"),
        moving_minutes=("is_moving", "sum"),
        overspeed_minutes=("evt_overspeed", "sum"),
        severe_overspeed_minutes=("evt_severe_overspeed", "sum"),
        harsh_horiz_minutes=("evt_harsh_horiz", "sum"),
        yaw_minutes=("evt_yaw", "sum"),
        z_bump_minutes=("evt_z_bump", "sum"),
        mean_horiz_g=("horiz_accel_g", "mean"),
        p95_speed=("Speed_kmph", lambda s: s.quantile(0.95)),
        cruise_vib=("accel_mag_g", lambda s: np.nan),  # filled below
    )
    cruise = (
        tel.loc[tel["is_cruise"]]
        .groupby("Trip_ID")
        .agg(
            cruise_minutes=("Timestamp", "size"),
            cruise_vib_mean=("accel_mag_g", lambda s: (s - 1.0).abs().mean()),
            cruise_gyro_mean=("gyro_mag_dps", "median"),
        )
    )
    feat = g.join(cruise)
    feat = trips.merge(feat, on="Trip_ID", how="left")
    km = feat["Distance_KM"].replace(0, np.nan)
    for col, src in [
        ("overspeed_per_100km", "overspeed_minutes"),
        ("harsh_horiz_per_100km", "harsh_horiz_minutes"),
        ("yaw_per_100km", "yaw_minutes"),
        ("z_bump_per_100km", "z_bump_minutes"),
        ("severe_overspeed_per_100km", "severe_overspeed_minutes"),
    ]:
        feat[col] = feat[src] / km * 100.0
    feat["overspeed_share"] = feat["overspeed_minutes"] / feat["moving_minutes"].replace(0, np.nan)
    return feat


def driver_scores(feat: pd.DataFrame, drivers: pd.DataFrame, thr: dict) -> pd.DataFrame:
    agg = feat.groupby("Driver_ID").agg(
        trips=("Trip_ID", "nunique"),
        km=("Distance_KM", "sum"),
        hours=("Duration_Min", "sum"),
        vehicles_used=("Vehicle_ID", "nunique"),
        avg_speed=("Avg_Speed_kmph", "mean"),
        mean_trip_max_speed=("Max_Speed_kmph", "mean"),
        overspeed_minutes=("overspeed_minutes", "sum"),
        moving_minutes=("moving_minutes", "sum"),
        harsh_horiz_minutes=("harsh_horiz_minutes", "sum"),
        yaw_minutes=("yaw_minutes", "sum"),
        z_bump_minutes=("z_bump_minutes", "sum"),
        overspeed_per_100km=("overspeed_per_100km", "mean"),
        harsh_horiz_per_100km=("harsh_horiz_per_100km", "mean"),
        yaw_per_100km=("yaw_per_100km", "mean"),
        severe_overspeed_per_100km=("severe_overspeed_per_100km", "mean"),
    )
    agg["overspeed_share"] = agg["overspeed_minutes"] / agg["moving_minutes"]
    # Percentile ranks so a driver is judged relative to this 30-driver week.
    agg["rk_overspeed"] = percentile_rank(agg["overspeed_per_100km"])
    agg["rk_harsh"] = percentile_rank(agg["harsh_horiz_per_100km"])
    agg["rk_yaw"] = percentile_rank(agg["yaw_per_100km"])
    agg["rk_max_speed"] = percentile_rank(agg["mean_trip_max_speed"])
    # Weights: speed exposure is the clearest safety signal in this dataset.
    weights = {"rk_overspeed": 0.30, "rk_harsh": 0.25, "rk_yaw": 0.25, "rk_max_speed": 0.20}
    agg["risk_score"] = sum(agg[k] * w for k, w in weights.items())
    p33, p67 = agg["risk_score"].quantile([1 / 3, 2 / 3])
    agg["risk_band"] = agg["risk_score"].apply(
        lambda s: band_from_tertile(s, p33, p67, ("Safe", "Moderate", "Risky"))
    )
    contrib = agg[["rk_overspeed", "rk_harsh", "rk_yaw", "rk_max_speed"]]
    labels = {
        "rk_overspeed": "overspeed minutes / 100 km",
        "rk_harsh": "harsh horizontal IMU spikes / 100 km",
        "rk_yaw": "high yaw-rate minutes / 100 km",
        "rk_max_speed": "mean trip max speed",
    }
    agg["top_contributor"] = contrib.idxmax(axis=1).map(labels)
    out = drivers.merge(agg.reset_index(), on="Driver_ID")
    out["p33_risk"] = float(p33)
    out["p67_risk"] = float(p67)
    out["why"] = out.apply(
        lambda r: (
            f"{r['Driver_Name']} ({r['Driver_ID']}) scored {r['risk_score']:.1f}/100 "
            f"({r['risk_band']}). Bands are fleet tertiles this week "
            f"(Safe ≤ {p33:.1f}, Risky > {p67:.1f}). "
            f"Largest contributor: {r['top_contributor']}. "
            f"Exposure: {r['km']:.1f} km, {int(r['trips'])} trips. "
            f"Overspeed (speed > {thr['overspeed_p95_kmph']:.1f} km/h) "
            f"{r['overspeed_per_100km']:.2f}/100 km; "
            f"harsh IMU {r['harsh_horiz_per_100km']:.2f}/100 km; "
            f"yaw events {r['yaw_per_100km']:.2f}/100 km; "
            f"mean trip max speed {r['mean_trip_max_speed']:.1f} km/h."
        ),
        axis=1,
    )
    return out.sort_values("risk_score", ascending=False)


def vehicle_scores(feat: pd.DataFrame, vehicles: pd.DataFrame, tel: pd.DataFrame, week_end: pd.Timestamp) -> pd.DataFrame:
    cruise = tel.loc[tel["is_cruise"]]
    vib = cruise.groupby("Vehicle_ID").agg(
        cruise_minutes=("Timestamp", "size"),
        cruise_vibration_g=("accel_mag_g", lambda s: (s - 1.0).abs().mean()),
        cruise_gyro_dps=("gyro_mag_dps", "median"),
        cruise_z_dev=("abs_z_dev", "mean"),
        cruise_bump_rate=("evt_z_bump", "mean"),
    )
    usage = feat.groupby("Vehicle_ID").agg(
        trips=("Trip_ID", "nunique"),
        km=("Distance_KM", "sum"),
        drivers=("Driver_ID", "nunique"),
        z_bump_per_100km=("z_bump_per_100km", "mean"),
    )
    v = vehicles.merge(usage.reset_index(), on="Vehicle_ID", how="left")
    v = v.merge(vib.reset_index(), on="Vehicle_ID", how="left")
    v["vehicle_age_years"] = week_end.year - v["Manufacture_Year"]
    v["days_since_service"] = (week_end - v["Last_Service_Date"]).dt.days
    v["rk_service"] = percentile_rank(v["days_since_service"])
    v["rk_odo"] = percentile_rank(v["Odometer_KM_Start_of_Week"])
    v["rk_age"] = percentile_rank(v["vehicle_age_years"])
    v["rk_vib"] = percentile_rank(v["cruise_vibration_g"])
    v["rk_gyro"] = percentile_rank(v["cruise_gyro_dps"])
    v["rk_bump"] = percentile_rank(v["z_bump_per_100km"].fillna(0))
    weights = {
        "rk_service": 0.22,
        "rk_odo": 0.18,
        "rk_age": 0.12,
        "rk_vib": 0.22,
        "rk_gyro": 0.12,
        "rk_bump": 0.14,
    }
    v["maintenance_risk"] = sum(v[k] * w for k, w in weights.items())
    v["health_score"] = 100.0 - v["maintenance_risk"]
    p33, p67 = v["maintenance_risk"].quantile([1 / 3, 2 / 3])
    v["health_band"] = v["maintenance_risk"].apply(
        lambda s: band_from_tertile(s, p33, p67, ("Healthy", "Needs Attention", "Maintenance Required"))
    )
    contrib = v[["rk_service", "rk_odo", "rk_age", "rk_vib", "rk_gyro", "rk_bump"]]
    labels = {
        "rk_service": "days since last service",
        "rk_odo": "odometer at week start",
        "rk_age": "vehicle age (years)",
        "rk_vib": "cruise |accel magnitude - 1 g|",
        "rk_gyro": "median cruise gyro magnitude",
        "rk_bump": "vertical bump events / 100 km",
    }
    v["top_contributor"] = contrib.idxmax(axis=1).map(labels)
    v["p33_risk"] = float(p33)
    v["p67_risk"] = float(p67)
    v["why"] = v.apply(
        lambda r: (
            f"{r['Vehicle_ID']} ({r['Make']} {r['Model']}, {int(r['Manufacture_Year'])}) "
            f"health {r['health_score']:.1f}/100 → {r['health_band']}. "
            f"Bands are fleet tertiles of maintenance risk "
            f"(Healthy if risk ≤ {p33:.1f}, Maintenance Required if risk > {p67:.1f}). "
            f"Largest contributor: {r['top_contributor']}. "
            f"Odometer {int(r['Odometer_KM_Start_of_Week'])} km; "
            f"{int(r['days_since_service'])} days since service "
            f"({r['Last_Service_Date'].date()}); "
            f"cruise vibration {r['cruise_vibration_g']:.4f} g; "
            f"cruise gyro {r['cruise_gyro_dps']:.2f} deg/s; "
            f"vertical bumps {r['z_bump_per_100km']:.2f}/100 km; "
            f"{int(r['drivers'])} driver(s) this week."
        ),
        axis=1,
    )
    return v.sort_values("maintenance_risk", ascending=False)


def kpi_rows(thr: dict, drivers: pd.DataFrame, vehicles: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "dashboard": "Driver Behaviour",
            "kpi": "Overspeed minutes / 100 km",
            "columns": "Telemetry.Speed_kmph, Trips.Distance_KM",
            "calculation": (
                f"Moving minute (speed ≥ {MOVING_SPEED_KMPH} km/h) with speed > "
                f"fleet moving P95 = {thr['overspeed_p95_kmph']:.2f} km/h. "
                "Count / trip km × 100, then mean across the driver's 15 trips."
            ),
            "why": "High speed is the only directly interpretable collision-energy signal in this workbook.",
            "threshold_source": "Empirical P95 of moving telemetry this week, not a legal speed limit.",
        },
        {
            "dashboard": "Driver Behaviour",
            "kpi": "Harsh horizontal IMU / 100 km",
            "columns": "Telemetry.Accel_X_g, Accel_Y_g",
            "calculation": (
                f"sqrt(X²+Y²) > moving P95 = {thr['harsh_horiz_p95_g']:.4f} g. "
                "Z is dominated by gravity (~1 g) so X/Y capture phone-plane jerks."
            ),
            "why": "Proxy for aggressive start/stop or swerve when 1-minute speed deltas are too smoothed.",
            "threshold_source": "Empirical P95 of moving minutes.",
        },
        {
            "dashboard": "Driver Behaviour",
            "kpi": "Yaw events / 100 km",
            "columns": "Telemetry.Gyro_Z_dps",
            "calculation": (
                f"|Gyro_Z| > moving P95 = {thr['yaw_p95_dps']:.2f} deg/s. "
                "Z has the heavy tail in this dataset (P99 ≫ P95)."
            ),
            "why": "Yaw-rate spikes indicate abrupt heading change / unstable riding on a two-wheeler.",
            "threshold_source": "Empirical P95 of |Gyro_Z| on moving minutes.",
        },
        {
            "dashboard": "Driver Behaviour",
            "kpi": "Mean trip max speed",
            "columns": "Trips.Max_Speed_kmph",
            "calculation": "Average of Max_Speed_kmph across the driver's trips.",
            "why": "Captures peak speeding even if it lasts under a full overspeed-minute share.",
            "threshold_source": "No hard cap; ranked vs the other 29 drivers.",
        },
        {
            "dashboard": "Driver Behaviour",
            "kpi": "Driver risk score (0-100)",
            "columns": "Percentile ranks of the four KPIs above",
            "calculation": (
                "0.30×overspeed rank + 0.25×harsh IMU rank + 0.25×yaw rank + "
                "0.20×max-speed rank. Rank = average percentile within the 30 drivers."
            ),
            "why": "Equal-ish weights with a slight emphasis on overspeed; ranks avoid arbitrary 0-1 scaling.",
            "threshold_source": f"Safe/Moderate/Risky = tertiles of this week's scores (cut {drivers['p33_risk'].iloc[0]:.1f} / {drivers['p67_risk'].iloc[0]:.1f}).",
        },
        {
            "dashboard": "Vehicle Health",
            "kpi": "Days since last service",
            "columns": "Vehicles.Last_Service_Date vs last trip date",
            "calculation": "(week_end − Last_Service_Date) in days, then fleet percentile rank.",
            "why": "Workbook has no prescribed service interval; lateness is relative to this fleet.",
            "threshold_source": "Relative rank, not a 90-day OEM rule.",
        },
        {
            "dashboard": "Vehicle Health",
            "kpi": "Odometer (week start)",
            "columns": "Vehicles.Odometer_KM_Start_of_Week",
            "calculation": "Percentile rank of odometer.",
            "why": "Wear accumulates with distance; this is the only mileage field.",
            "threshold_source": "Fleet rank.",
        },
        {
            "dashboard": "Vehicle Health",
            "kpi": "Vehicle age (years)",
            "columns": "Vehicles.Manufacture_Year",
            "calculation": "week_end.year − Manufacture_Year, then rank.",
            "why": "Older two-wheelers typically need more mechanical attention.",
            "threshold_source": "Fleet rank. Not a retirement age.",
        },
        {
            "dashboard": "Vehicle Health",
            "kpi": "Cruise gyro magnitude",
            "columns": "Telemetry Gyro_X/Y/Z_dps at 15-35 km/h",
            "calculation": (
                "Median sqrt(X^2+Y^2+Z^2) on cruise minutes, then fleet percentile rank. "
                "Median is used because gyro has a heavy tail."
            ),
            "why": "Persistent rotational shake at steady speed is a mechanical-instability clue.",
            "threshold_source": "Fleet rank of cruise-only minutes.",
        },
        {
            "dashboard": "Vehicle Health",
            "kpi": "Cruise vibration |a|−1g",
            "columns": "Telemetry Accel_X/Y/Z at 15–35 km/h",
            "calculation": (
                f"Mean |accel_mag − 1 g| on cruise minutes ({CRUISE_LO}-{CRUISE_HI} km/h), then rank. "
                "Cruise band reduces stop-go rider style vs mechanical shake."
            ),
            "why": "Persistent vibration at steady speed is a maintenance clue (engine/wheel/suspension).",
            "threshold_source": "Fleet rank of cruise-only minutes.",
        },
        {
            "dashboard": "Vehicle Health",
            "kpi": "Vertical bump rate / 100 km",
            "columns": "Telemetry.Accel_Z_g, Trips.Distance_KM",
            "calculation": (
                f"|Accel_Z − 1| > moving P95 = {thr['z_dev_p95_g']:.4f} g, exposure-adjusted."
            ),
            "why": "Z-axis spikes beyond gravity suggest potholes or worn suspension, not just throttle.",
            "threshold_source": "Empirical P95 of |Z−1|.",
        },
        {
            "dashboard": "Vehicle Health",
            "kpi": "Health score / maintenance risk",
            "columns": "Weighted percentile ranks listed above",
            "calculation": (
                "maintenance_risk = 0.22 service + 0.18 odo + 0.12 age + 0.22 vibration + "
                "0.12 cruise gyro + 0.14 bumps. health_score = 100 − risk."
            ),
            "why": "Mixes workshop metadata (independent of rider) with speed-controlled IMU.",
            "threshold_source": f"Healthy / Needs Attention / Maintenance Required = tertiles (cut {vehicles['p33_risk'].iloc[0]:.1f} / {vehicles['p67_risk'].iloc[0]:.1f}).",
        },
    ]
    return pd.DataFrame(rows)


def bar_risk(df: pd.DataFrame, id_col: str, name_col: str, score_col: str, band_col: str, title: str, y_title: str) -> go.Figure:
    color_map = {
        "Safe": "#2E7D32",
        "Moderate": "#EF6C00",
        "Risky": "#C62828",
        "Healthy": "#2E7D32",
        "Needs Attention": "#EF6C00",
        "Maintenance Required": "#C62828",
    }
    plot = df.sort_values(score_col)
    fig = go.Figure(
        go.Bar(
            x=plot[score_col],
            y=plot[id_col] + "  " + plot[name_col].astype(str),
            orientation="h",
            marker_color=[color_map[b] for b in plot[band_col]],
            customdata=np.stack([plot[band_col], plot["top_contributor"], plot["why"]], axis=1),
            hovertemplate=(
                "%{y}<br>Score %{x:.1f}<br>%{customdata[0]}"
                "<br>Largest contributor: %{customdata[1]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title=y_title,
        yaxis_title="",
        height=780,
        margin=dict(l=140, r=24, t=60, b=40),
        template="plotly_white",
        showlegend=False,
    )
    return fig


def dashboard_html(
    title: str,
    intro: str,
    figs: list[go.Figure],
    table_df: pd.DataFrame,
    path: Path,
    kpi_df: pd.DataFrame | None = None,
) -> None:
    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{title}</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#1a1a1a;max-width:1200px}",
        "h1{font-size:22px;margin:0 0 8px}h2{font-size:16px;margin:28px 0 8px}",
        "p,li{line-height:1.45;font-size:14px}table{border-collapse:collapse;width:100%;font-size:12px}",
        "th,td{border:1px solid #ddd;padding:6px 8px;vertical-align:top}th{background:#f4f4f4;text-align:left}",
        ".muted{color:#555;font-size:13px}.band-Safe,.band-Healthy{color:#2E7D32;font-weight:600}",
        ".band-Moderate,.band-Needs {color:#EF6C00;font-weight:600}",
        ".band-Risky,.band-Maintenance{color:#C62828;font-weight:600}</style></head><body>",
        f"<h1>{title}</h1>",
        f"<p class='muted'>{intro}</p>",
    ]
    if kpi_df is not None and len(kpi_df):
        parts.append("<h2>How every KPI on this page is calculated</h2>")
        parts.append(kpi_df.to_html(index=False, escape=True))
    for i, fig in enumerate(figs):
        parts.append(fig.to_html(full_html=False, include_plotlyjs=True if i == 0 else False))
    parts.append("<h2>Score explanation (every row)</h2>")
    parts.append(table_df.to_html(index=False, escape=True))
    parts.append("<p class='muted'>Source: VEXAR_Fleet_Dataset_CANDIDATE_VERSION · week 31 Jul-6 Aug 2026 · Bengaluru hubs.</p>")
    parts.append("</body></html>")
    path.write_text("\n".join(parts), encoding="utf-8")


def build_dashboards(drv: pd.DataFrame, veh: pd.DataFrame, kpis: pd.DataFrame) -> None:
    DASH.mkdir(parents=True, exist_ok=True)
    drv_plot = drv.copy()
    drv_plot["label"] = drv_plot["Driver_Name"]
    fig_d = bar_risk(
        drv_plot, "Driver_ID", "label", "risk_score", "risk_band",
        "Driver risk score (0 = safest in this week, 100 = riskiest vs peers)",
        "Risk score (fleet percentile mix)",
    )
    fig_dc = go.Figure()
    fig_dc.add_trace(go.Scatter(
        x=drv["overspeed_per_100km"], y=drv["harsh_horiz_per_100km"],
        mode="markers+text", text=drv["Driver_ID"], textposition="top center",
        marker=dict(
            size=10,
            color=drv["risk_score"],
            colorscale="YlOrRd",
            showscale=True,
            colorbar=dict(title="Risk"),
        ),
        hovertext=drv["Driver_Name"] + " · " + drv["risk_band"],
        hoverinfo="text+x+y",
    ))
    fig_dc.update_layout(
        title="Overspeed rate vs harsh IMU rate (each point is a driver)",
        xaxis_title="Overspeed minutes per 100 km",
        yaxis_title="Harsh horizontal IMU minutes per 100 km",
        height=480, template="plotly_white",
    )
    dtab = drv[[
        "Driver_ID", "Driver_Name", "Home_Hub", "risk_score", "risk_band", "top_contributor",
        "overspeed_per_100km", "harsh_horiz_per_100km", "yaw_per_100km",
        "mean_trip_max_speed", "km", "vehicles_used", "why",
    ]].round(2)
    dashboard_html(
        "VexarDrive — Driver Behaviour Dashboard",
        "Risk is relative to the 30 drivers in this week. Hover a bar for the band. "
        "The KPI table states columns, formula, and thresholds. Each driver row has a why sentence.",
        [fig_d, fig_dc],
        dtab,
        DASH / "driver_behaviour.html",
        kpi_df=kpis[kpis["dashboard"] == "Driver Behaviour"],
    )

    veh_plot = veh.copy()
    veh_plot["label"] = veh_plot["Make"] + " " + veh_plot["Model"]
    fig_v = bar_risk(
        veh_plot, "Vehicle_ID", "label", "maintenance_risk", "health_band",
        "Vehicle maintenance risk (0 = healthiest vs peers this week)",
        "Maintenance risk (fleet percentile mix)",
    )
    fig_vs = go.Figure()
    fig_vs.add_trace(go.Scatter(
        x=veh["days_since_service"], y=veh["cruise_vibration_g"],
        mode="markers+text", text=veh["Vehicle_ID"], textposition="top center",
        marker=dict(
            size=np.clip(veh["Odometer_KM_Start_of_Week"] / 2500, 6, 22),
            color=veh["maintenance_risk"],
            colorscale="YlOrRd",
            showscale=True,
            colorbar=dict(title="Risk"),
        ),
        hovertext=veh["Make"] + " " + veh["Model"] + " · " + veh["health_band"],
        hoverinfo="text+x+y",
    ))
    fig_vs.update_layout(
        title="Days since service vs cruise vibration (marker size ∝ odometer)",
        xaxis_title="Days since last service",
        yaxis_title="Mean |accel magnitude − 1 g| while cruising 15–35 km/h",
        height=480, template="plotly_white",
    )
    vtab = veh[[
        "Vehicle_ID", "Make", "Model", "Manufacture_Year", "health_score", "maintenance_risk",
        "health_band", "top_contributor", "Odometer_KM_Start_of_Week", "days_since_service",
        "cruise_vibration_g", "z_bump_per_100km", "drivers", "km", "why",
    ]].round(4)
    dashboard_html(
        "VexarDrive — Vehicle Health Status Dashboard",
        "Health mixes workshop fields (odometer, service date, age) with speed-controlled IMU. "
        "Driver style is partially confounded where a vehicle has only one rider.",
        [fig_v, fig_vs],
        vtab,
        DASH / "vehicle_health.html",
        kpi_df=kpis[kpis["dashboard"] == "Vehicle Health"],
    )

    index = """<!DOCTYPE html><html><head><meta charset='utf-8'><title>VexarDrive Intern Dashboards</title>
    <style>body{font-family:Segoe UI,Arial,sans-serif;margin:40px;max-width:800px;line-height:1.5}
    a{color:#0b57d0}</style></head><body>
    <h1>VexarDrive Data Scientist Intern — dashboards</h1>
    <p>Week of 31 Jul–6 Aug 2026. 30 drivers, 30 two-wheelers, 450 trips, 12,987 per-minute telemetry rows.</p>
    <ul>
      <li><a href="driver_behaviour.html">Driver Behaviour Dashboard</a></li>
      <li><a href="vehicle_health.html">Vehicle Health Status Dashboard</a></li>
    </ul>
    <p>Open <code>outputs/kpi_dictionary.csv</code> and <code>README.md</code> for how every number is calculated.</p>
    </body></html>"""
    (DASH / "index.html").write_text(index, encoding="utf-8")
    kpis.to_csv(OUT / "kpi_dictionary.csv", index=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = ensure_data()
    drivers, vehicles, trips, tel = load_all(path)
    qa = validate(drivers, vehicles, trips, tel)
    tel_f, thr = engineer_telemetry(tel)
    feat = trip_features(tel_f, trips)
    drv = driver_scores(feat, drivers, thr)
    week_end = pd.to_datetime(trips["Trip_Date"]).max()
    veh = vehicle_scores(feat, vehicles, tel_f, week_end)
    kpis = kpi_rows(thr, drv, veh)

    qa["thresholds"] = thr
    (OUT / "qa_report.json").write_text(json.dumps(qa, indent=2, default=str), encoding="utf-8")
    feat.to_csv(OUT / "trip_features.csv", index=False)
    drv.to_csv(OUT / "driver_scores.csv", index=False)
    veh.to_csv(OUT / "vehicle_scores.csv", index=False)
    tel_f.to_csv(OUT / "telemetry_with_events.csv", index=False)
    kpis.to_csv(OUT / "kpi_dictionary.csv", index=False)
    build_dashboards(drv, veh, kpis)
    print("QA", json.dumps({k: qa[k] for k in qa if k != "thresholds"}, default=str))
    print("Thresholds", json.dumps(thr, indent=2))
    print("Driver bands", drv["risk_band"].value_counts().to_dict())
    print("Vehicle bands", veh["health_band"].value_counts().to_dict())
    print("Top risky drivers")
    print(drv.head(5)[["Driver_ID", "Driver_Name", "risk_score", "risk_band", "top_contributor"]].to_string(index=False))
    print("Highest maintenance risk")
    print(veh.head(5)[["Vehicle_ID", "Make", "Model", "maintenance_risk", "health_band", "top_contributor"]].to_string(index=False))
    print("Wrote", OUT, "and", DASH)


if __name__ == "__main__":
    main()
