"""
ΟΙΚΟΓΕΝΕΙΑ ΣΗΜΑΤΩΝ: "τι λεει ο ΟΓΚΟΣ για την ΚΙΝΗΣΗ"
================================================================================
 Καθε σημα μετραει διαφορετικη πτυχη της σχεσης ογκου-τιμης (causal, cross-sectional):

 1. VolConfirm  : κινηση * ογκος  -> ανοδος ΜΕ ογκο = δυνατη (συνεχιζει)
 2. Amihud      : |αποδοση| / ογκος -> "πιεση": ποσο κουναει η τιμη ανα $ ογκου (illiquidity)
 3. VolShock    : σημερινος ογκος vs μ.ο. -> ασυνηθιστο ενδιαφερον
 4. OBVslope    : συσσωρευση signed volume -> "εξυπνο χρημα" μπαινει/βγαινει
 5. PVcorr      : συσχετιση τιμης-ογκου (20μερες) -> υγιης ανοδος = θετικη συσχ.
 6. MFI         : Money Flow Index (RSI σταθμισμενο με ογκο) -> overbought/oversold με ογκο

 Ελεγχουμε: (α) συσχετισεις μεταξυ τους (ανεξαρτησια), (β) προβλεπτικη ικανοτητα
 του καθενος ξεχωριστα (IC = correlation με την επομενη αποδοση, out-of-sample).
"""
import numpy as np
close=np.load('close_mat.npy'); volm=np.load('vol_mat.npy'); T,N=close.shape
ret=np.zeros_like(close); ret[1:]=close[1:]/close[:-1]-1
LB=60; days=np.arange(LB,T-1); D=len(days)

def zc(x):  # cross-sectional z-score ανα μερα (relative value, causal)
    return (x-np.nanmean(x,axis=1,keepdims=True))/(np.nanstd(x,axis=1,keepdims=True)+1e-9)

# ---- οι 6 πηγες, η καθεμια (D,N) ----
def build():
    W=20
    VC=np.zeros((D,N)); AM=np.zeros((D,N)); VS=np.zeros((D,N))
    OBV=np.zeros((D,N)); PV=np.zeros((D,N)); MFI=np.zeros((D,N))
    for k,i in enumerate(days):
        r=ret[i-W:i]; v=volm[i-W:i]; c=close[i-W:i]
        # 1. VolConfirm: μ.ο.(αποδοση*z-ογκου) τελευταιων W -- κινηση σταθμισμενη με ογκο
        vz=(v-v.mean(0))/(v.std(0)+1e-9)
        VC[k]=np.mean(r*vz,axis=0)
        # 2. Amihud illiquidity: μ.ο.(|r|/ογκο$) -- οσο μεγαλυτερο, τοσο πιο "σπρωχνεται"
        dollar=v*c+1e-9
        AM[k]=-np.mean(np.abs(r)/dollar,axis=0)*1e10        # προσημο: ρευστες προτιμωνται (-)
        # 3. VolShock: σημερινος ογκος vs μ.ο. (z-score)
        VS[k]=(volm[i]-v.mean(0))/(v.std(0)+1e-9)
        # 4. OBV slope: κλιση συσσωρευμενου signed volume
        sgn=np.sign(np.diff(close[i-W-1:i],axis=0))
        obv=np.cumsum(sgn*v,axis=0); OBV[k]=(obv[-1]-obv[0])/(v.mean(0)*W+1e-9)
        # 5. Price-Volume correlation (W μερες)
        rm=r-r.mean(0); vm=vz-vz.mean(0)
        PV[k]=np.sum(rm*vm,0)/(np.sqrt(np.sum(rm**2,0)*np.sum(vm**2,0))+1e-9)
        # 6. MFI (Money Flow Index, vol-weighted RSI)
        tp=c; mf=tp*v; pos=np.where(np.diff(close[i-W-1:i],axis=0)>0,mf,0).sum(0)
        neg=np.where(np.diff(close[i-W-1:i],axis=0)<0,mf,0).sum(0)
        MFI[k]=100-100/(1+pos/(neg+1e-9)); MFI[k]=MFI[k]/100-0.5
    return dict(VolConfirm=VC,Amihud=AM,VolShock=VS,OBVslope=OBV,PVcorr=PV,MFI=MFI)

sigs=build()
names=list(sigs.keys())
Z={n:zc(sigs[n]) for n in names}                  # cross-sectionally normalized
split=int(0.70*D)

# ---- (α) ΣΥΣΧΕΤΙΣΕΙΣ: ποσο ανεξαρτητα ειναι; ----
print("ΣΥΣΧΕΤΙΣΕΙΣ μεταξυ σηματων (μεσος cross-sectional, |r|):\n")
print("           "+"".join(f"{n[:7]:>9}" for n in names))
M=np.zeros((6,6))
for a in range(6):
    row=""
    for b in range(6):
        cc=np.nanmean([np.corrcoef(Z[names[a]][t],Z[names[b]][t])[0,1] for t in range(0,D,5)])
        M[a,b]=cc; row+=f"{cc:>9.2f}"
    print(f"{names[a][:10]:<11}{row}")

# ---- (β) ΠΡΟΒΛΕΠΤΙΚΗ ΙΚΑΝΟΤΗΤΑ: Information Coefficient (out-of-sample) ----
# IC = cross-sectional corr(signal_t, return_{t+1}), μεσος στο test set
print("\nΠΡΟΒΛΕΠΤΙΚΗ ΙΚΑΝΟΤΗΤΑ out-of-sample (Information Coefficient):")
print("  (IC = συσχ. σηματος με επομενη αποδοση· >0 καλο, ~0.03+ αξιοποιησιμο)\n")
rfwd=ret[days+1]
def IC(sig):
    ics=[np.corrcoef(sig[t],rfwd[t])[0,1] for t in range(split,D) if not np.isnan(sig[t]).all()]
    ics=np.array(ics); ics=ics[~np.isnan(ics)]
    return ics.mean(), ics.mean()/(ics.std()+1e-9)*np.sqrt(len(ics))   # IC, t-stat
print(f"  {'Σημα':<14}{'IC':>9}{'t-stat':>9}")
print("  "+"-"*32)
icvals={}
for n in names:
    ic,t=IC(Z[n]); icvals[n]=ic
    flag=" <--" if abs(t)>2 else ""
    print(f"  {n:<14}{ic:>9.4f}{t:>9.2f}{flag}")
# combined (ισοβαρες, με σωστο προσημο απο το train)
print("  "+"-"*32)
signs={n:np.sign(np.nanmean([np.corrcoef(Z[n][t],rfwd[t])[0,1] for t in range(0,split)])) for n in names}
combo=np.nansum([signs[n]*Z[n] for n in names],axis=0)
ic,t=IC(combo); print(f"  {'COMBINED(eq)':<14}{ic:>9.4f}{t:>9.2f}{'  <--' if abs(t)>2 else ''}")
print("\n  (προσημα απο train:",{n:int(signs[n]) for n in names},")")
