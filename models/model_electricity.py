import pandas as pd 
import json
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error

# Load dataset
with open("data/mock_dataset_electricity_30days.json") as f:
    data = json.load(f)

df = pd.DataFrame(data)

# Map day_of_week string to numeric value (0-6)
day_map = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
df["day_of_week"] = df["day_of_week"].map(day_map)

# Map time (HH:MM string) to numeric hours (e.g. "12:30" -> 12.5)
df["time"] = df["time"].apply(lambda x: int(x.split(":")[0]) + int(x.split(":")[1]) / 60.0)

# Create lag features. Since the dataset is sampled every 30 minutes, 
# there are 48 records per day.
df["lag_1"] = df["electricity_kwh"].shift(1)
df["lag_2"] = df["electricity_kwh"].shift(2)        # 1 hour ago
df["lag_24"] = df["electricity_kwh"].shift(48)      # 24 hours ago
df["lag_48"] = df["electricity_kwh"].shift(96)      # 48 hours ago
df["lag_weekly"] = df["electricity_kwh"].shift(336)  # 7 days ago (weekly patterns)

# Drop rows with NaN in the required lag features (drops first week of data, keeping normal records with NaN for optional anomalies)
df = df.dropna(subset=["lag_1", "lag_24", "lag_weekly"])

features = ["time", "day_of_week", "lag_1", "lag_2", "lag_24", "lag_48", "lag_weekly", "occupancy"]
X = df[features]
y = df["electricity_kwh"]

# Split train/test (80% train, 20% test without shuffling to preserve time order)
train_idx = int(len(df) * 0.8)
df_train = df.iloc[:train_idx]
df_test = df.iloc[train_idx:]

# Filter out anomalies ONLY from the training set so the model learns clean patterns
df_train_clean = df_train[df_train["anomaly"].fillna(False) != True]

X_train = df_train_clean[features]
y_train = df_train_clean["electricity_kwh"]
X_test = df_test[features]
y_test = df_test["electricity_kwh"]

# Train XGBoost with optimized hyperparameters
model = XGBRegressor(
    n_estimators=100,
    learning_rate=0.05,
    max_depth=5,
    random_state=42
    
)

model.fit(X_train, y_train)

# Make predictions and evaluate
predictions = model.predict(X_test)
mae = mean_absolute_error(y_test, predictions)

print(f"MAE: {mae:.4f}")

