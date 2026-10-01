"""
Natural Language Query Engine.
User question → Groq LLM → SQLite SQL → execute → LLM answer.
"""

import json
import logging
import os
import re
import time
from typing import Any

from groq import Groq

from app.data_ingestion import DataIngestion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — tells the LLM exactly what table/dialect to use
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an expert data analyst AI for a customer support ticket system.
Convert natural language questions into correct SQLite SQL queries.

{schema}

STRICT RULES:
1. Return ONLY a valid JSON object — no markdown, no code fences, nothing else.
2. JSON must have exactly these keys:
   - "sql"              : valid SQLite SQL targeting table `tickets_tbl`
   - "explanation"      : 1-2 sentence description of what the query does
   - "answer_template"  : sentence template; use {{result}} as the data placeholder
3. SQLite dialect only:
   - Date functions: strftime('%Y-%m', created_at) NOT date_trunc()
   - No ILIKE — use LOWER(col) LIKE LOWER('%value%') instead
   - NULL checks: IS NULL / IS NOT NULL
4. For aggregate questions (count, avg, etc.) always alias the column clearly.
5. Limit detail/list queries to 50 rows max.
6. Handle NULLs safely (resolution_time_hrs and customer_rating can be NULL).

Example output (no extra text around it):
{"sql": "SELECT COUNT(*) AS total FROM tickets_tbl WHERE status = 'Open'", "explanation": "Counts all open tickets", "answer_template": "There are {result} open tickets right now."}
"""


class NLQueryEngine:
    def __init__(self, ingestion: DataIngestion, groq_api_key: str | None = None):
        self.ingestion = ingestion
        api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")
        self.client = Groq(api_key=api_key)
        self.model  = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _system_prompt(self) -> str:
        return SYSTEM_PROMPT.format(schema=self.ingestion.get_schema_description())

    def _extract_json(self, raw: str) -> dict:
        """Robustly pull JSON from LLM output even if it's wrapped in markdown."""
        text = raw.strip()
        text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
        return json.loads(text)

    def _guard_sql(self, sql: str) -> str:
        """Reject any SQL that is not a SELECT statement to prevent data mutation."""
        cleaned = sql.strip().lstrip(";").strip()
        if not cleaned.upper().startswith("SELECT"):
            raise ValueError(
                f"Safety guard: only SELECT queries are allowed. Got: {cleaned[:80]}"
            )
        return cleaned

    def _call_groq_with_retry(self, messages: list, temperature: float, max_tokens: int, max_retries: int = 3) -> str:
        """Call Groq API with exponential backoff on rate-limit (429) errors."""
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
                    logger.warning(f"Groq rate limit hit. Retrying in {wait}s … (attempt {attempt+1}/{max_retries})")
                    time.sleep(wait)
                elif attempt < max_retries - 1:
                    logger.warning(f"Groq call failed: {e}. Retrying …")
                    time.sleep(1)
                else:
                    raise
        raise RuntimeError("Groq API failed after all retries.")

    def _llm_to_sql(self, question: str) -> dict:
        raw = self._call_groq_with_retry(
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user",   "content": f"Question: {question}"},
            ],
            temperature=0.1,
            max_tokens=1024,
        )
        logger.debug(f"LLM SQL response: {raw}")
        return self._extract_json(raw)

    def _df_to_str(self, df) -> str:
        if df is None or len(df) == 0:
            return "No results found."
        if len(df) == 1 and len(df.columns) == 1:
            return str(df.iloc[0, 0])
        suffix = f"\n... ({len(df)} total rows)" if len(df) > 10 else ""
        return df.head(10).to_string(index=False) + suffix

    def _llm_answer(self, question: str, sql: str, result_str: str, explanation: str) -> str:
        prompt = (
            f'User asked: "{question}"\n\n'
            f"SQL run:\n{sql}\n\n"
            f"Result:\n{result_str}\n\n"
            f"Query explanation: {explanation}\n\n"
            "Write a clear, concise natural-language answer (2-4 sentences max). "
            "Be specific with numbers. Summarize table results as key insights."
        )
        raw = self._call_groq_with_retry(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=512,
        )
        return raw.strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(self, question: str) -> dict[str, Any]:
        """
        Process a natural language question.

        Returns dict with keys:
          question, sql, explanation, data, result_text, answer, row_count
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        logger.info(f"NL query: {question}")

        # 1. Generate SQL
        llm_out     = self._llm_to_sql(question)
        sql         = llm_out.get("sql", "").strip()
        explanation = llm_out.get("explanation", "")

        if not sql:
            raise ValueError("LLM did not return a SQL query.")

        logger.info(f"Generated SQL: {sql}")

        # 1b. Safety guard — only allow SELECT
        sql = self._guard_sql(sql)

        # 2. Execute
        result_df  = self.ingestion.query_sql(sql)
        result_str = self._df_to_str(result_df)

        # 3. Natural-language answer
        answer = self._llm_answer(question, sql, result_str, explanation)

        # 4. Serialize DataFrame → JSON-safe list of dicts
        records = result_df.to_dict(orient="records") if result_df is not None else []
        for row in records:
            for k, v in row.items():
                if hasattr(v, "item"):          # numpy scalar
                    row[k] = v.item()
                elif v != v:                    # NaN check
                    row[k] = None

        return {
            "question":    question,
            "sql":         sql,
            "explanation": explanation,
            "data":        records,
            "result_text": result_str,
            "answer":      answer,
            "row_count":   len(result_df) if result_df is not None else 0,
        }
