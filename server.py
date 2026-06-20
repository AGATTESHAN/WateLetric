import os
import json
import urllib.request
import urllib.error
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.lstrip("\ufeff")
                if line.strip() and not line.startswith("#"):
                    parts = line.strip().split("=", 1)
                    if len(parts) == 2:
                        os.environ[parts[0].strip()] = parts[1].strip()

def send_telegram_alert(message):
    import urllib.request
    import json
    import sys
    
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    
    if not token or not chat_id:
        print("\n--- [TELEGRAM ALERT SIMULATION] ---")
        try:
            print(message)
        except UnicodeEncodeError:
            sys.stdout.buffer.write((message + "\n").encode('utf-8'))
            sys.stdout.flush()
        print("------------------------------------\n")
        return True
        
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
            print("Telegram alert sent successfully.")
            sys.stdout.flush()
            return True
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
        sys.stdout.flush()
        return False

class UtilityProxyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="public", **kwargs)

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        path = parsed_url.path
        
        if path == "/api/usage":
            utility = query_params.get("utility", ["electricity"])[0]
            day = int(query_params.get("day", ["1"])[0])
            
            import sqlite3
            try:
                conn = sqlite3.connect("utility_data.db")
                cursor = conn.cursor()
                cursor.execute("SELECT time, time_str, value, predicted, anomaly FROM intervals WHERE utility_type=? AND day=? ORDER BY time", (utility, day))
                rows = cursor.fetchall()
                conn.close()
                
                intervals = []
                for row in rows:
                    intervals.append({
                        "time": row[0],
                        "time_str": row[1],
                        "value": row[2],
                        "electricity_kwh" if utility == "electricity" else "water_liters": row[2],
                        "predicted": row[3],
                        "anomaly": bool(row[4])
                    })
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"intervals": intervals}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return
            
        elif path == "/api/summary":
            utility = query_params.get("utility", ["electricity"])[0]
            day = int(query_params.get("day", ["1"])[0])
            
            import sqlite3
            try:
                conn = sqlite3.connect("utility_data.db")
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT actual_so_far, projected_total, estimated_bill, daily_avg, next_prediction, surge_pct,
                           pumping_electricity_cost_rm, pumping_kwh_used, has_anomaly, anomaly_type, day_of_week
                    FROM daily_summaries WHERE utility_type=? AND day=?
                """, (utility, day))
                row = cursor.fetchone()
                
                if row:
                    # Fetch intervals as well
                    cursor.execute("SELECT time, time_str, value, predicted, anomaly FROM intervals WHERE utility_type=? AND day=? ORDER BY time", (utility, day))
                    int_rows = cursor.fetchall()
                    intervals = []
                    for r in int_rows:
                        intervals.append({
                            "time": r[0],
                            "time_str": r[1],
                            "electricity_kwh" if utility == "electricity" else "water_liters": r[2],
                            "predicted": r[3],
                            "anomaly": bool(r[4])
                        })
                        
                    data = {
                        "day": day,
                        "day_of_week": row[10],
                        "actual_so_far_kwh" if utility == "electricity" else "actual_so_far_liters": row[0],
                        "projected_total_kwh" if utility == "electricity" else "projected_total_liters": row[1],
                        "estimated_bill_rm": row[2],
                        "daily_avg_kwh" if utility == "electricity" else "daily_avg_kl": row[3],
                        "next_30m_prediction_kwh" if utility == "electricity" else "next_30m_prediction_liters": row[4],
                        "surge_pct": row[5],
                        "pumping_electricity_cost_rm": row[6],
                        "pumping_kwh_used": row[7],
                        "has_anomaly": bool(row[8]),
                        "anomaly_type": row[9],
                        "intervals": intervals
                    }
                else:
                    data = {"error": "Day summary not found"}
                conn.close()
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return
            
        elif path == "/api/peak-analysis":
            import sqlite3
            try:
                conn = sqlite3.connect("utility_data.db")
                cursor = conn.cursor()
                
                # Fetch peak electricity
                cursor.execute("SELECT time_str, value FROM intervals WHERE utility_type='electricity' ORDER BY value DESC LIMIT 1")
                elec_peak = cursor.fetchone()
                
                # Fetch peak water
                cursor.execute("SELECT time_str, value FROM intervals WHERE utility_type='water' ORDER BY value DESC LIMIT 1")
                water_peak = cursor.fetchone()
                
                conn.close()
                
                res = {
                    "electricity": {"time": elec_peak[0] if elec_peak else "--:--", "value": elec_peak[1] if elec_peak else 0.0},
                    "water": {"time": water_peak[0] if water_peak else "--:--", "value": water_peak[1] if water_peak else 0.0}
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(res).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return
            
        elif path == "/api/firebase-config":
            import os
            # Read from environment loaded from .env
            config = {
                "apiKey": os.environ.get("FIREBASE_API_KEY", "AIzaSyFakeKeyForFirebaseAuthentication_ReplaceMe"),
                "authDomain": f"{os.environ.get('PROJECT_ID', 'wateletric')}.firebaseapp.com",
                "projectId": os.environ.get("PROJECT_ID", "wateletric"),
                "storageBucket": f"{os.environ.get('PROJECT_ID', 'wateletric')}.appspot.com",
                "messagingSenderId": os.environ.get("PROJECT_NUMBER", "1054113403936"),
                "appId": f"1:{os.environ.get('PROJECT_NUMBER', '1054113403936')}:web:3a00000000000000"
            }
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(config).encode('utf-8'))
            return
            
        super().do_GET()

    def do_POST(self):
        if self.path == "/api/chat":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode('utf-8'))
            
            user_msg = payload.get("message")
            day = payload.get("day")
            water = payload.get("waterData")
            elec = payload.get("electricityData")
            
            # Read API Key
            api_key = os.environ.get("GEMINI_API_KEY", "").strip()
            if not api_key:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"reply": "Error: GEMINI_API_KEY is not configured in the .env file."}).encode('utf-8'))
                return
            
            # Extract data safely with helper fallbacks
            elec_actual = elec.get('actual_so_far_kwh') or elec.get('actual_so_far') or 0.0
            elec_projected = elec.get('projected_total_kwh') or elec.get('projected_total') or 0.0
            elec_bill = elec.get('estimated_bill_rm') or elec.get('estimated_bill') or 0.0
            elec_avg = elec.get('daily_avg_kwh') or elec.get('daily_avg') or 0.0
            elec_next = elec.get('next_30m_prediction_kwh') or elec.get('next_prediction') or 0.0
            elec_surge = elec.get('surge_pct') or 0.0
            elec_anomaly_type = elec.get('anomaly_type') or ''

            water_actual = water.get('actual_so_far_liters') or water.get('actual_so_far') or 0.0
            water_projected = water.get('projected_total_liters') or water.get('projected_total') or 0.0
            water_bill = water.get('estimated_bill_rm') or water.get('estimated_bill') or 0.0
            water_pumping_cost = water.get('pumping_electricity_cost_rm') or water.get('pumping_cost') or 0.0
            water_pumping_kwh = water.get('pumping_kwh_used') or 0.0
            water_avg_val = water.get('daily_avg_kl') or water.get('daily_avg') or 0.0
            if water_avg_val < 50:
                water_avg = water_avg_val * 1000
            else:
                water_avg = water_avg_val
            water_next = water.get('next_30m_prediction_liters') or water.get('next_prediction') or 0.0
            water_surge = water.get('surge_pct') or 0.0
            water_anomaly_type = water.get('anomaly_type') or ''

            # Construct system prompt with strict formatting rules
            system_prompt = (
                "You are WateLetric's Utility AI Assistant.\n"
                "Strict formatting rules you MUST follow in your response:\n"
                "1. Never use conversational filler (e.g., 'Hello', 'I would be happy to help', 'Sure, here is'). Get straight to the data immediately.\n"
                "2. Always use Markdown formatting.\n"
                "3. Separate utility types using clear headers and emojis: '⚡️ Electricity' and '💧 Water'.\n"
                "4. Do NOT use bullet points, list markers, asterisks, or dashes (like '*' or '-') for metrics. Put each metric on its own line and separate them with an empty line (double newline).\n"
                "5. Isolate and highlight anomalies: If an anomaly or leak is detected, it MUST be on its own line at the bottom of that utility's section, prefaced with a warning emoji (⚠️ or 🚨) and bolded text.\n\n"
                f"Context for simulated Day {day}:\n"
                "⚡️ Electricity:\n\n"
                f"Actual consumption: {elec_actual:.1f} kWh\n\n"
                f"Projected consumption: {elec_projected:.1f} kWh\n\n"
                f"Estimated bill: RM {elec_bill:.2f}\n\n"
                f"Daily average: {elec_avg:.1f} kWh\n\n"
                f"Next 30 min forecast: {elec_next:.1f} kWh (surge: {elec_surge:.1f}%)\n\n"
                f"{'⚠️ **ANOMALY DETECTED: ' + elec_anomaly_type.upper().replace('_', ' ') + '**\n\n' if elec.get('has_anomaly') else ''}"
                "💧 Water:\n\n"
                f"Actual consumption: {water_actual:.1f} Liters\n\n"
                f"Projected consumption: {water_projected:.1f} Liters\n\n"
                f"Estimated bill: RM {water_bill:.2f}\n\n"
                f"Pumping cost: RM {water_pumping_cost:.2f} (using {water_pumping_kwh:.1f} kWh)\n\n"
                f"Daily average: {water_avg:.1f} Liters\n\n"
                f"Next 30 min forecast: {water_next:.1f} Liters (surge: {water_surge:.1f}%)\n\n"
                f"{'🚨 **ANOMALY DETECTED: ' + water_anomaly_type.upper().replace('_', ' ') + '**\n\n' if water.get('has_anomaly') else ''}"
                "Respond to the user's question adhering strictly to the above formatting and content rules. Answer: "
            )
            
            # Call Gemini API (using gemini-2.5-flash)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            body = {
                "contents": [
                    {
                        "parts": [
                            {"text": system_prompt + user_msg}
                        ]
                    }
                ]
            }
            
            req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    res_body = response.read().decode('utf-8')
                    res_json = json.loads(res_body)
                    
                    # Extract reply
                    reply = res_json['candidates'][0]['content']['parts'][0]['text']
                    
                    # Post-process reply to clean up asterisks and prepare HTML line breaks
                    import re
                    # Convert **bold** to <b>bold</b>
                    reply = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', reply)
                    # Remove leading list markers
                    reply = re.sub(r'^\s*[\*\-]\s+', '', reply, flags=re.MULTILINE)
                    # Remove other stray list markers
                    reply = re.sub(r'\s+[\*\-]\s+', ' ', reply)
                    # Remove all other stray asterisks
                    reply = reply.replace('*', '')
                    # Convert newlines to HTML breaks for chatbot UI
                    reply = reply.replace('\n\n', '<br><br>').replace('\n', '<br>')
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"reply": reply}).encode('utf-8'))
            except urllib.error.HTTPError as e:
                err_msg = e.read().decode('utf-8')
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"reply": f"Gemini API Error {e.code}: {err_msg}"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"reply": f"Internal Server Error: {str(e)}"}).encode('utf-8'))
        elif self.path == "/api/trigger-alert":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode('utf-8'))
            
            utility = payload.get("utility")
            anomaly_type = payload.get("anomaly_type")
            time_str = payload.get("time")
            value = payload.get("value")
            
            # Construct alert message in Markdown
            if utility == "electricity":
                message = (
                    "*CRITICAL FACILITY ALERT*\n\n"
                    "⚡️ *Electricity Anomaly Detected!*\n"
                    "An unusual consumption spike occurred during the live simulation.\n\n"
                    f"*Time:* {time_str}\n"
                    f"*Value:* {value:.1f} kWh\n"
                    "*Status:* Exceeded predicted threshold (XGBoost baseline + 5.0 kWh)."
                )
            else:
                message = (
                    "*CRITICAL FACILITY ALERT*\n\n"
                    "💧 *Water Anomaly Detected!*\n"
                    "Potential water leak detected during the live simulation.\n\n"
                    f"*Time:* {time_str}\n"
                    f"*Value:* {value:.1f} L/hr\n"
                    "*Status:* Exceeded predicted threshold under zero building occupancy."
                )
            
            # Trigger alert
            success = send_telegram_alert(message)
            
            self.send_response(200 if success else 500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success" if success else "error"}).encode('utf-8'))
            return
        else:
            # Let simple HTTP server handle other POST requests normally or send 404
            super().do_POST()

def run(port=8000):
    load_env()
    server_address = ('', port)
    httpd = ThreadingHTTPServer(server_address, UtilityProxyHandler)
    print(f"Starting server on http://localhost:{port}/ ...")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
