import streamlit as st
import pandas as pd
st.set_page_config(page_title="ESG Thesis Dashboard", layout="wide")
st.title("ESG Extraction Coverage")
uploaded = st.file_uploader("Upload mapped JSONL", type=["jsonl"])
if uploaded:
    rows = [pd.read_json(l, typ="series").to_dict() for l in uploaded if l]
    df = pd.DataFrame(rows)
    st.write("Records:", len(df))
    if "schema_field" in df.columns:
        cov = df.groupby("schema_field").agg(count=("schema_field","count"), avg_conf=("confidence","mean")).reset_index()
        st.dataframe(cov)
