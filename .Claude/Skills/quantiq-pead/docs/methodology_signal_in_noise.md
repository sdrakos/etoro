# A Methodology for Signal Extraction under Anti-Inductive, Regime-Switching, Low-SNR Markets

*Unifying belief-state filtering and risk-sensitive reinforcement learning with leakage-resistant evaluation.*

Stefanos Drakos — AGEL AI I.K.E., Rhodes — ORCID 0000-0001-7417-2444
Working draft v0.1 (methodology + verified bibliography)

---

## 0. Origin of the problem

The framing is taken from In Young Cho's account of machine learning in markets (Jane Street, *Signals & Threads* ep. 22): financial ML is "like building an LLM, except you have 100 units of data, 1 useful and 99 garbage, and you do not know which is which." The task is to extract a signal in an extreme-noise regime using techniques designed for high-SNR domains, while the market actively changes underneath you.

We operationalise that account into **four named pathologies**, then map each to a defense, and show that the two existing AGEL papers — the *Differential Entropic Reward* (DER) paper and the *Belief-State RL for Cross-Sectional Equity Selection* paper — already supply two of the four legs. The methodology's contribution is to complete the remaining two (evaluation-space discipline and dynamic regime robustness) and to bind all four into one pipeline.

---

## 1. The four pathologies (formal statement)

**P1 — Low signal-to-noise (SNR).** For any feature set, the explainable fraction of return variance is tiny (R² often ≈ 10⁻²). This is structural: prices are the joint output of millions of interacting agents, so no single model captures more than a sliver.

**P2 — Effective low data + non-stationarity.** Tens of terabytes per day do *not* translate into many independent samples for any given hypothesis, because (i) labels overlap in time (non-IID) and (ii) the data-generating distribution shifts — "the market just works differently" — roughly with each crisis. The effective sample size for a regime-specific edge is small.

**P3 — Anti-inductivity (alpha decay).** Unlike digit recognition, where a "3" stays a "3", a detected regularity is an *incentive to trade against it*, which erodes it. The act of exploitation removes the pattern from the future. This is the efficient/adaptive-markets mechanism (Lo 2004) and is empirically measured: cross-sectional predictability decays ≈ 58% post-publication (McLean & Pontiff 2016).

**P4 — Multiple-testing / cross-researcher leakage.** With many researchers exploring overlapping ideas, an apparently out-of-sample result may already be contaminated. Naïve significance thresholds (|t| > 2) are far too lenient given the number of trials (Harvey, Liu & Zhu 2016).

---

## 2. Design principle: three axes of discipline + dynamic robustness

Minsky's observation in the same episode is the organising idea: the two research styles are *"not one more disciplined than the other — the discipline is in different places."* We make the axes explicit.

| Axis | Question it controls | Pathology addressed | AGEL asset |
|------|----------------------|---------------------|------------|
| **Input / state-space** | What goes *in*? (filter signal from noise before deciding) | P1, P2 | **Belief-State RL paper** |
| **Objective / model-space** | What do we *optimise*? (penalise variance per step, not just mean) | P1 (risk) | **DER paper** |
| **Evaluation-space** | What are we *allowed to believe*? (leakage-free, multiple-testing-aware) | P3, P4 | *(new — this draft)* |
| **Dynamic robustness** | How does the policy survive a *regime change*? | P2, P3 | *(new — this draft)* |

The "hard truth" already stated in the Belief-State paper governs the whole document: **better state estimation does not create alpha.** Filtering *extracts a signal more cleanly* (raises the Information Coefficient, protects the Transfer Coefficient in the Fundamental Law); it does not manufacture edge. The realistic target is therefore a legitimate IR ≈ 0.5–1.0, not a magic strategy. The methodology's job is to make every component of that IR *believable*.

---

## 3. The pipeline

### Stage A — Data and labels (attack P2: non-IID, non-stationarity)

1. **Stationarity with memory.** Replace naïve returns/differencing with *fractional differentiation* to obtain a near-stationary series that retains long memory (López de Prado 2018, ch. 5). Pure differencing destroys the predictive memory; raw prices are non-stationary.
2. **Event-based labels.** Use the *triple-barrier* method (profit-take / stop-loss / time horizon) instead of fixed-horizon returns, and *meta-labeling* to separate "which side" from "how much / whether to act" (López de Prado 2018, chs. 3, 13).
3. **Sample uniqueness weighting.** Because labels overlap in time, weight samples by uniqueness and use sequential bootstrap, so the model is not fooled into treating redundant observations as independent (López de Prado 2018, ch. 4).

### Stage B — State / belief construction (attack P1, P2)

Cast the problem as a **POMDP → belief-MDP**: the regime and latent value are hidden; observe noisy prices/flows. Construct the filtering posterior `b_t = p(x_t | y_{1:t})` and run control on the *belief*, not on raw prices.

- Linear-Gaussian core: Kalman filter / Local Linear Trend (Kalman 1960; Harvey 1989).
- Regime layer: Markov regime-switching (Hamilton 1989) and Bayesian online changepoint detection (Adams & MacKay 2007).
- Nonlinear / amortised generalisation: Deep Kalman Filters (Krishnan et al. 2015), deep SSMs S4/Mamba (Gu et al. 2022; Gu & Dao 2023).

This is exactly the construction in the Belief-State paper; here it becomes Stage B of a larger pipeline. The continuous-time RL ↔ exploratory-HJB bridge (Wang, Zariphopoulou & Zhou 2020; Wang & Zhou 2020; Jia & Zhou 2022) is the theoretical backbone, extended to the **partially observed** case (the gap the paper fills).

### Stage C — Objective (attack P1 via risk)

Optimise the **Differential Entropic Reward**: an online, per-step, differentiable reward derived from the entropic certainty equivalent of returns. It generalises the differential Sharpe ratio of Moody & Saffell (2001) and inherits the risk-sensitive (exponential/entropic) criterion (Fleming & McEneaney 1995; Borkar 2002; Fei et al. 2020/2021; Noorani, Mavridis & Baras 2022). Pair with CVaR / distributional RL where tail control matters (Rockafellar & Uryasev 2000; Bellemare, Dabney & Munos 2017). This is the DER paper, dropped in as the reward of the belief-MDP agent.

### Stage D — Dynamic regime robustness (attack P2, P3)

A regime change is a worst-case shift of the transition kernel. Solve a **distributionally robust MDP**: optimise the policy under the worst transition law inside an uncertainty set around the nominal dynamics (Iyengar 2005; Nilim & El Ghaoui 2005), using the modern DRRL framework (Wang, Si, Blanchet & Zhou 2024). Two natural couplings to Stage B:

- The belief over the latent regime *defines* the uncertainty set (its support = plausible regimes), turning ad-hoc robustness into a principled, data-driven set.
- The robust Bellman operator replaces the nominal one in the DER agent, so the same risk-sensitive objective is now also robust to the regime it was not trained on. **This is the original theoretical contribution candidate**: a *belief-conditioned distributionally robust, risk-sensitive* control — closing the loop between the two papers.

### Stage E — Evaluation and falsification (attack P3, P4)

This is the leg both existing papers are weakest on, and the one In Young/Minsky stress most ("you should only believe out-of-sample").

1. **No leakage.** Standard k-fold CV is invalid in finance (overlapping labels). Use *purged k-fold with embargo* (López de Prado 2018, chs. 7, 9).
2. **Many paths, not one.** Replace single walk-forward with *Combinatorial Purged Cross-Validation* (CPCV) to generate a distribution of backtest paths and avoid a single lucky history (López de Prado 2018, ch. 12).
3. **Count the trials.** Report the **Deflated Sharpe Ratio**, which corrects the observed Sharpe for the number of trials, sample length, skew and kurtosis (Bailey & López de Prado 2014); pair with the *Probability of Backtest Overfitting* (Bailey, Borwein, López de Prado & Zhu 2017) and a minimum-backtest-length check.
4. **Multiple-testing budget.** Adopt the elevated significance hurdle of Harvey, Liu & Zhu (2016) / Harvey & Liu (2014); treat the *team* as one multiple-testing process — pre-register hypotheses and share a trial ledger so cross-researcher leakage (P4) is accounted for, not hidden.
5. **Falsification criteria up front.** State, before running, what result would *kill* the hypothesis (e.g. DSR not significant after trial correction; IR collapses out-of-regime). The Belief-State paper already adopts this "experimental design and falsification criteria" section — generalise it.

### Stage F — Capacity and decay monitoring (attack P3)

Anti-inductivity is not a one-time test; it is a live process. Treat the edge as a decaying asset:

- Track realised IC/IR over rolling windows; expect post-deployment decay consistent with McLean & Pontiff (2016).
- Model the strategy life-cycle through the Adaptive Markets Hypothesis (Lo 2004): edges are ecological, not eternal; maintain a *portfolio of decaying edges* and a discovery pipeline rather than a single static model.
- Capacity/impact awareness: size to market impact (the pension-rebalance intuition from the episode) so that exploitation does not destroy the very signal being traded.

---

## 4. One-line synthesis

> The DER paper disciplines the **objective**; the Belief-State paper disciplines the **input**; this methodology adds the discipline of **what may be believed** (Stage E) and **what survives a regime** (Stage D), and binds them through a belief-conditioned, distributionally robust, risk-sensitive control loop — with the explicit, honest ceiling that filtering and risk-shaping *clean and protect* a signal, they do not create one.

---

## 5. Scope of this methodology (honest limitations)

- It does **not** generate alpha; it raises IC, protects TC, and suppresses false discovery. The breadth term of the Fundamental Law is untouched.
- The DRMDP uncertainty-set construction from the regime belief is a *proposed* coupling; it requires a proof that the belief support yields a rectangular (SA- or S-rectangular) set for dynamic programming to remain valid — this is the main open theoretical risk (verify numerically before claiming, per the AGEL workflow).
- On daily Yahoo data the realistic ceiling remains IR ≈ 0.5–1.0; the methodology improves *believability and durability* of that IR, not its level.
- Multiple-testing control across a *team* is organisational as much as statistical; the trial ledger is a process commitment, not an algorithm.

---

## 6. Verified bibliography

References are grouped; every entry below was verified this session by title + venue + year (+ DOI where one exists), except where marked **[AGEL canon]** (already verified inside the two existing papers).

### Anti-inductivity, alpha decay, market efficiency
1. Lo, A. W. (2004). *The Adaptive Markets Hypothesis: Market Efficiency from an Evolutionary Perspective.* Journal of Portfolio Management 30(5):15–29. DOI 10.3905/jpm.2004.442611.
2. McLean, R. D. & Pontiff, J. (2016). *Does Academic Research Destroy Stock Return Predictability?* Journal of Finance 71(1):5–32. DOI 10.1111/jofi.12365.

### Multiple testing, selection bias, backtest overfitting
3. Harvey, C. R., Liu, Y. & Zhu, H. (2016). *…and the Cross-Section of Expected Returns.* Review of Financial Studies 29(1):5–68. DOI 10.1093/rfs/hhv059.
4. Harvey, C. R. & Liu, Y. (2014). *Evaluating Trading Strategies.* Journal of Portfolio Management 40(5):108–118. DOI 10.3905/jpm.2014.40.5.108.
5. Bailey, D. H. & López de Prado, M. (2014). *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality.* Journal of Portfolio Management 40(5):94–107. DOI 10.3905/jpm.2014.40.5.094.
6. Bailey, D. H., Borwein, J. M., López de Prado, M. & Zhu, Q. J. (2017). *The Probability of Backtest Overfitting.* Journal of Computational Finance 20(4):39–69. SSRN 2326253; DOI 10.2139/ssrn.2326253.

### Practical financial-ML methodology (labels, sampling, CV)
7. López de Prado, M. (2018). *Advances in Financial Machine Learning.* Wiley. ISBN 978-1-119-48208-6. (Fractional differentiation ch. 5; triple-barrier & meta-labeling chs. 3, 13; uniqueness/sequential bootstrap ch. 4; purged k-fold + embargo chs. 7, 9; CPCV ch. 12.)
8. López de Prado, M. (2018). *The 10 Reasons Most Machine Learning Funds Fail.* Journal of Portfolio Management 44(6):120–133. DOI 10.3905/jpm.2018.44.6.120.

### Distributional / risk-sensitive RL and the HJB bridge
9. Moody, J. & Saffell, M. (2001). *Learning to Trade via Direct Reinforcement.* IEEE Transactions on Neural Networks 12(4):875–889. **[AGEL canon]**
10. Wang, H., Zariphopoulou, T. & Zhou, X. Y. (2020). *Reinforcement Learning in Continuous Time and Space: A Stochastic Control Approach.* JMLR 21(198):1–34. **[AGEL canon]**
11. Wang, H. & Zhou, X. Y. (2020). *Continuous-Time Mean–Variance Portfolio Selection: A Reinforcement Learning Framework.* Mathematical Finance 30(4):1273–1308. **[AGEL canon]**
12. Rockafellar, R. T. & Uryasev, S. (2000). *Optimization of Conditional Value-at-Risk.* Journal of Risk 2(3):21–41. **[AGEL canon]**
13. Bellemare, M. G., Dabney, W. & Munos, R. (2017). *A Distributional Perspective on Reinforcement Learning.* ICML, PMLR 70:449–458. **[AGEL canon]**
14. Fei, Y., Yang, Z., Chen, Y., Wang, Z. & Xie, Q. (2020/2021). *Risk-Sensitive RL: exponential criteria / regret.* NeurIPS. **[AGEL canon — verify exact pages]**

### Distributionally robust MDPs (Stage D)
15. Iyengar, G. N. (2005). *Robust Dynamic Programming.* Mathematics of Operations Research 30(2):257–280. DOI 10.1287/moor.1040.0129.
16. Nilim, A. & El Ghaoui, L. (2005). *Robust Control of Markov Decision Processes with Uncertain Transition Matrices.* Operations Research 53(5):780–798. DOI 10.1287/opre.1050.0216.
17. Wang, S., Si, N., Blanchet, J. & Zhou, Z. (2024). *On the Foundation of Distributionally Robust Reinforcement Learning.* arXiv:2311.09018.

### Filtering, regimes, cross-sectional baselines
18. Kalman, R. E. (1960). *A New Approach to Linear Filtering and Prediction Problems.* J. Basic Engineering 82(1):35–45. **[AGEL canon]**
19. Hamilton, J. D. (1989). *A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle.* Econometrica 57(2):357–384. **[AGEL canon]**
20. Adams, R. P. & MacKay, D. J. C. (2007). *Bayesian Online Changepoint Detection.* arXiv:0710.3742. **[AGEL canon]**
21. McLean & Pontiff — see [2]. Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*, J. Financial Economics 104(2):228–250. **[AGEL canon]**

*(Items 9–14, 18–21 carry their citation strings from the two existing papers and should be re-triangulated against those .bib files before any submission, per workflow rule 2.)*

---

## 7. Suggested next steps

1. Pick the **theoretical anchor**: prove the belief→uncertainty-set rectangularity result (Stage D) — that is the publishable novelty.
2. Or pick the **empirical anchor**: run the full Stage A–F pipeline on the QuantIQ cross-sectional universe and report a *deflated*, CPCV-based IR with a pre-registered trial ledger.
3. Decide the artifact: a methodology paper ("a disciplined pipeline for low-SNR, anti-inductive markets") vs. folding Stages D–F into the two existing papers as their missing evaluation/robustness sections.
