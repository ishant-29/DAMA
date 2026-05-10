import argparse
import yaml
import pandas as pd
import os
import sys
import importlib
import json
from datetime import datetime, timedelta
from app.ml.preprocessor import Preprocessor

# Add parent directory to path to allow imports if running from script
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

def load_config(path: str):
    with open(path, 'r') as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="NSE Signal Evaluator")
    parser.add_argument("--config", type=str, required=True, help="Path to evaluation config")
    args = parser.parse_args()

    config = load_config(args.config)
    
    # 1. Load Data
    # In a real app, fetch from DB or usage a DataFetcher service.
    # Here we load from cache
    data_path = config.get('data_path', 'app/data/market_cache.csv')
    if not os.path.exists(data_path):
        print(f"Data not found at {data_path}")
        return

    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    # Ensure date column
    df['date'] = pd.to_datetime(df['date'])
    
    # 2. Preprocessing
    preprocessor = Preprocessor()
    # Group by symbol and process
    X_list = []
    y_list = []
    
    # We need to compute features PER SYMBOL
    for symbol, group in df.groupby('symbol'):
        # Sort by date
        group_input = group.sort_values('date').copy()
        
        # Calculate target (classification)
        # Target: Next 7 days return > 3%
        y_symbol = preprocessor.calculate_target(group_input, lookahead=config.get('lookahead_days', 7))
        
        # Process features
        # Note: process_bars returns X, y (dummy), features. 
        # But we need to align indices carefully. 
        # Ideally Preprocessor returns a DF aligned with input.
        X_sym, _, _ = preprocessor.process_bars(group_input)
        
        # Align y with X (X might have rows dropped due to LAGS)
        common_idx = X_sym.index.intersection(y_symbol.index)
        
        X_list.append(X_sym.loc[common_idx])
        y_list.append(y_symbol.loc[common_idx])
        
    if not X_list:
        print("No data after preprocessing")
        return
        
    X_all = pd.concat(X_list)
    y_all = pd.concat(y_list)
    
    # 3. Train Test Split (Time based)
    # Split date
    split_date = pd.Timestamp.now() - timedelta(days=60) # Last 60 days as test/validation
    # In real world, use config['split_date'] or percentage
    
    # We need dates aligned with X_all. 
    # X_all index is original index from df usually.
    # Let's assume original df index was preserved or reliable.
    # Re-merge date for splitting
    X_all['date'] = df.loc[X_all.index, 'date']
    
    train_mask = X_all['date'] < split_date
    test_mask = X_all['date'] >= split_date
    
    X_train = X_all[train_mask].drop(columns=['date'])
    y_train = y_all[train_mask]
    X_test = X_all[test_mask].drop(columns=['date'])
    y_test = y_all[test_mask]
    
    print(f"Train size: {len(X_train)}, Test size: {len(X_test)}")
    
    # 4. Train Models
    models_to_train = config.get('models', ['xgboost'])
    results = {}
    
    artifacts_dir = config.get('artifacts_path', 'app/artifacts')
    if not os.path.exists(artifacts_dir):
        os.makedirs(artifacts_dir, exist_ok=True)
    
    for model_name in models_to_train:
        print(f"Training {model_name}...")
        try:
            # Dynamic import
            module = importlib.import_module(f"app.ml.ml_models.{model_name}_model")
            # Assume class name is Capitalized model_name + Model, e.g. XgboostModel ?
            # Or simplified: XgboostModel matches file name logic?
            # User prompt implied: xgboost_model.py
            # Let's try to map: xgboost -> XGBoostModel
            
            class_name = "".join([x.capitalize() for x in model_name.split('_')]) + "Model"
            if model_name == 'xgboost': class_name = 'XGBoostModel' # Special case if needed
            
            # Simple fallback / convention
            if hasattr(module, 'XGBoostModel'): ModelClass = module.XGBoostModel
            elif hasattr(module, 'RandomForestModel'): ModelClass = module.RandomForestModel
            else:
                 # Try dynamic
                 ModelClass = getattr(module, class_name)
                 
            model_instance = ModelClass()
            params = model_instance.default_params()
            # Override from config if exists
            if 'params' in config and model_name in config['params']:
                params.update(config['params'][model_name])
                
            res = model_instance.train(X_train, y_train, params, artifacts_dir)
            
            # Evaluate on test
            preds = model_instance.predict(res['model_path'], X_test)
            
            # Simple Metrics
            from sklearn.metrics import roc_auc_score, accuracy_score, precision_score
            binary_preds = (preds > config.get('ml_confidence_threshold', 0.65)).astype(int)
            
            metrics = {
                "roc_auc": float(roc_auc_score(y_test, preds)),
                "accuracy": float(accuracy_score(y_test, binary_preds)),
                "precision": float(precision_score(y_test, binary_preds, zero_division=0))
            }
            
            print(f"Results for {model_name}: {metrics}")
            res['test_metrics'] = metrics
            results[model_name] = res
            
        except Exception as e:
            print(f"Failed to train {model_name}: {e}")
            import traceback
            traceback.print_exc()
            
    # 5. Update Registry
    registry_path = os.path.join(artifacts_dir, 'model_registry.json')
    registry = {}
    if os.path.exists(registry_path):
        with open(registry_path, 'r') as f:
            registry = json.load(f)
            
    for m, data in results.items():
        registry[m] = data
        
    with open(registry_path, 'w') as f:
        json.dump(registry, f, indent=2)
        
    print("Evaluation Complete. Registry updated.")

if __name__ == "__main__":
    main()
