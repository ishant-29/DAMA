import os
import pandas as pd
import glob
import joblib
import logging
from datetime import timedelta
import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, 
    confusion_matrix
)
from app.ml.preprocessor import Preprocessor

logger = logging.getLogger(__name__)

class EvaluatorService:
    def __init__(self):
        # Resolve paths relative to backend/app/services/
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.app_dir = os.path.abspath(os.path.join(current_dir, '..'))
        self.artifacts_dir = os.path.join(self.app_dir, 'artifacts')
        self.data_path = os.path.join(self.app_dir, 'data', 'market_cache.csv')

    def find_latest_model(self, model_type="xgboost"):
        """Finds the latest .pkl model file in the artifacts directory."""
        search_path = os.path.join(self.artifacts_dir, f"*{model_type}*.pkl")
        files = glob.glob(search_path)
        if not files:
            return None
        return max(files, key=os.path.getmtime)

    def run_evaluation(self) -> dict:
        """
        Runs the evaluation pipeline and returns metrics.
        """
        logger.info("Starting On-Demand Model Evaluation...")
        
        # 1. Load Model
        model_path = self.find_latest_model(model_type="xgboost")
        if not model_path:
            return {"status": "error", "message": "No XGBoost model found."}

        try:
            model = joblib.load(model_path)
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return {"status": "error", "message": f"Model load failed: {str(e)}"}

        # 2. Load Data
        if not os.path.exists(self.data_path):
            return {"status": "error", "message": "market_cache.csv not found."}

        try:
            df = pd.read_csv(self.data_path)
            df['date'] = pd.to_datetime(df['date'])
        except Exception as e:
            return {"status": "error", "message": f"Data load failed: {str(e)}"}

        # 3. Preprocess
        preprocessor = Preprocessor()
        X_list = []
        y_list = []

        # Group processing to avoid data leakage mixing symbols
        for symbol, group in df.groupby('symbol'):
            # Preprocessor expects sorted data
            group_input = group.sort_values('date').copy()
            group_input.reset_index(drop=True, inplace=True) 
            
            # Calculate target (classification)
            y_symbol = preprocessor.calculate_target(group_input, lookahead=7)
            X_sym, _, _ = preprocessor.process_bars(group_input)
            
            # Align indices
            common_idx = X_sym.index.intersection(y_symbol.index)
            
            X_final = X_sym.loc[common_idx]
            y_final = y_symbol.loc[common_idx]
            
            # Attach date for splitting
            X_final = X_final.copy()
            X_final['date'] = group_input.loc[common_idx, 'date'].values
            
            X_list.append(X_final)
            y_list.append(y_final)

        if not X_list:
            return {"status": "error", "message": "No valid data after preprocessing."}

        X_all = pd.concat(X_list)
        y_all = pd.concat(y_list)

        # 4. Train/Test Split (Time-based, last 60 days)
        split_date = pd.Timestamp.now() - timedelta(days=60)
        mask_test = X_all['date'] >= split_date
        
        if not mask_test.any():
            return {"status": "error", "message": "No test data available in last 60 days."}

        X_test = X_all[mask_test].drop(columns=['date'])
        y_test = y_all[mask_test]

        # 5. Predictions
        try:
            y_probs = model.predict_proba(X_test)
            if y_probs.shape[1] == 2:
                y_probs = y_probs[:, 1]
            else:
                y_probs = y_probs[:, 0] if hasattr(model, 'classes_') and model.classes_[0] == 1 else np.zeros(len(y_probs))
        except Exception:
            # Fallback
            y_probs = model.predict(X_test)

        threshold = 0.65
        y_pred = (y_probs > threshold).astype(int)

        # 6. Metrics
        metrics = {
            "status": "success",
            "model_name": os.path.basename(model_path),
            "test_sample_size": len(X_test),
            "accuracy": round(accuracy_score(y_test, y_pred), 4),
            "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
            "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
            "f1_score": round(f1_score(y_test, y_pred, zero_division=0), 4),
            "confusion_matrix": confusion_matrix(y_test, y_pred).tolist()
        }
        
        try:
            metrics["auc"] = round(roc_auc_score(y_test, y_probs), 4)
        except:
            metrics["auc"] = 0.0
            
        return metrics
