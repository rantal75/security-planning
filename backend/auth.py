"""
auth.py — Accesso con utente e password (v25.10).

Attivo solo se la variabile d'ambiente PLANNING_AUTH=1 (impostata nel
servizio systemd sul server zonefpi). In locale sui PC, senza la variabile,
il planning funziona come prima, senza login.

File (nella cartella di lavoro dell'app, MAI su Git/Drive):
  users.json   utenti e password cifrate (scrypt): {"alex": "scrypt$..."}
  session.key  chiave segreta per firmare il cookie di accesso (creata da sola)

Gestione utenti, dal terminale del server (cartella ~/apps/planning):
  .venv/bin/python -m backend.auth imposta alex    # crea o cambia password
  .venv/bin/python -m backend.auth elenco
  .venv/bin/python -m backend.auth rimuovi momo
  .venv/bin/python -m backend.auth ruolo momo limitato   # oppure: completo

Ruoli (v25.12): "completo" vede e modifica tutto; "limitato" non vede le
preferenze/ruoli dei dipendenti (Opzioni avanzate, icone nella Squadra) e
non può cambiarle. Gli utenti senza ruolo indicato sono "completo".
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from pathlib import Path

AUTH_ENABLED = os.environ.get("PLANNING_AUTH") == "1"

USERS_FILE = Path("users.json")
KEY_FILE = Path("session.key")
COOKIE_NAME = "zp_planning"
SESSION_SHORT = 12 * 3600          # senza "Ricordami": 12 ore
SESSION_LONG = 30 * 24 * 3600      # con "Ricordami": 30 giorni
MAX_FAILS = 5                      # tentativi sbagliati prima del blocco
LOCK_SECONDS = 5 * 60              # durata del blocco
MIN_PASSWORD = 8
ROLES = ("completo", "limitato")

# Percorsi raggiungibili senza essere entrati
OPEN_PATHS = {"/login", "/style.css", "/api/auth/login", "/api/auth/logout", "/favicon.ico"}


# ---------------------------------------------------------------------
# Password (scrypt, libreria standard: nessuna dipendenza in più)
# ---------------------------------------------------------------------

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = 2 ** 14, 8, 1
    h = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${_b64(salt)}${_b64(h)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, h = stored.split("$")
        calc = hashlib.scrypt(password.encode(), salt=_unb64(salt),
                              n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(calc, _unb64(h))
    except (ValueError, TypeError):
        return False


# Calcolo "a vuoto" per utenti inesistenti: stessa durata di una verifica
# vera, così dai tempi di risposta non si capisce quali utenti esistono.
_DUMMY_HASH = hash_password(secrets.token_hex(8))


def load_users() -> dict:
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_users(users: dict) -> None:
    tmp = USERS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(users, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(USERS_FILE)


# Ogni utente in users.json è {"hash": "...", "role": "..."}; le voci della
# v25.10 erano solo la stringa dell'hash: valgono ancora, con ruolo "completo".

def _hash_of(entry) -> str:
    return entry if isinstance(entry, str) else entry.get("hash", "")


def get_role(username: str | None) -> str:
    entry = load_users().get(username) if username else None
    if isinstance(entry, dict) and entry.get("role") in ROLES:
        return entry["role"]
    return "completo"


def check_credentials(username: str, password: str) -> bool:
    entry = load_users().get(username)
    if entry is None:
        verify_password(password, _DUMMY_HASH)
        return False
    return verify_password(password, _hash_of(entry))


# ---------------------------------------------------------------------
# Cookie di accesso firmato: "utente|scadenza|firma"
# La firma include un pezzo dell'hash della password: cambiando la
# password, le sessioni aperte con quella vecchia non valgono più.
# ---------------------------------------------------------------------

def _secret() -> bytes:
    if not KEY_FILE.exists():
        KEY_FILE.write_text(secrets.token_hex(32), encoding="utf-8")
        os.chmod(KEY_FILE, 0o600)
    return bytes.fromhex(KEY_FILE.read_text(encoding="utf-8").strip())


def _sign(username: str, expires: int, pw_hash: str) -> str:
    msg = f"{username}|{expires}|{pw_hash[-16:]}".encode()
    return _b64(hmac.new(_secret(), msg, hashlib.sha256).digest())


def make_session(username: str, remember: bool) -> tuple[str, int]:
    duration = SESSION_LONG if remember else SESSION_SHORT
    expires = int(time.time()) + duration
    pw_hash = _hash_of(load_users()[username])
    return f"{username}|{expires}|{_sign(username, expires, pw_hash)}", duration


def session_user(cookie: str | None) -> str | None:
    """Utente del cookie, oppure None se manca, è scaduto o è falso."""
    if not cookie:
        return None
    try:
        username, expires, sig = cookie.split("|")
        expires = int(expires)
    except ValueError:
        return None
    if expires < time.time():
        return None
    entry = load_users().get(username)
    if entry is None:
        return None
    pw_hash = _hash_of(entry)
    if not hmac.compare_digest(sig, _sign(username, expires, pw_hash)):
        return None
    return username


# ---------------------------------------------------------------------
# Blocco dopo troppi tentativi sbagliati (per indirizzo IP, in memoria)
# ---------------------------------------------------------------------

_fails: dict[str, list[float]] = {}


def is_locked(ip: str) -> int:
    """Secondi di blocco rimasti per questo IP (0 = libero)."""
    recent = [t for t in _fails.get(ip, []) if time.time() - t < LOCK_SECONDS]
    _fails[ip] = recent
    if len(recent) >= MAX_FAILS:
        return int(LOCK_SECONDS - (time.time() - recent[0])) + 1
    return 0


def record_fail(ip: str) -> None:
    _fails.setdefault(ip, []).append(time.time())


def clear_fails(ip: str) -> None:
    _fails.pop(ip, None)


# ---------------------------------------------------------------------
# Gestione utenti da terminale
# ---------------------------------------------------------------------

def _cli(argv: list[str]) -> int:
    import getpass

    if len(argv) >= 1 and argv[0] == "elenco":
        users = load_users()
        if not users:
            print("(nessun utente)")
        for name in sorted(users):
            print(f"{name:12} {get_role(name)}")
        return 0
    if len(argv) == 2 and argv[0] == "imposta":
        name = argv[1].strip().lower()
        if not name.isalnum():
            print("Nome utente non valido: solo lettere e numeri.")
            return 1
        pw = getpass.getpass(f"Nuova password per {name}: ")
        if len(pw) < MIN_PASSWORD:
            print(f"Troppo corta: almeno {MIN_PASSWORD} caratteri.")
            return 1
        if getpass.getpass("Ripeti la password: ") != pw:
            print("Le due password non coincidono. Nulla è cambiato.")
            return 1
        users = load_users()
        nuovo = name not in users
        users[name] = {"hash": hash_password(pw), "role": "completo" if nuovo else get_role(name)}
        save_users(users)
        print(f"Utente {name} {'creato' if nuovo else 'aggiornato'}.")
        return 0
    if len(argv) == 3 and argv[0] == "ruolo":
        name, role = argv[1].strip().lower(), argv[2].strip().lower()
        users = load_users()
        if name not in users:
            print("Utente non trovato.")
            return 1
        if role not in ROLES:
            print("Ruolo non valido: usa completo oppure limitato.")
            return 1
        users[name] = {"hash": _hash_of(users[name]), "role": role}
        save_users(users)
        print(f"{name}: ruolo {role}.")
        return 0
    if len(argv) == 2 and argv[0] == "rimuovi":
        users = load_users()
        if users.pop(argv[1].strip().lower(), None) is None:
            print("Utente non trovato.")
            return 1
        save_users(users)
        print("Utente rimosso.")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
