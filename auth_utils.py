"""
Hirafi — JWT & Auth utilities (pure Python, no dependencies)
"""
import hmac, hashlib, base64, json, time, os, uuid, secrets, math

# ── JWT Secret — MUST be overridden in production via env ──
SECRET = os.environ.get('JWT_SECRET', '')
if not SECRET:
    # Generate a strong random secret at startup (dev only)
    SECRET = secrets.token_hex(32)
    print('[WARN] JWT_SECRET not set — using random secret (tokens reset on restart)')

TOKEN_EXPIRES_DAYS = int(os.environ.get('TOKEN_EXPIRES_DAYS', '7'))  # shorter in prod

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + '=' * (pad % 4))

def create_token(user_id: str, role: str, expires_days: int = TOKEN_EXPIRES_DAYS) -> str:
    header  = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "id":   user_id,
        "role": role,
        "iat":  int(time.time()),
        "exp":  int(time.time()) + expires_days * 86400,
        "jti":  secrets.token_hex(8),   # unique token ID
    }).encode())
    sig_input = f"{header}.{payload}".encode()
    sig = _b64url(hmac.new(SECRET.encode(), sig_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"

def verify_token(token: str) -> dict:
    try:
        if not token or len(token) > 2048:  # reject oversized tokens
            return None
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header, payload, sig = parts
        sig_input = f"{header}.{payload}".encode()
        expected  = _b64url(hmac.new(SECRET.encode(), sig_input, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_b64url_decode(payload))
        if data.get('exp', 0) < time.time():
            return None
        return data
    except Exception:
        return None

def generate_otp() -> str:
    # Cryptographically secure OTP
    return str(secrets.randbelow(900000) + 100000)

def generate_id() -> str:
    return str(uuid.uuid4())

def haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
