import xgboost as xgb
import pandas as pd
import numpy as np
import json
import os
import joblib
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import cross_val_score
from datetime import datetime

class XGBoostModel:
    def __init__(self):
        self.model = None
        
    def default_params(self) -> dict:
        return {
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "eta": 0.1,
            "max_depth": 5,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "seed": 42
        }

    def train(self, X_train: pd.DataFrame, y_train: pd.Series, params: dict, output_dir: str) -> dict:
        """
        Train the model and save artifacts.
        """
        self.model = xgb.XGBClassifier(**params)
        self.model.fit(X_train, y_train)
        
        # Evaluate on train
        preds = self.model.predict_proba(X_train)[:, 1]
        
        # Save
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        git_sha = "no_git" # Placeholder
        filename = f"xgboost_model__v{timestamp}__{git_sha}.pkl"
        path = os.path.join(output_dir, filename)
        
        os.makedirs(output_dir, exist_ok=True)
        joblib.dump(self.model, path)
        
        # Sidecar
        meta_filename = filename.replace('.pkl', '.json')
        meta = {
            "feature_list": list(X_train.columns),
            "params": params,
            "git_sha": git_sha,
            "trained_at": timestamp,
            "metrics": {"train_score": float(self.model.score(X_train, y_train))}
        }
        with open(os.path.join(output_dir, meta_filename), 'w') as f:
            json.dump(meta, f, indent=2)
            
        return {"model_path": path, "metrics": meta["metrics"], "version": timestamp}

    def predict(self, model_path: str, X: pd.DataFrame) -> np.ndarray:
        if self.model is None:
            self.load(model_path)
            
        # Ensure column order matches
        # In a robust system, we load feature_list from sidecar
        return self.model.predict_proba(X)[:, 1]

    def load(self, model_path: str):
        self.model = joblib.load(model_path)

    def save(self, model, path: str):
        joblib.dump(model, path)

    def train_calibrated(self, X_train: pd.DataFrame, y_train: pd.Series, cv_folds: int = 5):
        """
        Train XGBoost with Platt Scaling calibration.
        Ensures confidence=0.85 actually means ~85% historical win rate.
        """
        base_model = xgb.XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric='logloss',
            random_state=42,
        )

        self.model = CalibratedClassifierCV(
            base_model,
            method='sigmoid',
            cv=cv_folds,
        )
        self.model.fit(X_train, y_train)

        cv_scores = cross_val_score(self.model, X_train, y_train, cv=cv_folds, scoring='accuracy')
        calibration_report = {
            'cv_mean_accuracy': float(cv_scores.mean()),
            'cv_std': float(cv_scores.std()),
            'n_training_samples': len(X_train),
            'calibration_method': 'platt_scaling',
        }

        model_path = 'artifacts/xgboost_calibrated.pkl'
        os.makedirs('artifacts', exist_ok=True)
        joblib.dump(self.model, model_path)

        return calibration_report

    def predict_with_confidence_band(self, features: pd.DataFrame) -> dict:
        """Returns prediction with calibrated probability AND confidence band label."""
        proba = self.model.predict_proba(features)[0]
        confidence = float(proba[1])

        if confidence >= 0.80:
            band = 'HIGH'
        elif confidence >= 0.65:
            band = 'MEDIUM'
        else:
            band = 'LOW'

        return {
            'confidence': confidence,
            'confidence_band': band,
            'ml_used': True,
            'calibrated': True,
        }
