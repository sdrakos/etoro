# PEAD σε πραγματικά δεδομένα — Runbook

Τρέχει στο **δικό σου μηχάνημα** (το `data.sec.gov` και οι price vendors είναι μπλοκαρισμένοι στο sandbox).

## Τι χρειάζεσαι
1. **`pead_event_study.py`** και **`run_pead_real.py`** στον ίδιο φάκελο.
2. Το **`sec-edgar` skill** εγκατεστημένο (τα scripts του). Αν ο φάκελός του δεν είναι σε ένα από τα default paths, διόρθωσε το `SKILL_CANDIDATES` στην κορυφή του `run_pead_real.py`.
3. `pip install pandas numpy requests matplotlib`
4. Ένα **price panel** σε CSV: πρώτη στήλη ημερομηνία, υπόλοιπες στήλες tickers (adjusted close).
5. (Προαιρετικό) **sectors.csv**: δύο στήλες `ticker,sector` — ενεργοποιεί sector-neutral αποδόσεις (προτιμότερο για PEAD).
6. Έγκυρο **User-Agent** (όνομα + email) για το EDGAR.

## Έλεγχος καλωδίωσης (χωρίς δίκτυο)
```
python run_pead_real.py --selftest
```
Πρέπει να βγάλει half-life ~8,6, persistence ~0,315, αρνητικό durability trend, και να γράψει
`pead_real_selftest_results.{json,png}`. Αν δουλέψει αυτό, η μηχανή είναι σωστή — μένει μόνο να βάλεις πραγματικά δεδομένα.

## Πραγματικό τρέξιμο
```
python run_pead_real.py \
  --prices prices.csv \
  --tickers "AAPL,MSFT,NVDA,AMZN,GOOGL,..." \
  --user-agent "Stefanos Drakos stefanos@agelai.gr" \
  --sectors sectors.csv \
  --hold 60
```
Γράφει `pead_real_results.json` και `pead_real_results.png`.

## Πώς διαβάζεις τα αποτελέσματα
- **half_life_days** — πόσο γρήγορα σβήνει το drift (μισή ζωή).
- **optimal_horizon_days (h\*)** — προσοχή: το argmax(B) είναι ευαίσθητο στον θόρυβο της ουράς· πρακτικός ορίζοντας = εκεί που το marginal `b(k)` χάνει σημαντικότητα (συχνά ~15–20 μέρες).
- **oos_IR / oos_t_NW** — απόδοση/ρίσκο OOS με Newey-West (το μόνο t που εμπιστεύεσαι λόγω overlap/clustering). Στόχος ρεαλιστικά IR ~0,3–0,8, |t|>2.
- **durability_trend_per_year / IR_by_year** — αν είναι αρνητικό, το PEAD φθίνει διαχρονικά (το πιθανότερο post-2010).
- **sue_persistence_rho** — το νόμιμο forward κομμάτι.

## Κρίσιμα για τίμιο αποτέλεσμα (αλλιώς το backtest ψεύδεται)
- **Universe χωρίς survivorship bias.** Μη βάζεις μόνο τα σημερινά μέλη ενός δείκτη — χρησιμοποίησε **as-traded** λίστα (μέλη όπως ήταν κάθε χρονιά), αλλιώς φουσκώνεις τεχνητά το αποτέλεσμα.
- **Point-in-time είσοδος.** Η είσοδος γίνεται **T+1** μετά την `filed` ημερομηνία του EDGAR — ποτέ στο period end.
- **Sector-neutral.** Δώσε `sectors.csv`· αλλιώς το σήμα μολύνεται από κλαδικές κινήσεις.
- **XBRL κάλυψη.** Πλήρης μόνο μετά το ~2011 — μην περιμένεις βαθύ ιστορικό πριν.
- **Rate limit EDGAR.** ≤10 req/s· για πολλά tickers προτίμησε τα bulk ZIPs (δες το `references/endpoints.md` του skill).

## Τίμια προσδοκία
Στα free/EDGAR δεδομένα το own-firm PEAD είναι **αδύναμο και μάλλον φθίνον** — όπως ήδη βρήκες στο DER. Ένα μέτριο, τίμιο, sector-neutral αποτέλεσμα (ή ένα καθαρό null με σωστά t-stats) είναι το σωστό αποτέλεσμα και είναι δημοσιεύσιμο. Το alpha έρχεται από τον **συνδυασμό** πολλών τέτοιων ορθογώνιων σημάτων, όχι από αυτό μόνο του.
```
prices.csv  ┐
sectors.csv ┼─► run_pead_real.py ─► (sec-edgar: EDGAR→SUE) ─► pead_event_study ─► results.{json,png}
User-Agent  ┘
```
