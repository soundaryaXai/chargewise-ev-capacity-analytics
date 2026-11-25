
# ChargeWise | EV Charging Capacity Analytics

An empirical analytics dashboard for evaluating workplace EV charging utilization, capacity requirements, blocking risk, and hypothetical post-charge dwell policies using ACN-Data.

<p align="center">
  <strong>Data-driven capacity analysis | Session replay | Queueing benchmarks | Policy sensitivity | Bootstrap uncertainty</strong>
</p>

---

## Overview

ChargeWise investigates how reducing the number of available EV charging ports affects service availability under observed workplace charging patterns.

The project combines empirical occupancy reconstruction, capacity-pressure screening, Erlang-B analytical estimates, chronological session replay, hypothetical dwell-cap scenarios, and block-bootstrap uncertainty analysis.

The objective is to evaluate capacity requirements under observed session patterns while distinguishing empirical utilization from model-estimated blocking and hypothetical policy effects.

## Research question

**How does reducing available charging-port capacity affect service availability under observed workplace charging patterns, and how sensitive are the results to post-charge dwell assumptions and arrival patterns?**

### Analytical objectives

- Characterize charging utilization and occupancy patterns.
- Identify historically high-pressure periods.
- Evaluate capacity requirements under reduced-port scenarios.
- Compare chronological session replay against Erlang-B estimates.
- Assess hypothetical post-charge dwell-cap scenarios.
- Quantify uncertainty in selected capacity and policy outcomes using weekly block bootstrap resampling.

---

## Data source

The project uses [ACN-Data](https://ev.caltech.edu/dataset), a real-world electric vehicle charging dataset made available by the California Institute of Technology through its Adaptive Charging Network research.

The dataset contains charging-session records, including connection time, disconnection time, charging completion, energy delivered, station identifiers, and user-input information where available.

### Site coverage

| Site | Extracted sessions | Observed station IDs |
|---|---:|---:|
| Caltech | 31,424 | 55 |
| JPL | 33,638 | 52 |
| Office 1 | 1,683 | 8 |
| **Total** | **66,745** | — |

Caltech and JPL form the primary capacity-analysis sites. Office 1 is used mainly for descriptive comparisons.

### Data quality and exclusions

- Core timestamp, interval-order and identifier checks were performed.
- Station-level overlap anomalies were investigated.
- Two conflicting JPL records were identified at the same station, parking space, connection time and charging-completion time, with different disconnection and energy-delivery values.
- Both conflicting JPL records are excluded from the primary replay analysis.
- Caltech contains an additional station identifier with 1,130 sessions whose equipment classification is unresolved. These sessions are excluded from the primary capacity comparison.
- Raw session data and API credentials are not included in the public repository.

---

## Feasibility assessment and study scope

### Primary analysis: pre-disruption

| Site | Raw sessions | Eligible weeks |
|---|---:|---:|
| Caltech | 27,584 | 95 |
| JPL | 25,069 | 76 |

The pre-disruption period is the primary study regime because both sites meet the initial feasibility criteria and demonstrate meaningful historical utilization.

### Secondary analysis: recovery

| Site | Raw sessions | Eligible weeks |
|---|---:|---:|
| Caltech | 3,307 | 43 |
| JPL | 6,400 | 43 |

The JPL recovery count includes two conflicting records. The primary cleaned replay retains 6,398 recovery sessions.

Pre-disruption and recovery are analysed separately rather than pooled.

### Regime definitions

| Regime | Period | Analytical role |
|---|---|---|
| Pre-disruption | Through February 2020 | Primary |
| Transition | March 2020 | Excluded from primary comparisons |
| Disruption | April–October 2020 | Excluded from primary comparisons |
| Recovery | November 2020–September 2021 | Secondary |

---

## Capacity-pressure screening

Historical occupancy was reconstructed from connection to disconnection time.

A week was flagged when weekday business-hour peak occupancy reached at least 80% of the assumed site capacity.

- Business hours: weekdays, 07:00–19:00 local time.
- Pressure threshold: peak occupancy ≥80% of assumed capacity.
- Screening gate: at least 10% of eligible weeks with observed sessions meeting the pressure threshold.

### Pre-disruption findings

| Site | Assumed capacity | Eligible weeks | Pressure weeks | Pressure rate |
|---|---:|---:|---:|---:|
| Caltech | 54 | 95 | 20 | 21.05% |
| JPL | 50/52 | 76 | 74 | 97.37% |

JPL meets the pressure threshold under both the 50-port and 52-port assumptions.

These findings identify historically high observed utilization. They do not establish actual queues, rejected arrivals, waiting times, or unmet demand.

### Inventory limitations

- Caltech uses a provisional 54-port Level 2 capacity denominator.
- An additional station identifier with 1,130 sessions is excluded because its equipment type is unverified.
- JPL uses 52 as the primary historical observed station-count assumption and 50 as a sensitivity.
- The discrepancy between the 52 observed historical station identifiers and the currently published 50-EVSE inventory remains unresolved.

Capacity assumptions are not equivalent to independently verified engineering inventory.

---

## Occupancy and utilization analysis

Occupancy is reconstructed using:

\[
[connectionTime,\ disconnectTime)
\]

The interval includes both active charging and post-charge connected dwell.

### Historical occupancy summaries

| Site | Mean occupancy | P95 occupancy | Maximum occupancy |
|---|---:|---:|---:|
| Caltech | 5.98 | 28 | 51 |
| JPL | 8.69 | 51 | 52 |
| Office 1 | 0.50 | 3 | 8 |

These statistics describe reconstructed historical occupancy. Observed station identifiers and maximum occupancy are not independently verified commissioned capacity.

The dashboard explores:

- Occupancy distributions and temporal patterns.
- Hour-of-week utilization.
- Arrival patterns.
- Weekday versus weekend behaviour.
- Connected duration and charging duration.
- Post-charge dwell.
- Long-session duration sensitivity.
- Regime-specific occupancy.

---

## Capacity modelling

ChargeWise evaluates capacity using complementary analytical approaches.

### 1. Empirical capacity

Historical occupancy and weekly peak summaries provide descriptive capacity benchmarks.

These include:

- Maximum simultaneous occupancy.
- Weekly peak occupancy.
- Hour-of-week occupancy patterns.
- Empirical capacity summaries.

Empirical occupancy is not interpreted as a guaranteed service-level capacity.

### 2. Erlang-B benchmark

Erlang-B is used as an analytical loss-system benchmark.

The model assumes:

- Poisson arrivals.
- Independent service durations.
- A finite number of charging ports.
- No waiting queue.
- Blocked arrivals leave.

Offered load is represented as:

\[
A=\lambda E[S]
\]

The analytical blocking probability is compared against chronological session replay.

Erlang-B is a benchmark, not a claim that workplace arrivals satisfy its assumptions.

### 3. Chronological session replay

The replay evaluates reduced-port scenarios using observed session arrival and duration patterns.

The process:

1. Sort sessions chronologically by arrival.
2. Track available charging ports.
3. Accept an arrival when a port is available.
4. Block an arrival when all simulated ports are occupied.
5. Calculate blocking rates across capacity scenarios.

The replay uses observed connection and disconnection intervals.

### Replay assumptions

- Blocked drivers leave rather than wait.
- Arrival patterns and session durations remain unchanged.
- The simulation evaluates port availability.
- Electrical infrastructure constraints are not independently simulated.
- Actual denied arrivals are not available in ACN-Data and are therefore modelled, not observed.

---

## Hypothetical post-charge dwell scenarios

ChargeWise evaluates hypothetical 30-, 60- and 120-minute post-charge dwell caps.

For sessions with valid charging-completion timestamps:

\[
t_{new}=\min(t_{disconnect},t_{charging\ completion}+cap)
\]

Sessions without valid charging-completion timestamps are not modified by the dwell-cap rule.

### Scenarios

| Scenario | Hypothetical post-charge cap |
|---|---|
| Baseline | No cap |
| Policy scenario 1 | 30 minutes |
| Policy scenario 2 | 60 minutes |
| Policy scenario 3 | 120 minutes |

The analysis evaluates:

- Sessions affected by the cap.
- Connected hours removed.
- Blocking under the modified session intervals.
- Capacity requirements under the scenarios.
- Policy effects at a fixed baseline capacity.
- Sensitivity to different dwell assumptions.

### Interpretation

These are hypothetical policy scenarios, not observed interventions.

The dataset does not establish driver compliance, actual enforcement outcomes, or whether post-charge connection time represents purely idle behaviour.

---

## Bootstrap uncertainty analysis

Weekly moving-block bootstrap resampling is used to assess uncertainty in selected capacity and policy outcomes.

### Bootstrap configuration

| Parameter | Configuration |
|---|---|
| Replicates | 2,000 |
| Random seed | 42 |
| Block lengths | 1, 2 and 4 weeks |
| Confidence intervals | 95% |
| Resampling unit | Complete weeks |
| Stratification | Site and regime |

### Policy-effect evaluation

Policy effects are paired against baseline outcomes at a fixed baseline capacity selected using the full-sample baseline capacity analysis.

The analysis evaluates:

- Capacity reduction.
- Blocking-rate reduction.
- Confidence intervals.
- Block-length sensitivity.
- Site and regime differences.

### Uncertainty limitations

Bootstrap confidence intervals are conditional on the original chronological replay and its carry-in state.

They do not capture all uncertainty sources, including baseline capacity-selection uncertainty, model assumptions, changes in driver behaviour, electrical constraints, or actual operational response to policies.

---

## Dashboard

The Streamlit dashboard is organized into five analytical pages.

| Page | Description |
|---|---|
| Overview | Site-level summary, occupancy, pressure screening, data-quality context |
| Utilization & Behaviour | Temporal utilization, occupancy patterns, arrival and duration analysis |
| Capacity & Queueing | Empirical capacity, Erlang-B and session replay comparison |
| Policy & Scenarios | Hypothetical dwell caps and bootstrap policy effects |
| Data & Methodology | Data definitions, exclusions, assumptions, validation and limitations |

---

## Repository structure

```text
chargewise-ev-capacity-analytics/
├── app.py
├── requirements.txt
├── README.md
├── assets/
│   └── styles.css
├── components/
│   └── sidebar.py
├── pages/
│   ├── 1_Overview.py
│   ├── 2_Utilization_and_Behaviour.py
│   ├── 3_Capacity_and_Queueing.py
│   ├── 4_Policy_and_Scenarios.py
│   └── 5_Data_and_Methodology.py
├── scripts/
│   ├── audit_acndata.py
│   ├── download_acndata.py
│   ├── audit_downloaded_data.py
│   ├── reconstruct_occupancy.py
│   ├── audit_station_inventory.py
│   ├── audit_regime_feasibility.py
│   ├── audit_capacity_pressure.py
│   ├── build_exploratory_eda.py
│   ├── audit_duration_sensitivity.py
│   ├── summarize_empirical_capacity.py
│   ├── build_erlang_b_baseline.py
│   ├── build_session_replay.py
│   ├── build_dwell_scenarios.py
│   └── bootstrap_capacity_uncertainty.py
├── data/
│   └── .gitkeep
└── utils/
```

Raw data and generated processed datasets are excluded from the repository.

---

## Reproducibility

### Requirements

- Python
- Git
- ACN-Data API access for data extraction
- Python dependencies listed in `requirements.txt`

### Installation

Clone the repository:

```bash
git clone https://github.com/soundaryaXai/chargewise-ev-capacity-analytics.git
cd chargewise-ev-capacity-analytics
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Data extraction

Configure your ACN-Data access token locally using the project’s Streamlit secrets configuration.

Do not commit API credentials or raw dataset files.

Run the extraction script:

```powershell
python scripts/download_acndata.py
```

### Rebuild analytical outputs

The scripts in `scripts/` perform the audit, occupancy reconstruction, exploratory analysis, empirical capacity summaries, queueing benchmark, replay, dwell scenarios and bootstrap analysis.

Run the relevant scripts in the analysis workflow order documented in the repository.

### Run the dashboard

```powershell
streamlit run app.py
```

---

## Limitations

- ACN-Data records sessions that obtained a charging port; actual rejected arrivals and unmet demand are not directly observed.
- Blocking outcomes are modelled rather than empirically observed.
- Historical station identifiers may not represent independently verified commissioned capacity.
- The JPL historical inventory discrepancy remains unresolved.
- Caltech equipment classification requires a provisional capacity assumption.
- Dwell scenarios are hypothetical.
- Charging-completion time may be affected by charging-system behaviour and adaptive scheduling.
- Electrical load, transformer constraints, energy-management policies and feeder-level constraints are not independently modelled.
- The analysis primarily concerns workplace/campus charging environments.
- Results should not automatically be generalized to public fast-charging environments.
- Bootstrap uncertainty does not encompass all model, data or capacity-selection uncertainty.

---

## Acknowledgements

Dataset: [ACN-Data](https://ev.caltech.edu/dataset), California Institute of Technology.

ACN-Data is made available through the collaboration supporting Adaptive Charging Networks.

Please consult the official dataset documentation and applicable terms before using or redistributing data.

---

## Project status

The analytical pipeline and five-page dashboard have been integrated using derived ACN-Data results.

The next project phase is deployment, dashboard presentation refinement, and portfolio documentation.
