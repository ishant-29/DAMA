from sklearn.ensemble import RandomForestClassifier
import pickle
import os
import joblib
from datetime import datetime

class RandomForestModel:
    def default_params(self):
        return {
            "n_estimators": 100,
            "max_depth": 10,
            "random_state": 42
        }

    def train(self, X, y, params, artifacts_dir):
        model = RandomForestClassifier(**params)
        model.fit(X, y)
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"random_forest_model__v{timestamp}.pkl"
        path = os.path.join(artifacts_dir, filename)
        
        # Save
        joblib.dump(model, path)
        print(f"Saved Random Forest model to {path}")
        
        return {
            "model_path": path,
            "timestamp": timestamp,
            "params": params,
            "type": "random_forest"
        }

    def predict(self, model_path, X):
        model = joblib.load(model_path)
        probs = model.predict_proba(X)
        
        if probs.shape[1] == 2:
            return probs[:, 1]
        else:
            # Handle single class case (e.g. only 0s in training)
            # model.classes_ will contain [0] or [1]
            if model.classes_[0] == 1:
                return probs[:, 0]
            else:
                # Class 0 present, so prob of 1 is 0
                import numpy as np
                return np.zeros(probs.shape[0])

    def load(self, model_path):
        self.model = joblib.load(model_path)
        return self.model
