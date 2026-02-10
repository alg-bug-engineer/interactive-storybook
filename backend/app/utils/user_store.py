"""用户与登录态：本地文件系统存储"""
import hashlib
import json
import re
import secrets
from pathlib import Path
from typing import Optional

from app.config import get_settings

# 邮箱格式校验
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _users_dir() -> Path:
    base = Path(__file__).resolve().parent.parent.parent / get_settings().data_dir
    d = base / "users"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _tokens_path() -> Path:
    base = Path(__file__).resolve().parent.parent.parent / get_settings().data_dir
    base.mkdir(parents=True, exist_ok=True)
    return base / "tokens.json"


def _email_to_filename(email: str) -> str:
    """将邮箱转为安全文件名（小写、替换特殊字符）"""
    safe = email.strip().lower().replace("@", "_at_").replace(".", "_")
    return hashlib.sha256(safe.encode()).hexdigest()[:32] + ".json"


def _hash_password(password: str) -> str:
    secret = get_settings().auth_secret
    return hashlib.sha256((secret + password).encode()).hexdigest()


def validate_email(email: str) -> bool:
    return bool(email and EMAIL_RE.match(email.strip()))


def get_user_by_email(email: str) -> Optional[dict]:
    """按邮箱读取用户，返回 None 或 { email, is_paid, created_at }（不含密码）"""
    email = email.strip().lower()
    path = _users_dir() / _email_to_filename(email)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {
            "email": data["email"],
            "is_paid": data.get("is_paid", False),
            "created_at": data.get("created_at", ""),
        }
    except Exception:
        return None


def verify_user(email: str, password: str) -> bool:
    """验证邮箱+密码，返回是否通过。"""
    email = email.strip().lower()
    path = _users_dir() / _email_to_filename(email)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        want = _hash_password(password)
        return data.get("password_hash") == want
    except Exception:
        return False


def create_user(email: str, password: str) -> dict:
    """注册新用户（免费）。邮箱需已校验格式且未被占用。返回用户信息 dict。"""
    email = email.strip().lower()
    if get_user_by_email(email):
        raise ValueError("该邮箱已注册")
    import time
    user = {
        "email": email,
        "password_hash": _hash_password(password),
        "is_paid": False,
        "created_at": str(int(time.time())),
    }
    path = _users_dir() / _email_to_filename(email)
    path.write_text(json.dumps(user, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"email": user["email"], "is_paid": user["is_paid"], "created_at": user["created_at"]}


def set_user_paid(email: str) -> None:
    """将用户设为付费用户。"""
    email = email.strip().lower()
    path = _users_dir() / _email_to_filename(email)
    if not path.exists():
        raise ValueError("用户不存在")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["is_paid"] = True
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- 登录态 token（内存 + 文件持久化，便于重启保留）-----------
def _load_tokens() -> dict:
    p = _tokens_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_tokens(tokens: dict) -> None:
    p = _tokens_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(tokens, ensure_ascii=False), encoding="utf-8")


def create_token(email: str) -> str:
    """创建登录 token，关联邮箱。返回 token 字符串。"""
    email = email.strip().lower()
    token = secrets.token_urlsafe(32)
    tokens = _load_tokens()
    tokens[token] = email
    _save_tokens(tokens)
    return token


def get_email_by_token(token: str) -> Optional[str]:
    """根据 token 取邮箱，无效则返回 None。"""
    if not token or not token.strip():
        return None
    tokens = _load_tokens()
    return tokens.get(token.strip())


def delete_token(token: str) -> None:
    """登出：删除 token。"""
    tokens = _load_tokens()
    tokens.pop(token, None)
    _save_tokens(tokens)
