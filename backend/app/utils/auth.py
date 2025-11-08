"""Password hashing and JWT token utilities."""

from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os, warnings

# Configure CryptContext with fallback options
pwd_context = CryptContext(
    # Start with strongest schemes, fall back to more compatible ones
    schemes=["pbkdf2_sha256", "sha256_crypt"],
    default="pbkdf2_sha256",
    pbkdf2_sha256__rounds=29000,
    sha256_crypt__rounds=29000,
)

def truncate_password(password: str) -> str:
    """Truncate password to avoid bcrypt's 72-byte limitation."""
    if not isinstance(password, str):
        password = str(password)
    # bcrypt truncates at 72 bytes, not chars; encode first
    encoded = password.encode('utf-8')
    return encoded[:72].decode('utf-8', errors='ignore')

def hash_password(password: str) -> str:
    """Hash password using the configured context with automatic truncation."""
    return pwd_context.hash(truncate_password(password))

def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against hash with proper truncation and error handling."""
    try:
        return pwd_context.verify(truncate_password(plain), hashed)
    except Exception:
        return False

def create_access_token(
    data: dict,
    secret_key: str,
    algorithm: str,
    expires_delta: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
) -> str:
    """Create JWT access token with standard claims (sub, exp).
    Requires secret_key and algorithm to be passed explicitly for safety."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_delta)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)

def decode_token(
    token: str,
    secret_key: str,
    algorithm: str
) -> dict:
    """Decode and verify JWT token.
    Requires secret_key and algorithm to be passed explicitly for safety."""
    try:
        return jwt.decode(token, secret_key, algorithms=[algorithm])
    except JWTError:
        return None