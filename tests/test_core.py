"""
Unit tests for the Support Ticket AI System core modules.
Run: pytest tests/ -v
"""

import os
import sys
import sqlite3
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.data_ingestion import DataIngestion
from app.analytics import Analytics
from app.anomaly_detector import AnomalyDetector


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ingestion():
    ing = DataIngestion()  # uses data/support_tickets.csv by default
    ing.load()
    return ing


@pytest.fixture(scope="module")
def analytics(ingestion):
    return Analytics(ingestion)


@pytest.fixture(scope="module")
def detector(ingestion):
    # AnomalyDetector can work without Groq for statistical tests
    os.environ.setdefault("GROQ_API_KEY", "dummy-for-tests")
    return AnomalyDetector(ingestion, groq_api_key="dummy-for-tests")


# ---------------------------------------------------------------------------
# DataIngestion tests
# ---------------------------------------------------------------------------

class TestDataIngestion:

    def test_loads_successfully(self, ingestion):
        assert ingestion.df is not None
        assert len(ingestion.df) > 0

    def test_has_expected_columns(self, ingestion):
        expected = {"ticket_id", "created_at", "category", "priority",
                    "status", "response_time_hrs", "resolution_time_hrs",
                    "agent_id", "customer_rating", "issue_summary"}
        assert expected.issubset(set(ingestion.df.columns))

    def test_derived_columns_exist(self, ingestion):
        assert "is_unresolved" in ingestion.df.columns
        assert "created_month" in ingestion.df.columns
        assert "created_date" in ingestion.df.columns

    def test_sqlite_table_exists(self, ingestion):
        result = ingestion.query_sql("SELECT COUNT(*) AS cnt FROM tickets_tbl")
        assert result.iloc[0]["cnt"] == len(ingestion.df)

    def test_priority_values(self, ingestion):
        valid = {"Low", "Medium", "High", "Critical"}
        assert set(ingestion.df["priority"].unique()).issubset(valid)

    def test_status_values(self, ingestion):
        valid = {"Open", "Resolved", "Escalated"}
        assert set(ingestion.df["status"].unique()).issubset(valid)

    def test_category_values(self, ingestion):
        valid = {"Billing", "Technical", "General"}
        assert set(ingestion.df["category"].unique()).issubset(valid)

    def test_query_sql_count(self, ingestion):
        df = ingestion.query_sql("SELECT COUNT(*) AS n FROM tickets_tbl")
        assert df.iloc[0]["n"] == len(ingestion.df)

    def test_query_sql_filter(self, ingestion):
        df = ingestion.query_sql("SELECT * FROM tickets_tbl WHERE priority = 'Critical'")
        assert all(df["priority"] == "Critical")

    def test_get_summary_stats(self, ingestion):
        stats = ingestion.get_summary_stats()
        assert "total_tickets" in stats
        assert stats["total_tickets"] == len(ingestion.df)
        assert "open_tickets" in stats
        assert "resolved_tickets" in stats
        assert "avg_customer_rating" in stats

    def test_get_schema_description(self, ingestion):
        schema = ingestion.get_schema_description()
        assert "tickets_tbl" in schema
        assert "priority" in schema
        assert "resolution_time_hrs" in schema

    def test_unresolved_flag(self, ingestion):
        df = ingestion.df
        open_mask = df["status"].isin(["Open", "Escalated"])
        assert (df.loc[open_mask, "is_unresolved"] == 1).all()
        assert (df.loc[~open_mask, "is_unresolved"] == 0).all()


# ---------------------------------------------------------------------------
# Analytics tests
# ---------------------------------------------------------------------------

class TestAnalytics:

    def test_agent_performance_returns_list(self, analytics):
        result = analytics.agent_performance()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_agent_performance_fields(self, analytics):
        agents = analytics.agent_performance()
        required = {"agent_id", "total_tickets", "resolved", "resolution_rate_pct"}
        for agent in agents:
            assert required.issubset(set(agent.keys()))

    def test_resolution_rate_valid(self, analytics):
        for a in analytics.agent_performance():
            assert 0 <= a["resolution_rate_pct"] <= 100

    def test_top_resolver(self, analytics):
        top = analytics.top_resolver()
        assert "agent_id" in top
        assert top["resolved"] >= 0

    def test_best_agent(self, analytics):
        best = analytics.best_agent()
        assert "agent_id" in best
        assert best["avg_customer_rating"] is not None

    def test_worst_agent(self, analytics):
        worst = analytics.worst_agent()
        assert "agent_id" in worst

    def test_tickets_by_category(self, analytics):
        cats = analytics.tickets_by_category()
        assert len(cats) == 3  # Billing, Technical, General
        for c in cats:
            assert "category" in c
            assert "total" in c

    def test_tickets_by_priority(self, analytics):
        prios = analytics.tickets_by_priority()
        names = [p["priority"] for p in prios]
        assert "Critical" in names
        assert "High" in names

    def test_monthly_trend(self, analytics):
        trend = analytics.monthly_trend()
        assert isinstance(trend, list)
        assert len(trend) > 0
        assert "created_month" in trend[0]
        assert "total" in trend[0]

    def test_resolution_time_stats(self, analytics):
        stats = analytics.resolution_time_stats()
        assert "mean" in stats
        assert "median" in stats
        assert stats["min"] <= stats["median"] <= stats["max"]

    def test_sla_breach_analysis(self, analytics):
        sla = analytics.sla_breach_analysis()
        assert isinstance(sla, dict)
        for prio, data in sla.items():
            assert "sla_hrs" in data
            assert "breach_rate_pct" in data
            assert 0 <= data["breach_rate_pct"] <= 100

    def test_full_dashboard(self, analytics):
        dash = analytics.full_dashboard()
        required_keys = {"summary", "agent_performance", "tickets_by_category",
                         "monthly_trend", "sla_breach_analysis"}
        assert required_keys.issubset(set(dash.keys()))


# ---------------------------------------------------------------------------
# AnomalyDetector tests (statistical only, no Groq call)
# ---------------------------------------------------------------------------

class TestAnomalyDetector:

    def test_slow_resolution_returns_list(self, detector):
        result = detector.detect_slow_resolution()
        assert isinstance(result, list)

    def test_slow_resolution_fields(self, detector):
        results = detector.detect_slow_resolution()
        for item in results:
            assert "anomaly_type" in item
            assert item["anomaly_type"] == "slow_resolution"
            assert "severity" in item
            assert "ticket_id" in item
            assert "resolution_time_hrs" in item

    def test_overdue_high_priority_returns_list(self, detector):
        result = detector.detect_overdue_high_priority()
        assert isinstance(result, list)
        for item in result:
            assert item["priority"] in ("High", "Critical")
            assert item["age_hrs"] > 24

    def test_critical_unresolved_all_critical(self, detector):
        result = detector.detect_critical_unresolved()
        for item in result:
            assert item["priority"] == "Critical"
            assert item["status"] in ("Open", "Escalated")

    def test_slow_response_returns_list(self, detector):
        result = detector.detect_slow_response()
        assert isinstance(result, list)

    def test_low_rated_agents_returns_list(self, detector):
        result = detector.detect_low_rated_agents()
        assert isinstance(result, list)
        for item in result:
            assert "agent_id" in item
            assert "avg_rating" in item

    def test_detect_by_type_valid(self, detector):
        for t in ("slow_resolution", "overdue_high_priority",
                  "critical_unresolved", "slow_response", "low_rated_agents"):
            result = detector.detect_by_type(t)
            assert isinstance(result, list)

    def test_detect_by_type_invalid(self, detector):
        with pytest.raises(ValueError, match="Unknown type"):
            detector.detect_by_type("nonexistent_type")

    def test_severity_values(self, detector):
        valid_severities = {"Critical", "High", "Medium", "Low"}
        for method in (detector.detect_slow_resolution,
                       detector.detect_overdue_high_priority,
                       detector.detect_critical_unresolved,
                       detector.detect_slow_response):
            for item in method():
                assert item["severity"] in valid_severities
