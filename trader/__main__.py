import sys

# Force UTF-8 on Windows so unicode arrows/symbols print on any console code page.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from trader.cli import main

if __name__ == "__main__":
    main()
