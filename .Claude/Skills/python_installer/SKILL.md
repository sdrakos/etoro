---
name: nuitka-inno-packager
description: >
  Complete workflow για να μετατρέψεις Python κώδικα σε επαγγελματικό Windows installer (.exe setup)
  με ένα κλικ για τελικό χρήστη που δεν είναι τεχνικός. Χρησιμοποιεί Nuitka για compilation
  Python → native .exe και Inno Setup για δημιουργία installer πακέτου.
  
  ΧΡΗΣΙΜΟΠΟΙΕ αυτό το skill ΠΑΝΤΑ όταν ο χρήστης θέλει να:
  - Κάνει "package" ή "compile" Python εφαρμογή για Windows
  - Φτιάξει installer / setup.exe για διανομή
  - Μετατρέψει .py → .exe → setup πακέτο
  - Στείλει εφαρμογή σε non-technical χρήστες
  - Αναφέρει "nuitka", "inno setup", "standalone exe", "διανομή εφαρμογής"
  - Ζητήσει να τρέξει Python app σε υπολογιστή χωρίς Python
---

# Python → Windows Installer (Nuitka + Inno Setup)

Αυτό το skill καλύπτει ολόκληρο το pipeline:
**Python source code → Compiled .exe (Nuitka) → Installer Setup.exe (Inno Setup)**

## Γρήγορη Αναφορά

| Βήμα | Εργαλείο | Αποτέλεσμα |
|------|----------|------------|
| 1. Compile | Nuitka | `myapp.dist/` φάκελος με .exe |
| 2. Package | Inno Setup | `Setup_MyApp_v1.0.exe` ένα αρχείο |
| 3. Διανομή | — | Ο χρήστης κάνει διπλό κλικ και εγκαθιστά |

---

## ΒΗΜΑ 1: Προαπαιτούμενα (Developer machine)

### Εγκατάσταση Python
```
https://www.python.org/downloads/windows
# Επίλεξε Windows x86-64 installer
# ✅ Tick "Add Python to PATH" κατά την εγκατάσταση
python --version  # Επαλήθευση
```

### Εγκατάσταση Nuitka + βοηθητικά
```bash
pip install nuitka
pip install ordered-set   # Επιταχύνει compilation
pip install zstandard     # Συμπίεση onefile (προαιρετικό)
python -m nuitka --version  # Επαλήθευση
```

> **Σημείωση:** Την πρώτη φορά, Nuitka θα ρωτήσει να κατεβάσει MinGW64 C compiler.
> Πες **Yes** και στις δύο ερωτήσεις (compiler + ccache).

### Εγκατάσταση Inno Setup
```
https://jrsoftware.org/isdl.php
# Κατέβασε: innosetup-X.X.X.exe
# Εγκατάσταση με default settings
```

---

## ΒΗΜΑ 2: Οργάνωση Project

Δομή φακέλου πριν compilation:
```
MyProject/
├── main.py              ← Κεντρικό αρχείο (entry point)
├── requirements.txt
├── assets/              ← Εικόνες, fonts, config files
│   ├── icon.ico         ← Icon για το .exe (προαιρετικό)
│   └── config.json
└── data/                ← Άλλα data files
```

**Κανόνας:** Βεβαιώσου ότι `python main.py` τρέχει σωστά πριν compilation!

---

## ΒΗΜΑ 3: Compilation με Nuitka

### Απλή εντολή (standalone mode - συνιστάται πρώτα)
```bash
python -m nuitka ^
  --mode=standalone ^
  --output-dir=dist ^
  --output-filename=MyApp ^
  main.py
```

### Πλήρης εντολή με όλες τις επιλογές
```bash
python -m nuitka ^
  --mode=standalone ^
  --output-dir=dist ^
  --output-filename=MyApp ^
  --windows-icon-from-ico=assets/icon.ico ^
  --windows-company-name="MyCompany" ^
  --windows-product-name="My Application" ^
  --windows-file-version=1.0.0.0 ^
  --windows-product-version=1.0.0.0 ^
  --windows-file-description="My App Description" ^
  --enable-plugin=tk-inter ^
  --include-data-dir=assets=assets ^
  --include-data-dir=data=data ^
  --assume-yes-for-downloads ^
  main.py
```

### Plugin flags ανά framework
| Framework | Flag |
|-----------|------|
| Tkinter | `--enable-plugin=tk-inter` |
| PyQt5 | `--enable-plugin=pyqt5` |
| PyQt6 | `--enable-plugin=pyqt6` |
| PySide2 | `--enable-plugin=pyside2` |
| PySide6 | `--enable-plugin=pyside6` |
| NumPy | `--enable-plugin=numpy` |
| Matplotlib | `--enable-plugin=matplotlib` |
| Django | `--enable-plugin=django` |

### Αποτέλεσμα compilation
```
dist/
└── MyApp.dist/           ← Αυτός ο φάκελος πηγαίνει στο Inno Setup
    ├── MyApp.exe         ← Κύριο εκτελέσιμο
    ├── python3X.dll
    └── ... (DLLs και dependencies)
```

### Onefile mode (προαιρετικό, μετά το standalone test)
```bash
python -m nuitka ^
  --mode=onefile ^
  --output-dir=dist ^
  --output-filename=MyApp ^
  main.py
```
> ⚠️ Πρώτα δοκίμασε standalone. Onefile έχει αργότερη εκκίνηση και δυσκολότερο debugging.

---

## ΒΗΜΑ 4: Nuitka Project Options (ενσωμάτωση στον κώδικα)

Αντί για μακριά command line, βάλε options στο `main.py`:
```python
# nuitka-project: --mode=standalone
# nuitka-project: --output-dir=dist
# nuitka-project: --output-filename=MyApp
# nuitka-project: --windows-icon-from-ico={MAIN_DIRECTORY}/assets/icon.ico
# nuitka-project: --include-data-dir={MAIN_DIRECTORY}/assets=assets
# nuitka-project-if: {OS} == "Windows":
#    nuitka-project: --enable-plugin=tk-inter
```

Μετά απλά: `python -m nuitka main.py`

---

## ΒΗΜΑ 5: Δημιουργία Installer με Inno Setup

### Αυτόματο ISS Script (copy-paste και τροποποίησε)

Δες το reference file: `references/inno-setup-template.iss`

### Βήματα στο Inno Setup GUI
1. Άνοιξε **Inno Setup Compiler**
2. **File → New** → Script Wizard
3. Ή άνοιξε απευθείας το `.iss` αρχείο
4. **Build → Compile** (ή F9)
5. Αποτέλεσμα: `Output/Setup_MyApp_v1.0.exe`

---

## ΒΗΜΑ 6: Αυτοματοποίηση - Build Script

Δες το reference file: `references/build.bat`

Τρέξε: `build.bat` → παράγει αυτόματα το `Setup_MyApp.exe`

---

## Συνηθισμένα Προβλήματα

| Πρόβλημα | Λύση |
|---------|------|
| Missing module import error | `--include-module=module_name` |
| Missing data files | `--include-data-dir=src=dest` ή `--include-data-files=file=dest/` |
| Fork bomb (multiprocessing) | `--no-deployment-flag=self-execution` |
| Antivirus false positive | Χρησιμοποίησε code signing certificate |
| Αργή εκκίνηση onefile | Χρήση standalone mode + Inno Setup |
| Memory error κατά compile | `--low-memory` flag |
| Windows Defender lock | Εξαίρεσε dist/ φάκελο από Windows Defender |
| DLL not found στο target PC | Εγκατάστησε Visual C++ Redistributable (βλ. παρακάτω) |

### Visual C++ Redistributable
Για Python 3.10-3.13: Χρειάζεται **VC++ 2022 Redistributable** στο target PC.
Λύση: Συμπερίλαβε το installer στο Inno Setup `[Run]` section:
```ini
[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/quiet /norestart"; \
  StatusMsg: "Installing Visual C++ Runtime..."; \
  Check: NeedsVCRedist
```

---

## Checklist πριν διανομή

- [ ] `python main.py` τρέχει χωρίς errors
- [ ] Standalone dist φάκελος τρέχει σε καθαρό Windows VM
- [ ] Inno Setup installer τρέχει σε PC χωρίς Python
- [ ] Desktop shortcut δημιουργείται σωστά
- [ ] Uninstall λειτουργεί από Control Panel
- [ ] Icon εμφανίζεται σωστά

---

## Reference Files
- `references/inno-setup-template.iss` — Έτοιμο ISS script template
- `references/build.bat` — Αυτοματοποιημένο build script
- `references/nuitka-options-cheatsheet.md` — Όλες οι σημαντικές Nuitka options