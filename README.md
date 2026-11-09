# MacroStress Test Engine

## Overview
This is a personal quantitative finance project built to test how investment portfolios hold up under extreme macroeconomic shocks. Standard financial models often assume that market returns follow a predictable bell curve. This engine assumes they don't. 

Instead, it actively simulates "fat-tail" events—sudden market crashes, liquidity dry-ups, and panic selling—to provide a more realistic assessment of maximum drawdown. 

**Note:** This project originally started as a Python Streamlit web application and was later migrated and scaled into a Vercel application.

## How It Works (Core Mechanics)

The engine doesn't just apply a flat negative return to the portfolio. It dynamically calculates risk using historical data and applies several quantitative layers:

### 1. Correlated Monte Carlo Simulation
Assets don't move in a vacuum. The engine generates thousands of possible future price paths over a set time horizon. It uses Cholesky decomposition on the historical covariance matrix to ensure that the simulated assets move together exactly as they do in the real world.

### 2. Merton Jump-Diffusion Model
To fix the "bell curve lie," the engine combines standard Brownian motion (normal daily price fluctuations) with a Poisson jump process. This means that at any random point in the simulation, an asset can experience a sudden, violent drop in price, accurately mimicking real-world market shocks.

### 3. Dynamic Risk Classifier
The tool autonomously evaluates the historical volatility of each inputted ticker against a benchmark (SPY). 
* **Defensive assets** (low relative risk) receive a volatility shield.
* **Speculative assets** (high relative risk) are assigned higher jump intensities and heavier mean drops during a crisis.

### 4. Liquidity Slippage Penalty
In a real market panic, you can't always sell at the quoted price. The engine calculates the Average Daily Trading Volume (ADTV) for each asset. If a stock is highly illiquid, a mathematical penalty is applied to its simulated returns to account for the slippage you would face trying to exit the position.

### 5. Stressed Correlation Matrix
During a financial crisis, diversification often fails because the correlation between all assets approaches 1.0. When a severe macro scenario is selected, the engine artificially tightens the correlation matrix, forcing assets to crash together.

## Stress Scenarios
Users can test their portfolio against different predefined macroeconomic headwinds:
* **Hawkish Policy (Interest Rate Shock):** Moderate drift shock, slight volatility increase.
* **Stagflation (High Inflation & Low Growth):** Heavier drift shock, higher jump intensity.
* **Black Swan (Liquidity Crisis):** Extreme volatility multiplier, near-perfect correlation across all assets, and severe liquidity penalties.

## Key Risk Metrics Output
After running the simulation, the dashboard outputs standard institutional risk metrics:
* **Expected Value:** The mean portfolio value across all simulated paths.
* **VaR 95% (Value at Risk):** The threshold where there is a 5% chance the portfolio will perform worse than this number.
* **CVaR 95% (Expected Shortfall):** The average expected loss *if* the portfolio falls beyond the VaR threshold (answering: "If things go really bad, exactly how bad will it get?").
* **Probability of Loss:** The mathematical percentage chance of ending up with less money than the initial investment.

Vercel link: https://macro-stress-test-engine.vercel.app

Streamlit link: https://macrostress-test-engine.streamlit.app
