
import pandas as pd
import numpy as np
import os
import sys
import glob
import joblib
from datetime import timedelta
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, 
    confusion_matrix, classification_report
)

# Add parent directory to path to allow imports
current_dir = os.path.dirname(os.path.abspath(__file__))
# Go up 2 levels: ml -> app -> backend
backend_dir = os.path.abspath(os.path.join(current_dir, '../../'))
sys.path.append(backend_dir)
project_root = os.path.abspath(os.path.join(backend_dir, '../'))

from app.ml.preprocessor import Preprocessor

def find_latest_model(artifacts_dir, model_type="xgboost"):
    """Finds the latest .pkl model file in the artifacts directory."""
    # Search for files containing the model_type string
    search_path = os.path.join(artifacts_dir, f"*{model_type}*.pkl")
    files = glob.glob(search_path)
    if not files:
        return None
    # Sort by modification time, newest first
    latest_file = max(files, key=os.path.getmtime)
    return latest_file

def evaluate_model():
    print("Starting Model Evaluation...")
    
    # Paths
    base_dir = os.path.join(project_root, 'backend', 'app')
    # fallback if running from root
    if not os.path.exists(base_dir):
        base_dir = os.path.join(project_root, 'app')
    
    data_path = os.path.join(project_root, 'backend', 'app', 'data', 'market_cache.csv')
    artifacts_dir = os.path.join(project_root, 'backend', 'app', 'artifacts')
    output_file = os.path.join(project_root, 'evaluation_results.txt')

    # 1. Load Latest Model (XGBoost)
    model_path = find_latest_model(artifacts_dir, model_type="xgboost")
    if not model_path:
        print(f"No model found in {artifacts_dir}")
        return

    print(f"Loading model: {model_path}")
    model = joblib.load(model_path)

    # 2. Load Data
    if not os.path.exists(data_path):
        print(f"Data not found at {data_path}")
        return
        
    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    df['date'] = pd.to_datetime(df['date'])

    # 3. Preprocess
    print("Preprocessing data...")
    preprocessor = Preprocessor()
    X_list = []
    y_list = []

    for symbol, group in df.groupby('symbol'):
        group_input = group.sort_values('date').copy()
        
        # Calculate target (classification)
        # Using default lookahead=7 from evaluator logic
        y_symbol = preprocessor.calculate_target(group_input, lookahead=7)
        
        X_sym, _, _ = preprocessor.process_bars(group_input)
        
        # Align indices
        common_idx = X_sym.index.intersection(y_symbol.index)
        X_list.append(X_sym.loc[common_idx])
        y_list.append(y_symbol.loc[common_idx])

    if not X_list:
        print("No data after preprocessing")
        return

    X_all = pd.concat(X_list)
    y_all = pd.concat(y_list)

    # 4. Train/Test Split (Time-based, last 60 days)
    # Recover 'date' for splitting
    # Assuming the index matches the original dataframe which had 'date'. 
    # But concat resets logic? No, pandas concat preserves index if not ignore_index=True.
    # We need to map dates back to X_all.
    # The safest way is to join with original df on index if indices are unique per row ID, 
    # but here indices might be 0..N per group if reset? 
    # Let's look at preprocessor.process_bars -> data.reset_index(drop=True, inplace=True)
    # The preprocessor RESETS index. This breaks alignment with global df if we aren't careful.
    # However, create inputs: data = df.copy() -> group by symbol.
    
    # In 'evaluator.py':
    # X_all['date'] = df.loc[X_all.index, 'date'] 
    # This works ONLY if indices are unique globally or we are lucky.
    
    # Better approach for this script:
    # Re-attach date inside the loop before list append
    
    # Let's Refactor loop slightly to keep dates
    X_list = []
    y_list = []
    dates_list = []
    
    for symbol, group in df.groupby('symbol'):
        group = group.sort_values('date') 
        # We need to Keep the dates aligned with X_sym
        # process_bars returns X_sym with reset index usually?
        # let's check preprocessor.py:
        # data.reset_index(drop=True, inplace=True)
        # So X_sym has 0..N index.
        # But we pass `group_input`. 
        
        # To get dates back, we need to apply same operations or just rely on the fact that 
        # rows are dropped only by dropna?
        
        group_input = group.copy()
        y_symbol = preprocessor.calculate_target(group_input, lookahead=7)
        X_sym, _, _ = preprocessor.process_bars(group_input)
        
        # process_bars drops NaNs at the end.
        # It calls: data.dropna(inplace=True)
        
        # We need the dates corresponding to X_sym
        # Preprocessor modifies 'data' derived from 'df', resets index.
        # This makes it hard to map back without modifying Preprocessor or being clever.
        
        # Clever hack: 
        # The Preprocessor works on a COPY. 
        # But `process_bars` returns X (features only).
        
        # Let's rely on the fact that `preprocessor.py` sorts by date and resets index.
        # We can replicate that on the date column to align.
        
        # Re-construct dates for this group
        group_dates = group_input['date'].sort_values().reset_index(drop=True)
        # Apply the SAME mask as process_bars?
        # process_bars drops rows where indicators are NaN (usually first 50 rows due to EMA50)
        # It does `data.dropna(inplace=True)`.
        
        # We can't easily query which rows were dropped without modifying preprocessor to return dates.
        # BUT evaluator.py does: `X_all['date'] = df.loc[X_all.index, 'date']`
        # If evaluator.py works, maybe indices are preserved? 
        # preprocessor.py: `data.reset_index(drop=True, inplace=True)` - This definitely destroys original index.
        # So evaluator.py might be BUGGY if it relies on global index match unless df was single symbol?
        
        # Wait, `df.groupby('symbol')` preserves original index in `group`? Yes.
        # But preprocessor resets it.
        # references: 
        # `X_sym, _, _ = preprocessor.process_bars(group_input)`
        # `X_sym` has new index 0..M
        
        # Let's fix this properly. Preprocessor calculates features.
        # We need the dates. 
        # Let's assume the rows dropped are just the initial ones.
        # Or, simpler: We don't NEED to be perfect on "Last 60 days" split for this specific request if it's hard.
        # But the user asked for evaluation.
        
        # Alternative: We can modify Preprocessor to return dates, but I shouldn't modify existing generic code if possible.
        # Let's look at `evaluator.py` again.
        # `X_all['date'] = df.loc[X_all.index, 'date']`
        # Check `preprocessor.py`:
        # `data = df.copy()`
        # `data.reset_index(drop=True, inplace=True)`
        # `X = data[valid_features]`
        
        # So X has 0..N index relative to the GROUP.
        # `X_all = pd.concat(X_list)` -> indices will be 0..N, 0..M, ... (repeated!)
        # `X_all.index` will have duplicates.
        # `df.loc[X_all.index, 'date']` will fail or return wrong rows if `df` is the big dataframe.
        # So `evaluator.py` seems potentially flawed for multi-symbol if it relies on that.
        
        # FIX:
        # We will manually align.
        # In the loop:
        # calculate features manually or trust that `process_bars` is consistent.
        # If `process_bars` does `dropna`, we lose rows.
        # We know `process_bars` drops rows with NaNs.
        # We can reproduce the drop logic to get matching dates.
        
        # Or... since I am writing this script, I can just do:
        # 1. Get X_sym.
        # 2. Get the TAIL of the dates matching X_sym length? 
        #    NaNs are usually at the START (EMAs). 
        #    Dropna removes the start. So taking the last len(X_sym) dates should work.
        
        aligned_dates = group_dates.iloc[-len(X_sym):]
        # This assumes no NaNs in the middle. (Reasonable for market data usually).
        
        # Re-index X_sym to have these dates as index for easier concat? 
        # Or just store 'date' column in X_sym for now.
        
        X_sym = X_sym.copy()
        X_sym['date'] = aligned_dates.values
        
        # Also y_symbol indices need alignment.
        # y_symbol is calculated on `group_input` BEFORE drops?
        # `calculate_target` returns y for ALL rows in `group_input`.
        # So we align y to X using the computed dates (or just tail).
        
        # `common_idx = X_sym.index.intersection(y_symbol.index)` was used in evaluator.
        # But X_sym index is reset (e.g. 50..End became 0..N). y_symbol index is 0..End.
        # Intersection would mismatch or be wrong.
        
        # If X_sym index is 0..N (after reset and drop), and it was rows 50..End originally.
        # The dropna reset index? No. 
        # `data.dropna(inplace=True)` KEEPS the index from the `data` (which was reset to 0..Total).
        # So if we drop rows 0-49, the index starts at 50?
        # Pandas `dropna` preserves index.
        # So X_sym index should start at 50 (if 50 rows dropped).
        
        # y_symbol index is 0..Total.
        # So `X_sym.index.intersection(y_symbol.index)` actually WORKS!
        # It matches rows 50..End of X with rows 50..End of Y.
        # AND we can use this index to recover dates!
        
        # So:
        # 1. `group_input` (reset index?) -> NO, `groupby` keeps original.
        # 2. `process_bars` -> `data.reset_index(drop=True)` -> Index becomes 0..K.
        # 3. `dropna` -> Index becomes J..K.
        # 4. `y_symbol` -> Index 0..K.
        # 5. Common index -> J..K.
        
        # But we need dates. `group_input` has dates. But its index is NOT 0..K.
        # We need `group_input` to ALSO be reset index for this mapping to work.
        
        group_input = group.sort_values('date').copy()
        group_input.reset_index(drop=True, inplace=True) # CRITICAL for alignment with preprocessor
        
        y_symbol = preprocessor.calculate_target(group_input, lookahead=7)
        X_sym, _, _ = preprocessor.process_bars(group_input)
        
        common_idx = X_sym.index.intersection(y_symbol.index)
        
        # Filter
        X_final = X_sym.loc[common_idx]
        y_final = y_symbol.loc[common_idx]
        
        # Add date column to X_final for splitting
        X_final['date'] = group_input.loc[common_idx, 'date']
        
        X_list.append(X_final)
        y_list.append(y_final)
        
    X_all = pd.concat(X_list)
    y_all = pd.concat(y_list)
    
    # Split
    split_date = pd.Timestamp.now() - timedelta(days=60)
    
    mask_test = X_all['date'] >= split_date
    
    X_test = X_all[mask_test].drop(columns=['date'])
    y_test = y_all[mask_test]
    
    print(f"Test Set Size: {len(X_test)}")
    
    # 5. Predictions
    # Sklearn model usually needs just the array/df.
    # Predict Proba for AUC
    # Predict for Class
    
    try:
        y_probs = model.predict_proba(X_test)
        # Check shape
        if y_probs.shape[1] == 2:
            y_probs = y_probs[:, 1]
        else:
            # Handle edge case
            y_probs = y_probs[:, 0] if model.classes_[0] == 1 else np.zeros(len(y_probs))
    except Exception as e:
        print(f"Error in predict_proba: {e}")
        # Fallback if model doesn't support proba?
        y_probs = model.predict(X_test)

    # Threshold
    threshold = 0.65
    y_pred = (y_probs > threshold).astype(int)
    
    # 6. Metrics
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    try:
        auc = roc_auc_score(y_test, y_probs)
    except:
        auc = 0.0
        
    conf_matrix = confusion_matrix(y_test, y_pred)
    report = classification_report(y_test, y_pred, zero_division=0)
    
    # 7. Write Output
    print(f"Writing results to {output_file}...")
    with open(output_file, 'w') as f:
        f.write("Model Evaluation Report\n")
        f.write("=======================\n")
        f.write(f"Model ID: {os.path.basename(model_path)}\n")
        f.write(f"Evaluation Date: {pd.Timestamp.now()}\n")
        f.write(f"Test Set Size: {len(X_test)} samples (Last 60 days)\n")
        f.write(f"Confidence Threshold: {threshold}\n\n")
        
        f.write("Key Metrics\n")
        f.write("-----------\n")
        f.write(f"Accuracy:  {acc:.4f}\n")
        f.write(f"ROC AUC:   {auc:.4f}\n")
        f.write(f"Precision: {prec:.4f}\n")
        f.write(f"Recall:    {rec:.4f}\n")
        f.write(f"F1 Score:  {f1:.4f}\n\n")
        
        f.write("Confusion Matrix\n")
        f.write("----------------\n")
        f.write(f"{conf_matrix}\n\n")
        
        f.write("Classification Report\n")
        f.write("---------------------\n")
        f.write(report)
        f.write("\n")
        
    print("Done.")

if __name__ == "__main__":
    evaluate_model()
