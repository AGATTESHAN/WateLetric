import pandas as pd
import numpy as np
import json
import os
from xgboost import XGBRegressor
from dotenv import load_dotenv

# This automatically loads the variables from the .env file into your system
load_dotenv()

def send_telegram_alert(message):
    """
    Sends a Markdown-formatted message to Telegram Bot API.
    Uses environment variables TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.
    """
    import os
    import urllib.request
    
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    
    if not token or not chat_id:
        print("\n--- [TELEGRAM ALERT SIMULATION] ---")
        try:
            print(message)
        except UnicodeEncodeError:
            import sys
            sys.stdout.buffer.write((message + "\n").encode('utf-8'))
            sys.stdout.flush()
        print("------------------------------------\n")
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode('utf-8')
            print("Telegram alert sent successfully.")
            return True
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
        return False


def process_utility_alerts(anomaly_data):
    """
    Iterates through the anomaly data dictionary.
    If any anomaly is True, compiles their messages under a master
    'CRITICAL FACILITY ALERT' header in Markdown and sends via Telegram.
    """
    has_any = any(info.get("status") for info in anomaly_data.values())
    if not has_any:
        return
        
    messages = []
    for utility, info in anomaly_data.items():
        if info.get("status"):
            messages.append(info.get("message"))
            
    # Combine cleanly separated by double newlines and horizontal line
    payload = "*CRITICAL FACILITY ALERT*\n\n" + "\n\n---\n\n".join(messages)
    send_telegram_alert(payload)

# Tariff Calculators
def calculate_electricity_bill(kwh):
    """
    TNB Industrial Tariff D (Malaysia):
    - First 200 kWh (1 - 200 kWh): 38.00 sen/kWh (RM 0.380)
    - Subsequent usage (201 kWh onwards): 44.10 sen/kWh (RM 0.441)
    - Minimum charge: RM 7.20
    """
    bill = 0.0
    remaining = kwh
    
    # Block 1: First 200 kWh
    if remaining <= 200:
        bill += remaining * 0.38
        remaining = 0
    else:
        bill += 200 * 0.38
        remaining -= 200
        
    # Block 2: 201 kWh onwards
    if remaining > 0:
        bill += remaining * 0.441
        
    return max(bill, 7.20)


def calculate_water_bill(liters):
    """
    Air Selangor Non-Domestic (Commercial/Industrial) Tariff (using Liters):
    - First 35,000 Liters: RM 0.00351 / Liter (RM 3.51 / m3)
    - Above 35,000 Liters: RM 0.00383 / Liter (RM 3.83 / m3)
    - Minimum monthly charge: RM 36.00
    """
    bill = 0.0
    remaining = liters
    
    # Block 1: First 35,000 Liters
    if remaining <= 35000:
        bill += remaining * 0.00351
        remaining = 0
    else:
        bill += 35000 * 0.00351
        remaining -= 35000
        
    # Block 2: Remaining Liters
    if remaining > 0:
        bill += remaining * 0.00383
        
    return max(bill, 36.00)


def train_model(json_file, target_col):
    with open(json_file) as f:
        data = json.load(f)
    
    df_raw = pd.DataFrame(data)
    df = df_raw.copy()
    
    # Map time (HH:MM string) to numeric hours (e.g. "12:30" -> 12.5)
    df["time"] = df["time"].apply(lambda x: int(x.split(":")[0]) + int(x.split(":")[1]) / 60.0)
    
    # Map day_of_week string to numeric value (0-6)
    day_map = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
    df["day_of_week"] = df["day_of_week"].map(day_map)
    
    # Create lag features
    df["lag_1"] = df[target_col].shift(1)
    df["lag_2"] = df[target_col].shift(2)
    df["lag_24"] = df[target_col].shift(48)
    df["lag_48"] = df[target_col].shift(96)
    df["lag_weekly"] = df[target_col].shift(336)
    
    features = ["time", "day_of_week", "lag_1", "lag_2", "lag_24", "lag_48", "lag_weekly", "occupancy"]
    
    # Split train/test (80% train, 20% test without shuffling)
    # Fit on non-anomalies in train set
    train_idx = int(len(df) * 0.8)
    df_train = df.iloc[:train_idx]
    
    df_train_clean = df_train[df_train.get("anomaly", pd.Series([False]*len(df_train))).fillna(False) != True]
    df_train_clean_lags = df_train_clean.dropna(subset=["lag_1", "lag_24", "lag_weekly"])
    
    model = XGBRegressor(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=5,
        random_state=42
    )
    model.fit(df_train_clean_lags[features], df_train_clean_lags[target_col])
    return model


def process_runtime_data(mock_file, runtime_file, target_col, model, threshold):
    with open(mock_file) as f:
        mock_data = json.load(f)
    with open(runtime_file) as f:
        runtime_data = json.load(f)
        
    df_mock = pd.DataFrame(mock_data)
    df_runtime = pd.DataFrame(runtime_data)
    
    # We take the end of the mock data to build lag features for the runtime day
    df_mock_slice = df_mock.tail(350).copy()
    
    # Concatenate mock slice and runtime data
    df_combined = pd.concat([df_mock_slice, df_runtime], ignore_index=True)
    
    # Map fields
    day_map = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
    df_combined["day_of_week_num"] = df_combined["day_of_week"].fillna("Wed").map(day_map)
    df_combined["time_str"] = df_combined["time"]
    df_combined["time_num"] = df_combined["time"].apply(lambda x: int(x.split(":")[0]) + int(x.split(":")[1]) / 60.0)
    
    df_combined["lag_1"] = df_combined[target_col].shift(1)
    df_combined["lag_2"] = df_combined[target_col].shift(2)
    df_combined["lag_24"] = df_combined[target_col].shift(48)
    df_combined["lag_48"] = df_combined[target_col].shift(96)
    df_combined["lag_weekly"] = df_combined[target_col].shift(336)
    
    features = ["time_num", "day_of_week_num", "lag_1", "lag_2", "lag_24", "lag_48", "lag_weekly", "occupancy"]
    
    # Extract only the runtime slice
    df_runtime_features = df_combined.tail(len(df_runtime)).copy()
    
    # Prepare features and fill NaNs
    X_runtime = df_runtime_features[features].rename(columns={
        "time_num": "time",
        "day_of_week_num": "day_of_week"
    }).ffill().bfill()
    
    # Predict using XGBoost
    preds = model.predict(X_runtime)
    
    df_runtime_features["predicted"] = preds
    
    # Dynamic anomaly detection (deviation from XGBoost forecast)
    df_runtime_features["deviation"] = df_runtime_features[target_col] - df_runtime_features["predicted"]
    df_runtime_features["detected_anomaly"] = df_runtime_features["deviation"] > threshold
    
    return df_runtime_features


def make_serializable(obj):
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(x) for x in obj]
    elif isinstance(obj, (np.float32, np.float64, np.floating)):
        return float(obj)
    elif isinstance(obj, (np.int32, np.int64, np.integer)):
        return int(obj)
    elif isinstance(obj, np.ndarray):
        return make_serializable(obj.tolist())
    else:
        return obj


def main():
    print("Training electricity model on mock dataset...")
    model_elec = train_model("data/mock_dataset_electricity_30days.json", "electricity_kwh")
    
    print("Training water model on mock dataset...")
    model_water = train_model("data/mock_dataset_water_30days.json", "water_liters")
    
    print("Predicting and detecting anomalies on electricity runtime data...")
    # Threshold for electricity anomaly: 5.0 kWh deviation
    df_elec = process_runtime_data("data/mock_dataset_electricity_30days.json", "data/runtime_data_electric.json", "electricity_kwh", model_elec, 5.0)
    
    print("Predicting and detecting anomalies on water runtime data...")
    # Threshold for water anomaly: 10.0 Liters deviation
    df_water = process_runtime_data("data/mock_dataset_water_30days.json", "data/runtime_data_water.json", "water_liters", model_water, 10.0)
    
    # 1. Electricity Metrics (Simulating at 2:00 PM / 14:00)
    actuals_elec = df_elec[df_elec["time_num"] <= 14.0]["electricity_kwh"].sum()
    forecasts_elec = df_elec[df_elec["time_num"] > 14.0]["predicted"].sum()
    daily_total_elec = actuals_elec + forecasts_elec
    
    # Project 1 day of runtime data to 30 days
    projected_elec_kwh = daily_total_elec * 30
    estimated_elec_bill = calculate_electricity_bill(projected_elec_kwh)
    elec_daily_avg = daily_total_elec
    
    # 2. Water Metrics (Simulating at 2:00 PM / 14:00)
    actuals_water = df_water[df_water["time_num"] <= 14.0]["water_liters"].sum()
    forecasts_water = df_water[df_water["time_num"] > 14.0]["predicted"].sum()
    daily_total_water = actuals_water + forecasts_water
    
    # Project to 30 days
    projected_water_liters = daily_total_water * 30
    estimated_water_bill = calculate_water_bill(projected_water_liters)
    water_daily_avg = daily_total_water / 1000.0  # in kL
    
    # 3. Intervals
    elec_intervals = []
    for _, row in df_elec.iterrows():
        elec_intervals.append({
            "time": row["time_num"],
            "time_str": row["time_str"],
            "electricity_kwh": row["electricity_kwh"],
            "predicted": row["predicted"],
            "anomaly": bool(row["detected_anomaly"])
        })
        
    water_intervals = []
    for _, row in df_water.iterrows():
        water_intervals.append({
            "time": row["time_num"],
            "time_str": row["time_str"],
            "water_liters": row["water_liters"],
            "predicted": row["predicted"],
            "anomaly": bool(row["detected_anomaly"])
        })
        
    # 4. Next 30m Prediction
    elec_next30m = df_elec[(df_elec["time_num"] > 14.0) & (df_elec["time_num"] <= 14.5)]
    water_next30m = df_water[(df_water["time_num"] > 14.0) & (df_water["time_num"] <= 14.5)]
    elec_next30m_val = elec_next30m["predicted"].sum()
    water_next30m_val = water_next30m["predicted"].sum()
    
    # Historical average from mock data for 14:30
    with open("data/mock_dataset_electricity_30days.json") as f:
        mock_elec = json.load(f)
    with open("data/mock_dataset_water_30days.json") as f:
        mock_water = json.load(f)
    df_mock_elec = pd.DataFrame(mock_elec)
    df_mock_water = pd.DataFrame(mock_water)
    
    hist_elec_30m_avg = df_mock_elec[df_mock_elec["time"] == "14:30"]["electricity_kwh"].mean()
    hist_water_30m_avg = df_mock_water[df_mock_water["time"] == "14:30"]["water_liters"].mean()
    
    elec_surge = ((elec_next30m_val - hist_elec_30m_avg) / max(hist_elec_30m_avg, 1)) * 100
    water_surge = ((water_next30m_val - hist_water_30m_avg) / max(hist_water_30m_avg, 1)) * 100
    
    # 5. Anomaly Detection Summary
    elec_anomaly = df_elec[df_elec["detected_anomaly"] == True]
    water_anomaly = df_water[df_water["detected_anomaly"] == True]
    
    has_elec_anomaly = len(elec_anomaly) > 0
    elec_anomaly_type = "electricity_spike" if has_elec_anomaly else None
    
    has_water_anomaly = len(water_anomaly) > 0
    water_anomaly_type = "water_leak" if has_water_anomaly else None
    
    # Anomaly state dictionary for Telegram alerts
    alert_messages = {
        "electricity": {
            "status": has_elec_anomaly,
            "message": "⚡️ *Electricity Anomaly Detected!*\nAn unusual consumption spike occurred. High energy usage was recorded during off-peak/irregular baseline hours."
        },
        "water": {
            "status": has_water_anomaly,
            "message": "💧 *Water Anomaly Detected!*\nPotential water leak detected. Constant flow rate measured under zero-occupancy conditions."
        }
    }
    process_utility_alerts(alert_messages)
    
    # Pumping cost estimate for water (0.05 kWh/L at average tariff)
    avg_elec_rate = estimated_elec_bill / max(projected_elec_kwh, 1)
    pumping_kwh_used = actuals_water * 0.05
    pumping_cost_rm = pumping_kwh_used * avg_elec_rate
    
    simulation_data = {
        "1": {
            "day": 1,
            "day_of_week": "Wed",
            "electricity": {
                "actual_so_far_kwh": round(actuals_elec, 2),
                "projected_total_kwh": round(projected_elec_kwh, 2),
                "estimated_bill_rm": round(estimated_elec_bill, 2),
                "daily_avg_kwh": round(elec_daily_avg, 2),
                "next_30m_prediction_kwh": round(elec_next30m_val, 2),
                "surge_pct": round(elec_surge, 1),
                "intervals": elec_intervals,
                "has_anomaly": has_elec_anomaly,
                "anomaly_type": elec_anomaly_type,
            },
            "water": {
                "actual_so_far_liters": round(actuals_water, 2),
                "projected_total_liters": round(projected_water_liters, 2),
                "estimated_bill_rm": round(estimated_water_bill, 2),
                "pumping_electricity_cost_rm": round(pumping_cost_rm, 2),
                "pumping_kwh_used": round(pumping_kwh_used, 2),
                "daily_avg_kl": round(water_daily_avg, 2),
                "next_30m_prediction_liters": round(water_next30m_val, 2),
                "surge_pct": round(water_surge, 1),
                "intervals": water_intervals,
                "has_anomaly": has_water_anomaly,
                "anomaly_type": water_anomaly_type,
            }
        }
    }
    
    print("Writing runtime predictions and calculation data to public/billing_data.js...")
    with open("public/billing_data.js", "w") as out:
        out.write(f"window.billingData = {json.dumps(make_serializable(simulation_data), indent=2)};\n")
        
    # Synchronize with SQLite database
    import sqlite3
    try:
        conn = sqlite3.connect("utility_data.db")
        cursor = conn.cursor()
        for day_str, day_data in simulation_data.items():
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
        conn.close()
        print("Successfully synchronized agent simulation data with SQLite database!")
    except Exception as e:
        print(f"Error saving to SQLite database: {e}")
        
    print("Agent simulation data generation complete!")

if __name__ == "__main__":
    main()
