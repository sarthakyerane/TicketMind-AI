<div align="center">

# 🧠 TicketMind AI

### AI-Powered Customer Support Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Groq](https://img.shields.io/badge/LLM-Groq%20%7C%20Llama%203.3-F54E42?style=for-the-badge)](https://groq.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

*Ask questions about your support tickets in plain English. Detect anomalies automatically. Explore data visually — all from a single command.*

[🚀 Quick Start](#-quick-start) · [📡 API Docs](#-rest-api-reference) · [💬 Example Queries](#-example-queries) · [🏗 Architecture](#-architecture) · [⚠️ Known Limitations](#️-known-limitations)

---

</div>

## 📌 What is TicketMind AI?

TicketMind AI is a full-stack AI system built for the **DOTMappers AI Intern Assessment**. It ingests a CSV/Excel customer support ticket dataset and exposes two interfaces:

- **REST API** (FastAPI) — for programmatic access, integration, and automation
- **Interactive UI** (Streamlit) — for humans to explore, query, and analyze

Under the hood, it uses **Groq's free Llama 3.3 70B** model to understand natural language questions and convert them to SQL, then executes those queries against an **in-memory SQLite** database, and returns clear, human-readable answers. Anomaly detection uses statistical methods (IQR + Z-score) with an LLM-generated executive summary.

---

## ✨ Features

| Feature | Details |
|---|---|
| 🗣️ **Natural Language Queries** | Ask anything in plain English — AI translates it to SQL and explains the result |
| 🚨 **Anomaly Detection** | 5 statistical detectors (IQR + Z-score) with AI-generated executive summaries |
| 📊 **Rich Dashboard** | KPIs, priority charts, monthly trends, SLA breach analysis |
| 👤 **Agent Analytics** | Per-agent performance leaderboard, ratings, resolution rates |
| 🔍 **SQL Explorer** | Run raw SQLite queries with preset templates and CSV export |
| 📁 **Multi-format Ingestion** | Supports both `.csv` and `.xlsx` — auto-detected at startup |
| 🔁 **Retry + Rate Limiting** | Exponential backoff on Groq API calls; graceful 429 handling |
| 🛡️ **SQL Safety Guard** | Only `SELECT` queries allowed — prevents any data mutation |
| 🐳 **One-command Launch** | `docker-compose up --build` starts everything |
| 💰 **Zero Cost** | Groq free tier + Python built-in SQLite — no paid services |

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT LAYER                              │
│              data/support_tickets.csv  /  .xlsx                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DataIngestion                                 │
│  • Loads CSV or Excel (auto-detected)                           │
│  • Cleans & normalises columns                                  │
│  • Pushes DataFrame into in-memory SQLite (tickets_tbl)         │
│  • Adds derived columns: is_unresolved, created_month, etc.     │
└──────┬─────────────────────┬──────────────────────┬────────────┘
       │                     │                      │
       ▼                     ▼                      ▼
┌─────────────┐   ┌──────────────────┐   ┌──────────────────────┐
│ NLQuery     │   │ AnomalyDetector  │   │ Analytics            │
│ Engine      │   │                  │   │                      │
│             │   │ • slow_resolution│   │ • Agent leaderboard  │
│ Question    │   │   (IQR ×2.0)     │   │ • Tickets by category│
│   ↓         │   │ • overdue_high   │   │ • Priority breakdown │
│ Groq LLM   │   │   _priority       │   │ • Monthly trends     │
│ (temp=0.1) │   │   (>24 hrs)       │   │ • SLA breach rates   │
│   ↓         │   │ • critical       │   │ • Resolution stats   │
│ SQLite SQL  │   │   _unresolved     │   │ • Top/worst agents   │
│   ↓         │   │ • slow_response  │   └──────────────────────┘
│ Execute     │   │   (IQR ×2.5)     │
│   ↓         │   │ • low_rated      │
│ Groq LLM   │   │   _agents (Z ×1.5│
│ (temp=0.3) │   │                  │
│   ↓         │   │ + Groq LLM       │
│ NL Answer   │   │   Executive      │
└─────────────┘   │   Summary        │
                  └──────────────────┘
                           │
          ┌────────────────┴──────────────────┐
          │                                   │
          ▼                                   ▼
┌──────────────────────┐           ┌─────────────────────────┐
│  FastAPI REST API    │           │  Streamlit UI            │
│  :8000               │           │  :8501                   │
│                      │           │                          │
│  GET  /health        │           │  🏠 Dashboard            │
│  POST /query         │           │     KPIs, charts, trends │
│  GET  /anomalies     │           │  💬 NL Query             │
│  GET  /anomalies/:t  │           │     Chat + history       │
│  GET  /analytics     │           │  🚨 Anomalies            │
│  GET  /analytics/    │           │     Detection + summary  │
│        agents        │           │  📊 Agent Analytics      │
│  GET  /analytics/sla │           │     Leaderboard + detail │
│  POST /sql           │           │  🔍 SQL Explorer         │
└──────────────────────┘           │     Presets + export     │
                                   └─────────────────────────┘
```

### Technology Decisions

| Component | Choice | Reason |
|---|---|---|
| **LLM** | Groq · Llama 3.3 70B | Free tier, ~200 tok/s — fastest available. Excellent SQL generation. |
| **Database** | SQLite (Python built-in) | Zero installation, zero config. Perfect for 500-row analytical workloads. |
| **API** | FastAPI | Async, auto Swagger docs at `/docs`, Pydantic validation, industry standard. |
| **UI** | Streamlit | Fastest Python data-app framework. Rich widgets, zero frontend code. |
| **Data layer** | Pandas | Industry-standard DataFrame operations. Handles CSV + XLSX natively. |
| **Containerisation** | Docker + Compose | Single command to run everything. Zero environment issues for evaluator. |

---

## 🚀 Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- A free [Groq API key](https://console.groq.com) (takes 60 seconds to get)

### Step 1 — Clone the repository

```bash
git clone https://github.com/sarthakyerane/TicketMind-AI.git
cd TicketMind-AI
```

### Step 2 — Add your Groq API key

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder:

```env
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```


### Step 3 — Launch with Docker

```bash
docker-compose up --build
```

That's it. Both services start automatically:

| Service | URL | Description |
|---|---|---|
| 🖥️ **Streamlit UI** | http://localhost:8501 | Interactive dashboard |
| ⚡ **FastAPI API** | http://localhost:8000 | REST API |
| 📖 **Swagger Docs** | http://localhost:8000/docs | Auto-generated API docs |

---

### Alternative — Local Python (no Docker)

```bash
# Python 3.11+ required
pip install -r requirements.txt

# Terminal 1 — API
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — UI
streamlit run streamlit_app.py
```

---

## 📁 Project Structure

```
ticketmind-ai/
│
├── 🐳 Docker
│   ├── Dockerfile               # Python 3.11-slim, no unnecessary system deps
│   ├── docker-compose.yml       # Spins up api + ui services
│   └── start.sh                 # Boots both services in one container (fallback)
│
├── ⚡ API
│   └── main.py                  # FastAPI app — 8 endpoints, lifespan state
│
├── 🖥️ UI
│   └── streamlit_app.py         # 5-page Streamlit dashboard, dark glassmorphism theme
│
├── 🧩 Core Modules (app/)
│   ├── __init__.py
│   ├── data_ingestion.py        # CSV/XLSX → pandas → SQLite
│   ├── nl_query.py              # Groq LLM → SQL → execute → NL answer + retry
│   ├── anomaly_detector.py      # IQR/Z-score detectors + LLM executive summary
│   └── analytics.py            # Agent perf, SLA breach, trends, category stats
│
├── 📊 Data (data/)
│   ├── support_tickets.csv      # Primary dataset (500 tickets, Jan–Mar 2024)
│   └── support_tickets.xlsx     # Excel version of same dataset
│
├── 🧪 Tests (tests/)
│   └── test_core.py             # 31 unit tests across all core modules
│
└── 📋 Config
    ├── requirements.txt         # 8 Python packages (sqlite3 is built-in)
    ├── .env.example             # Environment variable template
    ├── .gitignore               # Excludes .env, __pycache__, etc.
    └── README.md                # This file
```

---

## 📡 REST API Reference

### `GET /health`
Health check — confirms the API is live and returns dataset statistics.

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "uptime_s": 42.3,
  "llm_model": "llama-3.3-70b-versatile",
  "dataset": {
    "total_tickets": 500,
    "source_file": "support_tickets.csv",
    "open_tickets": 127,
    "resolved_tickets": 285,
    "escalated_tickets": 88,
    "critical_tickets": 47,
    "avg_resolution_time_hrs": 11.43,
    "avg_customer_rating": 3.74
  }
}
```

---

### `POST /query`
Answer any natural language question about the ticket data.

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Which agent resolved the most tickets?"}'
```

```json
{
  "success": true,
  "question": "Which agent resolved the most tickets?",
  "sql": "SELECT agent_id, COUNT(*) AS resolved FROM tickets_tbl WHERE status = 'Resolved' GROUP BY agent_id ORDER BY resolved DESC LIMIT 1",
  "explanation": "Groups resolved tickets by agent and picks the one with the highest count.",
  "answer": "AGT-07 resolved the most tickets with 52 total resolved tickets, making them the top performer in the dataset.",
  "data": [{"agent_id": "AGT-07", "resolved": 52}],
  "row_count": 1
}
```

---

### `GET /anomalies`
Detect all anomalies with an optional AI executive summary.

```bash
curl "http://localhost:8000/anomalies?llm_summary=true"
```

```json
{
  "total_anomalies": 34,
  "counts_by_type": {
    "slow_resolution": 12,
    "overdue_high_priority": 8,
    "critical_unresolved": 7,
    "slow_response": 4,
    "low_rated_agents": 3
  },
  "severity_distribution": {
    "Critical": 15,
    "High": 12,
    "Medium": 7
  },
  "llm_summary": "The support system shows 34 anomalies requiring immediate attention...",
  "anomalies": { "...": "..." }
}
```

---

### `GET /anomalies/{type}`
Detect a specific anomaly type.

Valid types: `slow_resolution` · `overdue_high_priority` · `critical_unresolved` · `slow_response` · `low_rated_agents`

```bash
curl http://localhost:8000/anomalies/critical_unresolved
```

---

### `GET /analytics`
Full dashboard data — summary stats, agent performance, SLA analysis, trends.

```bash
curl http://localhost:8000/analytics
```

---

### `GET /analytics/agents`
Per-agent performance with top resolver, best rated, and worst rated.

```bash
curl http://localhost:8000/analytics/agents
```

---

### `GET /analytics/sla`
SLA breach rates by priority tier.

```bash
curl http://localhost:8000/analytics/sla
```

```json
{
  "Critical": { "sla_hrs": 4,  "total_resolved": 21, "breached": 14, "breach_rate_pct": 66.7 },
  "High":     { "sla_hrs": 12, "total_resolved": 89, "breached": 31, "breach_rate_pct": 34.8 },
  "Medium":   { "sla_hrs": 24, "total_resolved": 112,"breached": 18, "breach_rate_pct": 16.1 },
  "Low":      { "sla_hrs": 72, "total_resolved": 63, "breached":  4, "breach_rate_pct":  6.3 }
}
```

---

### `POST /sql` *(dev helper)*
Execute raw SQLite queries directly against `tickets_tbl`.

```bash
curl -X POST http://localhost:8000/sql \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT category, COUNT(*) as total FROM tickets_tbl GROUP BY category"}'
```

---

## 💬 Example Queries

These are the assessment's sample queries and how TicketMind AI handles them:

| Question | What the system does |
|---|---|
| *"How many tickets are currently open?"* | Counts `status = 'Open'` rows |
| *"Which agent resolved the most tickets this month?"* | Groups by `agent_id` on resolved tickets, orders DESC |
| *"Show me all Critical tickets not resolved within 12 hours"* | Filters `priority = 'Critical' AND resolution_time_hrs > 12` |
| *"What is the average customer rating for Technical tickets?"* | `AVG(customer_rating)` where `category = 'Technical'` |
| *"Are there any anomalies in resolution times?"* | Runs IQR detector on `resolution_time_hrs`, returns outliers |
| *"Which agent has the lowest average customer rating?"* | Groups by agent, sorts ASC on avg rating |
| *"How many high priority tickets are unresolved?"* | Filters `priority = 'High' AND is_unresolved = 1` |

---

## 🚨 Anomaly Detection Logic

TicketMind AI runs 5 independent anomaly detectors on every request:

### 1. Slow Resolution (`slow_resolution`)
- **Method:** IQR with 2.0× multiplier on `resolution_time_hrs`
- **Flags:** Tickets whose resolution time exceeds the upper IQR fence
- **Severity:** `High` if priority is Critical/High, else `Medium`

### 2. Overdue High Priority (`overdue_high_priority`)
- **Method:** Time threshold (default: 24 hours)
- **Flags:** High or Critical tickets still Open/Escalated past the threshold
- **Severity:** `Critical` for Critical priority, `High` for High priority

### 3. Critical Unresolved (`critical_unresolved`)
- **Method:** Direct status filter
- **Flags:** Any ticket where `priority = 'Critical'` and `status != 'Resolved'`
- **Severity:** Always `Critical`

### 4. Slow Response (`slow_response`)
- **Method:** IQR with 2.5× multiplier on `response_time_hrs`
- **Flags:** Tickets with abnormally long first-response times
- **Severity:** `High` for Critical/High priority tickets, else `Low`

### 5. Low Rated Agents (`low_rated_agents`)
- **Method:** Z-score with 1.5σ threshold on per-agent average ratings
- **Flags:** Agents statistically below the mean (minimum 5 rated tickets)
- **Severity:** `Medium`

All anomalies are followed by a **Groq LLM executive summary** with actionable recommendations.

---

## 📊 Dataset

| Property | Value |
|---|---|
| File | `data/support_tickets.csv` + `data/support_tickets.xlsx` |
| Rows | 500 tickets |
| Date range | January 2024 – March 2024 |
| Agents | AGT-01 through AGT-12 |
| Categories | Billing, Technical, General |
| Priorities | Low, Medium, High, Critical |
| Statuses | Open, Resolved, Escalated |
| Null columns | `resolution_time_hrs`, `customer_rating` (null for unresolved tickets) |

---

## 🧪 Running Tests

```bash
pip install pytest
pytest tests/ -v
```

**31 tests** covering:
- `DataIngestion` — CSV loading, SQLite registration, schema validation, derived columns (11 tests)
- `Analytics` — Agent performance, SLA breach, category breakdowns, trend data (11 tests)
- `AnomalyDetector` — All 5 detectors, severity values, edge cases, type validation (9 tests)

---

## ⚠️ Known Limitations

1. **Static dataset** — Data is loaded once at startup into memory. There is no live ticket ingestion endpoint in v1.

2. **"Now" approximation** — Anomaly detectors that check ticket age use the dataset's latest `created_at` date as the current time reference (since the dataset ends in March 2024). In production this would use `datetime.now()`.

3. **LLM hallucination** — The LLM may occasionally generate syntactically incorrect SQLite SQL (e.g., using `date_trunc()` which is DuckDB-only). The API returns a clear error with the generated SQL for debugging. This is mitigated by a strongly constrained system prompt and a SELECT-only safety guard.

4. **Groq rate limits** — The free tier allows 6,000 tokens/minute. Rapid-fire queries may trigger a 429 error. TicketMind AI handles this automatically with exponential backoff (up to 3 retries).

5. **Single file input** — Merging multiple CSVs or Excel files requires manual pre-processing before startup.

6. **No authentication** — The API has no auth layer. The `/sql` dev endpoint is open. Not intended for public deployment without adding an API key or OAuth layer.

---

## 🛠 Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | ✅ Yes | — | Your Groq API key from [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL` | ❌ No | `llama-3.3-70b-versatile` | Groq model to use. `llama-3.1-8b-instant` is faster but less accurate. |

---

## 📦 Dependencies

```
fastapi          — REST API framework
uvicorn          — ASGI server for FastAPI
streamlit        — Interactive web UI
groq             — Groq LLM client (Llama 3.3 70B)
pandas           — Data manipulation and CSV/Excel loading
numpy            — Statistical computations (IQR, Z-score)
openpyxl         — Excel (.xlsx) file reading
python-dotenv    — .env file loading
pydantic         — Request/response data validation
sqlite3          — In-memory SQL database (Python built-in, no install needed)
```

---

<div align="center">

**TicketMind AI** · Built with ❤️ using FastAPI, Streamlit, Groq & SQLite

</div>
