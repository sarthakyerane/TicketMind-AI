"""
Data ingestion module.
Loads support_tickets.csv or .xlsx into Pandas + SQLite (in-memory).
SQLite is built into Python — zero extra installation needed.
"""

import logging
import sqlite3
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_CSV  = DATA_DIR / "support_tickets.csv"
DEFAULT_XLSX = DATA_DIR / "support_tickets.xlsx"


class DataIngestion:
    def __init__(self, file_path: str | None = None):
        if file_path:
            self.file_path = Path(file_path)
        elif DEFAULT_CSV.exists():
            self.file_path = DEFAULT_CSV
        elif DEFAULT_XLSX.exists():
            self.file_path = DEFAULT_XLSX
        else:
            raise FileNotFoundError(f"No dataset found in {DATA_DIR}")

        self.df: pd.DataFrame | None = None
        self.con: sqlite3.Connection | None = None   # in-memory SQLite

    # ------------------------------------------------------------------
    # File loaders
    # ------------------------------------------------------------------

    def _load_raw(self) -> pd.DataFrame:
        suffix = self.file_path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(
                self.file_path,
                parse_dates=["created_at"],
                dtype={"ticket_id": str, "category": str, "priority": str,
                       "status": str, "agent_id": str, "issue_summary": str},
            )
        elif suffix in (".xlsx", ".xls"):
            xl = pd.ExcelFile(self.file_path)
            df = pd.read_excel(
                self.file_path, sheet_name=xl.sheet_names[0],
                parse_dates=["created_at"],
                dtype={"ticket_id": str, "category": str, "priority": str,
                       "status": str, "agent_id": str, "issue_summary": str},
            )
        else:
            raise ValueError(f"Unsupported format: {suffix}")
        return df

    def load(self) -> pd.DataFrame:
        """Load file → clean → push into in-memory SQLite."""
        logger.info(f"Loading {self.file_path.name}")
        df = self._load_raw()

        # Normalize column names
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # Coerce numerics
        for col in ("response_time_hrs", "resolution_time_hrs", "customer_rating"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Strip string whitespace
        for col in ("category", "priority", "status", "agent_id"):
            df[col] = df[col].str.strip()

        # Derived helper columns
        df["is_unresolved"] = df["status"].isin(["Open", "Escalated"]).astype(int)
        df["created_date"]  = pd.to_datetime(df["created_at"]).dt.date.astype(str)
        df["created_month"] = pd.to_datetime(df["created_at"]).dt.to_period("M").astype(str)

        self.df = df

        # ---- Push into in-memory SQLite --------------------------------
        self.con = sqlite3.connect(":memory:", check_same_thread=False)
        df.to_sql("tickets_tbl", self.con, if_exists="replace", index=False)
        logger.info(f"Loaded {len(df)} rows into SQLite (in-memory)")
        return df

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def query_sql(self, sql: str) -> pd.DataFrame:
        """Execute any SQL against the SQLite tickets_tbl and return a DataFrame."""
        if self.con is None:
            raise RuntimeError("Data not loaded. Call load() first.")
        try:
            return pd.read_sql_query(sql, self.con)
        except Exception as e:
            logger.error(f"SQL error: {e}\nQuery: {sql}")
            raise

    def get_schema_description(self) -> str:
        return """
Table name: tickets_tbl   (SQLite, in-memory)
Columns:
  - ticket_id            TEXT        Unique ticket identifier (e.g., TKT-001)
  - created_at           TEXT        Ticket creation timestamp (ISO format)
  - category             TEXT        'Billing' | 'Technical' | 'General'
  - priority             TEXT        'Low' | 'Medium' | 'High' | 'Critical'
  - status               TEXT        'Open' | 'Resolved' | 'Escalated'
  - response_time_hrs    REAL        Hours to first response (can be NULL)
  - resolution_time_hrs  REAL        Hours to resolution (NULL if unresolved)
  - agent_id             TEXT        Agent identifier e.g. AGT-04
  - customer_rating      INTEGER     Rating 1–5 (NULL if unresolved)
  - issue_summary        TEXT        Brief issue description
  - is_unresolved        INTEGER     1 if Open/Escalated, 0 if Resolved
  - created_date         TEXT        Date string e.g. '2024-01-03'
  - created_month        TEXT        Month string e.g. '2024-01'

Important SQLite notes:
  - Use strftime() for date functions, NOT date_trunc()
  - String comparisons are case-sensitive; use LOWER() if needed
  - NULL handling: use IS NULL / IS NOT NULL
  - Agents: AGT-01 through AGT-12
  - Date range: 2024-01-01 to 2024-03-30
  - Total rows: 500
""".strip()

    def get_summary_stats(self) -> dict:
        if self.df is None:
            return {}
        df = self.df
        return {
            "total_tickets":        len(df),
            "source_file":          self.file_path.name,
            "open_tickets":         int((df["status"] == "Open").sum()),
            "resolved_tickets":     int((df["status"] == "Resolved").sum()),
            "escalated_tickets":    int((df["status"] == "Escalated").sum()),
            "critical_tickets":     int((df["priority"] == "Critical").sum()),
            "high_priority_tickets":int((df["priority"] == "High").sum()),
            "avg_resolution_time_hrs": round(float(df["resolution_time_hrs"].mean()), 2),
            "avg_response_time_hrs":   round(float(df["response_time_hrs"].mean()), 2),
            "avg_customer_rating":     round(float(df["customer_rating"].mean()), 2),
            "unique_agents":           int(df["agent_id"].nunique()),
            "date_range": {
                "from": str(df["created_at"].min()),
                "to":   str(df["created_at"].max()),
            },
            "categories":             df["category"].value_counts().to_dict(),
            "priority_distribution":  df["priority"].value_counts().to_dict(),
            "status_distribution":    df["status"].value_counts().to_dict(),
        }
