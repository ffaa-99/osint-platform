from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import hashlib
import hmac
import json
import os
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

BASE_DIR    = Path(__file__).resolve().parent.parent
USERS_FILE  = BASE_DIR / "users.json"
SESSION_TTL = 60 * 60 * 8
COOKIE_NAME = "osint_session"
SECRET_KEY  = os.getenv("SECRET_KEY", secrets.token_hex(32))
_sessions: dict = {}

def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def _load_users() -> dict:
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    default = {"admin": {"password_hash": _hash("admin123"), "role": "admin", "created_at": datetime.now().isoformat()}}
    _save_users(default)
    return default

def _save_users(users: dict):
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")

def _make_token() -> str:
    return secrets.token_urlsafe(32)

def login(username: str, password: str) -> Optional[str]:
    users = _load_users()
    user  = users.get(username)
    if not user: return None
    if not hmac.compare_digest(user["password_hash"], _hash(password)): return None
    token = _make_token()
    _sessions[token] = {"username": username, "role": user.get("role","user"),
        "expires_at": (datetime.now() + timedelta(seconds=SESSION_TTL)).isoformat()}
    return token

def logout(token: str):
    _sessions.pop(token, None)

def get_session(token: str) -> Optional[dict]:
    sess = _sessions.get(token)
    if not sess: return None
    if datetime.now() > datetime.fromisoformat(sess["expires_at"]):
        _sessions.pop(token, None); return None
    return sess

def get_current_user(request: Request) -> Optional[dict]:
    token = request.cookies.get(COOKIE_NAME)
    if not token: return None
    return get_session(token)

def require_auth(request: Request) -> dict:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user

def require_admin(request: Request) -> dict:
    user = require_auth(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user

def create_user(username: str, password: str, role: str = "user") -> bool:
    users = _load_users()
    if username in users: return False
    users[username] = {"password_hash": _hash(password), "role": role, "created_at": datetime.now().isoformat()}
    _save_users(users); return True

def delete_user(username: str) -> bool:
    users = _load_users()
    if username not in users or username == "admin": return False
    users.pop(username); _save_users(users)
    for t in [t for t,s in _sessions.items() if s["username"]==username]: _sessions.pop(t)
    return True

def change_password(username: str, new_password: str) -> bool:
    users = _load_users()
    if username not in users: return False
    users[username]["password_hash"] = _hash(new_password)
    _save_users(users); return True

def list_users() -> list:
    users = _load_users()
    return [{"username":u,"role":d["role"],"created_at":d["created_at"]} for u,d in users.items()]

def active_sessions() -> list:
    now = datetime.now()
    return [{"username":s["username"],"role":s["role"],"expires_at":s["expires_at"],"token_prefix":t[:8]+"..."}
        for t,s in _sessions.items() if now <= datetime.fromisoformat(s["expires_at"])]
