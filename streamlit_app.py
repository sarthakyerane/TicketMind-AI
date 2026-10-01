"""
Streamlit UI — Support Ticket AI System
A rich, interactive dashboard that talks directly to the core modules
(no HTTP round-trip needed — faster and simpler in a Docker container).
"""

import os
import time

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Page config — MUST be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="TicketMind AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — dark glassmorphism theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  .stApp { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); }

  /* Cards */
  .metric-card {
    background: rgba(255,255,255,0.08);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 16px;
    padding: 20px 24px;
    text-align: center;
    transition: transform .2s, box-shadow .2s;
  }
  .metric-card:hover { transform: translateY(-3px); box-shadow: 0 12px 40px rgba(0,0,0,0.4); }
  .metric-card h2 { font-size: 2.2rem; font-weight: 700; margin: 0; }
  .metric-card p  { font-size: 0.85rem; color: rgba(255,255,255,0.65); margin: 4px 0 0; }

  /* Anomaly severity badges */
  .badge-critical { background:#ff4757; color:#fff; padding:3px 10px; border-radius:20px; font-size:.75rem; font-weight:600; }
  .badge-high     { background:#ff6b35; color:#fff; padding:3px 10px; border-radius:20px; font-size:.75rem; font-weight:600; }
  .badge-medium   { background:#ffa502; color:#fff; padding:3px 10px; border-radius:20px; font-size:.75rem; font-weight:600; }
  .badge-low      { background:#2ed573; color:#fff; padding:3px 10px; border-radius:20px; font-size:.75rem; font-weight:600; }

  /* Answer box */
  .answer-box {
    background: rgba(0,230,118,0.12);
    border-left: 4px solid #00e676;
    border-radius: 8px;
    padding: 16px 20px;
    margin: 12px 0;
    font-size: 1rem;
    line-height: 1.6;
  }
  .sql-box {
    background: rgba(0,0,0,0.4);
    border-left: 4px solid #7c4dff;
    border-radius: 8px;
    padding: 12px 16px;
    font-family: 'Courier New', monospace;
    font-size: 0.85rem;
  }
  /* Section headers */
  .section-title {
    font-size: 1.4rem; font-weight: 700;
    background: linear-gradient(90deg, #00e676, #7c4dff);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 16px;
  }

  /* Streamlit overrides */
  div[data-testid="stMetricValue"]  { font-size: 1.8rem !important; color: #fff !important; }
  div[data-testid="stMetricLabel"]  { color: rgba(255,255,255,0.7) !important; }
  .stTextArea textarea { background: rgba(255,255,255,0.08) !important; color: #fff !important; border-color: rgba(255,255,255,0.2) !important; }
  .stButton > button  { background: linear-gradient(135deg, #7c4dff, #00e676) !important; color: #fff !important; border: none !important; border-radius: 10px !important; font-weight: 600 !important; padding: 10px 28px !important; }
  .stButton > button:hover { opacity: 0.88; transform: translateY(-1px); }
  section[data-testid="stSidebar"] { background: rgba(15,12,41,0.95) !important; }
  .stDataFrame { border-radius: 12px; overflow: hidden; }
  .stSelectbox > div { background: rgba(255,255,255,0.08) !important; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Load core modules — cached so they only run once
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Loading dataset …")
def load_system():
    from app.data_ingestion import DataIngestion
    from app.analytics import Analytics
    from app.anomaly_detector import AnomalyDetector
    from app.nl_query import NLQueryEngine

    groq_key = os.getenv("GROQ_API_KEY", "")
    ingestion = DataIngestion()
    ingestion.load()
    analytics = Analytics(ingestion)
    detector  = AnomalyDetector(ingestion, groq_api_key=groq_key)
    nl_engine = NLQueryEngine(ingestion, groq_api_key=groq_key)
    return ingestion, analytics, detector, nl_engine


try:
    ingestion, analytics, detector, nl_engine = load_system()
    stats = ingestion.get_summary_stats()
except Exception as e:
    st.error(f"❌ Failed to load system: {e}")
    st.stop()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🧠 TicketMind AI")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["🏠 Dashboard", "💬 NL Query", "🚨 Anomalies", "📊 Agent Analytics", "🔍 SQL Explorer"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown(f"**Dataset:** `{stats.get('source_file','—')}`")
    st.markdown(f"**Total tickets:** `{stats.get('total_tickets',0):,}`")
    st.markdown(f"**Date range:** `{stats['date_range']['from'][:10]}` → `{stats['date_range']['to'][:10]}`")
    st.markdown("---")
    st.caption("💬 Powered by Groq Llama 3.3 + SQLite")


# ===========================================================================
# PAGE: Dashboard
# ===========================================================================
if page == "🏠 Dashboard":
    st.markdown('<p class="section-title">🧠 TicketMind AI — Dashboard</p>', unsafe_allow_html=True)

    # KPI row
    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        (c1, "🎫 Total",    stats["total_tickets"],        "#7c4dff"),
        (c2, "🟢 Resolved", stats["resolved_tickets"],     "#00e676"),
        (c3, "🔴 Open",     stats["open_tickets"],         "#ff4757"),
        (c4, "⚡ Escalated",stats["escalated_tickets"],    "#ffa502"),
        (c5, "🔥 Critical", stats["critical_tickets"],     "#ff6b35"),
    ]
    for col, label, val, color in kpis:
        with col:
            st.markdown(
                f'<div class="metric-card"><h2 style="color:{color}">{val:,}</h2><p>{label}</p></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # Second row of metrics
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("⏱️ Avg Resolution Time", f"{stats['avg_resolution_time_hrs']} hrs")
    with m2:
        st.metric("⚡ Avg Response Time", f"{stats['avg_response_time_hrs']} hrs")
    with m3:
        st.metric("⭐ Avg Customer Rating", f"{stats['avg_customer_rating']} / 5")

    st.markdown("---")

    # Charts row 1
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("#### Priority Distribution")
        prio_data = pd.DataFrame(
            list(stats["priority_distribution"].items()),
            columns=["Priority", "Count"]
        )
        st.bar_chart(prio_data.set_index("Priority"), color="#7c4dff")

    with col_r:
        st.markdown("#### Status Distribution")
        status_data = pd.DataFrame(
            list(stats["status_distribution"].items()),
            columns=["Status", "Count"]
        )
        st.bar_chart(status_data.set_index("Status"), color="#00e676")

    # Monthly trend
    st.markdown("---")
    st.markdown("#### Monthly Ticket Trend")
    monthly = pd.DataFrame(analytics.monthly_trend())
    if not monthly.empty:
        st.line_chart(
            monthly.set_index("created_month")[["total","resolved","open","critical"]],
        )

    # SLA breach
    st.markdown("---")
    st.markdown("#### SLA Breach Analysis")
    sla = analytics.sla_breach_analysis()
    if sla:
        sla_df = pd.DataFrame([
            {"Priority": p, "SLA (hrs)": v["sla_hrs"],
             "Total Resolved": v["total_resolved"],
             "Breached": v["breached"],
             "Breach Rate %": v["breach_rate_pct"]}
            for p, v in sla.items()
        ])
        st.dataframe(sla_df, use_container_width=True, hide_index=True)

    # Category breakdown
    st.markdown("---")
    st.markdown("#### Tickets by Category")
    cat_df = pd.DataFrame(analytics.tickets_by_category())
    if not cat_df.empty:
        st.dataframe(cat_df, use_container_width=True, hide_index=True)


# ===========================================================================
# PAGE: NL Query
# ===========================================================================
elif page == "💬 NL Query":
    st.markdown('<p class="section-title">💬 Ask Anything About Your Tickets</p>', unsafe_allow_html=True)
    st.markdown("Type a natural language question and the AI will query the dataset and explain the result.")

    EXAMPLE_QUESTIONS = [
        "How many tickets are currently open?",
        "Which agent resolved the most tickets?",
        "What is the average customer rating for Technical category tickets?",
        "Show me all Critical tickets not resolved within 12 hours.",
        "Which agent has the lowest average customer rating?",
        "How many high priority tickets are unresolved?",
        "What is the most common issue category this year?",
        "List the top 5 agents by number of resolved tickets.",
    ]

    col_q, col_ex = st.columns([3, 1])
    with col_ex:
        example = st.selectbox("💡 Load example", [""] + EXAMPLE_QUESTIONS)

    with col_q:
        question = st.text_area(
            "Your question",
            value=example if example else "",
            height=100,
            placeholder="e.g. How many critical tickets are unresolved?",
        )

    if st.button("🔍 Ask AI", use_container_width=False):
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("🤖 Thinking …"):
                try:
                    t0 = time.time()
                    result = nl_engine.query(question)
                    elapsed = round(time.time() - t0, 2)

                    # Save to history
                    if "query_history" not in st.session_state:
                        st.session_state.query_history = []
                    st.session_state.query_history.append({
                        "question": result["question"],
                        "answer":   result["answer"],
                        "sql":      result["sql"],
                    })

                    # Answer
                    st.markdown(
                        f'<div class="answer-box">🤖 <strong>Answer:</strong><br>{result["answer"]}</div>',
                        unsafe_allow_html=True,
                    )

                    # SQL
                    with st.expander("🔎 Generated SQL", expanded=False):
                        st.markdown(
                            f'<div class="sql-box">{result["sql"]}</div>',
                            unsafe_allow_html=True,
                        )
                        st.caption(f"📝 {result['explanation']}")

                    # Raw data
                    if result["data"]:
                        with st.expander(f"📋 Raw Data ({result['row_count']} rows)", expanded=False):
                            st.dataframe(pd.DataFrame(result["data"]), use_container_width=True, hide_index=True)

                    st.caption(f"⏱️ Response time: {elapsed}s")

                except Exception as e:
                    st.error(f"❌ Error: {e}")

    # Query History
    if "query_history" not in st.session_state:
        st.session_state.query_history = []

    if st.session_state.query_history:
        st.markdown("---")
        st.markdown("#### 📜 Recent Queries")
        for past in reversed(st.session_state.query_history[-5:]):
            with st.expander(f"❓ {past['question'][:80]}", expanded=False):
                st.markdown(f'<div class="answer-box">{past["answer"]}</div>', unsafe_allow_html=True)
                st.caption(f"SQL: `{past['sql']}`")


# ===========================================================================
# PAGE: Anomalies
# ===========================================================================
elif page == "🚨 Anomalies":
    st.markdown('<p class="section-title">🚨 Anomaly Detection</p>', unsafe_allow_html=True)

    col_opt1, col_opt2 = st.columns([2, 1])
    with col_opt1:
        anomaly_filter = st.selectbox(
            "Filter by type",
            ["All", "slow_resolution", "overdue_high_priority",
             "critical_unresolved", "slow_response", "low_rated_agents"],
        )
    with col_opt2:
        run_llm = st.checkbox("Include AI summary", value=True)

    if st.button("🔍 Detect Anomalies", use_container_width=False):
        with st.spinner("Running anomaly detection …"):
            try:
                if anomaly_filter == "All":
                    result = detector.detect_all(include_llm_summary=run_llm)

                    # Summary KPIs
                    ka, kb, kc, kd, ke = st.columns(5)
                    pairs = [
                        (ka, "Total",            result["total_anomalies"],                                "#ff4757"),
                        (kb, "Slow Resolution",  result["counts_by_type"]["slow_resolution"],             "#ffa502"),
                        (kc, "Overdue Priority", result["counts_by_type"]["overdue_high_priority"],       "#ff6b35"),
                        (kd, "Critical Open",    result["counts_by_type"]["critical_unresolved"],         "#ff4757"),
                        (ke, "Low Rated Agents", result["counts_by_type"]["low_rated_agents"],            "#7c4dff"),
                    ]
                    for col, label, val, color in pairs:
                        with col:
                            st.markdown(
                                f'<div class="metric-card"><h2 style="color:{color}">{val}</h2><p>{label}</p></div>',
                                unsafe_allow_html=True,
                            )

                    # LLM summary
                    if run_llm and result.get("llm_summary"):
                        st.markdown("---")
                        st.markdown("#### 🤖 AI Executive Summary")
                        st.info(result["llm_summary"])

                    # Per-type tables
                    st.markdown("---")
                    for atype, items in result["anomalies"].items():
                        if items:
                            label_map = {
                                "slow_resolution":       "⏱️ Slow Resolution",
                                "overdue_high_priority": "🔴 Overdue High Priority",
                                "critical_unresolved":   "🔥 Critical Unresolved",
                                "slow_response":         "📞 Slow Response",
                                "low_rated_agents":      "⭐ Low Rated Agents",
                            }
                            with st.expander(f"{label_map.get(atype, atype)} ({len(items)} items)", expanded=atype=="critical_unresolved"):
                                st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True)

                else:
                    items = detector.detect_by_type(anomaly_filter)
                    st.success(f"Found **{len(items)}** anomalies of type `{anomaly_filter}`")
                    if items:
                        st.dataframe(pd.DataFrame(items), use_container_width=True, hide_index=True)
                    else:
                        st.success("✅ No anomalies detected for this type!")

            except Exception as e:
                st.error(f"❌ Error: {e}")


# ===========================================================================
# PAGE: Agent Analytics
# ===========================================================================
elif page == "📊 Agent Analytics":
    st.markdown('<p class="section-title">📊 Agent Performance Analytics</p>', unsafe_allow_html=True)

    agents = analytics.agent_performance()
    top    = analytics.top_resolver()
    best   = analytics.best_agent()
    worst  = analytics.worst_agent()

    a1, a2, a3 = st.columns(3)
    with a1:
        st.success(f"🏆 **Top Resolver:** {top.get('agent_id','—')} ({top.get('resolved',0)} tickets)")
    with a2:
        st.info(f"⭐ **Best Rated:** {best.get('agent_id','—')} ({best.get('avg_customer_rating','—')}/5)")
    with a3:
        st.warning(f"⚠️ **Needs Attention:** {worst.get('agent_id','—')} ({worst.get('avg_customer_rating','—')}/5)")

    st.markdown("---")
    st.markdown("#### Full Agent Leaderboard")
    df_agents = pd.DataFrame(agents)

    # Color-code by rating
    def color_rating(val):
        if val is None or (isinstance(val, float) and val != val):
            return ""
        if val >= 4.5:
            return "background-color: rgba(0,230,118,0.25)"
        if val < 3.5:
            return "background-color: rgba(255,71,87,0.25)"
        return ""

    if not df_agents.empty:
        styled = df_agents.style.applymap(color_rating, subset=["avg_customer_rating"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

    # Per-agent detail
    st.markdown("---")
    st.markdown("#### Agent Detail View")
    selected = st.selectbox("Select agent", [a["agent_id"] for a in agents])
    agent_info = next((a for a in agents if a["agent_id"] == selected), {})
    if agent_info:
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Total Tickets",     agent_info["total_tickets"])
        d2.metric("Resolved",          agent_info["resolved"])
        d3.metric("Avg Rating",        f"{agent_info['avg_customer_rating'] or '—'}/5")
        d4.metric("Avg Resolution",    f"{agent_info['avg_resolution_time_hrs'] or '—'} hrs")

        # Tickets for this agent
        agent_df = ingestion.df[ingestion.df["agent_id"] == selected].copy()
        agent_df["created_at"] = agent_df["created_at"].astype(str)
        st.dataframe(
            agent_df[["ticket_id","created_at","category","priority","status",
                       "response_time_hrs","resolution_time_hrs","customer_rating","issue_summary"]],
            use_container_width=True, hide_index=True,
        )


# ===========================================================================
# PAGE: SQL Explorer
# ===========================================================================
elif page == "🔍 SQL Explorer":
    st.markdown('<p class="section-title">🔍 SQL Explorer</p>', unsafe_allow_html=True)
    st.markdown("Run raw SQLite queries directly against `tickets_tbl`.")

    PRESET_QUERIES = {
        "Count by status":
            "SELECT status, COUNT(*) AS count FROM tickets_tbl GROUP BY status ORDER BY count DESC",
        "Avg resolution by priority":
            "SELECT priority, ROUND(AVG(resolution_time_hrs),2) AS avg_hrs FROM tickets_tbl WHERE resolution_time_hrs IS NOT NULL GROUP BY priority",
        "Top 5 agents by resolved tickets":
            "SELECT agent_id, COUNT(*) AS resolved FROM tickets_tbl WHERE status='Resolved' GROUP BY agent_id ORDER BY resolved DESC LIMIT 5",
        "Critical unresolved tickets":
            "SELECT ticket_id, created_at, category, agent_id, issue_summary FROM tickets_tbl WHERE priority='Critical' AND status != 'Resolved'",
        "Slow resolutions (>24 hrs)":
            "SELECT ticket_id, priority, agent_id, resolution_time_hrs, issue_summary FROM tickets_tbl WHERE resolution_time_hrs > 24 ORDER BY resolution_time_hrs DESC LIMIT 20",
        "Monthly ticket count":
            "SELECT created_month, COUNT(*) AS total FROM tickets_tbl GROUP BY created_month ORDER BY created_month",
        "Agent avg rating":
            "SELECT agent_id, ROUND(AVG(customer_rating),2) AS avg_rating, COUNT(*) AS tickets FROM tickets_tbl WHERE customer_rating IS NOT NULL GROUP BY agent_id ORDER BY avg_rating DESC",
    }

    preset = st.selectbox("📋 Load preset query", [""] + list(PRESET_QUERIES.keys()))
    sql_input = st.text_area(
        "SQL Query",
        value=PRESET_QUERIES.get(preset, "") if preset else "",
        height=140,
        placeholder="SELECT * FROM tickets_tbl LIMIT 10",
    )

    if st.button("▶️ Run Query", use_container_width=False):
        if not sql_input.strip():
            st.warning("Enter a SQL query.")
        else:
            try:
                t0 = time.time()
                result_df = ingestion.query_sql(sql_input)
                elapsed   = round(time.time() - t0, 3)
                st.success(f"✅ {len(result_df)} rows returned in {elapsed}s")
                st.dataframe(result_df, use_container_width=True, hide_index=True)
                csv = result_df.to_csv(index=False)
                st.download_button("⬇️ Download CSV", csv, "query_result.csv", "text/csv")
            except Exception as e:
                st.error(f"❌ SQL Error: {e}")

    with st.expander("📖 Schema Reference"):
        st.code(ingestion.get_schema_description(), language="text")
