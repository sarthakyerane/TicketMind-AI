"""
FastAPI REST API — Support Ticket AI System
Endpoints:
  GET  /health           — Health check + dataset summary
  POST /query            — Natural language query
  GET  /anomalies        — Detect all anomalies
  GET  /anomalies/{type} — Detect specific anomaly type
  GET  /analytics        — Full dashboard analytics
  GET  /analytics/agents — Agent performance table
  GET  /sql              — Raw SQL execution (dev helper)
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.analytics import Analytics
from app.anomaly_detector import AnomalyDetector
from app.data_ingestion import DataIngestion
from app.nl_query import NLQueryEngine

# ---------------------------------------------------------------------------
load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared state — loaded once at startup
# ---------------------------------------------------------------------------
state: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — loading dataset …")
    ingestion = DataIngestion()
    ingestion.load()

    groq_key = os.getenv("GROQ_API_KEY", "")
    state["ingestion"]  = ingestion
    state["analytics"]  = Analytics(ingestion)
    state["nl_engine"]  = NLQueryEngine(ingestion, groq_api_key=groq_key)
    state["detector"]   = AnomalyDetector(ingestion, groq_api_key=groq_key)
    state["start_time"] = time.time()
    logger.info("Startup complete ✓")
    yield
    logger.info("Shutting down …")


# ---------------------------------------------------------------------------
app = FastAPI(
    title="TicketMind AI — API",
    description=(
        "🧠 TicketMind AI — AI-powered REST API for querying, analysing, and detecting "
        "anomalies in customer support ticket data. Powered by Groq LLM + SQLite."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class QueryRequest(BaseModel):
    question: str
    model_config = {"json_schema_extra": {"example": {"question": "How many tickets are currently open?"}}}


class SQLRequest(BaseModel):
    sql: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
def health():
    """Health check — confirms API is live and returns dataset statistics."""
    uptime = round(time.time() - state.get("start_time", time.time()), 1)
    return {
        "status":    "ok",
        "uptime_s":  uptime,
        "dataset":   state["ingestion"].get_summary_stats(),
        "llm_model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
    }


@app.post("/query", tags=["NL Query"])
def nl_query(req: QueryRequest):
    """
    Answer a natural language question about the ticket data.

    Examples:
    - "How many tickets are currently open?"
    - "Which agent resolved the most tickets?"
    - "What is the average customer rating for Technical tickets?"
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    try:
        result = state["nl_engine"].query(req.question)
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/anomalies", tags=["Anomalies"])
def get_anomalies(
    llm_summary: bool = Query(True, description="Include LLM-generated executive summary"),
):
    """
    Detect all anomalies in the dataset:
    - Slow resolution times (IQR outliers)
    - Overdue high/critical priority tickets
    - Unresolved critical tickets
    - Slow response times
    - Low-rated agents (Z-score outliers)
    """
    try:
        return state["detector"].detect_all(include_llm_summary=llm_summary)
    except Exception as e:
        logger.error(f"Anomaly detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/anomalies/{anomaly_type}", tags=["Anomalies"])
def get_anomalies_by_type(anomaly_type: str):
    """
    Detect a specific anomaly type.

    Valid types: slow_resolution | overdue_high_priority | critical_unresolved |
                 slow_response | low_rated_agents
    """
    try:
        results = state["detector"].detect_by_type(anomaly_type)
        return {"anomaly_type": anomaly_type, "count": len(results), "results": results}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Anomaly error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics", tags=["Analytics"])
def get_analytics():
    """Full dashboard analytics — summary stats, trends, agent performance, SLA."""
    try:
        return state["analytics"].full_dashboard()
    except Exception as e:
        logger.error(f"Analytics error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/agents", tags=["Analytics"])
def get_agent_performance():
    """Per-agent performance: ticket count, resolution rate, avg rating, response time."""
    try:
        return {
            "agents":      state["analytics"].agent_performance(),
            "top_resolver":state["analytics"].top_resolver(),
            "best_agent":  state["analytics"].best_agent(),
            "worst_agent": state["analytics"].worst_agent(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/sla", tags=["Analytics"])
def get_sla_analysis():
    """SLA breach analysis by priority tier."""
    try:
        return state["analytics"].sla_breach_analysis()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sql", tags=["Dev"])
def run_sql(req: SQLRequest):
    """
    Execute raw SQL against the tickets_tbl (SQLite).
    For development and exploration only.
    """
    if not req.sql.strip():
        raise HTTPException(status_code=400, detail="SQL cannot be empty.")
    try:
        df = state["ingestion"].query_sql(req.sql)
        records = df.to_dict(orient="records")
        for row in records:
            for k, v in row.items():
                if v != v:  # NaN
                    row[k] = None
        return {"row_count": len(records), "data": records}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SQL error: {str(e)}")
