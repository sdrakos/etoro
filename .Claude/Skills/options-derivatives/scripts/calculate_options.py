#!/usr/bin/env python3
"""
Options Derivatives Calculator
Calculates Black-Scholes option prices and Greeks
"""

import math
import sys
import json
from typing import Dict, Tuple


def normal_cdf(x: float) -> float:
    """Cumulative distribution function for the standard normal distribution"""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def normal_pdf(x: float) -> float:
    """Probability density function for the standard normal distribution"""
    return math.exp(-x**2 / 2.0) / math.sqrt(2.0 * math.pi)


def calculate_d1_d2(S: float, K: float, T: float, r: float, sigma: float) -> Tuple[float, float]:
    """Calculate d1 and d2 for Black-Scholes formula"""
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return d1, d2


def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculate Black-Scholes call option price"""
    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)
    call_price = S * normal_cdf(d1) - K * math.exp(-r * T) * normal_cdf(d2)
    return call_price


def black_scholes_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Calculate Black-Scholes put option price"""
    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)
    put_price = K * math.exp(-r * T) * normal_cdf(-d2) - S * normal_cdf(-d1)
    return put_price


def calculate_greeks(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> Dict[str, float]:
    """Calculate all Greeks for the option"""
    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)

    # Delta
    if option_type.lower() == 'call':
        delta = normal_cdf(d1)
    else:
        delta = normal_cdf(d1) - 1

    # Gamma (same for calls and puts)
    gamma = normal_pdf(d1) / (S * sigma * math.sqrt(T))

    # Theta (annualized, divide by 365 for daily)
    if option_type.lower() == 'call':
        theta = (-(S * normal_pdf(d1) * sigma) / (2 * math.sqrt(T))
                 - r * K * math.exp(-r * T) * normal_cdf(d2))
    else:
        theta = (-(S * normal_pdf(d1) * sigma) / (2 * math.sqrt(T))
                 + r * K * math.exp(-r * T) * normal_cdf(-d2))

    # Vega (same for calls and puts, typically divided by 100 for 1% change)
    vega = S * normal_pdf(d1) * math.sqrt(T)

    # Rho (typically divided by 100 for 1% change)
    if option_type.lower() == 'call':
        rho = K * T * math.exp(-r * T) * normal_cdf(d2)
    else:
        rho = -K * T * math.exp(-r * T) * normal_cdf(-d2)

    return {
        'delta': delta,
        'gamma': gamma,
        'theta': theta,
        'theta_daily': theta / 365,  # Daily theta
        'vega': vega,
        'vega_percent': vega / 100,  # Vega for 1% volatility change
        'rho': rho,
        'rho_percent': rho / 100  # Rho for 1% interest rate change
    }


def calculate_option_metrics(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> Dict:
    """Calculate comprehensive option metrics"""

    # Price
    if option_type.lower() == 'call':
        price = black_scholes_call(S, K, T, r, sigma)
        intrinsic_value = max(S - K, 0)
    else:
        price = black_scholes_put(S, K, T, r, sigma)
        intrinsic_value = max(K - S, 0)

    time_value = price - intrinsic_value

    # Greeks
    greeks = calculate_greeks(S, K, T, r, sigma, option_type)

    # Moneyness
    if option_type.lower() == 'call':
        if S > K:
            moneyness = "ITM (In-the-Money)"
        elif S == K:
            moneyness = "ATM (At-the-Money)"
        else:
            moneyness = "OTM (Out-of-the-Money)"
    else:
        if S < K:
            moneyness = "ITM (In-the-Money)"
        elif S == K:
            moneyness = "ATM (At-the-Money)"
        else:
            moneyness = "OTM (Out-of-the-Money)"

    # Probability of being ITM at expiration (approximate)
    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)
    if option_type.lower() == 'call':
        prob_itm = normal_cdf(d2)
    else:
        prob_itm = normal_cdf(-d2)

    return {
        'option_type': option_type.upper(),
        'price': price,
        'intrinsic_value': intrinsic_value,
        'time_value': time_value,
        'moneyness': moneyness,
        'probability_itm': prob_itm * 100,
        **greeks
    }


def format_output(results: Dict, S: float, K: float, T: float, r: float, sigma: float) -> str:
    """Format results for display"""
    output = []
    output.append("=" * 70)
    output.append("OPTIONS DERIVATIVES CALCULATOR - BLACK-SCHOLES MODEL")
    output.append("=" * 70)
    output.append("")

    output.append("INPUT PARAMETERS:")
    output.append(f"  Underlying Price (S):     ${S:.2f}")
    output.append(f"  Strike Price (K):         ${K:.2f}")
    output.append(f"  Time to Expiration (T):   {T:.4f} years ({T*365:.0f} days)")
    output.append(f"  Risk-free Rate (r):       {r*100:.2f}%")
    output.append(f"  Volatility (σ):           {sigma*100:.2f}%")
    output.append(f"  Option Type:              {results['option_type']}")
    output.append("")

    output.append("-" * 70)
    output.append("OPTION VALUATION:")
    output.append("-" * 70)
    output.append(f"  Option Price:             ${results['price']:.4f}")
    output.append(f"  Intrinsic Value:          ${results['intrinsic_value']:.4f}")
    output.append(f"  Time Value:               ${results['time_value']:.4f}")
    output.append(f"  Moneyness:                {results['moneyness']}")
    output.append(f"  Probability ITM:          {results['probability_itm']:.2f}%")
    output.append("")

    output.append("-" * 70)
    output.append("THE GREEKS:")
    output.append("-" * 70)
    output.append(f"  Delta (Δ):                {results['delta']:.4f}")
    output.append(f"    → For $1 increase in stock, option changes by ${results['delta']:.4f}")
    output.append("")
    output.append(f"  Gamma (Γ):                {results['gamma']:.4f}")
    output.append(f"    → Delta changes by {results['gamma']:.4f} for $1 stock move")
    output.append("")
    output.append(f"  Theta (Θ):                {results['theta']:.4f} (annual)")
    output.append(f"                            {results['theta_daily']:.4f} (daily)")
    output.append(f"    → Option loses ${abs(results['theta_daily']):.4f} per day (time decay)")
    output.append("")
    output.append(f"  Vega (ν):                 {results['vega']:.4f}")
    output.append(f"                            {results['vega_percent']:.4f} (per 1% vol change)")
    output.append(f"    → Option changes by ${results['vega_percent']:.4f} for 1% volatility change")
    output.append("")
    output.append(f"  Rho (ρ):                  {results['rho']:.4f}")
    output.append(f"                            {results['rho_percent']:.4f} (per 1% rate change)")
    output.append(f"    → Option changes by ${results['rho_percent']:.4f} for 1% rate change")
    output.append("")
    output.append("=" * 70)

    return "\n".join(output)


def main():
    """Main function to parse arguments and calculate options"""
    if len(sys.argv) < 7:
        print("Usage: python calculate_options.py <S> <K> <T> <r> <sigma> <option_type>")
        print("  S: Current stock price")
        print("  K: Strike price")
        print("  T: Time to expiration (years)")
        print("  r: Risk-free rate (decimal, e.g., 0.05 for 5%)")
        print("  sigma: Volatility (decimal, e.g., 0.20 for 20%)")
        print("  option_type: 'call' or 'put'")
        sys.exit(1)

    try:
        S = float(sys.argv[1])
        K = float(sys.argv[2])
        T = float(sys.argv[3])
        r = float(sys.argv[4])
        sigma = float(sys.argv[5])
        option_type = sys.argv[6].lower()

        if option_type not in ['call', 'put']:
            raise ValueError("option_type must be 'call' or 'put'")

        if T <= 0:
            raise ValueError("Time to expiration must be positive")

        if sigma <= 0:
            raise ValueError("Volatility must be positive")

        if S <= 0 or K <= 0:
            raise ValueError("Prices must be positive")

        # Calculate results
        results = calculate_option_metrics(S, K, T, r, sigma, option_type)

        # Output formatted results
        print(format_output(results, S, K, T, r, sigma))

        # Also output JSON for programmatic access
        print("\nJSON OUTPUT:")
        print(json.dumps(results, indent=2))

    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
