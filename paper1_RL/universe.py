# paper1_RL/universe.py
"""Fixed research universe. ΠΡΟΣΟΧΗ: current constituents -> survivorship bias
(τεκμηριωμενο limitation στο spec). Window με 2 crashes (2020 COVID, 2022 bear)."""
START = "2015-01-01"
END = "2024-12-31"

TICKERS = [
    "AAPL","MSFT","AMZN","GOOGL","META","NVDA","TSLA","AVGO","ADBE","CRM",
    "ORCL","CSCO","INTC","AMD","QCOM","TXN","INTU","AMAT","MU","ADI",
    "JPM","BAC","WFC","GS","MS","C","AXP","BLK","SCHW","USB",
    "JNJ","UNH","PFE","ABBV","MRK","TMO","ABT","LLY","BMY","AMGN",
    "XOM","CVX","COP","SLB","EOG","PSX","MPC","VLO","OXY","KMI",
    "PG","KO","PEP","COST","WMT","MCD","NKE","SBUX","TGT","LOW",
    "HD","DIS","CMCSA","NFLX","VZ","T","TMUS","CAT","BA","GE",
    "HON","UNP","UPS","RTX","LMT","DE","MMM","EMR","GD","NOC",
    "V","MA","PYPL","FISV","ADP","BKNG","NOW","SNPS","CDNS","KLAC",
    "LRCX","PANW","FTNT","MRVL","CRWD","DDOG","ABNB","UBER","SHOP","SQ",
    "PLD","AMT","CCI","EQIX","SPG","O","PSA","WELL","DLR","AVB",
    "NEE","DUK","SO","D","AEP","EXC","SRE","XEL","PEG","ED",
    "LIN","APD","SHW","ECL","FCX","NEM","DOW","DD","NUE","VMC",
    "GILD","ISRG","REGN","VRTX","MDT","CI","CVS","HUM","ZTS","BDX",
    "MDLZ","CL","KMB","GIS","KHC","SYY","ADM","HSY","STZ","KDP",
]
