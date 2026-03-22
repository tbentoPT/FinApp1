import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from itertools import product

# Set Page Config
st.set_page_config(layout="wide", page_title="Professional Financial Stress-Tester")

# Fix for large dataframe rendering
pd.set_option("styler.render.max_elements", 1000000)

# --- UI SIDEBAR: BASE INPUTS ---
st.sidebar.header("1. Base Case Product Inputs")

product_data = []
products = ["Indoor CU", "Indoor EXT", "Outdoor CU", "Outdoor EXT"]
default_prices = [3600.0, 1800.0, 5350.0, 2000.0]
default_vols = [1000, 2000, 6000, 18000]

for i, p in enumerate(products):
    with st.sidebar.expander(f"📦 {p}"):
        price = st.number_input(f"Price (€)", value=default_prices[i], key=f"p_{i}")
        vol = st.number_input(f"Volume", value=default_vols[i], key=f"v_{i}")
        gm = st.slider(f"Gross Margin %", 0, 100, 45, key=f"gm_{i}") / 100
        product_data.append({"name": p, "price": price, "vol": vol, "gm": gm})

st.sidebar.header("2. Operational Inputs")
fte = st.sidebar.number_input("# FTE", value=400)
cost_per_fte = st.sidebar.number_input("€/FTE", value=60000.0)
ga_month = st.sidebar.number_input("G&A/Month", value=750000.0)
depreciation = st.sidebar.number_input("Depreciation", value=650000.0)
interest = st.sidebar.number_input("Interest Income", value=50000.0)
tax_rate = st.sidebar.number_input("Tax Rate %", value=20.0) / 100

st.sidebar.header("3. Working Capital")
dso_v = st.sidebar.number_input("DSO", value=10)
dio_v = st.sidebar.number_input("DIO", value=5)
dpo_v = st.sidebar.number_input("DPO", value=10)

st.sidebar.header("4. Simulation Deltas (%)")
num_steps = 10 
d_price = st.sidebar.slider("Price Delta % (±)", 0.0, 20.0, 5.0) / 100
d_vol = st.sidebar.slider("Volume Delta % (±)", 0.0, 20.0, 10.0) / 100
d_gm = st.sidebar.slider("GM Delta % (±)", 0.0, 20.0, 5.0) / 100
d_wages = st.sidebar.slider("Wages Delta % (±)", 0.0, 20.0, 15.0) / 100
d_ga = st.sidebar.slider("G&A Delta % (±)", 0.0, 20.0, 10.0) / 100

# --- THE CALCULATION ENGINE ---
def calc_engine(p_m, v_m, gm_m, w_m, ga_m):
    total_rev = 0
    total_cogs = 0
    for p in product_data:
        p_rev = (p['price'] * p_m) * (p['vol'] * v_m)
        p_cogs = p_rev * (1 - (p['gm'] * gm_m))
        total_rev += p_rev
        total_cogs += p_cogs
    
    wages = (fte * cost_per_fte) * w_m
    ga = (ga_month * 12) * ga_m
    
    ebit = total_rev - total_cogs - wages - ga - depreciation
    ebt = ebit + interest
    tax = max(0, ebt * tax_rate)
    net_profit = ebt - tax
    
    rec = (dso_v / 365) * total_rev
    inv = (dio_v / 365) * total_cogs
    pay = (dpo_v / 365) * (total_cogs + ga)
    total_cf = net_profit + depreciation - (rec + inv - pay)
    
    return net_profit, total_cf

# --- SIMULATION EXECUTION ---
@st.cache_data
def run_sim(p_d, v_d, g_d, w_d, a_d, p_data, steps_n):
    steps = [np.linspace(1-p_d, 1+p_d, steps_n), np.linspace(1-v_d, 1+v_d, steps_n), 
             np.linspace(1-g_d, 1+g_d, steps_n), np.linspace(1-w_d, 1+w_d, steps_n), 
             np.linspace(1-a_d, 1+a_d, steps_n)]
    combos = list(product(*steps))
    data = []
    for p, v, g, w, a in combos:
        np_val, cf_val = calc_engine(p, v, g, w, a)
        data.append({
            "P_Mult": p, "V_Mult": v, "G_Mult": g, "W_Mult": w, "A_Mult": a,
            "Price Δ": f"{round((p-1)*100,1)}%", "Vol Δ": f"{round((v-1)*100,1)}%",
            "GM Δ": f"{round((g-1)*100,1)}%", "Wages Δ": f"{round((w-1)*100,1)}%",
            "G&A Δ": f"{round((a-1)*100,1)}%", "Net Profit": np_val, "Total CF": cf_val
        })
    return pd.DataFrame(data)

df = run_sim(d_price, d_vol, d_gm, d_wages, d_ga, product_data, num_steps)

# --- DASHBOARD LAYOUT ---
st.title("Strategic Financial Stress-Tester")

# SECTION: BASE CASE & RISK
st.header("Base Case & Risk Analysis")
base_np, base_cf = calc_engine(1.0, 1.0, 1.0, 1.0, 1.0)
loss_scenarios = len(df[df['Net Profit'] < 0])
risk_pct = (loss_scenarios / len(df)) * 100

col_b1, col_b2, col_b3 = st.columns([1,1,2])
col_b1.metric("Base Net Profit", f"€{base_np:,.0f}")
col_b2.metric("Base Total CF", f"€{base_cf:,.0f}")
col_b3.metric("Probability of Loss", f"{risk_pct:.1f}%", f"{loss_scenarios:,} failure scenarios", delta_color="inverse")

# SECTION: SENSITIVITY ANALYSIS
with st.expander("🔍 Run Variable Sensitivity Analysis"):
    st.write("Impact calculation: Red = Negative impact on Profit | Green = Positive impact on Profit.")
    # Calculate Correlation
    corr_df = df[['P_Mult', 'V_Mult', 'G_Mult', 'W_Mult', 'A_Mult', 'Net Profit']].corr()['Net Profit'].drop('Net Profit').reset_index()
    corr_df.columns = ['Variable', 'Correlation']
    corr_df['Impact'] = corr_df['Correlation'].apply(lambda x: 'Positive' if x > 0 else 'Negative')
    corr_df['Variable'] = ["Price", "Volume", "Gross Margin", "Wages", "G&A"]
    
    fig_sens = px.bar(corr_df.sort_values(by='Correlation'), x='Correlation', y='Variable', 
                      orientation='h', color='Impact',
                      color_discrete_map={'Positive': '#00CC96', 'Negative': '#EF553B'},
                      title="Sensitivity Analysis (Profit Impact)")
    st.plotly_chart(fig_sens, use_container_width=True)

# SECTION: HISTOGRAMS
st.divider()
st.header(f"Distribution of {len(df):,} Scenarios")
df['NP_Status'] = df['Net Profit'].apply(lambda x: 'Profit (≥0)' if x >= 0 else 'Loss (<0)')
df['CF_Status'] = df['Total CF'].apply(lambda x: 'Cash Pos (≥0)' if x >= 0 else 'Cash Neg (<0)')
color_map = {'Profit (≥0)': '#00CC96', 'Loss (<0)': '#EF553B', 
             'Cash Pos (≥0)': '#00CC96', 'Cash Neg (<0)': '#EF553B'}

tab1, tab2 = st.tabs(["Net Profit Distribution", "Cash Flow Distribution"])
with tab1:
    fig_np = px.histogram(df, x="Net Profit", nbins=100, color='NP_Status', color_discrete_map=color_map)
    st.plotly_chart(fig_np, use_container_width=True)
with tab2:
    fig_cf = px.histogram(df, x="Total CF", nbins=100, color='CF_Status', color_discrete_map=color_map)
    st.plotly_chart(fig_cf, use_container_width=True)

# SECTION: QUARTILE EXPLORER
st.divider()
st.header("Scenario Data Explorer")
df['Quartile'] = pd.qcut(df['Net Profit'], 4, labels=["1st (Bottom 25%)", "2nd", "3rd", "4th (Top 25%)"])
sel_q = st.selectbox("View Quartile in Table:", options=["1st (Bottom 25%)", "2nd", "3rd", "4th (Top 25%)"], index=3)

df_view = df[df['Quartile'] == sel_q].drop(columns=['NP_Status', 'CF_Status', 'Quartile', 'P_Mult', 'V_Mult', 'G_Mult', 'W_Mult', 'A_Mult'])
st.dataframe(df_view.style.format({"Net Profit": "€{:,.0f}", "Total CF": "€{:,.0f}"}), use_container_width=True)

st.divider()
csv = df_view.to_csv(index=False).encode('utf-8')
st.download_button("📥 Download This Quartile as CSV", data=csv, file_name="scenario_extract.csv", mime="text/csv")