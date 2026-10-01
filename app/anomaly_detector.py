"""
Anomaly Detection Module.
Statistical methods (IQR / Z-score) on SQLite-backed data + Groq LLM for summaries.
"""

import json
import logging
import os
import time
from typing import Any

import numpy as np
import pandas as pd
from groq import Groq

from app.data_ingestion import DataIngestion

logger = logging.getLogger(__name__)


class AnomalyDetector:
    def __init__(self, ingestion: DataIngestion, groq_api_key: str | None = None):
        self.ingestion = ingestion
        api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self.client = Groq(api_key=api_key)
        self.model  = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # ------------------------------------------------------------------
    # Statistical helpers
    # ------------------------------------------------------------------

    def _iqr_upper_mask(self, series: pd.Series, multiplier: float = 2.0) -> pd.Series:
        """Boolean mask: values above the upper IQR fence."""
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        upper  = q3 + multiplier * (q3 - q1)
        return series > upper

    def _zscore_mask(self, series: pd.Series, threshold: float = 2.0) -> pd.Series:
        """Boolean mask: values whose Z-score exceeds the threshold."""
        std = series.std()
        if std == 0:
            return pd.Series(False, index=series.index)
        return ((series - series.mean()) / std).abs() > threshold

    # ------------------------------------------------------------------
    # Individual detectors
    # ------------------------------------------------------------------

    def detect_slow_resolution(self) -> list[dict]:
        """Tickets whose resolution time is an IQR outlier (high end)."""
        df = self.ingestion.df
        resolved = df[df["resolution_time_hrs"].notna()].copy()
        if len(resolved) < 10:
            return []
        mask   = self._iqr_upper_mask(resolved["resolution_time_hrs"])
        median = resolved["resolution_time_hrs"].median()
        out    = []
        for _, r in resolved[mask].iterrows():
            out.append({
                "anomaly_type":        "slow_resolution",
                "severity":            "High" if r["priority"] in ("Critical","High") else "Medium",
                "ticket_id":           r["ticket_id"],
                "category":            r["category"],
                "priority":            r["priority"],
                "status":              r["status"],
                "agent_id":            r["agent_id"],
                "resolution_time_hrs": round(float(r["resolution_time_hrs"]), 1),
                "customer_rating":     int(r["customer_rating"]) if pd.notna(r["customer_rating"]) else None,
                "issue_summary":       r["issue_summary"],
                "description": (
                    f"Resolution time {r['resolution_time_hrs']:.1f} hrs is far above "
                    f"the dataset median of {median:.1f} hrs."
                ),
            })
        return sorted(out, key=lambda x: -x["resolution_time_hrs"])

    def detect_overdue_high_priority(self, threshold_hrs: float = 24.0) -> list[dict]:
        """High/Critical tickets still Open/Escalated beyond the time threshold."""
        df  = self.ingestion.df
        now = df["created_at"].max()          # dataset's latest date as "now"
        sub = df[
            df["status"].isin(["Open","Escalated"]) &
            df["priority"].isin(["High","Critical"])
        ].copy()
        sub["age_hrs"] = (now - pd.to_datetime(sub["created_at"])).dt.total_seconds() / 3600
        out = []
        for _, r in sub[sub["age_hrs"] > threshold_hrs].iterrows():
            out.append({
                "anomaly_type": "overdue_high_priority",
                "severity":     "Critical" if r["priority"] == "Critical" else "High",
                "ticket_id":    r["ticket_id"],
                "category":     r["category"],
                "priority":     r["priority"],
                "status":       r["status"],
                "agent_id":     r["agent_id"],
                "age_hrs":      round(float(r["age_hrs"]), 1),
                "issue_summary":r["issue_summary"],
                "description": (
                    f"{r['priority']} ticket unresolved for {r['age_hrs']:.0f} hrs "
                    f"(SLA threshold: {threshold_hrs} hrs)."
                ),
            })
        return sorted(out, key=lambda x: -x["age_hrs"])

    def detect_critical_unresolved(self) -> list[dict]:
        """Any Critical ticket that is not Resolved."""
        df  = self.ingestion.df
        sub = df[(df["priority"] == "Critical") & df["is_unresolved"].astype(bool)]
        out = []
        for _, r in sub.iterrows():
            out.append({
                "anomaly_type":       "critical_unresolved",
                "severity":           "Critical",
                "ticket_id":          r["ticket_id"],
                "category":           r["category"],
                "priority":           r["priority"],
                "status":             r["status"],
                "agent_id":           r["agent_id"],
                "response_time_hrs":  round(float(r["response_time_hrs"]), 1) if pd.notna(r["response_time_hrs"]) else None,
                "issue_summary":      r["issue_summary"],
                "description":        f"Critical ticket is '{r['status']}' — not yet resolved.",
            })
        return out

    def detect_slow_response(self) -> list[dict]:
        """Tickets with abnormally high first-response times."""
        df    = self.ingestion.df
        valid = df[df["response_time_hrs"].notna()].copy()
        if len(valid) < 10:
            return []
        mask   = self._iqr_upper_mask(valid["response_time_hrs"], multiplier=2.5)
        median = valid["response_time_hrs"].median()
        out    = []
        for _, r in valid[mask].iterrows():
            out.append({
                "anomaly_type":      "slow_response",
                "severity":          "High" if r["priority"] in ("Critical","High") else "Low",
                "ticket_id":         r["ticket_id"],
                "category":          r["category"],
                "priority":          r["priority"],
                "status":            r["status"],
                "agent_id":          r["agent_id"],
                "response_time_hrs": round(float(r["response_time_hrs"]), 1),
                "issue_summary":     r["issue_summary"],
                "description": (
                    f"Response time {r['response_time_hrs']:.1f} hrs far above "
                    f"median {median:.1f} hrs."
                ),
            })
        return sorted(out, key=lambda x: -x["response_time_hrs"])

    def detect_low_rated_agents(self, min_tickets: int = 5) -> list[dict]:
        """Agents whose average customer rating is a Z-score outlier (low end)."""
        df     = self.ingestion.df
        rated  = df[df["customer_rating"].notna()]
        stats  = rated.groupby("agent_id").agg(
            avg_rating=("customer_rating","mean"),
            ticket_count=("ticket_id","count"),
        ).reset_index()
        stats  = stats[stats["ticket_count"] >= min_tickets]
        if len(stats) < 3:
            return []
        mask        = self._zscore_mask(stats["avg_rating"], threshold=1.5)
        overall_avg = stats["avg_rating"].mean()
        out = []
        for _, r in stats[mask & (stats["avg_rating"] < overall_avg)].iterrows():
            out.append({
                "anomaly_type":     "low_rated_agent",
                "severity":         "Medium",
                "agent_id":         r["agent_id"],
                "avg_rating":       round(float(r["avg_rating"]), 2),
                "ticket_count":     int(r["ticket_count"]),
                "overall_avg":      round(float(overall_avg), 2),
                "description": (
                    f"Agent {r['agent_id']} avg rating {r['avg_rating']:.2f} is significantly "
                    f"below overall avg {overall_avg:.2f} across {r['ticket_count']} tickets."
                ),
            })
        return sorted(out, key=lambda x: x["avg_rating"])

    # ------------------------------------------------------------------
    # LLM summary
    # ------------------------------------------------------------------

    def _call_groq_with_retry(self, messages: list, temperature: float, max_tokens: int, max_retries: int = 3) -> str:
        """Groq call with exponential backoff on rate-limit errors."""
        for attempt in range(max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate_limit" in err_str.lower():
                    wait = 2 ** attempt
                    logger.warning(f"Groq rate limit. Retry in {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                elif attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    raise
        raise RuntimeError("Groq API failed after all retries.")

    def _llm_summary(self, all_anomalies: list[dict]) -> str:
        if not all_anomalies:
            return "No anomalies detected in the current dataset."
        sample = json.dumps(all_anomalies[:15], indent=2, default=str)
        prompt = (
            "You are a senior support operations analyst.\n"
            f"Total anomalies detected: {len(all_anomalies)}\n\n"
            f"Sample anomalies:\n{sample}\n\n"
            "Provide:\n"
            "1. Executive summary (2-3 sentences)\n"
            "2. Top 3 most critical issues needing immediate attention\n"
            "3. One specific action recommendation per critical issue\n\n"
            "Be concise and actionable."
        )
        raw = self._call_groq_with_retry(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=700,
        )
        return raw.strip()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def detect_all(self, include_llm_summary: bool = True) -> dict[str, Any]:
        logger.info("Running all anomaly detectors …")
        results = {
            "slow_resolution":       self.detect_slow_resolution(),
            "overdue_high_priority": self.detect_overdue_high_priority(),
            "critical_unresolved":   self.detect_critical_unresolved(),
            "slow_response":         self.detect_slow_response(),
            "low_rated_agents":      self.detect_low_rated_agents(),
        }
        flat = [a for items in results.values() for a in items]

        severity_dist: dict[str,int] = {}
        for a in flat:
            sev = a.get("severity","Unknown")
            severity_dist[sev] = severity_dist.get(sev, 0) + 1

        llm_summary = ""
        if include_llm_summary:
            try:
                llm_summary = self._llm_summary(flat)
            except Exception as e:
                logger.warning(f"LLM summary failed: {e}")
                llm_summary = f"LLM summary unavailable: {e}"

        return {
            "total_anomalies":      len(flat),
            "counts_by_type":       {k: len(v) for k, v in results.items()},
            "severity_distribution":severity_dist,
            "anomalies":            results,
            "all_anomalies_flat":   flat,
            "llm_summary":          llm_summary,
        }

    def detect_by_type(self, anomaly_type: str) -> list[dict]:
        mapping = {
            "slow_resolution":       self.detect_slow_resolution,
            "overdue_high_priority": self.detect_overdue_high_priority,
            "critical_unresolved":   self.detect_critical_unresolved,
            "slow_response":         self.detect_slow_response,
            "low_rated_agents":      self.detect_low_rated_agents,
        }
        if anomaly_type not in mapping:
            raise ValueError(f"Unknown type '{anomaly_type}'. Valid: {list(mapping)}")
        return mapping[anomaly_type]()
