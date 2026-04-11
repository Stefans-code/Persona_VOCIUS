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
    # On desktop, we prefer the system UUID
    system = platform.system()
    detected_id = ""
    try:
        if system == "Windows":
            cmd = "wmic csproduct get uuid 2>nul"
            output = subprocess.check_output(cmd, shell=True).decode().split("\n")
            if len(output) > 1: detected_id = output[1].strip()
        elif system == "Darwin": # macOS
            cmd = "ioreg -rd1 -c IOPlatformExpertDevice | grep -i 'UUID'"
            try:
                output = subprocess.check_output(cmd, shell=True).decode()
                # Esempio output: | "IOPlatformUUID" = "12345678-ABCD-EFGH-IJKL-MN1234567890"
                if "=" in output:
                    detected_id = output.split("=")[1].strip().replace('"', '')
            except: pass
        elif system == "Linux":
            if os.path.exists("/etc/machine-id"):
                with open("/etc/machine-id", "r") as f: detected_id = f.read().strip()
    except Exception:
        pass
    
    if not detected_id:
        detected_id = str(uuid.getnode())
    
    return detected_id

def verify_license(license_path="license.vocius"):
    """
    Verifies the license file using JWT and HWID check.
    Returns (is_valid, message, details)
    Details contains: status_code, expiry_date, hwid
    Status codes: 0=OK, 1=Expiring soon, 2=Expired, 3=Invalid/Missing
    """
    details = {"status_code": 3, "expiry": "N/D", "hwid": get_hwid()}
    
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
