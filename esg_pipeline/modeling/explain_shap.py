import shap, numpy as np, pandas as pd

def shap_values(model, X: pd.DataFrame):
    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(X)
    base = float(explainer.expected_value)
    return sv, base
