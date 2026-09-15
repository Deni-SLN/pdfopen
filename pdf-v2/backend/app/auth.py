from datetime import datetime, timedelta, timezone
from jose import jwt
import hashlib, bcrypt
from .config import settings

ALG = "HS256"

def hash_password(p: str) -> str:
    # bcrypt direct, handle 72 char limit by sha256 pre-hash if needed
    pw = p.encode()
    if len(pw) > 72:
        pw = hashlib.sha256(pw).hexdigest().encode()
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode()

def verify_password(p: str, h: str) -> bool:
    pw = p.encode()
    if len(pw) > 72:
        pw = hashlib.sha256(pw).hexdigest().encode()
    try:
        return bcrypt.checkpw(pw, h.encode())
    except: return False

def create_token(sub: str):
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": sub, "exp": exp}, settings.SECRET_KEY, algorithm=ALG)

def decode_token(token: str):
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALG])
