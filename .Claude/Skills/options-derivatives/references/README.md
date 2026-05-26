# Options Derivatives Reference

## Black-Scholes Model Overview

The Black-Scholes model is used to calculate the theoretical price of European-style options. It was developed by Fischer Black, Myron Scholes, and Robert Merton in 1973.

### Key Assumptions

1. European exercise (can only be exercised at expiration)
2. No dividends during the option's life
3. Markets are efficient (no arbitrage opportunities)
4. No transaction costs or taxes
5. Risk-free rate and volatility are constant
6. Returns are normally distributed

## The Greeks Explained

### Delta (Δ)
- **Range**: -1 to 1
- **Call Delta**: 0 to 1
- **Put Delta**: -1 to 0
- **Meaning**: Change in option price for $1 change in underlying
- **Use**: Hedge ratio, probability approximation
- **Example**: Delta of 0.60 means option gains $0.60 when stock rises $1

### Gamma (Γ)
- **Range**: 0 to ∞
- **Same for calls and puts**
- **Meaning**: Rate of change of Delta
- **Use**: Measures Delta stability, risk management
- **Peak**: ATM options have highest Gamma
- **Note**: High Gamma means Delta changes rapidly

### Theta (Θ)
- **Usually negative** (except deep ITM puts)
- **Meaning**: Time decay per day
- **Use**: Measures how much option value erodes daily
- **Peak**: ATM options have highest Theta (most time value)
- **Strategy**: Option sellers benefit from Theta decay

### Vega (ν)
- **Range**: 0 to ∞
- **Same for calls and puts**
- **Meaning**: Change in option price for 1% change in implied volatility
- **Use**: Volatility risk management
- **Peak**: ATM options have highest Vega
- **Note**: Long options benefit from volatility increases

### Rho (ρ)
- **Call Rho**: Positive
- **Put Rho**: Negative
- **Meaning**: Change in option price for 1% change in interest rate
- **Use**: Interest rate risk (usually minor for short-term options)
- **Note**: More significant for long-dated options

## Moneyness Classification

### For Call Options:
- **ITM (In-the-Money)**: S > K (has intrinsic value)
- **ATM (At-the-Money)**: S ≈ K (no intrinsic value, maximum time value)
- **OTM (Out-of-the-Money)**: S < K (no intrinsic value)

### For Put Options:
- **ITM (In-the-Money)**: S < K (has intrinsic value)
- **ATM (At-the-Money)**: S ≈ K (no intrinsic value, maximum time value)
- **OTM (Out-of-the-Money)**: S > K (no intrinsic value)

## Important Formulas

### Black-Scholes Pricing

```
d₁ = [ln(S/K) + (r + σ²/2)T] / (σ√T)
d₂ = d₁ - σ√T

Call Price = S·N(d₁) - K·e^(-rT)·N(d₂)
Put Price = K·e^(-rT)·N(-d₂) - S·N(-d₁)
```

Where:
- S = Current stock price
- K = Strike price
- T = Time to expiration (years)
- r = Risk-free interest rate
- σ = Volatility (annualized)
- N(x) = Cumulative standard normal distribution

### Put-Call Parity

```
C - P = S - K·e^(-rT)
```

This relationship must hold for European options to prevent arbitrage.

## Trading Strategies Using Greeks

### Delta Neutral
- **Goal**: Portfolio Delta = 0
- **Method**: Balance long/short positions
- **Use**: Profit from Gamma or Theta without directional risk

### Gamma Scalping
- **Goal**: Profit from Delta changes
- **Method**: Continuously rehedge Delta
- **Works best**: High Gamma positions, volatile markets

### Theta Farming
- **Goal**: Collect time decay
- **Method**: Sell options (covered calls, cash-secured puts)
- **Risk**: Unlimited losses if not hedged

### Vega Trading
- **Goal**: Profit from volatility changes
- **Long Vega**: Buy options, expect volatility increase
- **Short Vega**: Sell options, expect volatility decrease

## Limitations of Black-Scholes

1. **Volatility is not constant**: Real markets show volatility smile/skew
2. **Markets are not frictionless**: Transaction costs and taxes exist
3. **Dividends matter**: Must adjust for dividend-paying stocks
4. **Early exercise**: American options can be exercised before expiration
5. **Fat tails**: Market returns have more extreme events than normal distribution
6. **Interest rates vary**: Rates are not constant in practice

## Practical Considerations

### Time Conversion
- **Days to years**: Days / 365
- **Weeks to years**: Weeks / 52
- **Months to years**: Months / 12

### Percentage Conversion
- **20% volatility** → 0.20
- **5% interest rate** → 0.05

### Volatility Estimates
- **Historical Volatility**: Calculate from past price data
- **Implied Volatility**: Back out from market option prices
- **ATM IV**: Often used as baseline volatility measure

### Risk-Free Rate
- Common choices: US Treasury rates matching option expiration
- Short-term: T-bills (< 1 year)
- Long-term: T-notes/bonds (> 1 year)

## Further Reading

- **Books**:
  - "Options, Futures, and Other Derivatives" by John Hull
  - "Option Volatility and Pricing" by Sheldon Natenberg
  - "The Concepts and Practice of Mathematical Finance" by Mark Joshi

- **Research Papers**:
  - Black, F., & Scholes, M. (1973). "The Pricing of Options and Corporate Liabilities"
  - Merton, R. C. (1973). "Theory of Rational Option Pricing"

- **Online Resources**:
  - CBOE Options Institute
  - Khan Academy - Options and Derivatives
  - Investopedia Options Guide
