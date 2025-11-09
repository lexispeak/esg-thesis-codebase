import pandas as pd
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error

def train_xgb(X: pd.DataFrame, y: pd.Series, random_state=42):
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=random_state)
    model = XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.07, subsample=0.9, colsample_bytree=0.9, random_state=random_state)
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    return {
        "model": model,
        "metrics": {"r2": float(r2_score(y_test, pred)), "mae": float(mean_absolute_error(y_test, pred))}
    }
