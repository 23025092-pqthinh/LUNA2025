from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
import warnings

from dotenv import load_dotenv
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

# Prefer bcrypt if available and working; otherwise fallback to pbkdf2_sha256 to avoid
# bcrypt binary/import issues on some environments (e.g. mismatched bcrypt wheels).
_schemes = ["bcrypt"]
try:
    import bcrypt as _bcrypt
    # quick sanity check for expected attribute
    _ = getattr(_bcrypt, "__about__", None)
except Exception:
    warnings.warn("bcrypt backend not usable, falling back to pbkdf2_sha256 for password hashing")
    _schemes = ["pbkdf2_sha256"]

pwd_context = CryptContext(schemes=_schemes, deprecated="auto")

def hash_password(password: str):
    # passlib/bcrypt has a 72-byte limit; to avoid ValueError in environments where
    # bcrypt is used, ensure password is not excessively long.
    if isinstance(password, str) and len(password.encode('utf-8')) > 72 and pwd_context.policy.name == 'bcrypt':
        password = password[:72]
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str):
    try:
        return pwd_context.verify(password, hashed)
    except Exception:
        return False

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
