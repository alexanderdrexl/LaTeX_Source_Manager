# LaTeX Quellen Manager - Start ohne Konsolenfenster
# Doppelklick startet den Server via pythonw.exe (kein CMD-Fenster)
import sys
import pathlib
import subprocess

# Eigenes Verzeichnis zum Suchpfad hinzufügen
sys.path.insert(0, str(pathlib.Path(__file__).parent))

# Alten Server auf Port 5000 beenden (falls noch aktiv)
try:
    result = subprocess.run(
        ['netstat', '-ano'],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if ':5000 ' in line and 'LISTEN' in line:
            parts = line.split()
            pid = parts[-1]
            subprocess.run(['taskkill', '/PID', pid, '/F'],
                           capture_output=True)
except Exception:
    pass

from latex_quellen_manager import main
main()
