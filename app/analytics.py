"""
Analytics module — pre-computed aggregations over the SQLite-backed DataFrame.
"""

import logging
import pandas as pd
from app.data_ingestion import DataIngestion

logger = logging.getLogger(__name__)


class Analytics:
    def __init__(self, ingestion: DataIngestion):
        self.ingestion = ingestion

    # ------------------------------------------------------------------
    # Agent analytics
    # ------------------------------------------------------------------

    def agent_performance(self) -> list[dict]:
        df = self.ingestion.df
        out = []
        for agent, grp in df.groupby("agent_id"):
            resolved  = (grp["status"] == "Resolved").sum()
            escalated = (grp["status"] == "Escalated").sum()
            open_     = (grp["status"] == "Open").sum()
            avg_r     = grp["customer_rating"].mean()
            avg_res   = grp["resolution_time_hrs"].mean()
            avg_resp  = grp["response_time_hrs"].mean()
            out.append({
                "agent_id":               agent,
                "total_tickets":          int(len(grp)),
                "resolved":               int(resolved),
                "escalated":              int(escalated),
                "open":                   int(open_),
                "resolution_rate_pct":    round(resolved / len(grp) * 100, 1),
                "avg_customer_rating":    round(float(avg_r), 2)   if pd.notna(avg_r)  else None,
                "avg_resolution_time_hrs":round(float(avg_res), 2) if pd.notna(avg_res) else None,
                "avg_response_time_hrs":  round(float(avg_resp), 2)if pd.notna(avg_resp) else None,
            })
        return sorted(out, key=lambda x: -x["total_tickets"])

    def top_resolver(self) -> dict:
        agents = self.agent_performance()
        return max(agents, key=lambda x: x["resolved"]) if agents else {}

    def best_agent(self) -> dict:
        rated = [a for a in self.agent_performance() if a["avg_customer_rating"] is not None]
        return max(rated, key=lambda x: (x["avg_customer_rating"], x["resolution_rate_pct"])) if rated else {}

    def worst_agent(self) -> dict:
        rated = [a for a in self.agent_performance()
                 if a["avg_customer_rating"] is not None and a["total_tickets"] >= 5]
        return min(rated, key=lambda x: (x["avg_customer_rating"], x["resolution_rate_pct"])) if rated else {}

    # ------------------------------------------------------------------
    # Ticket analytics
    # ------------------------------------------------------------------

    def tickets_by_category(self) -> list[dict]:
        df  = self.ingestion.df
        grp = df.groupby("category").agg(
            total            =("ticket_id","count"),
            resolved         =("status", lambda x: (x=="Resolved").sum()),
            avg_rating       =("customer_rating","mean"),
            avg_resolution_hrs=("resolution_time_hrs","mean"),
        ).reset_index()
        grp["resolution_rate_pct"] = (grp["resolved"] / grp["total"] * 100).round(1)
        grp["avg_rating"]          = grp["avg_rating"].round(2)
        grp["avg_resolution_hrs"]  = grp["avg_resolution_hrs"].round(2)
        return grp.to_dict(orient="records")

    def tickets_by_priority(self) -> list[dict]:
        df    = self.ingestion.df
        order = ["Critical","High","Medium","Low"]
        grp   = df.groupby("priority").agg(
            total            =("ticket_id","count"),
            resolved         =("status", lambda x: (x=="Resolved").sum()),
            open             =("status", lambda x: (x=="Open").sum()),
            escalated        =("status", lambda x: (x=="Escalated").sum()),
            avg_resolution_hrs=("resolution_time_hrs","mean"),
        ).reset_index()
        grp["resolution_rate_pct"] = (grp["resolved"] / grp["total"] * 100).round(1)
        grp["avg_resolution_hrs"]  = grp["avg_resolution_hrs"].round(2)
        grp["priority"]            = pd.Categorical(grp["priority"], categories=order, ordered=True)
        return grp.sort_values("priority").to_dict(orient="records")

    def monthly_trend(self) -> list[dict]:
        df  = self.ingestion.df
        grp = df.groupby("created_month").agg(
            total   =("ticket_id","count"),
            resolved=("status", lambda x: (x=="Resolved").sum()),
            open    =("status", lambda x: (x=="Open").sum()),
            critical=("priority", lambda x: (x=="Critical").sum()),
            avg_rating=("customer_rating","mean"),
        ).reset_index()
        grp["avg_rating"] = grp["avg_rating"].round(2)
        return grp.sort_values("created_month").to_dict(orient="records")

    def resolution_time_stats(self) -> dict:
        resolved = self.ingestion.df["resolution_time_hrs"].dropna()
        if len(resolved) == 0:
            return {}
        return {
            "count":  int(len(resolved)),
            "mean":   round(float(resolved.mean()), 2),
            "median": round(float(resolved.median()), 2),
            "std":    round(float(resolved.std()), 2),
            "min":    round(float(resolved.min()), 2),
            "max":    round(float(resolved.max()), 2),
            "p25":    round(float(resolved.quantile(0.25)), 2),
            "p75":    round(float(resolved.quantile(0.75)), 2),
            "p90":    round(float(resolved.quantile(0.90)), 2),
            "p95":    round(float(resolved.quantile(0.95)), 2),
        }

    def sla_breach_analysis(self) -> dict:
        """Checks resolved tickets against SLA thresholds by priority."""
        SLA = {"Critical": 4, "High": 12, "Medium": 24, "Low": 72}
        df  = self.ingestion.df
        resolved = df[df["resolution_time_hrs"].notna()].copy()
        out = {}
        for priority, hrs in SLA.items():
            sub     = resolved[resolved["priority"] == priority]
            if len(sub) == 0:
                continue
            breached = sub[sub["resolution_time_hrs"] > hrs]
            out[priority] = {
                "sla_hrs":         hrs,
                "total_resolved":  int(len(sub)),
                "breached":        int(len(breached)),
                "breach_rate_pct": round(len(breached) / len(sub) * 100, 1),
            }
        return out

    def critical_unresolved(self) -> list[dict]:
        df  = self.ingestion.df
        sub = df[(df["priority"] == "Critical") & df["is_unresolved"].astype(bool)].copy()
        sub["created_at"] = sub["created_at"].astype(str)
        cols = ["ticket_id","created_at","category","status","agent_id",
                "response_time_hrs","issue_summary"]
        return sub[cols].to_dict(orient="records")

    def full_dashboard(self) -> dict:
        return {
            "summary":                  self.ingestion.get_summary_stats(),
            "agent_performance":        self.agent_performance(),
            "tickets_by_category":      self.tickets_by_category(),
            "tickets_by_priority":      self.tickets_by_priority(),
            "monthly_trend":            self.monthly_trend(),
            "resolution_time_stats":    self.resolution_time_stats(),
            "critical_unresolved":      self.critical_unresolved(),
            "sla_breach_analysis":      self.sla_breach_analysis(),
            "top_resolver":             self.top_resolver(),
            "best_agent":               self.best_agent(),
            "worst_agent":              self.worst_agent(),
        }
