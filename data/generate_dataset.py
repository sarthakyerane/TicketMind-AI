"""
Generate a realistic 500-row support_tickets.csv dataset.
Run once: python data/generate_dataset.py
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(42)

CATEGORIES = ["Billing", "Technical", "General"]
PRIORITIES = ["Low", "Medium", "High", "Critical"]
STATUSES = ["Open", "Resolved", "Escalated"]
AGENTS = [f"AGT-{str(i).zfill(2)}" for i in range(1, 13)]

ISSUE_SUMMARIES = {
    "Billing": [
        "Incorrect charge on invoice",
        "Refund not processed",
        "Double billing detected",
        "Subscription not cancelled",
        "Promo code not applied",
        "Unexpected fee added",
        "Invoice missing details",
        "Payment declined unexpectedly",
        "Overcharge on plan upgrade",
        "Tax calculation error",
        "Credit not reflected",
        "Auto-renewal issue",
    ],
    "Technical": [
        "Login failure after update",
        "API timeout in production",
        "App crashes on startup",
        "Data not syncing correctly",
        "Export feature broken",
        "Webhook not triggering",
        "SSL certificate error",
        "Dashboard loading slow",
        "Import fails with CSV",
        "Email notifications not sent",
        "OAuth integration broken",
        "Search returning wrong results",
    ],
    "General": [
        "Request for product docs",
        "How to export reports",
        "Onboarding help needed",
        "Feature request submission",
        "Account settings confusion",
        "Password reset not working",
        "How to add team members",
        "Language preference change",
        "Accessibility concern reported",
        "Request for SLA document",
        "Query about data retention",
        "General product feedback",
    ],
}

PRIORITY_WEIGHTS = [0.35, 0.30, 0.25, 0.10]  # Low, Medium, High, Critical
STATUS_WEIGHTS_BY_PRIORITY = {
    "Low": [0.30, 0.65, 0.05],
    "Medium": [0.25, 0.60, 0.15],
    "High": [0.20, 0.55, 0.25],
    "Critical": [0.15, 0.45, 0.40],
}

def random_datetime(start, end):
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))

def generate_ticket(ticket_num, created_at, priority, status):
    category = random.choice(CATEGORIES)
    agent = random.choice(AGENTS)
    summary = random.choice(ISSUE_SUMMARIES[category])

    # Response time: faster for critical
    resp_ranges = {"Low": (1.0, 8.0), "Medium": (0.5, 5.0), "High": (0.2, 3.0), "Critical": (0.1, 2.0)}
    resp_min, resp_max = resp_ranges[priority]
    resp_time = round(random.uniform(resp_min, resp_max), 1)

    resol_time = None
    cust_rating = None

    if status == "Resolved":
        resol_ranges = {"Low": (3.0, 30.0), "Medium": (2.0, 20.0), "High": (1.0, 15.0), "Critical": (0.5, 48.0)}
        resol_min, resol_max = resol_ranges[priority]
        resol_time = round(random.uniform(resol_min, resol_max), 1)
        # Inject some anomalous resolution times
        if random.random() < 0.05:
            resol_time = round(random.uniform(50.0, 120.0), 1)
        cust_rating = random.choices([1, 2, 3, 4, 5], weights=[0.05, 0.10, 0.20, 0.35, 0.30])[0]
        # Lower ratings for high resol times
        if resol_time > 40:
            cust_rating = random.choices([1, 2, 3], weights=[0.5, 0.3, 0.2])[0]
    elif status == "Escalated":
        # Escalated tickets often have long times without full resolution
        resol_time = round(random.uniform(8.0, 30.0), 1)
        cust_rating = random.choices([1, 2, 3], weights=[0.5, 0.3, 0.2])[0]

    return {
        "ticket_id": f"TKT-{str(ticket_num).zfill(3)}",
        "created_at": created_at.strftime("%Y-%m-%d %H:%M"),
        "category": category,
        "priority": priority,
        "status": status,
        "response_time_hrs": resp_time,
        "resolution_time_hrs": resol_time if resol_time is not None else "",
        "agent_id": agent,
        "customer_rating": cust_rating if cust_rating is not None else "",
        "issue_summary": summary,
    }

def main():
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 12, 31)

    rows = []
    for i in range(1, 501):
        created_at = random_datetime(start_date, end_date)
        priority = random.choices(PRIORITIES, weights=PRIORITY_WEIGHTS)[0]
        status = random.choices(STATUSES, weights=STATUS_WEIGHTS_BY_PRIORITY[priority])[0]
        row = generate_ticket(i, created_at, priority, status)
        rows.append(row)

    # Sort by created_at
    rows.sort(key=lambda x: x["created_at"])

    # Fix ticket IDs after sort
    for idx, row in enumerate(rows, 1):
        row["ticket_id"] = f"TKT-{str(idx).zfill(3)}"

    fieldnames = [
        "ticket_id", "created_at", "category", "priority", "status",
        "response_time_hrs", "resolution_time_hrs", "agent_id",
        "customer_rating", "issue_summary"
    ]

    with open("data/support_tickets.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} tickets -> data/support_tickets.csv")

if __name__ == "__main__":
    main()
