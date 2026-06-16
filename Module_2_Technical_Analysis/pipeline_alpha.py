import os
import pandas as pd
import qlib
from typing import cast
from qlib.config import REG_CN
from qlib.data.dataset.loader import StaticDataLoader
from qlib.data.dataset.handler import DataHandlerLP
from qlib.data.dataset import DatasetH
from qlib.contrib.model.gbdt import LGBModel

# 1️⃣ Initialize Qlib with your data directory
provider_uri = r"/Users/allanaziz/Desktop/ThinkFree/ThinkFree-main/qlib_data"
qlib.init(provider_uri=provider_uri, region=REG_CN)

# 2️⃣ Load your pre-formatted Qlib dataset
data_path = os.path.join(provider_uri, "formatted", "data.pkl")
df = pd.read_pickle(data_path)
print(f"✅ Loaded DataFrame: shape={df.shape}, index.names={df.index.names}")

# Ensure that the 'datetime' level is actual datetime dtype
if not pd.api.types.is_datetime64_any_dtype(df.index.get_level_values('datetime')):
    dates = pd.to_datetime(df.index.get_level_values('datetime'))
    insts = df.index.get_level_values('instrument')
    df.index = pd.MultiIndex.from_arrays([dates, insts], names=['datetime', 'instrument'])
    print("🔧 Converted 'datetime' level to datetime dtype")

# 3️⃣ Ensure columns are MultiIndex: features under 'feature', label under 'label'
if not isinstance(df.columns, pd.MultiIndex) or 'label' not in df.columns.get_level_values(0):
    # Wrap all existing columns as feature group
    feat_cols = df.columns.tolist()
    df_feat = df[feat_cols].copy()
    df_feat.columns = pd.MultiIndex.from_product([['feature'], feat_cols])
    # Create next-day return label
    next_returns = df_feat['feature']['close'].pct_change().shift(-1)
    df_label = next_returns.to_frame('label')
    df_label.columns = pd.MultiIndex.from_product([['label'], ['label']])
    # Concatenate features and label
    df = pd.concat([df_feat, df_label], axis=1)
print(f"🔧 Columns levels: {df.columns.nlevels}")

# 4️⃣ Set up DataLoader and DataHandler
data_loader = StaticDataLoader(config=df)
# Determine date bounds for handler
min_dt = df.index.get_level_values('datetime').min()
max_dt = df.index.get_level_values('datetime').max()
# Format dates as ISO strings where possible
def to_iso(val):
    return val.date().isoformat() if hasattr(val, 'date') else str(val)
min_date = to_iso(min_dt)
max_date = to_iso(max_dt)
handler = DataHandlerLP(
    instruments=None,
    start_time=min_date,
    end_time=max_date,
    data_loader=data_loader,
    infer_processors=[{"class": "Fillna", "kwargs": {"fields_group": "feature"}}],
    learn_processors=[{"class": "DropnaLabel", "kwargs": {}}],
    process_type="append"
)

# 5️⃣ Fit and process the data
# 5️⃣ Automatically update to predict for the latest day
dates = df.index.get_level_values('datetime').unique().sort_values()

if len(dates) < 3:
    # fallback in case of insufficient data
    segments = {'train': (dates[0], dates[0]), 'test': (dates[0], dates[0])}
else:
    train_end = dates[-2]  # Train until second last date
    test_start = dates[-2] # Predict on the last full available day
    test_end = dates[-1]
    segments = {'train': (dates[0], train_end), 'test': (test_start, test_end)}

print(f"🗓 Segments Automatically Set:")
print(f"  ➤ Train: {segments['train'][0]} → {segments['train'][1]}")
print(f"  ➤ Test:  {segments['test'][0]} → {segments['test'][1]}")


# 6️⃣ Create DatasetH with handler and segments
dataset = DatasetH(handler=handler, segments=segments)

# 7️⃣ Prepare slices for inspection
train_df = cast(pd.DataFrame, dataset.prepare('train'))
test_df  = cast(pd.DataFrame, dataset.prepare('test'))
print(f"📊 Train data: type={type(train_df).__name__}, shape={train_df.shape}")
print(f"📊 Test data:  type={type(test_df).__name__}, shape={test_df.shape}")

# 8️⃣ Train a LightGBM model
model = LGBModel()
model.fit(dataset)
print("✅ Model training completed")

# 9️⃣ Generate predictions
preds = model.predict(dataset)
print(f"📈 Predictions: shape={preds.shape}\n", preds.head())

# 🔟 Save predictions
out_csv = os.path.join(provider_uri, 'predictions.csv')
preds.to_csv(out_csv)
print(f"✅ Predictions saved to {out_csv}")










# 📘 PIPELINE OUTPUT EXPLAINED: Qlib Model Training & Prediction

# ✅ Qlib Initialization:
#     - Qlib is successfully initialized using the specified data directory (`qlib_data`).
#     - It confirms that the data is recognized and in the correct format (MultiIndex with 'datetime' and 'instrument').

# ✅ Data Loaded:
#     - A DataFrame is loaded with 120,500 rows and 2 columns, typically including features and target labels.
#     - The 'datetime' level is converted to actual datetime dtype to ensure accurate time-based operations.

# ✅ Data Processing Steps:
#     - Fillna: Missing values are filled or interpolated.
#     - DropnaLabel: Any rows without target labels (used for supervised learning) are dropped.
#     - "fit & process data" combines both feature preparation and alignment with the labels.

# 🗓 Data Segmentation:
#     - The dataset is split into:
#         • 'train': June 21, 2024 to June 18, 2025
#         • 'test':  June 18, 2025 to June 20, 2025
#     - This allows the model to learn patterns from the training set and evaluate performance on unseen data.

# 📊 Training/Testing Set Size:
#     - Train data: 120,018 rows and 3 columns (features + label)
#     - Test data:   964 rows and 3 columns

# ⚙️ Model Training:
#     - A LightGBM (LGBModel) gradient boosting model is trained.
#     - The model runs for 1000 boosting rounds — each round adds one decision tree.
#     - The printed values like `train's l2: 5.66657` show the training loss (mean squared error) decreasing with each round.
#     - Lower L2 loss means better model fit on training data.

# ⚠️ Early Stopping Warning:
#     - Warning: Only training data is provided, so early stopping is disabled.
#     - Normally, a validation set would stop training early if no improvement is seen.

# 🧪 Model Experiment Tracking:
#     - Qlib creates a new experiment and assigns it a unique ID.
#     - It attempts to log the state of the current Git repository, but errors are shown since the project isn't under Git version control.
#     - These Git warnings are non-critical and can be ignored unless using Qlib's version tracking.

# 📈 Predictions:
#     - The model generates predictions for the test set (964 rows).
#     - Each prediction is tied to a stock ticker (instrument) and a specific date.
#     - Example: On 2025-06-18, AAPL is predicted to move -0.027855 (a relative movement indicator).

# 💾 Output:
#     - The predictions are saved to `predictions.csv` inside the `qlib_data` directory.
#     - This CSV file can be used for further tasks like ranking stocks, portfolio selection, or backtesting.
