import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION
# ---------------------------------------------------------
st.set_page_config(page_title="MacroStress Test", page_icon="📈", layout="wide")
st.title("MacroStress Test Engine")
st.markdown(
    "This is a personal project designed for advanced portfolio stress testing and tail-risk analysis. The program uses Correlated Monte Carlo simulations to generate thousands of possible future price paths and integrates the Merton Jump-Diffusion model to capture sudden, extreme market crashes (fat tails) rather than just normal distributions. \n The underlying mechanism is also powered by a data-driven risk classifier. By dynamically evaluating historical volatility and Average Daily Trading Volume (ADTV), the engine autonomously applies quantitative brakes—deploying an absolute volatility shield for defensive assets and strict liquidity slippage penalties for highly speculative equities. Combined with a stressed correlation matrix, this tool transforms complex mathematical models into an uncompromising, highly realistic assessment of maximum drawdown under extreme macroeconomic headwinds. \n \n Made by Khang Dang")
st.divider()

# ---------------------------------------------------------
# 2. SIDEBAR - CONFIGURATION
# ---------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 1. Portfolio Configuration")
    tickers_input = st.text_input("Enter Tickers (comma-separated):", value="JNJ, WMT, PG")
    tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

    weights_input = st.text_input("Corresponding Weights:", value="0.33, 0.33, 0.34")
    try:
        weights = [float(w.strip()) for w in weights_input.split(",") if w.strip()]
        weights = np.array(weights) / np.sum(weights)
    except:
        st.error("Invalid weights!")
        st.stop()

    initial_investment = st.number_input("Initial Investment:", min_value=1000000, value=100000000, step=5000000)

    st.header("🌪️ 2. Macroeconomic Shocks")
    scenario = st.selectbox(
        "Stress Scenario:",
        ["Normal Market Conditions", "Hawkish Policy (Interest Rate Shock)", "Stagflation (High Inflation & Low Growth)",
         "Black Swan Crash (Liquidity Crisis)"]
    )

    if scenario == "Hawkish Policy (Interest Rate Shock)":
        base_drift_shock = -0.15
        vol_multiplier = 1.35
        corr_stress = 0.5
        base_jump_intensity = 3
        base_jump_mean = -0.05
        base_jump_vol = 0.02
        max_liquidity_penalty = 0.05
    elif scenario == "Stagflation (High Inflation & Low Growth)":
        base_drift_shock = -0.20
        vol_multiplier = 1.50
        corr_stress = 0.7
        base_jump_intensity = 5
        base_jump_mean = -0.07
        base_jump_vol = 0.03
        max_liquidity_penalty = 0.08
    elif scenario == "Black Swan Crash (Liquidity Crisis)":
        base_drift_shock = -0.35
        vol_multiplier = 2.00
        corr_stress = 0.95
        base_jump_intensity = 10
        base_jump_mean = -0.10
        base_jump_vol = 0.05
        max_liquidity_penalty = 0.15
    else:
        base_drift_shock, vol_multiplier, corr_stress = 0.0, 1.0, 0.0
        base_jump_intensity, base_jump_mean, base_jump_vol, max_liquidity_penalty = 0, 0.0, 0.0, 0.0

    st.header("🎲 3. Simulation Parameters")
    sim_days = st.slider("Time Horizon (Trading Days):", 30, 252, 90)
    num_simulations = st.slider("Number of Monte Carlo Paths:", 1000, 10000, 3000, step=1000)


# ---------------------------------------------------------
# 3. DATA PIPELINE & CLASSIFIER (FULLY DYNAMIC)
# ---------------------------------------------------------
@st.cache_data(ttl=300)
def fetch_market_data(tickers_list):
    close_dict = {}
    vol_dict = {}
    for ticker in tickers_list:
        try:
            data = yf.download(ticker, period="2y", progress=False, threads=False)
            if data is not None and not data.empty:
                if isinstance(data.columns, pd.MultiIndex):
                    close_dict[ticker] = data['Close'].iloc[:, 0]
                    vol_dict[ticker] = data['Volume'].iloc[:, 0]
                else:
                    close_dict[ticker] = data['Close']
                    vol_dict[ticker] = data['Volume']
        except Exception:
            continue
            
    if close_dict and vol_dict:
        return pd.DataFrame(close_dict), pd.DataFrame(vol_dict)
    return pd.DataFrame(), pd.DataFrame()

with st.spinner("Fetching data individually to bypass Cloud rate-limits..."):
    prices_raw, volumes_raw = fetch_market_data(tickers)

if prices_raw.empty or len(prices_raw.columns) != len(tickers):
    st.error(f"🚨 API Cloud Blocked: Could not fetch data for all {len(tickers)} tickers. Please wait a moment and refresh.")
    st.stop()

prices = prices_raw.dropna()
volumes = volumes_raw.loc[prices.index].fillna(0)

if prices.empty or len(prices) < 2:
    st.error("🚨 API Cloud Failed: Data is empty after strict cleaning. Please refresh.")
    st.stop()

daily_returns = prices.pct_change().dropna()
historical_vols = daily_returns.std().values * np.sqrt(252)
historical_corr = daily_returns.corr().values

historical_corr = np.nan_to_num(historical_corr, nan=0.0)
np.fill_diagonal(historical_corr, 1.0)

mu = daily_returns.mean().values * 252

adtv = np.nan_to_num((prices.tail(90).mean() * volumes.tail(90).mean()).values, nan=1e-8)

# --- ULTIMATE CLASSIFIER ALGORITHM ---
if scenario != "Normal Market Conditions":
    try:
        spy_data = yf.download("SPY", period="2y", progress=False, threads=False)
        if isinstance(spy_data.columns, pd.MultiIndex):
            spy_close = spy_data['Close'].iloc[:, 0]
        else:
            spy_close = spy_data['Close']
            
        spy_vol = float(np.squeeze(spy_close.pct_change().dropna().std())) * np.sqrt(252)
        if np.isnan(spy_vol) or spy_vol == 0:
            spy_vol = 0.15
    except:
        spy_vol = 0.15

    raw_rel_risk = np.nan_to_num(historical_vols / spy_vol, nan=1.0)
    rel_risk = np.clip(raw_rel_risk, 0.4, 2.5)

    jump_intensity_arr = np.where(historical_vols < 0.25, 0, base_jump_intensity * np.log1p(rel_risk))
    jump_mean_arr = np.clip(base_jump_mean * rel_risk, -0.20, 0.0)
    jump_vol_arr = base_jump_vol * rel_risk

    drift_multiplier = np.where(rel_risk < 1, rel_risk ** 1.5, rel_risk)
    drift_shock_arr = base_drift_shock * drift_multiplier

    global_adtv_benchmark = 50_000_000 if tickers[0].isalpha() else 1_200_000_000_000
    base_penalty = 0.005
    liquidity_penalty_arr = base_penalty * (global_adtv_benchmark / np.maximum(adtv, 1e-8))
    liquidity_penalty_arr = np.clip(liquidity_penalty_arr, base_penalty, max_liquidity_penalty)

    mu_shocked = mu + drift_shock_arr
    panic_matrix = np.ones_like(historical_corr)
    stressed_corr = (1 - corr_stress) * historical_corr + corr_stress * panic_matrix
    shocked_vols = historical_vols * vol_multiplier
    cov_shocked = np.outer(shocked_vols, shocked_vols) * stressed_corr
else:
    jump_intensity_arr = np.zeros(len(tickers))
    jump_mean_arr = np.zeros(len(tickers))
    jump_vol_arr = np.zeros(len(tickers))
    liquidity_penalty_arr = np.zeros(len(tickers))
    mu_shocked = mu
    cov_shocked = np.outer(historical_vols, historical_vols) * historical_corr
    stressed_corr = historical_corr 

with st.expander("🔍 View Personalized Risk Classification Report (Full Dynamic)", expanded=False):
    classifier_df = pd.DataFrame({
        'Ticker': tickers,
        'Relative Risk Proxy (vs SPY)': np.round(historical_vols / spy_vol if scenario != "Normal Market Conditions" else historical_vols / 0.15, 2),
        'Liquidity Penalty (Slippage)': [f"{p * 100:.2f}%" for p in liquidity_penalty_arr],
        'Macro Drift Shock': [f"{d * 100:.2f}%" for d in (mu_shocked - mu)],
        'Jump Intensity (per year)': np.round(jump_intensity_arr, 1),
        'Jump Severity (Mean)': [f"{jm * 100:.2f}%" for jm in jump_mean_arr]
    })
    st.dataframe(classifier_df, use_container_width=True)

# ---------------------------------------------------------
# 4. CORE ENGINE (SAFE BROADCASTING & VECTORIZATION)
# ---------------------------------------------------------
@st.cache_data
def run_ultimate_quant_engine(mu_vec, cov_mat, weights_vec, initial_val, days, n_sims,
                              lambda_j_arr, mu_j_arr, sigma_j_arr, liq_penalty_arr):
    num_assets = len(weights_vec)
    dt = 1 / 252

    cov_mat = np.nan_to_num(cov_mat, nan=0.0)

    try:
        L = np.linalg.cholesky(cov_mat)
    except np.linalg.LinAlgError:
        eigenvalues, eigenvectors = np.linalg.eigh(cov_mat)
        cov_mat_fixed = eigenvectors @ np.diag(np.maximum(eigenvalues, 1e-8)) @ eigenvectors.T
        L = np.linalg.cholesky(cov_mat_fixed)

    simulated_paths = np.zeros((days + 1, n_sims))
    simulated_paths[0] = initial_val
    asset_prices = np.zeros((days + 1, num_assets, n_sims))
    asset_prices[0] = 1.0

    Z = np.random.normal(0, 1, size=(days, num_assets, n_sims))
    Poisson_Jumps = np.zeros((days, num_assets, n_sims))
    Jump_Sizes = np.zeros((days, num_assets, n_sims))

    for i in range(num_assets):
        lam = lambda_j_arr[i]
        if np.isnan(lam) or lam < 0: 
            lam = 0.0
        Poisson_Jumps[:, i, :] = np.random.poisson(lam * dt, size=(days, n_sims))
        
        m_j = np.nan_to_num(mu_j_arr[i])
        s_j = np.nan_to_num(sigma_j_arr[i])
        Jump_Sizes[:, i, :] = np.random.normal(m_j, s_j, size=(days, n_sims))

    for t in range(1, days + 1):
        epsilon = L @ Z[t - 1]
        drift = (mu_vec - 0.5 * np.diag(cov_mat)) * dt
        diffusion = epsilon * np.sqrt(dt)
        jumps = Poisson_Jumps[t - 1] * Jump_Sizes[t - 1]

        step_returns = np.exp(drift[:, np.newaxis] + diffusion + jumps)
        asset_prices[t] = asset_prices[t - 1] * step_returns

        penalized_prices = asset_prices[t] * (1 - liq_penalty_arr)[:, np.newaxis]
        simulated_paths[t] = initial_val * np.tensordot(weights_vec, penalized_prices, axes=(0, 0))

    return simulated_paths

simulated_paths = run_ultimate_quant_engine(
    mu_shocked, cov_shocked, weights, initial_investment, sim_days, num_simulations,
    jump_intensity_arr, jump_mean_arr, jump_vol_arr, liquidity_penalty_arr
)

# ---------------------------------------------------------
# 5. DASHBOARD & VISUALIZATION
# ---------------------------------------------------------
final_values = simulated_paths[-1, :]
percentage_returns = (final_values / initial_investment - 1) * 100
var_95_val = np.percentile(final_values, 5)
var_95_pct = np.percentile(percentage_returns, 5)
cvar_95_val = final_values[final_values <= var_95_val].mean()
cvar_95_pct = percentage_returns[percentage_returns <= var_95_pct].mean()
prob_of_loss = np.mean(final_values < initial_investment) * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("Expected Value (Mean)", f"{np.mean(final_values):,.0f}",
            f"{(np.mean(final_values) / initial_investment - 1) * 100:.2f}%")
col2.metric("VaR 95%", f"{var_95_val:,.0f}", f"{var_95_pct:.2f}%", delta_color="inverse")
col3.metric("CVaR 95% (Expected Shortfall)", f"{cvar_95_val:,.0f}", f"{cvar_95_pct:.2f}%", delta_color="inverse")
col4.metric("Probability of Loss", f"{prob_of_loss:.1f}%", "Danger" if prob_of_loss > 50 else "Safe",
            delta_color="inverse" if prob_of_loss > 50 else "normal")

st.divider()
tab1, tab2, tab3 = st.tabs(["📉 Monte Carlo Paths", "📊 Returns Distribution", "🔍 Correlation Matrices"])

with tab1:
    fig_paths = go.Figure()
    sample_indices = np.random.choice(num_simulations, size=100, replace=False)
    for idx in sample_indices:
        fig_paths.add_trace(
            go.Scatter(y=simulated_paths[:, idx], mode='lines', line=dict(width=0.8, color='rgba(70, 130, 180, 0.4)'),
                       showlegend=False))
    fig_paths.add_trace(go.Scatter(y=[initial_investment] * (sim_days + 1), mode='lines', name='Initial Capital',
                                   line=dict(color='yellow', width=2, dash='dash')))
    
    # BẢN VÁ LỖI ÉP BIỂU ĐỒ TRÊN ĐIỆN THOẠI: Đẩy Legend lên trên cùng nằm ngang
    fig_paths.update_layout(
        template="plotly_dark", 
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        )
    )
    st.plotly_chart(fig_paths, use_container_width=True, key="mc_paths_chart") 

with tab2:
    fig_hist = px.histogram(x=final_values, nbins=60, color_discrete_sequence=['#1f77b4'])
    
    # BẢN VÁ LỖI ĐÈ CHỮ: Phân chia top left (Trái trên) và bottom right (Phải dưới)
    fig_hist.add_vline(x=var_95_val, line_width=3, line_dash="dash", line_color="red",
                       annotation_text=f"VaR 95%: {var_95_pct:.1f}%", annotation_position="top left")
    
    fig_hist.add_vline(x=initial_investment, line_width=2, line_color="yellow", 
                       annotation_text="Breakeven", annotation_position="top right")
                       
    fig_hist.update_layout(template="plotly_dark")
    st.plotly_chart(fig_hist, use_container_width=True, key="mc_hist_chart") 

with tab3:
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**(1) Historical Correlation Matrix**")
        fig_corr_1 = px.imshow(historical_corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
        fig_corr_1.update_layout(template="plotly_dark")
        st.plotly_chart(fig_corr_1, use_container_width=True, key="corr_matrix_hist") 
    with c2:
        st.markdown("**(2) Stressed (Panic) Correlation Matrix**")
        fig_corr_2 = px.imshow(stressed_corr, text_auto=".2f", color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
        fig_corr_2.update_layout(template="plotly_dark")
        st.plotly_chart(fig_corr_2, use_container_width=True, key="corr_matrix_stress")
