import json, pickle, pandas as pd, numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import shap

with open('outputs/models/xgb.pkl','rb') as f:
    model = pickle.load(f)
labels = pd.read_csv('data/labels/financials.csv')

mapped_file = next(Path('data/mapped').glob('*.mapped.jsonl'))
rows = [json.loads(l) for l in open(mapped_file, 'r', encoding='utf-8') if l.strip()]
df = pd.DataFrame(rows)
X = df.pivot_table(index=[], columns='schema_field', values='value', aggfunc='last').reset_index(drop=True)
X = X.select_dtypes(include='number').fillna(0)

explainer = shap.TreeExplainer(model)
sv = explainer.shap_values(X)

sector = labels.get('sector', pd.Series(['Banking']*len(X)))
if len(sector) != len(X):
    sector = pd.Series(['Banking']*len(X))

abs_sv = np.abs(sv)
feat_names = X.columns.tolist()

stats = []
for s in pd.Series(sector).unique():
    idx = (pd.Series(sector)==s).values
    if idx.sum()==0: continue
    mean_abs = abs_sv[idx].mean(axis=0)
    top_idx = np.argsort(-mean_abs)[:15]
    for i in top_idx:
        stats.append({'sector': s, 'feature': feat_names[i], 'mean_abs_shap': float(mean_abs[i])})
stats_df = pd.DataFrame(stats).sort_values(['sector','mean_abs_shap'], ascending=[True, False])
print(stats_df.head(30))
