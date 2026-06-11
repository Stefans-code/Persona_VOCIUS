import os
import platform
import subprocess
import uuid
import jwt
from datetime import datetime, timezone

# --- SECRET KEY ---
# Maintaining compatibility with the enterprise version
LICENSE_SECRET = os.environ.get("VOCIUS_LICENSE_SECRET", "vocius_offline_secure_key_2026_x99")

# Flag per non far comparire finestre console quando lanciamo subprocess su Windows
_CREATE_NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0


def _run_hidden(cmd):
    """Esegue un comando e ne restituisce lo stdout, senza finestre console."""
    return subprocess.check_output(
        cmd, shell=True,
        stderr=subprocess.DEVNULL,
        creationflags=_CREATE_NO_WINDOW
    ).decode(errors="ignore")


def _get_windows_uuid():
    """UUID SMBIOS della macchina.

    wmic e CIM (Win32_ComputerSystemProduct) restituiscono lo STESSO valore, quindi
    le licenze già emesse restano valide. wmic però è stato rimosso da Windows 11
    24H2+, perciò usiamo PowerShell/CIM come fallback per non cadere su un HWID
    instabile (uuid.getnode()).
    """
    # 1. wmic (legacy)
    try:
        lines = _run_hidden("wmic csproduct get uuid").split("\n")
        if len(lines) > 1:
            val = lines[1].strip()
            if val and val.lower() != "uuid":
                return val
    except Exception:
        pass
    # 2. PowerShell / CIM — stesso UUID SMBIOS di wmic
    try:
        val = _run_hidden(
            'powershell -NoProfile -Command "(Get-CimInstance Win32_ComputerSystemProduct).UUID"'
        ).strip()
        if val:
            return val
    except Exception:
        pass
    return ""


def get_hwid():
    """Detects a persistent hardware ID for the current machine."""
    system = platform.system()
    detected_id = ""
    try:
        if system == "Windows":
            detected_id = _get_windows_uuid()
        elif system == "Linux":
            if os.path.exists("/etc/machine-id"):
                with open("/etc/machine-id", "r") as f:
                    detected_id = f.read().strip()
        elif system == "Darwin":
            out = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]
            ).decode(errors="ignore")
            for line in out.split("\n"):
                if "IOPlatformUUID" in line:
                    detected_id = line.split('"')[-2].strip()
                    break
    except Exception:
        pass

    if not detected_id:
        detected_id = str(uuid.getnode())

    return detected_id


def get_license_path():
    """Percorso persistente del file di licenza, in AppData (coerente col DB).

    Evita i percorsi relativi alla CWD, che falliscono quando l'app gira da
    Program Files (cartella non scrivibile).
    """
    if platform.system() == "Windows":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
    else:
        base = os.path.join(os.path.expanduser("~"), ".config")
    base_dir = os.path.join(base, "VociusPersona")
    try:
        os.makedirs(base_dir, exist_ok=True)
    except Exception:
        pass
    target = os.path.join(base_dir, "license.vocius")
    # Migrazione una tantum dalla vecchia posizione relativa (CWD)
    try:
        legacy = os.path.abspath("license.vocius")
        if not os.path.exists(target) and os.path.exists(legacy):
            import shutil
            shutil.copy(legacy, target)
    except Exception:
        pass
    return target

def check_online_validation(hwid):
    """Verifica online lo stato della licenza per l'HWID (revoca remota).
    Ritorna una stringa:
      "active"      licenza attiva sul database
      "revoked"     licenza revocata o eliminata
      "not_found"   server raggiunto ma nessuna voce per questo HWID
      "unreachable" impossibile contattare il server (offline / errore di rete)
    """
    import urllib.request
    import json

    reached = False

    # 1. Tentativo tramite RPC (Remote Procedure Call) che bypassa l'RLS
    url_rpc = "https://xoowkjepvbokxmhsqmnm.supabase.co/rest/v1/rpc/check_license_validity"
    headers = {
        "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inhvb3dramVwdmJva3htaHNxbW5tIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY3NTI2NjUsImV4cCI6MjA5MjMyODY2NX0.2S_baIWot9ZkW7bsi16hy84O9Edf_XlBcQBmhXs3H1Y",
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inhvb3dramVwdmJva3htaHNxbW5tIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY3NTI2NjUsImV4cCI6MjA5MjMyODY2NX0.2S_baIWot9ZkW7bsi16hy84O9Edf_XlBcQBmhXs3H1Y",
        "Content-Type": "application/json"
    }
    try:
        req = urllib.request.Request(url_rpc, data=json.dumps({"p_hwid": hwid}).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=3) as response:
            reached = True
            result = json.loads(response.read().decode())
            if result is True:
                return "active"
            elif result is False:
                return "revoked"
    except:
        pass

    # 2. Fallback tramite REST API classica
    url_rest = f"https://xoowkjepvbokxmhsqmnm.supabase.co/rest/v1/licenses?hwid=eq.{hwid}"
    headers_rest = {
        "apikey": headers["apikey"],
        "Authorization": headers["Authorization"]
    }
    try:
        req = urllib.request.Request(url_rest, headers=headers_rest)
        with urllib.request.urlopen(req, timeout=3) as response:
            reached = True
            data = json.loads(response.read().decode())
            if isinstance(data, list):
                if any(item.get("status") == "active" for item in data):
                    return "active"
                if any(item.get("status") == "revoked" for item in data):
                    return "revoked"
                return "not_found"
    except:
        pass

    return "not_found" if reached else "unreachable"

def verify_license(license_path=None):
    """
    Verifies the license file using JWT and HWID check.
    Returns (is_valid, message, details)
    Details contains: status_code, expiry_date, hwid
    Status codes: 0=OK, 1=Expiring soon, 2=Expired, 3=Invalid/Missing
    """
    if license_path is None:
        license_path = get_license_path()

    current_hwid = get_hwid()
    details = {"status_code": 3, "expiry": "N/D", "hwid": current_hwid}

    # Validazione remota OBBLIGATORIA all'avvio (revoca + presenza connessione).
    # - offline / server irraggiungibile  -> NON si avvia (serve connessione)
    # - revocata                          -> licenza bloccata e rimossa
    # - attiva / non trovata              -> si prosegue con la verifica LOCALE
    #   (JWT + HWID + scadenza); dopo l'avvio l'app può restare offline.
    online_status = check_online_validation(current_hwid)
    if online_status == "unreachable":
        return False, "Connessione a internet richiesta all'avvio", details
    if online_status == "revoked":
        if os.path.exists(license_path):
            try: os.remove(license_path)
            except: pass
        return False, "Licenza revocata o terminata (Database validation failed)", details

    if not os.path.exists(license_path):
        return False, "Licenza mancante (.vocius)", details

    try:
        with open(license_path, "r") as f:
            token = f.read().strip()

        payload = jwt.decode(token, LICENSE_SECRET, algorithms=["HS256"])
        details["hwid"] = payload.get("hwid") or details["hwid"]
        
        # Expiry check
        expiry = datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc)
        details["expiry"] = expiry.strftime("%d/%m/%Y %H:%M")
        
        # HWID check
        if payload.get("hwid") != current_hwid:
            details["status_code"] = 3
            return False, "Licenza per hardware differente", details

        now = datetime.now(timezone.utc)
        if now > expiry:
            details["status_code"] = 2
            return False, "Licenza scaduta", details
        
        diff = expiry - now
        if diff.days < 7:
            details["status_code"] = 1
            return True, f"In scadenza tra {diff.days} giorni", details

        details["status_code"] = 0
        return True, "Licenza valida", details

    except jwt.ExpiredSignatureError:
        details["status_code"] = 2
        return False, "Licenza scaduta", details
    except Exception:
        details["status_code"] = 3
        return False, "Licenza non valida o corrotta", details
