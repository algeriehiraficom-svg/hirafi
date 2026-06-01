"""
Hirafi REST API Server - Pure Python, PostgreSQL (psycopg2), zero dependencies
Run: python server.py
"""
import json, os, sys, traceback, threading, time, re
from psycopg2.extras import RealDictCursor

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8')

# ── PostgreSQL Connection ───────────────────────────────────────────
import psycopg2
DATABASE_URL = os.environ.get('DATABASE_URL', '')
def _pg_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in environment")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# ── Helpers ─────────────────────────────────────────────────────────
def row_to_dict(row):
    if row is None: return None
    return dict(row)

def rows_to_list(rows):
    return [dict(r) for r in rows]

def _cors_origin(handler):
    origin = handler.headers.get('Origin', '')
    if origin in ALLOWED_ORIGINS:
        return origin
    return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else '*'

def json_resp(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False, default=str).encode()
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', len(body))
    handler.send_header('Access-Control-Allow-Origin', _cors_origin(handler))
    handler.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS')
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('X-Frame-Options', 'DENY')
    handler.send_header('Vary', 'Origin')
    handler.end_headers()
    handler.wfile.write(body)

def error(handler, msg, status=400):
    json_resp(handler, {'error': msg}, status)

def read_body(handler) -> dict:
    length = int(handler.headers.get('Content-Length', 0))
    if length == 0: return {}
    try:
        return json.loads(handler.rfile.read(length))
    except:
        return {}

# ── Auth Token ──────────────────────────────────────────────────────
def get_token_user(handler):
    auth = handler.headers.get('Authorization', '')
    token = auth.replace('Bearer ', '').strip()
    if not token: return None
    data = verify_token(token)
    if not data: return None
    conn = _pg_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=%s AND is_active=1", (data['id'],))
    row = c.fetchone()
    conn.close()
    return row_to_dict(row) if row else None

# ── Rate Limiter ────────────────────────────────────────────────────
_rate_lock  = threading.Lock()
_rate_store: dict = {}   # {ip: [(timestamp, path), ...]}

RATE_LIMITS = {
    '/api/auth/send-otp':    (5,  60),   # 5 req / 60s
    '/api/auth/verify-otp':  (10, 60),   # 10 req / 60s
    'default':               (60, 60),   # 60 req / 60s
}

def _check_rate_limit(ip: str, path: str) -> bool:
    """Returns True if allowed, False if rate-limited."""
    max_req, window = RATE_LIMITS.get(path, RATE_LIMITS['default'])
    now = time.time()
    with _rate_lock:
        history = _rate_store.get(ip, [])
        history = [(t, p) for t, p in history if now - t < window]
        path_hits = sum(1 for t, p in history if p == path)
        if path_hits >= max_req:
            _rate_store[ip] = history
            return False
        history.append((now, path))
        _rate_store[ip] = history
    return True

# ── Input Sanitizer ────────────────────────────────────────
def _sanitize_phone(phone: str) -> str | None:
    """Validate Algerian phone number: +213XXXXXXXXX"""
    if not phone:
        return None
    cleaned = re.sub(r'\s', '', phone)
    if re.match(r'^\+213[5-7]\d{8}$', cleaned):
        return cleaned
    return None

def _safe_str(val, max_len: int = 500) -> str:
    if val is None:
        return ''
    return str(val)[:max_len].strip()

from database  import get_conn, init_db
from auth_utils import verify_token, create_token, generate_otp, generate_id, haversine_km

PORT       = int(os.environ.get('PORT', 5000))
COMMISSION = float(os.environ.get('COMMISSION_RATE', '0.10'))
DEBUG      = os.environ.get('DEBUG', '0') == '1'          # dev only
ALLOWED_ORIGINS = os.environ.get(
    'ALLOWED_ORIGINS',
    'http://localhost:3021,http://localhost:3000,http://127.0.0.1:3021'
).split(',')

# ── Helpers ────────────────────────────────────────────────────
def row_to_dict(row):
    if row is None: return None
    return dict(row)

def rows_to_list(rows):
    return [dict(r) for r in rows]

def _cors_origin(handler):
    origin = handler.headers.get('Origin', '')
    if origin in ALLOWED_ORIGINS:
        return origin
    return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else '*'

def json_resp(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False, default=str).encode()
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', len(body))
    handler.send_header('Access-Control-Allow-Origin', _cors_origin(handler))
    handler.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS')
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('X-Frame-Options', 'DENY')
    handler.send_header('Vary', 'Origin')
    handler.end_headers()
    handler.wfile.write(body)

def error(handler, msg, status=400):
    json_resp(handler, {'error': msg}, status)

def get_token_user(handler):
    auth = handler.headers.get('Authorization', '')
    token = auth.replace('Bearer ', '').strip()
    if not token: return None
    data = verify_token(token)
    if not data: return None
    conn = get_conn()
    row  = conn.execute("SELECT * FROM users WHERE id=? AND is_active=1", (data['id'],)).fetchone()
    conn.close()
    return row_to_dict(row) if row else None

def read_body(handler) -> dict:
    length = int(handler.headers.get('Content-Length', 0))
    if length == 0: return {}
    try:
        return json.loads(handler.rfile.read(length))
    except:
        return {}

# ── Router ─────────────────────────────────────────────────────
class HirafiHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {fmt % args}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', _cors_origin(self))
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, DELETE, OPTIONS')
        self.send_header('Access-Control-Max-Age', '86400')
        self.send_header('Vary', 'Origin')
        self.end_headers()

    def do_GET(self):    self.route('GET')
    def do_POST(self):   self.route('POST')
    def do_PATCH(self):  self.route('PATCH')
    def do_PUT(self):    self.route('PATCH')  # treat PUT as PATCH
    def do_DELETE(self): self.route('DELETE')

    def route(self, method):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip('/')
        query  = parse_qs(parsed.query)
        params = {k: v[0] for k, v in query.items()}

        # Rate limiting
        client_ip = self.headers.get('X-Forwarded-For', self.client_address[0]).split(',')[0].strip()
        if not _check_rate_limit(client_ip, path):
            return json_resp(self, {'error': 'Too many requests. Please try again later.'}, 429)

        try:
            # ── Health ─────────────────────────────────────────
            if method == 'GET' and path == '/health':
                return json_resp(self, {'status': 'ok', 'app': 'حرفيكم', 'version': '1.0.0'})

            # ── Auth ───────────────────────────────────────────
            if method == 'POST' and path == '/api/auth/send-otp':
                return self.auth_send_otp()
            if method == 'POST' and path == '/api/auth/verify-otp':
                return self.auth_verify_otp()
            if method == 'GET'  and path == '/api/auth/me':
                return self.auth_me()
            if method == 'PATCH' and path == '/api/auth/profile':
                return self.auth_update_profile()

            # ── Specialties ────────────────────────────────────
            if method == 'GET' and path == '/api/specialties':
                return self.get_specialties()

            # ── Craftsmen ──────────────────────────────────────
            if method == 'GET' and path == '/api/craftsmen/nearby':
                return self.craftsmen_nearby(params)
            if method == 'GET' and path.startswith('/api/craftsmen/') and len(path.split('/')) == 4:
                cid = path.split('/')[-1]
                return self.craftsman_get(cid)
            if method == 'PATCH' and path == '/api/craftsmen/me':
                return self.craftsman_update()
            if method == 'PATCH' and path == '/api/craftsmen/me/location':
                return self.craftsman_update_location()

            # ── Requests ───────────────────────────────────────
            if method == 'POST' and path == '/api/requests':
                return self.request_create()
            if method == 'GET'  and path == '/api/requests':
                return self.request_list(params)
            if method == 'GET'  and path.startswith('/api/requests/') and not path.endswith('/status'):
                rid = path.split('/')[-1]
                return self.request_get(rid)
            if method == 'PATCH' and path.endswith('/status'):
                rid = path.split('/')[-2]
                return self.request_update_status(rid)

            # ── Reviews ────────────────────────────────────────
            if method == 'POST' and path == '/api/reviews':
                return self.review_create()
            if method == 'GET' and path.startswith('/api/reviews/craftsman/'):
                uid = path.split('/')[-1]
                return self.reviews_by_craftsman(uid)

            # ── Payments ───────────────────────────────────────
            if method == 'GET'  and path == '/api/payments/wallet':
                return self.wallet_get()
            if method == 'POST' and path == '/api/payments/top-up':
                return self.wallet_topup()
            if method == 'POST' and path == '/api/payments/subscribe':
                return self.wallet_subscribe()
            if method == 'POST' and path == '/api/payments/withdraw':
                return self.wallet_withdraw()

            # ── Subscription Requests (manual payment) ─────────
            if method == 'POST' and path == '/api/payments/subscription-request':
                return self.sub_request_create()
            if method == 'GET'  and path == '/api/payments/subscription-request':
                return self.sub_request_get()
            if method == 'GET'  and path == '/api/admin/subscription-requests':
                return self.admin_sub_requests(params)
            if method == 'PATCH' and path.startswith('/api/admin/subscription-requests/'):
                sid = path.split('/')[-1]
                return self.admin_sub_approve(sid)

            # ── Notifications ──────────────────────────────────
            if method == 'GET'  and path == '/api/notifications':
                return self.notif_list()
            if method == 'PATCH' and path == '/api/notifications/read-all':
                return self.notif_read_all()
            if method == 'PATCH' and path.startswith('/api/notifications/') and path.endswith('/read'):
                nid = path.split('/')[-2]
                return self.notif_read_one(nid)

            # ── Messages ───────────────────────────────────────
            if method == 'GET'  and path.startswith('/api/messages/'):
                rid = path.split('/')[-1]
                return self.messages_list(rid)
            if method == 'POST' and path == '/api/messages':
                return self.message_create()

            # ── Admin ──────────────────────────────────────────
            if method == 'GET'  and path == '/api/admin/stats':
                return self.admin_stats()
            if method == 'GET'  and path == '/api/admin/craftsmen':
                return self.admin_craftsmen(params)
            if method == 'GET'  and path == '/api/admin/users':
                return self.admin_users(params)
            if method == 'PATCH' and path.endswith('/verify') and '/craftsmen/' in path:
                cid = path.split('/')[-2]
                return self.admin_verify_craftsman(cid)
            if method == 'PATCH' and path.endswith('/suspend') and '/users/' in path:
                uid = path.split('/')[-2]
                return self.admin_suspend_user(uid)
            if method == 'GET'  and path == '/api/admin/requests':
                return self.admin_requests(params)
            if method == 'GET'  and path == '/api/admin/revenue':
                return self.admin_revenue()

            error(self, 'Route not found', 404)

        except Exception as e:
            traceback.print_exc()
            error(self, str(e), 500)

    # ════════════════════════════════════════════════════════════
    # AUTH
    # ════════════════════════════════════════════════════════════

    def auth_send_otp(self):
        body  = read_body(self)
        phone = _sanitize_phone(body.get('phone', ''))
        if not phone:
            return error(self, 'Numéro invalide. Format requis: +213XXXXXXXXX')

        code       = generate_otp()
        expires_at = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
        conn = get_conn()
        # Clean expired OTPs for this phone
        conn.execute("DELETE FROM otp_codes WHERE phone=? AND expires_at<?",
                     (phone, datetime.utcnow().isoformat()))
        # Max 3 active OTPs per phone
        active = conn.execute(
            "SELECT COUNT(*) FROM otp_codes WHERE phone=? AND used=0", (phone,)
        ).fetchone()[0]
        if active >= 3:
            conn.close()
            return error(self, 'Trop de tentatives. Réessayez dans 5 minutes.', 429)

        conn.execute("INSERT INTO otp_codes(phone,code,expires_at) VALUES(?,?,?)",
                     (phone, code, expires_at))
        conn.commit()
        conn.close()
        print(f"[OTP] {phone} -> {code}")
        resp = {'message': 'OTP sent'}
        if DEBUG:
            resp['dev_code'] = code
        json_resp(self, resp)

    def auth_verify_otp(self):
        body  = read_body(self)
        phone = _sanitize_phone(body.get('phone', ''))
        code  = re.sub(r'\D', '', str(body.get('code', '')))[:6]
        role  = body.get('role', 'client') if body.get('role') in ('client','craftsman','admin') else 'client'
        name  = _safe_str(body.get('name', ''), 100)

        if not phone:
            return error(self, 'Numéro de téléphone invalide')
        if not code or len(code) != 6:
            return error(self, 'Code OTP invalide (6 chiffres requis)')

        conn = get_conn()
        now  = datetime.utcnow().isoformat()

        # Dev bypass: only allowed when DEBUG=1
        if DEBUG and code == '000000':
            otp = {'id': None}
        else:
            otp = conn.execute(
                "SELECT * FROM otp_codes WHERE phone=? AND code=? AND used=0 AND expires_at>? ORDER BY created_at DESC LIMIT 1",
                (phone, code, now)
            ).fetchone()
            if not otp:
                conn.close()
                return error(self, 'Invalid or expired OTP', 401)

        if otp['id']:
            conn.execute("UPDATE otp_codes SET used=1 WHERE id=?", (otp['id'],))

        user = conn.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
        is_new = False
        if not user:
            uid = generate_id()
            conn.execute(
                "INSERT INTO users(id,phone,name,role) VALUES(?,?,?,?)",
                (uid, phone, name or phone, role)
            )
            if role == 'craftsman':
                cid = generate_id()
                conn.execute("INSERT INTO craftsmen(id,user_id) VALUES(?,?)", (cid, uid))
            user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            is_new = True
        else:
            # If role provided explicitly and craftsman record missing, create it
            if role == 'craftsman' and row_to_dict(user)['role'] == 'craftsman':
                existing = conn.execute("SELECT id FROM craftsmen WHERE user_id=?", (row_to_dict(user)['id'],)).fetchone()
                if not existing:
                    cid = generate_id()
                    conn.execute("INSERT INTO craftsmen(id,user_id) VALUES(?,?)", (cid, row_to_dict(user)['id']))

        conn.commit()
        conn.close()

        user_dict = row_to_dict(user)
        token = create_token(user_dict['id'], user_dict['role'])
        json_resp(self, {
            'token': token,
            'user': {k: user_dict[k] for k in ('id','phone','name','role')},
            'is_new': is_new
        })

    def auth_me(self):
        user = get_token_user(self)
        if not user: return error(self, 'Unauthorized', 401)
        conn = get_conn()
        craftsman = None
        if user['role'] == 'craftsman':
            row = conn.execute("SELECT * FROM craftsmen WHERE user_id=?", (user['id'],)).fetchone()
            craftsman = row_to_dict(row)
        conn.close()
        result = {**user}
        if craftsman:
            result.update({k: craftsman[k] for k in ('id','rating','total_jobs','is_available','subscription_active','wallet_balance','city','wilaya') if k in craftsman})
            result['craftsman_id'] = craftsman['id']
        json_resp(self, {'user': result})

    def auth_update_profile(self):
        user = get_token_user(self)
        if not user: return error(self, 'Unauthorized', 401)
        body = read_body(self)
        conn = get_conn()
        conn.execute(
            "UPDATE users SET name=COALESCE(?,name), email=COALESCE(?,email), fcm_token=COALESCE(?,fcm_token), updated_at=datetime('now') WHERE id=?",
            (body.get('name'), body.get('email'), body.get('fcm_token'), user['id'])
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id=?", (user['id'],)).fetchone()
        conn.close()
        json_resp(self, row_to_dict(row))

    # ════════════════════════════════════════════════════════════
    # SPECIALTIES
    # ════════════════════════════════════════════════════════════

    def get_specialties(self):
        conn = get_conn()
        rows = conn.execute("SELECT * FROM specialties ORDER BY id").fetchall()
        conn.close()
        json_resp(self, {'specialties': rows_to_list(rows)})

    # ════════════════════════════════════════════════════════════
    # CRAFTSMEN
    # ════════════════════════════════════════════════════════════

    def craftsmen_nearby(self, params):
        user = get_token_user(self)
        if not user: return error(self, 'Unauthorized', 401)
        try:
            lat    = float(params.get('lat', 0))
            lng    = float(params.get('lng', 0))
            radius = float(params.get('radius', 10))
            spec   = params.get('specialty_id')
        except:
            return error(self, 'Invalid parameters')

        conn  = get_conn()
        query = """
            SELECT c.*, u.name, u.avatar_url,
                   GROUP_CONCAT(DISTINCT s.name_ar) AS specialties_str
            FROM craftsmen c
            JOIN users u ON u.id = c.user_id
            LEFT JOIN craftsman_specialties cs ON cs.craftsman_id = c.id
            LEFT JOIN specialties s ON s.id = cs.specialty_id
            WHERE c.is_available=1
              AND c.subscription_active=1
              AND c.lat IS NOT NULL AND c.lng IS NOT NULL
        """
        args = []
        if spec:
            query += " AND cs.specialty_id=?"
            args.append(int(spec))
        query += " GROUP BY c.id ORDER BY c.rating DESC LIMIT 50"

        rows = conn.execute(query, args).fetchall()
        conn.close()

        results = []
        for r in rows:
            d = dict(r)
            dist = haversine_km(lat, lng, d.get('lat') or 0, d.get('lng') or 0)
            if dist <= radius:
                d['distance_km'] = round(dist, 1)
                d['specialties'] = (d.get('specialties_str') or '').split(',')
                results.append(d)

        results.sort(key=lambda x: x['distance_km'])
        json_resp(self, {'craftsmen': results[:30]})

    def craftsman_get(self, craftsman_id):
        conn = get_conn()
        row  = conn.execute("""
            SELECT c.*, u.name, u.phone, u.avatar_url
            FROM craftsmen c JOIN users u ON u.id=c.user_id
            WHERE c.id=?
        """, (craftsman_id,)).fetchone()
        if not row:
            conn.close()
            return error(self, 'Craftsman not found', 404)
        d = dict(row)

        specs = conn.execute("""
            SELECT s.id, s.name_ar, s.icon FROM specialties s
            JOIN craftsman_specialties cs ON cs.specialty_id=s.id
            WHERE cs.craftsman_id=?
        """, (craftsman_id,)).fetchall()
        d['specialties'] = rows_to_list(specs)

        photos = conn.execute(
            "SELECT url FROM craftsman_photos WHERE craftsman_id=? AND type='work'",
            (craftsman_id,)
        ).fetchall()
        d['work_photos'] = [p['url'] for p in photos]
        conn.close()
        json_resp(self, d)

    def craftsman_update(self):
        user = get_token_user(self)
        if not user or user['role'] != 'craftsman':
            return error(self, 'Forbidden', 403)
        body = read_body(self)
        conn = get_conn()
        conn.execute("""
            UPDATE craftsmen SET
                bio=COALESCE(?,bio), experience_years=COALESCE(?,experience_years),
                price_min=COALESCE(?,price_min), price_max=COALESCE(?,price_max),
                city=COALESCE(?,city), wilaya=COALESCE(?,wilaya),
                is_available=COALESCE(?,is_available), updated_at=datetime('now')
            WHERE user_id=?
        """, (body.get('bio'), body.get('experience_years'), body.get('price_min'),
              body.get('price_max'), body.get('city'), body.get('wilaya'),
              body.get('is_available'), user['id']))

        spec_list = body.get('specialty_ids') or body.get('specialties')
        if spec_list:
            craft = conn.execute("SELECT id FROM craftsmen WHERE user_id=?", (user['id'],)).fetchone()
            if craft:
                conn.execute("DELETE FROM craftsman_specialties WHERE craftsman_id=?", (craft['id'],))
                for sid in spec_list:
                    conn.execute("INSERT OR IGNORE INTO craftsman_specialties VALUES(?,?)", (craft['id'], int(sid)))

        conn.commit()
        row = conn.execute("SELECT * FROM craftsmen WHERE user_id=?", (user['id'],)).fetchone()
        conn.close()
        json_resp(self, {'craftsman': row_to_dict(row)})

    def craftsman_update_location(self):
        user = get_token_user(self)
        if not user or user['role'] != 'craftsman':
            return error(self, 'Forbidden', 403)
        body = read_body(self)
        lat, lng = body.get('lat'), body.get('lng')
        if lat is None or lng is None:
            return error(self, 'lat and lng required')
        conn = get_conn()
        conn.execute("UPDATE craftsmen SET lat=?, lng=?, updated_at=datetime('now') WHERE user_id=?",
                     (float(lat), float(lng), user['id']))
        conn.commit()
        conn.close()
        json_resp(self, {'message': 'Location updated'})

    # ════════════════════════════════════════════════════════════
    # REQUESTS
    # ════════════════════════════════════════════════════════════

    def request_create(self):
        user = get_token_user(self)
        if not user or user['role'] != 'client':
            return error(self, 'Forbidden', 403)
        body = read_body(self)
        rid  = generate_id()
        conn = get_conn()
        conn.execute("""
            INSERT INTO requests(id,client_id,craftsman_id,specialty_id,title,description,
                lat,lng,address_text,city,scheduled_at,notes)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (rid, user['id'], body.get('craftsman_id'), body.get('specialty_id'),
              body.get('title'), body.get('description'),
              body.get('lat'), body.get('lng'), body.get('address_text'),
              body.get('city'), body.get('scheduled_at'), body.get('notes')))

        # Notification for craftsman
        if body.get('craftsman_id'):
            craft_user = conn.execute(
                "SELECT u.id FROM craftsmen c JOIN users u ON u.id=c.user_id WHERE c.id=?",
                (body['craftsman_id'],)
            ).fetchone()
            if craft_user:
                nid = generate_id()
                conn.execute(
                    "INSERT INTO notifications(id,user_id,type,title,body) VALUES(?,?,?,?,?)",
                    (nid, craft_user['id'], 'new_request',
                     '🔔 طلب خدمة جديد!', f"{body.get('title','طلب جديد')} — {body.get('city','')}")
                )

        conn.commit()
        row = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
        conn.close()
        json_resp(self, {'request': row_to_dict(row)}, 201)

    def request_list(self, params):
        user = get_token_user(self)
        if not user: return error(self, 'Unauthorized', 401)
        status = params.get('status')
        conn = get_conn()

        if user['role'] == 'client':
            q = """SELECT r.*, u.name AS craftsman_name, s.name_ar AS specialty
                   FROM requests r
                   LEFT JOIN craftsmen c ON c.id=r.craftsman_id
                   LEFT JOIN users u ON u.id=c.user_id
                   LEFT JOIN specialties s ON s.id=r.specialty_id
                   WHERE r.client_id=?"""
            args = [user['id']]
        elif user['role'] == 'craftsman':
            craft = conn.execute("SELECT id FROM craftsmen WHERE user_id=?", (user['id'],)).fetchone()
            if not craft: conn.close(); return json_resp(self, [])
            q = """SELECT r.*, u.name AS client_name, s.name_ar AS specialty
                   FROM requests r
                   JOIN users u ON u.id=r.client_id
                   LEFT JOIN specialties s ON s.id=r.specialty_id
                   WHERE r.craftsman_id=?"""
            args = [craft['id']]
        else:
            q    = "SELECT * FROM requests WHERE 1=1"
            args = []

        if status:
            q += " AND r.status=?" if user['role'] != 'admin' else " AND status=?"
            args.append(status)
        q += " ORDER BY created_at DESC LIMIT 50"

        rows = conn.execute(q, args).fetchall()
        conn.close()
        json_resp(self, {'requests': rows_to_list(rows)})

    def request_get(self, rid):
        conn = get_conn()
        row  = conn.execute("""
            SELECT r.*,
                   uc.name AS client_name, uc.phone AS client_phone,
                   uh.id AS craftsman_user_id,
                   uh.name AS craftsman_name, uh.phone AS craftsman_phone,
                   s.name_ar AS specialty, s.icon AS specialty_icon
            FROM requests r
            JOIN users uc ON uc.id=r.client_id
            LEFT JOIN craftsmen c ON c.id=r.craftsman_id
            LEFT JOIN users uh ON uh.id=c.user_id
            LEFT JOIN specialties s ON s.id=r.specialty_id
            WHERE r.id=?
        """, (rid,)).fetchone()
        conn.close()
        if not row: return error(self, 'Request not found', 404)
        json_resp(self, row_to_dict(row))

    def request_update_status(self, rid):
        user = get_token_user(self)
        if not user: return error(self, 'Unauthorized', 401)
        body   = read_body(self)
        status = body.get('status')
        price  = body.get('price_agreed')

        allowed = {
            'craftsman': ['accepted', 'in_progress', 'completed'],
            'client':    ['cancelled'],
            'admin':     ['cancelled', 'disputed']
        }
        if status not in allowed.get(user['role'], []):
            return error(self, 'Status transition not allowed', 403)

        now  = datetime.utcnow().isoformat()
        conn = get_conn()
        extra_fields = ''
        extra_args   = []
        if status == 'in_progress':
            extra_fields = ', started_at=?'
            extra_args   = [now]
        elif status == 'completed':
            extra_fields = ', completed_at=?'
            extra_args   = [now]

        conn.execute(
            f"UPDATE requests SET status=?, price_agreed=COALESCE(?,price_agreed){extra_fields}, updated_at=? WHERE id=?",
            [status, price] + extra_args + [now, rid]
        )

        # Auto-commission on electronic payment completion
        if status == 'completed':
            req = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
            if req and req['payment_method'] == 'electronic' and req['price_agreed']:
                commission = int(req['price_agreed'] * COMMISSION)
                craft = conn.execute("SELECT id FROM craftsmen WHERE id=?", (req['craftsman_id'],)).fetchone()
                if craft:
                    conn.execute("UPDATE craftsmen SET wallet_balance=wallet_balance-? WHERE id=?",
                                 (commission, craft['id']))
                    conn.execute(
                        "INSERT INTO transactions(id,craftsman_id,request_id,type,amount) VALUES(?,?,?,?,?)",
                        (generate_id(), craft['id'], rid, 'commission', -commission)
                    )

        conn.commit()
        row = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
        conn.close()
        json_resp(self, row_to_dict(row))

    # ════════════════════════════════════════════════════════════
    # REVIEWS
    # ════════════════════════════════════════════════════════════

    def review_create(self):
        user = get_token_user(self)
        if not user: return error(self, 'Unauthorized', 401)
        body = read_body(self)
        conn = get_conn()
        req  = conn.execute(
            "SELECT * FROM requests WHERE id=?", (body.get('request_id'),)
        ).fetchone()
        if not req:
            conn.close(); return error(self, 'Request not found', 404)
        if req['status'] != 'completed':
            conn.close(); return error(self, 'Request must be completed first')

        try:
            conn.execute("""
                INSERT INTO reviews(request_id,reviewer_id,reviewee_id,rating,comment)
                VALUES(?,?,?,?,?)
                ON CONFLICT(request_id,reviewer_id) DO UPDATE SET rating=?,comment=?
            """, (body['request_id'], user['id'], body['reviewee_id'],
                  body['rating'], body.get('comment'),
                  body['rating'], body.get('comment')))

            # Update craftsman average rating
            avg = conn.execute(
                "SELECT AVG(rating) AS avg, COUNT(*) AS cnt FROM reviews WHERE reviewee_id=?",
                (body['reviewee_id'],)
            ).fetchone()
            conn.execute(
                "UPDATE craftsmen SET rating=ROUND(?,1), total_reviews=? WHERE user_id=?",
                (avg['avg'] or 0, avg['cnt'], body['reviewee_id'])
            )
            conn.commit()
        except Exception as e:
            conn.close(); return error(self, str(e))

        conn.close()
        json_resp(self, {'message': 'Review submitted'}, 201)

    def reviews_by_craftsman(self, user_id):
        conn  = get_conn()
        rows  = conn.execute("""
            SELECT rv.*, u.name AS reviewer_name
            FROM reviews rv JOIN users u ON u.id=rv.reviewer_id
            WHERE rv.reviewee_id=? ORDER BY rv.created_at DESC LIMIT 20
        """, (user_id,)).fetchall()
        conn.close()
        json_resp(self, {'reviews': rows_to_list(rows)})

    # ════════════════════════════════════════════════════════════
    # PAYMENTS / WALLET
    # ════════════════════════════════════════════════════════════

    def wallet_get(self):
        user = get_token_user(self)
        if not user or user['role'] != 'craftsman':
            return error(self, 'Forbidden', 403)
        conn  = get_conn()
        craft = conn.execute("SELECT * FROM craftsmen WHERE user_id=?", (user['id'],)).fetchone()
        if not craft: conn.close(); return error(self, 'Craftsman not found', 404)
        txs = conn.execute(
            "SELECT * FROM transactions WHERE craftsman_id=? ORDER BY created_at DESC LIMIT 20",
            (craft['id'],)
        ).fetchall()
        conn.close()
        result = dict(craft)
        result['balance'] = result.get('wallet_balance', 0)
        result['transactions'] = rows_to_list(txs)
        json_resp(self, result)

    def wallet_topup(self):
        user = get_token_user(self)
        if not user or user['role'] != 'craftsman':
            return error(self, 'Forbidden', 403)
        body   = read_body(self)
        amount = int(body.get('amount', 0))
        if amount < 500: return error(self, 'Minimum top-up is 500 DZD')
        conn  = get_conn()
        craft = conn.execute("SELECT id FROM craftsmen WHERE user_id=?", (user['id'],)).fetchone()
        if not craft: conn.close(); return error(self, 'Craftsman not found', 404)
        conn.execute("UPDATE craftsmen SET wallet_balance=wallet_balance+? WHERE id=?", (amount, craft['id']))
        conn.execute(
            "INSERT INTO transactions(id,craftsman_id,type,amount) VALUES(?,?,?,?)",
            (generate_id(), craft['id'], 'top_up', amount)
        )
        conn.commit()
        conn.close()
        json_resp(self, {'message': 'Wallet topped up', 'amount': amount})

    def wallet_subscribe(self):
        user = get_token_user(self)
        if not user or user['role'] != 'craftsman':
            return error(self, 'Forbidden', 403)
        body  = read_body(self)
        plan  = body.get('plan', 'basic')
        price = 2000 if plan == 'premium' else 1000
        conn  = get_conn()
        craft = conn.execute("SELECT * FROM craftsmen WHERE user_id=?", (user['id'],)).fetchone()
        if not craft: conn.close(); return error(self, 'Craftsman not found', 404)
        if craft['wallet_balance'] < price:
            conn.close(); return error(self, 'Insufficient balance. Please top up first.')

        start = datetime.utcnow().date().isoformat()
        end   = (datetime.utcnow() + timedelta(days=30)).date().isoformat()
        conn.execute("UPDATE craftsmen SET wallet_balance=wallet_balance-?, subscription_active=1 WHERE id=?",
                     (price, craft['id']))
        conn.execute(
            "INSERT INTO subscriptions(craftsman_id,plan,price,start_date,end_date) VALUES(?,?,?,?,?)",
            (craft['id'], plan, price, start, end)
        )
        conn.execute(
            "INSERT INTO transactions(id,craftsman_id,type,amount) VALUES(?,?,?,?)",
            (generate_id(), craft['id'], 'subscription', -price)
        )
        conn.commit()
        conn.close()
        json_resp(self, {'message': 'Subscription activated', 'plan': plan, 'expires': end})

    def wallet_withdraw(self):
        user = get_token_user(self)
        if not user or user['role'] != 'craftsman':
            return error(self, 'Forbidden', 403)
        body   = read_body(self)
        amount = int(body.get('amount', 0))
        conn   = get_conn()
        craft  = conn.execute("SELECT * FROM craftsmen WHERE user_id=?", (user['id'],)).fetchone()
        if not craft: conn.close(); return error(self, 'Craftsman not found', 404)
        if craft['wallet_balance'] < amount:
            conn.close(); return error(self, 'Insufficient balance')
        conn.execute("UPDATE craftsmen SET wallet_balance=wallet_balance-? WHERE id=?", (amount, craft['id']))
        conn.execute(
            "INSERT INTO transactions(id,craftsman_id,type,amount,status) VALUES(?,?,?,?,?)",
            (generate_id(), craft['id'], 'withdrawal', -amount, 'pending')
        )
        conn.commit()
        conn.close()
        json_resp(self, {'message': 'Withdrawal request submitted. Processing within 48 hours.'})

    # ════════════════════════════════════════════════════════════
    # SUBSCRIPTION REQUESTS (manual payment verification)
    # ════════════════════════════════════════════════════════════

    def sub_request_create(self):
        user = get_token_user(self)
        if not user or user['role'] != 'craftsman':
            return error(self, 'Forbidden', 403)
        body   = read_body(self)
        plan   = body.get('plan', 'basic')
        amount = 2000 if plan == 'premium' else 1000
        ref    = body.get('reference', '').strip()
        method = body.get('payment_method', 'baridimob')

        conn  = get_conn()
        craft = conn.execute("SELECT * FROM craftsmen WHERE user_id=?", (user['id'],)).fetchone()
        if not craft:
            conn.close(); return error(self, 'Craftsman not found', 404)

        # Check no pending request already exists
        existing = conn.execute(
            "SELECT id FROM subscription_requests WHERE craftsman_id=? AND status='pending'",
            (craft['id'],)
        ).fetchone()
        if existing:
            conn.close()
            return error(self, 'لديك طلب اشتراك معلق بالفعل، انتظر موافقة الإدارة')

        sid = generate_id()
        conn.execute(
            "INSERT INTO subscription_requests(id,craftsman_id,user_id,plan,amount,payment_method,reference) VALUES(?,?,?,?,?,?,?)",
            (sid, craft['id'], user['id'], plan, amount, method, ref)
        )

        # Notify admin
        admin = conn.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()
        if admin:
            conn.execute(
                "INSERT INTO notifications(id,user_id,type,title,body) VALUES(?,?,?,?,?)",
                (generate_id(), admin['id'], 'sub_request',
                 '💳 طلب اشتراك جديد',
                 f"{user.get('name','حرفي')} — {plan} — {amount} دج — ref: {ref or 'بدون مرجع'}")
            )
        conn.commit()
        conn.close()
        json_resp(self, {
            'message': 'تم إرسال طلب الاشتراك، سيتم تفعيله خلال 24 ساعة بعد التحقق',
            'id': sid,
            'amount': amount,
            'plan': plan,
        }, 201)

    def sub_request_get(self):
        user = get_token_user(self)
        if not user or user['role'] != 'craftsman':
            return error(self, 'Forbidden', 403)
        conn  = get_conn()
        craft = conn.execute("SELECT id FROM craftsmen WHERE user_id=?", (user['id'],)).fetchone()
        if not craft:
            conn.close(); return json_resp(self, {'request': None})
        row = conn.execute(
            "SELECT * FROM subscription_requests WHERE craftsman_id=? ORDER BY created_at DESC LIMIT 1",
            (craft['id'],)
        ).fetchone()
        conn.close()
        json_resp(self, {'request': dict(row) if row else None})

    def admin_sub_requests(self, params):
        if not self._require_admin(): return
        status = params.get('status', 'pending')
        conn   = get_conn()
        rows   = conn.execute("""
            SELECT sr.*, u.name, u.phone, c.city, c.subscription_active
            FROM subscription_requests sr
            JOIN users u ON u.id = sr.user_id
            JOIN craftsmen c ON c.id = sr.craftsman_id
            WHERE sr.status=?
            ORDER BY sr.created_at DESC LIMIT 100
        """, (status,)).fetchall()
        conn.close()
        json_resp(self, {'requests': rows_to_list(rows)})

    def admin_sub_approve(self, sub_id):
        admin = self._require_admin()
        if not admin: return
        body   = read_body(self)
        action = body.get('action', 'approve')  # 'approve' | 'reject'
        note   = body.get('note', '')
        now    = datetime.utcnow().isoformat()

        conn = get_conn()
        sub  = conn.execute("SELECT * FROM subscription_requests WHERE id=?", (sub_id,)).fetchone()
        if not sub:
            conn.close(); return error(self, 'Request not found', 404)
        if sub['status'] != 'pending':
            conn.close(); return error(self, 'Request already reviewed')

        conn.execute(
            "UPDATE subscription_requests SET status=?, admin_note=?, reviewed_at=? WHERE id=?",
            (('approved' if action == 'approve' else 'rejected'), note, now, sub_id)
        )

        if action == 'approve':
            start = datetime.utcnow().date().isoformat()
            end   = (datetime.utcnow() + __import__('datetime').timedelta(days=30)).date().isoformat()
            conn.execute(
                "UPDATE craftsmen SET subscription_active=1 WHERE id=?",
                (sub['craftsman_id'],)
            )
            conn.execute(
                "INSERT INTO subscriptions(craftsman_id,plan,price,start_date,end_date) VALUES(?,?,?,?,?)",
                (sub['craftsman_id'], sub['plan'], sub['amount'], start, end)
            )
            conn.execute(
                "INSERT INTO transactions(id,craftsman_id,type,amount,reference) VALUES(?,?,?,?,?)",
                (generate_id(), sub['craftsman_id'], 'subscription', -sub['amount'], sub['reference'])
            )
            notif_title = '✅ تم تفعيل اشتراكك!'
            notif_body  = f"اشتراك {sub['plan']} مفعّل حتى {end}. يمكنك الآن استقبال طلبات العملاء."
        else:
            notif_title = '❌ طلب الاشتراك مرفوض'
            notif_body  = note or 'لم يتم التحقق من الدفع. تواصل مع الإدارة.'

        conn.execute(
            "INSERT INTO notifications(id,user_id,type,title,body) VALUES(?,?,?,?,?)",
            (generate_id(), sub['user_id'], 'sub_result', notif_title, notif_body)
        )
        conn.commit()
        conn.close()
        json_resp(self, {
            'message': 'approved' if action == 'approve' else 'rejected',
            'subscription_active': action == 'approve'
        })

    # ════════════════════════════════════════════════════════════
    # NOTIFICATIONS
    # ════════════════════════════════════════════════════════════

    def notif_list(self):
        user = get_token_user(self)
        if not user: return error(self, 'Unauthorized', 401)
        conn = get_conn()
        rows = conn.execute(
            "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 30",
            (user['id'],)
        ).fetchall()
        conn.close()
        json_resp(self, {'notifications': rows_to_list(rows)})

    def notif_read_all(self):
        user = get_token_user(self)
        if not user: return error(self, 'Unauthorized', 401)
        conn = get_conn()
        conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user['id'],))
        conn.commit()
        conn.close()
        json_resp(self, {'message': 'All read'})

    def notif_read_one(self, notif_id):
        user = get_token_user(self)
        if not user: return error(self, 'Unauthorized', 401)
        conn = get_conn()
        conn.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (notif_id, user['id']))
        conn.commit()
        conn.close()
        json_resp(self, {'message': 'Notification marked as read'})

    # ════════════════════════════════════════════════════════════
    # MESSAGES
    # ════════════════════════════════════════════════════════════

    def messages_list(self, request_id):
        user = get_token_user(self)
        if not user: return error(self, 'Unauthorized', 401)
        conn = get_conn()
        rows = conn.execute("""
            SELECT m.*, u.name AS sender_name FROM messages m
            JOIN users u ON u.id=m.sender_id
            WHERE m.request_id=? ORDER BY m.created_at ASC
        """, (request_id,)).fetchall()
        conn.close()
        json_resp(self, {'messages': rows_to_list(rows)})

    def message_create(self):
        user = get_token_user(self)
        if not user: return error(self, 'Unauthorized', 401)
        body = read_body(self)
        mid  = generate_id()
        conn = get_conn()
        conn.execute(
            "INSERT INTO messages(id,request_id,sender_id,content,type) VALUES(?,?,?,?,?)",
            (mid, body.get('request_id'), user['id'], body.get('content'), body.get('type','text'))
        )
        conn.commit()
        row = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
        conn.close()
        json_resp(self, {'message': row_to_dict(row)}, 201)

    # ════════════════════════════════════════════════════════════
    # ADMIN
    # ════════════════════════════════════════════════════════════

    def _require_admin(self):
        user = get_token_user(self)
        if not user or user['role'] != 'admin':
            error(self, 'Admin only', 403)
            return None
        return user

    def admin_stats(self):
        if not self._require_admin(): return
        conn = get_conn()
        month_start = datetime.utcnow().replace(day=1).date().isoformat()
        clients       = conn.execute("SELECT COUNT(*) AS c FROM users WHERE role='client'").fetchone()['c']
        craftsmen     = conn.execute("SELECT COUNT(*) AS c FROM craftsmen WHERE is_verified=1").fetchone()['c']
        craftsmen_sub = conn.execute("SELECT COUNT(*) AS c FROM craftsmen WHERE subscription_active=1").fetchone()['c']
        completed     = conn.execute("SELECT COUNT(*) AS c FROM requests WHERE status='completed'").fetchone()['c']
        active        = conn.execute("SELECT COUNT(*) AS c FROM requests WHERE status IN ('accepted','in_progress')").fetchone()['c']
        pending       = conn.execute("SELECT COUNT(*) AS c FROM requests WHERE status='pending'").fetchone()['c']
        rev_month     = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM transactions WHERE type IN ('subscription','commission') AND amount>0 AND created_at>=?",
            (month_start,)
        ).fetchone()['t']
        rev_total = conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM transactions WHERE amount>0"
        ).fetchone()['t']
        conn.close()
        json_resp(self, {
            'clients': clients, 'craftsmen': craftsmen,
            'craftsmen_subscribed': craftsmen_sub,
            'completed_requests': completed,
            'requests_active': active, 'requests_pending': pending,
            'revenue_month': rev_month, 'revenue_total': rev_total,
            # legacy keys
            'total_clients': clients, 'total_craftsmen': craftsmen,
            'monthly_revenue': rev_month
        })

    def admin_craftsmen(self, params):
        if not self._require_admin(): return
        status = params.get('status', '')
        conn   = get_conn()
        q = """SELECT c.*, u.name, u.phone, u.email, u.is_active
               FROM craftsmen c JOIN users u ON u.id=c.user_id WHERE 1=1"""
        args = []
        if status == 'pending':   q += " AND c.is_verified=0 AND u.is_active=1"
        elif status == 'active':  q += " AND c.is_verified=1 AND u.is_active=1"
        elif status == 'suspended': q += " AND u.is_active=0"
        q += " ORDER BY c.created_at DESC LIMIT 50"
        rows = conn.execute(q, args).fetchall()
        conn.close()
        json_resp(self, rows_to_list(rows))

    def admin_users(self, params):
        if not self._require_admin(): return
        role = params.get('role', '')
        conn = get_conn()
        q = "SELECT u.*, (SELECT COUNT(*) FROM requests WHERE client_id=u.id) AS request_count FROM users u WHERE 1=1"
        args = []
        if role:
            q += " AND u.role=?"; args.append(role)
        q += " ORDER BY u.created_at DESC LIMIT 100"
        rows = conn.execute(q, args).fetchall()
        conn.close()
        json_resp(self, {'users': rows_to_list(rows)})

    def admin_verify_craftsman(self, craftsman_id):
        if not self._require_admin(): return
        conn = get_conn()
        conn.execute("UPDATE craftsmen SET is_verified=1 WHERE id=?", (craftsman_id,))
        conn.commit()
        conn.close()
        json_resp(self, {'message': 'Craftsman verified'})

    def admin_suspend_user(self, user_id):
        if not self._require_admin(): return
        conn = get_conn()
        conn.execute("UPDATE users SET is_active=0 WHERE id=?", (user_id,))
        conn.commit()
        conn.close()
        json_resp(self, {'message': 'User suspended'})

    def admin_requests(self, params):
        if not self._require_admin(): return
        status = params.get('status')
        conn   = get_conn()
        q = (
            "SELECT r.*, uc.name AS client_name, uh.name AS craftsman_name"
            " FROM requests r"
            " JOIN users uc ON uc.id=r.client_id"
            " LEFT JOIN craftsmen c ON c.id=r.craftsman_id"
            " LEFT JOIN users uh ON uh.id=c.user_id"
        )
        args = []
        if status:
            q += " WHERE r.status=?"; args = [status]
        q += " ORDER BY r.created_at DESC LIMIT 100"
        rows = conn.execute(q, args).fetchall()
        conn.close()
        json_resp(self, rows_to_list(rows))

    def admin_revenue(self):
        if not self._require_admin(): return
        month_start = datetime.utcnow().replace(day=1).date().isoformat()
        conn  = get_conn()
        rows  = conn.execute(
            "SELECT type, SUM(ABS(amount)) AS total, COUNT(*) AS count"
            " FROM transactions WHERE created_at>=? GROUP BY type",
            (month_start,)
        ).fetchall()
        conn.close()
        json_resp(self, rows_to_list(rows))


import threading

def expire_subscriptions():
    """Run every hour: deactivate expired subscriptions and notify craftsmen."""
    while True:
        try:
            conn  = get_conn()
            today = datetime.utcnow().date().isoformat()
            expired = conn.execute("""
                SELECT c.id AS craftsman_id, c.user_id, s.plan, s.end_date
                FROM subscriptions s
                JOIN craftsmen c ON c.id = s.craftsman_id
                WHERE s.end_date < ? AND s.is_active = 1 AND c.subscription_active = 1
            """, (today,)).fetchall()

            for row in expired:
                conn.execute("UPDATE subscriptions SET is_active=0 WHERE craftsman_id=? AND end_date<?",
                             (row['craftsman_id'], today))
                conn.execute("UPDATE craftsmen SET subscription_active=0 WHERE id=?",
                             (row['craftsman_id'],))
                conn.execute(
                    "INSERT INTO notifications(id,user_id,type,title,body) VALUES(?,?,?,?,?)",
                    (generate_id(), row['user_id'], 'sub_expired',
                     '⚠️ انتهى اشتراكك',
                     'اشتراكك انتهى اليوم. جدّد الآن لتستمر في استقبال طلبات العملاء.')
                )
            if expired:
                conn.commit()
                print(f"[Subscriptions] Expired {len(expired)} subscription(s)")
            conn.close()
        except Exception as e:
            print(f"[Subscriptions] Error: {e}")
        # Run every hour
        threading.Event().wait(3600)


# Main
if __name__ == '__main__':
    init_db()
    # Start subscription expiry background thread
    t = threading.Thread(target=expire_subscriptions, daemon=True)
    t.start()
    HOST   = os.environ.get('HOST', '0.0.0.0')
    server = HTTPServer((HOST, PORT), HirafiHandler)
    print(f"[Hirafi] Server running on http://0.0.0.0:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[Server] Stopped.")
