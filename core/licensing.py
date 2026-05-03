import os
import platform
import subprocess
import uuid
import jwt
from datetime import datetime, timezone

# --- SECRET KEY ---
# Maintaining compatibility with the enterprise version
LICENSE_SECRET = os.environ.get("VOCIUS_LICENSE_SECRET", "vocius_offline_secure_key_2026_x99")

def get_hwid():
    """Detects a persistent hardware ID for the current machine."""
    system = platform.system()
    detected_id = ""
    try:
        if system == "Windows":
            cmd = "wmic csproduct get uuid 2>nul"
            try:
                output = subprocess.check_output(cmd, shell=True).decode().split("\n")
                if len(output) > 1:
                    detected_id = output[1].strip()
            except: pass
        elif system == "Darwin": # macOS
            cmd = "ioreg -rd1 -c IOPlatformExpertDevice | grep -i 'UUID'"
            try:
                output = subprocess.check_output(cmd, shell=True).decode()
                if "=" in output:
                    detected_id = output.split("=")[1].strip().replace('"', '')
            except: pass
        elif system == "Linux":
            if os.path.exists("/etc/machine-id"):
                with open("/etc/machine-id", "r") as f:
                    detected_id = f.read().strip()
    except Exception:
        pass
    
    if not detected_id:
        detected_id = str(uuid.getnode())
    
    return detected_id

def check_online_validation(hwid):
    """Verifica se l'HWID ha una licenza valida su Supabase.
    Restituisce True se ha una licenza attiva online.
    Restituisce False se la licenza è revocata o eliminata dal database.
    Restituisce None se non c'è connessione o se la funzione non esiste (offline fallback).
    """
    import urllib.request
    import json
    
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
            result = json.loads(response.read().decode())
            if result is True:
                return True
            elif result is False:
                return False
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
            data = json.loads(response.read().decode())
            if isinstance(data, list):
                if any(item.get("status") == "active" for item in data):
                    return True
                if any(item.get("status") == "revoked" for item in data):
                    return False
    except:
        pass
    return None

def verify_license(license_path="license.vocius"):
    """
    Verifies the license file using JWT and HWID check.
    Returns (is_valid, message, details)
    Details contains: status_code, expiry_date, hwid
    Status codes: 0=OK, 1=Expiring soon, 2=Expired, 3=Invalid/Missing
    """
    details = {"status_code": 3, "expiry": "N/D", "hwid": get_hwid()}
    current_hwid = get_hwid()

    online_valid = check_online_validation(current_hwid)
    if online_valid is False:
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
        if payload.get("hwid") != get_hwid():
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
