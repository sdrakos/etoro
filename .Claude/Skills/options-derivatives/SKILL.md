---
name: options-derivatives
description: Calculate options pricing and Greeks using Black-Scholes model and other derivatives analytics
---

# Options Derivatives Calculator

This skill provides comprehensive options derivatives calculations including pricing and risk metrics (Greeks).

## Capabilities

You can calculate:

### 1. Black-Scholes Option Pricing
- **Call Option Price**: Price of European call options
- **Put Option Price**: Price of European put options

### 2. The Greeks
- **Delta (Δ)**: Rate of change of option price with respect to underlying asset price
- **Gamma (Γ)**: Rate of change of delta with respect to underlying asset price
- **Theta (Θ)**: Rate of change of option price with respect to time (time decay)
- **Vega (ν)**: Rate of change of option price with respect to volatility
- **Rho (ρ)**: Rate of change of option price with respect to interest rate

### 3. Additional Metrics
- **Implied Volatility**: Calculate the implied volatility from a given option price
- **Intrinsic Value**: The immediate exercise value of the option
- **Time Value**: The premium over intrinsic value
- **Probability of Profit**: Estimated probability the option will be profitable at expiration

## Required Parameters

When a user asks to calculate option derivatives, gather these parameters:

1. **S** - Current stock/underlying price
2. **K** - Strike price
3. **T** - Time to expiration (in years)
4. **r** - Risk-free interest rate (as decimal, e.g., 0.05 for 5%)
5. **σ (sigma)** - Volatility (as decimal, e.g., 0.20 for 20%)
6. **option_type** - 'call' or 'put'

## Instructions

When the user requests options calculations:

1. **Gather Parameters**: Ask for any missing parameters listed above
2. **Use the Python Script**: Execute the `calculate_options.py` script in the scripts/ folder
3. **Present Results Clearly**: Format the output in a readable table or structured format
4. **Explain the Results**: Briefly explain what each Greek means in practical terms if requested

## Example Interactions

**User**: "Calculate a call option with S=100, K=105, T=0.5 years, r=5%, volatility=20%"

**You should**:
- Run the calculation script with these parameters
- Display: Option Price, Delta, Gamma, Theta, Vega, Rho
- Optionally explain what these values mean for the trader

**User**: "What's the delta of a put option, stock at $50, strike $55, 3 months to expiry, 3% interest rate, 25% volatility"

**You should**:
- Convert 3 months to years (0.25)
- Run calculation for put option
- Highlight the Delta value and explain it

## Usage Tips

- Always convert percentages to decimals (20% → 0.20)
- Convert days/months to years for time parameter
- Explain that these are theoretical values based on Black-Scholes assumptions
- Mention limitations: works for European options, assumes constant volatility, etc.

## Formulas Reference

The script implements:

### Black-Scholes Formula
```
d1 = [ln(S/K) + (r + σ²/2)T] / (σ√T)
d2 = d1 - σ√T

Call Price = S·N(d1) - K·e^(-rT)·N(d2)
Put Price = K·e^(-rT)·N(-d2) - S·N(-d1)
```

### Greeks Formulas
- **Delta Call**: N(d1)
- **Delta Put**: N(d1) - 1
- **Gamma**: φ(d1) / (S·σ·√T)
- **Theta Call**: -(S·φ(d1)·σ)/(2√T) - rK·e^(-rT)·N(d2)
- **Theta Put**: -(S·φ(d1)·σ)/(2√T) + rK·e^(-rT)·N(-d2)
- **Vega**: S·φ(d1)·√T
- **Rho Call**: K·T·e^(-rT)·N(d2)
- **Rho Put**: -K·T·e^(-rT)·N(-d2)

Where:
- N(x) = Cumulative standard normal distribution
- φ(x) = Standard normal probability density function
