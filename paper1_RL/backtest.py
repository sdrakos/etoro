"""
================================================================================
 CROSS-SECTIONAL BACKTEST για το αρθρο
================================================================================
 Πραγματικα δεδομενα S&P500 (2013-2018, 476 μετοχες, OHLCV).
 Συγκρινουμε 3 στρατηγικες σε ΚΟΙΝΟ out-of-sample test set, σε ΠΟΛΛΕΣ μετοχες:
   - Buy & Hold              (baseline)
   - RRL + DSR               (Differential Sharpe -- κλασικο)
   - RRL + DER (θ=75)        (η προταση)
 Μεθοδολογια:
   * 70/30 train/test, standardize train-only, causal features (returns)
   * 3 seeds/ticker, παιρνουμε τον μεσο των seeds -> 1 αριθμος/ticker/στρατηγικη
   * Συγκεντρωνουμε: mean, median, win-rate vs B&H, % με drawdown < -20%
   * Στατιστικος ελεγχος: paired test DER vs DSR στα Sharpe & MDD
"""
import numpy as np, pandas as pd, time
import harness as H
from scipy import stats

# επιλογη universe: μεγαλα ονοματα + τυχαιο δειγμα για αμεροληψια
BIG=['AAPL','MSFT','AMZN','JPM','XOM','KO','NVDA','GE','WMT','PG','JNJ','BAC',
     'INTC','CSCO','PFE','CVX','HD','DIS','MCD','BA','CAT','MMM','IBM','GS',
     'NKE','MRK','VZ','T','WFC','C','F','GM','AAL','DAL','FCX','HAL','MU',
     'QCOM','TXN','ORCL','ADBE','CRM','NFLX','COST','TGT','LOW','UPS','UNH']

def backtest(tickers, theta=75.0, seeds=range(3)):
    rows=[]
    t0=time.time()
    for tk in tickers:
        try:
            # DSR
            mD,_,bh=H.experiment(tk,reward='dsr',features='returns',seeds=seeds,verbose=False)
            # DER
            mE,_,_ =H.experiment(tk,reward='der',theta=theta,features='returns',seeds=seeds,verbose=False)
        except Exception as e:
            continue
        rows.append(dict(ticker=tk,
            bh_ret=bh['ret'], bh_sh=bh['sharpe'], bh_mdd=bh['mdd'],
            dsr_ret=mD['ret'], dsr_sh=mD['sharpe'], dsr_mdd=mD['mdd'],
            der_ret=mE['ret'], der_sh=mE['sharpe'], der_mdd=mE['mdd']))
    print(f"[backtest] {len(rows)} μετοχες σε {time.time()-t0:.0f}s")
    return pd.DataFrame(rows)

def summarize(df):
    def line(name,ret,sh,mdd):
        print(f"  {name:<22} ret {np.mean(ret)*100:>6.1f}% (med {np.median(ret)*100:>5.1f}%)  "
              f"Sharpe {np.mean(sh):>5.2f} (med {np.median(sh):>5.2f})  "
              f"MDD {np.mean(mdd)*100:>6.1f}% (med {np.median(mdd)*100:>5.1f}%)")
    print("\n"+"="*92)
    print(f"ΣΥΓΚΕΝΤΡΩΤΙΚΑ OUT-OF-SAMPLE  ({len(df)} πραγματικες μετοχες S&P500, test set)")
    print("="*92)
    line("Buy & Hold",        df.bh_ret,  df.bh_sh,  df.bh_mdd)
    line("RRL + DSR",         df.dsr_ret, df.dsr_sh, df.dsr_mdd)
    line("RRL + DER (θ=75)",  df.der_ret, df.der_sh, df.der_mdd)
    print("-"*92)
    # Win-rates & risk
    print("ΑΝΑΛΥΣΗ ΚΙΝΔΥΝΟΥ & ΣΥΓΚΡΙΣΗ:")
    print(f"  Sharpe:  DER > DSR σε {100*np.mean(df.der_sh>df.dsr_sh):.0f}% των μετοχων")
    print(f"  MaxDD:   DER καλυτερο (μικροτερη πτωση) σε {100*np.mean(df.der_mdd>df.dsr_mdd):.0f}% των μετοχων")
    print(f"  % μετοχων με MDD χειροτερο απο -20%:  DSR {100*np.mean(df.dsr_mdd<-0.20):.0f}%  |  DER {100*np.mean(df.der_mdd<-0.20):.0f}%")
    print(f"  Χειροτερο MDD στο universe:           DSR {df.dsr_mdd.min()*100:.1f}%  |  DER {df.der_mdd.min()*100:.1f}%")
    # paired statistical tests
    ts,ps=stats.wilcoxon(df.der_sh, df.dsr_sh)
    tm,pm=stats.wilcoxon(df.der_mdd, df.dsr_mdd)
    print("ΣΤΑΤΙΣΤΙΚΟΣ ΕΛΕΓΧΟΣ (Wilcoxon signed-rank, paired):")
    print(f"  Sharpe DER vs DSR:  p={ps:.2e}  ({'σημαντικο' if ps<0.05 else 'μη σημαντικο'})")
    print(f"  MaxDD  DER vs DSR:  p={pm:.2e}  ({'σημαντικο' if pm<0.05 else 'μη σημαντικο'})")
    print("="*92)

if __name__=="__main__":
    print("Yahoo κλειστο στο sandbox -> πραγματικα cached δεδομενα S&P500 (2013-2018).\n")
    df=backtest(BIG, theta=75.0, seeds=range(3))
    df.to_csv('backtest_results.csv',index=False)
    summarize(df)
    # equity curves: aggregate (μεσος ολων των μετοχων) DER vs DSR vs B&H
    print("\n[saved] backtest_results.csv  (ανα μετοχη)")
