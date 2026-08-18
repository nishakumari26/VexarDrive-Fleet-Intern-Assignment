# VexarDrive Data Scientist Intern Assignment

Python · Pandas · Plotly — intern assignment that scores **every driver** and **every vehicle** from one week of VexarDrive two-wheeler GPS + IMU telemetry, with a full explanation of each KPI, threshold, and band.

Two explainable dashboards from the candidate workbook `VEXAR_Fleet_Dataset_CANDIDATE_VERSION.xlsx`.

| | |
| --- | --- |
| Fleet week | 31 Jul 2026 – 6 Aug 2026 |
| Drivers / vehicles / trips | 30 / 30 / 450 (15 trips each driver) |
| Telemetry | 12,987 per-minute GPS + IMU rows |
| Geography | Bengaluru hubs (Rajajinagar, HSR, Bellandur, …) |
| Vehicle type | Two-wheeler (scooter/motorcycle) |

**Open the dashboards** (double-click):

1. [dashboards/index.html](dashboards/index.html)
2. [dashboards/driver_behaviour.html](dashboards/driver_behaviour.html)
3. [dashboards/vehicle_health.html](dashboards/vehicle_health.html)

Every KPI, threshold, and band is defined in [outputs/kpi_dictionary.csv](outputs/kpi_dictionary.csv) and below. Scores are **relative to this 30-unit week**, not a national safety standard.

## Reproduce

```bash
python -m pip install -r requirements.txt
python src/pipeline.py
```

The script copies the Excel file into `data/` if needed, validates joins, writes `outputs/*.csv`, and rebuilds the HTML dashboards.

## Data loading and validation

Sheets are read with `header=2` because rows 0–1 are titles (`Drivers (Master Data)`, blank, then column names).

Joins (as specified):

- `Telemetry.Trip_ID` → `Trips.Trip_ID`
- `Trips.Driver_ID` → `Drivers.Driver_ID`
- `Trips.Vehicle_ID` → `Vehicles.Vehicle_ID`

`Telemetry` already carries `Driver_ID` and `Vehicle_ID`; they were checked against `Trips`.

QA (`outputs/qa_report.json`):

- 0 null cells on all four tables
- 0 orphan trip keys
- every trip has telemetry; telemetry row count per trip equals `Duration_Min`
- telemetry `Driver_ID` / `Vehicle_ID` match the parent trip row
- 15 trips per driver

Data-quality notes (not used in scores):

- Two drivers share the name Kavya Pillai (`D07`, `D23`) — analysis keys on `Driver_ID`
- `Gender` sometimes disagrees with the given name; **gender is not an input to any score**

## Why thresholds are empirical

Phone IMU here is **one sample per minute**. A textbook harsh-brake cut-off (~0.4 g for ~1 s) cannot be applied honestly: a 60-second average hides the spike.

Observed moving-minute tails (speed ≥ 5 km/h, n = 11,891):

| Signal | P95 (event line) | P99 |
| --- | --- | --- |
| Speed | **42.4 km/h** | 52.1 km/h |
| Horizontal accel √(X²+Y²) | **0.460 g** | — |
| \|Gyro_Z\| | **5.01 deg/s** | ~39.7 deg/s (heavy tail) |
| \|Accel_Z − 1 g\| | **0.087 g** | — |

`Accel_Z` mean is 1.007 g (gravity on Z). `Accel_X`/`Accel_Y` are near 0. Correlation of 1-minute Δspeed with accel axes is ~0, so **speed-change is not used as a harsh-event detector**. Events are IMU/GPS tails, then exposure-adjusted per 100 km.

5 km/h is only an idle gate (below crawl). It is not a safety limit.

## Driver Behaviour Dashboard

### Metrics (per driver, mean of 15 trips unless noted)

| Metric | Columns | Calculation | Relevance |
| --- | --- | --- | --- |
| Overspeed min / 100 km | `Speed_kmph`, `Distance_KM` | Minutes with speed > 42.4 km/h, ÷ km × 100 | Only direct speed/energy signal |
| Harsh horizontal IMU / 100 km | `Accel_X_g`, `Accel_Y_g` | √(X²+Y²) > 0.460 g | Jerks in the phone plane |
| Yaw events / 100 km | `Gyro_Z_dps` | \|Z\| > 5.01 deg/s | Abrupt heading change on a 2W |
| Mean trip max speed | `Max_Speed_kmph` | Average of trip maxima | Peak speeding even if short |

### Risk score

Each metric is converted to a **percentile rank among the 30 drivers** (0–100).

```
risk_score = 0.30*overspeed_rank + 0.25*harsh_rank + 0.25*yaw_rank + 0.20*max_speed_rank
```

Weights put slightly more mass on overspeed (interpretable) and keep IMU components equal. They are assumptions; changing them reorders the middle of the pack more than the extremes.

### Bands

Tertiles of `risk_score` this week (10 / 10 / 10):

- **Safe** ≤ 37.0
- **Moderate** 37.0–64.3
- **Risky** > 64.3

These labels mean “safer / typical / riskier **than peers this week**”, not “legal / illegal”.

### How to read a driver

The dashboard table column `why` is a full sentence with the four rates, km, and the **largest contributing rank**. Example: D19 Senthil Pillai scores **95.0 (Risky)** because overspeed is 53.1 min/100 km (fleet-worst) vs safest drivers at ~0.

Highest risk this week: **D19, D14, D06, D03, D24**.  
Lowest: **D28, D09, D11, D22, D05**.

## Vehicle Health Status Dashboard

No OBD, DTCs, tyre pressure, or workshop job cards exist. Health is inferred from **master-data wear** plus **speed-controlled IMU**.

Cruise window **15–35 km/h** matches this fleet’s typical urban speed (trip avg ~24 km/h) and reduces stop–go riding style.

| Metric | Columns | Calculation | Relevance |
| --- | --- | --- | --- |
| Days since service | `Last_Service_Date` vs 6 Aug 2026 | Rank | No OEM interval in the file; lateness is relative |
| Odometer | `Odometer_KM_Start_of_Week` | Rank | Only mileage field |
| Age (years) | `Manufacture_Year` | 2026 − year, rank | Older bikes tend to need more shop time |
| Cruise vibration | Accel magnitude at 15–35 km/h | Mean \|mag − 1 g\|, rank | Shake at steady speed |
| Cruise gyro | Gyro X/Y/Z magnitude (median) | Rank of cruise minutes | Rotational shake at steady speed |
| Vertical bumps / 100 km | `Accel_Z_g` | \|Z−1\| > 0.087 g | Pothole / suspension proxy |

GPS is used as `Speed_kmph` (dictionary: instantaneous speed). Latitude/longitude are not in the health score because there is no planned route or road-quality layer; they are listed as a pothole-heatmap extra use case.

```
maintenance_risk = 0.22*service + 0.18*odo + 0.12*age + 0.22*vibration + 0.12*gyro + 0.14*bumps
health_score = 100 - maintenance_risk
```

Bands (tertiles of maintenance risk):

- **Healthy** if risk ≤ 36.0
- **Needs Attention** 36.0–65.4
- **Maintenance Required** if risk > 65.4

Priority shop list: **V02 (TVS Raider, 46,601 km, 92 days since service, health 4.8)**, then V12, V01, V23, V10.

**Confounding:** 19 vehicles have a single driver this week, so IMU can still mix rider style with machine. Mitigation: (1) service/odometer/age do not depend on riding style; (2) vibration is measured only while cruising; (3) V02’s rider D02 is only **Moderate** on behaviour while V02 is the worst health unit — that split is evidence the vehicle metrics are not a copy of the driver score.

## Assumptions

1. One week is enough to **rank** the current roster, not to predict crashes.
2. Phone orientation is stable enough that Z ≈ gravity (supported by mean Z ≈ 1.0 g).
3. P95 event lines are “unusual for this fleet”, not physics constants.
4. Tertile bands are the only classification justified by n = 30 (no labelled accidents).
5. Distance in `Trips.Distance_KM` is the exposure base (dictionary: derived from per-minute speed).

## What this dataset cannot support

Do not invent: fuel, idling cost, engine temperature, brake-pad wear, crash probability, legal speeding vs a posted limit (no speed-limit layer), or a “safe” g-threshold from automotive literature.

## Additional use cases the columns actually support

1. **Hub workload** — trip counts and km by `Home_Hub` / start coordinates.
2. **Time-of-day risk** — `Start_Time` + overspeed minutes (evening vs morning).
3. **Rider–bike rotation** — 44 driver–vehicle pairs; isolate a bike by putting two riders on it (already true for V23: 4 drivers).
4. **Service scheduling** — rank `days_since_service` × odometer without IMU.
5. **Route roughness map** — lat/lon of `evt_z_bump` minutes (pothole heatmap).
6. **Onboarding quality** — `License_Experience_Years` vs risk rank (exploratory only; do not treat as causal).
7. **Telematics product prototype** — same event flags as in-app coaching, if VexarDrive samples faster than 1/min later.

## Deliverable map

| Path | Role |
| --- | --- |
| `src/pipeline.py` | Load, validate, score, export |
| `outputs/driver_scores.csv` | One row per driver + `why` |
| `outputs/vehicle_scores.csv` | One row per vehicle + `why` |
| `outputs/trip_features.csv` | Trip-level events |
| `outputs/kpi_dictionary.csv` | Column / formula / why / threshold |
| `dashboards/*.html` | The two required dashboards |

Submission form (from the brief): https://forms.gle/qsaiteGEi9qDNQVS7
