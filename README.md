# WateLetric - Smart Utility Management Platform

WateLetric is an AI-powered smart utility management and monitoring platform designed for non-domestic and industrial facilities. It dynamically monitors energy and water usage, forecasts future loads using local Machine Learning models (XGBoost), flags anomalies, and integrates with Google Gemini for context-aware explanations and optimizations.

---

## ⚡️ Key Features

*   **Dual-Utility Dashboards:** Separate, specialized dashboards for Electricity (TNB Industrial Tariff D) and Water (Air Selangor Commercial Tariff & Pumping Cost evaluations).
*   **Predictive ML Forecasting:** Uses local **XGBoost Regressors** trained on 30 days of historical patterns to generate expected baseline predictions for future load mapping.
*   **Real-time Sensor Simulation:** Continuous live playback simulator that feeds chart visualizations and triggers anomaly detection metrics (cooling load spikes, water leaks).
*   **Automated Facility Alerting:** Integrated Telegram Bot notification webhook dispatching Markdown critical alerts dynamically to facility operators when anomalies occur.
*   **Context-Aware AI Assistant:** Integrated chat panel ("Berry Assistant") proxying to the **Google Gemini API** (`gemini-2.5-flash`) that consumes the active browser metrics to recommend real-time billing optimizations.
*   **Secure Authentication:** Integrated **Firebase Auth** setup supporting registration, credential validation, route protection states, and developer bypass modes.

---

## 📂 Project Structure

```text
├── .env                              # API keys, Telegram Bot Tokens, & Firebase settings
├── db_init.py                        # Database setup & initial static data seeding script
├── run_agent.py                      # ML training, forecasting computation, & data synchronization
├── server.py                         # HTTP file server, Gemini chat proxy, & alert endpoint
├── utility_data.db                   # Local SQLite3 database storing metrics & daily summaries
├── system_design.md                  # Comprehensive architectural blueprint & system flows
├── data/                             # JSON datasets and active simulation streams
│   ├── mock_dataset_electricity_30days.json
│   ├── mock_dataset_water_30days.json
│   ├── runtime_data_electric.json
│   └── runtime_data_water.json
├── models/                           # Validation/training scripts for model baselines
│   ├── model_electricity.py
│   └── model_water.py
└── public/                           # Frontend assets and web server directory root
    ├── index.html                    # Authentication Portal / Landing page
    ├── summary.html                  # Unified dual-utility analytics dashboard
    ├── electricity.html              # Electricity consumption & forecast dashboard
    ├── water.html                    # Water leakage, usage, & pumping metrics dashboard
    ├── profile.html                  # User account details settings panel
    ├── design.html                   # HTML layout design mockup
    ├── billing_data.js               # Static JS cache containing compiled forecast data
    └── firebase-mock.js              # Local mock wrapper fallback for offline development
```

---

## ⚙️ Configuration & Secrets

Configure local API keys and bot webhooks by creating/editing the `.env` file in the root directory:

```env
GEMINI_API_KEY=your_google_gemini_api_key_here
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here
FIREBASE_API_KEY=your_firebase_api_key_here
PROJECT_ID=your_firebase_project_id_here
PROJECT_NUMBER=your_firebase_project_number_here
```

*Note: If `TELEGRAM_BOT_TOKEN` or `TELEGRAM_CHAT_ID` are left unconfigured, the system automatically redirects alert payloads to safe, local standard output logging (Simulation Mode).*

---

## 🚀 Quick Start Guide

Follow these steps to install dependencies, train the forecasting models, initialize records, and host the web dashboard locally.

### 1. Prerequisite Installations
Ensure you have Python 3 installed. Install the necessary machine learning, data engineering, and environment variables packages:
```bash
pip install pandas numpy xgboost python-dotenv
```

### 2. Initialize the SQLite Database
Create the database tables and populate them with the initial static dashboard records:
```bash
python db_init.py
```

### 3. Run the Predictive Forecasting Pipeline
Train the XGBoost baseline forecasting models and compute projected billing costs, monthly aggregates, and anomalies:
```bash
python run_agent.py
```
*Note: This script generates updated configurations and overrides `billing_data.js` and `utility_data.db`.*

### 4. Deploy the Local Web Server
Start the multi-threaded backend server with unbuffered logging outputs (`-u`):
```bash
python -u server.py
```

### 5. Access the Platform
Open your browser and navigate to:
```text
http://localhost:8000/index.html
```
Use the **"Bypass / Demo Sign In"** button to log in instantly using cached details, or use **Firebase Auth** for registration.
