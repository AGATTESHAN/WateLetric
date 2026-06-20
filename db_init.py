import sqlite3
import json
import re
import os

def init_db():
    db_path = "utility_data.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_summaries (
            day INTEGER,
            utility_type TEXT,
            day_of_week TEXT,
            actual_so_far REAL,
            projected_total REAL,
            estimated_bill REAL,
            daily_avg REAL,
            next_prediction REAL,
            surge_pct REAL,
            pumping_electricity_cost_rm REAL,
            pumping_kwh_used REAL,
            has_anomaly INTEGER,
            anomaly_type TEXT,
            PRIMARY KEY (day, utility_type)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intervals (
            day INTEGER,
            utility_type TEXT,
            time REAL,
            time_str TEXT,
            value REAL,
            predicted REAL,
            anomaly INTEGER,
            PRIMARY KEY (day, utility_type, time)
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_intervals_lookup ON intervals(utility_type, day);")
    conn.commit()
    
    # Read public/billing_data.js
    if os.path.exists("public/billing_data.js"):
        with open("public/billing_data.js", "r", encoding="utf-8") as f:
            content = f.read()
        # Extract JSON substring
        match = re.search(r"window\.billingData\s*=\s*(\{.*?\});", content, re.DOTALL)
        if match:
            json_str = match.group(1)
            billing_data = json.loads(json_str)
            
            for day_str, day_data in billing_data.items():
                day = int(day_str)
                day_of_week = day_data.get("day_of_week", "")
                
                for utility in ["electricity", "water"]:
                    ut_data = day_data.get(utility, {})
                    if not ut_data:
                        continue
                    
                    actual_so_far = ut_data.get("actual_so_far_kwh" if utility == "electricity" else "actual_so_far_liters", 0.0)
                    projected_total = ut_data.get("projected_total_kwh" if utility == "electricity" else "projected_total_liters", 0.0)
                    estimated_bill = ut_data.get("estimated_bill_rm", 0.0)
                    daily_avg = ut_data.get("daily_avg_kwh" if utility == "electricity" else "daily_avg_kl", 0.0)
                    next_prediction = ut_data.get("next_30m_prediction_kwh" if utility == "electricity" else "next_30m_prediction_liters", 0.0)
                    surge_pct = ut_data.get("surge_pct", 0.0)
                    pumping_cost = ut_data.get("pumping_electricity_cost_rm", 0.0)
                    pumping_kwh = ut_data.get("pumping_kwh_used", 0.0)
                    has_anomaly = 1 if ut_data.get("has_anomaly", False) else 0
                    anomaly_type = ut_data.get("anomaly_type", "")
                    
                    # Insert daily summary
                    cursor.execute("""
                        INSERT OR REPLACE INTO daily_summaries (
                            day, utility_type, day_of_week, actual_so_far, projected_total,
                            estimated_bill, daily_avg, next_prediction, surge_pct,
                            pumping_electricity_cost_rm, pumping_kwh_used, has_anomaly, anomaly_type
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        day, utility, day_of_week, actual_so_far, projected_total,
                        estimated_bill, daily_avg, next_prediction, surge_pct,
                        pumping_cost, pumping_kwh, has_anomaly, anomaly_type
                    ))
                    
                    # Insert intervals
                    intervals = ut_data.get("intervals", [])
                    for val in intervals:
                        t = val.get("time", 0.0)
                        t_str = val.get("time_str", "")
                        v = val.get("electricity_kwh" if utility == "electricity" else "water_liters", 0.0)
                        pred = val.get("predicted", 0.0)
                        anom = 1 if val.get("anomaly", False) else 0
                        
                        cursor.execute("""
                            INSERT OR REPLACE INTO intervals (
                                day, utility_type, time, time_str, value, predicted, anomaly
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (day, utility, t, t_str, v, pred, anom))
            
            conn.commit()
            print("Successfully initialized SQLite database from billing_data.js!")
        else:
            print("Could not parse JSON from billing_data.js")
    else:
        print("billing_data.js not found.")
        
    conn.close()

if __name__ == "__main__":
    init_db()
