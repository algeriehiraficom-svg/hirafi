"""
Hirafi Database Layer - PostgreSQL (Neon) compatible
"""
import os
import sys
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8')

DATABASE_URL = os.environ.get('DATABASE_URL', '')

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL not set in environment")
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # ── USERS ──────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id          TEXT PRIMARY KEY,
        phone       TEXT UNIQUE NOT NULL,
        name        TEXT,
        email       TEXT,
        avatar_url  TEXT,
        role        TEXT NOT NULL CHECK(role IN ('client','craftsman','admin')),
        is_active   INTEGER DEFAULT 1,
        is_verified INTEGER DEFAULT 0,
        fcm_token   TEXT,
        created_at  TIMESTAMPTZ DEFAULT NOW(),
        updated_at  TIMESTAMPTZ DEFAULT NOW()
    )''')

    # ── OTP ────────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS otp_codes (
        id          SERIAL PRIMARY KEY,
        phone       TEXT NOT NULL,
        code        TEXT NOT NULL,
        expires_at  TIMESTAMPTZ NOT NULL,
        used        INTEGER DEFAULT 0,
        created_at  TIMESTAMPTZ DEFAULT NOW()
    )''')

    # ── CRAFTSMEN ──────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS craftsmen (
        id                  TEXT PRIMARY KEY,
        user_id             TEXT UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        bio                 TEXT,
        experience_years    INTEGER DEFAULT 0,
        price_min           INTEGER DEFAULT 0,
        price_max           INTEGER DEFAULT 0,
        rating              REAL DEFAULT 0.0,
        total_reviews       INTEGER DEFAULT 0,
        total_jobs          INTEGER DEFAULT 0,
        is_available        INTEGER DEFAULT 1,
        is_verified         INTEGER DEFAULT 0,
        lat                 REAL,
        lng                 REAL,
        city                TEXT,
        wilaya              TEXT,
        subscription_active INTEGER DEFAULT 0,
        wallet_balance      INTEGER DEFAULT 0,
        created_at          TIMESTAMPTZ DEFAULT NOW(),
        updated_at          TIMESTAMPTZ DEFAULT NOW()
    )''')

    # ── SPECIALTIES ────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS specialties (
        id       SERIAL PRIMARY KEY,
        name_ar  TEXT NOT NULL,
        name_fr  TEXT,
        icon     TEXT,
        category TEXT
    )''')

    # Seed specialties
    c.execute("SELECT COUNT(*) FROM specialties")
    if c.fetchone()['count'] == 0:
        specs = [
            ('سباق',         'Plomberie',     '🔧', 'construction'),
            ('كهرباء',        'Électricité',   '⚡', 'construction'),
            ('نجارة',         'Menuiserie',    '🪵', 'construction'),
            ('دهان',          'Peinture',      '🎨', 'construction'),
            ('تكييف وتبريد', 'Climatisation', '❄️', 'appliances'),
            ('بلاط وسيراميك','Carrelage',     '🏠', 'construction'),
            ('لحام',          'Soudure',       '🔩', 'construction'),
            ('إصلاح أجهزة',  'Électroménager','📺', 'appliances'),
            ('بناء وإسمنت',  'Maçonnerie',    '🧱', 'construction'),
            ('تنظيف',         'Nettoyage',     '🧹', 'cleaning'),
        ]
        for s in specs:
            c.execute("INSERT INTO specialties(name_ar,name_fr,icon,category) VALUES(%s,%s,%s,%s)", s)

    # ── CRAFTSMAN_SPECIALTIES ──────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS craftsman_specialties (
        craftsman_id TEXT REFERENCES craftsmen(id) ON DELETE CASCADE,
        specialty_id INTEGER REFERENCES specialties(id) ON DELETE CASCADE,
        PRIMARY KEY(craftsman_id, specialty_id)
    )''')

    # ── CRAFTSMAN_PHOTOS ───────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS craftsman_photos (
        id           SERIAL PRIMARY KEY,
        craftsman_id TEXT NOT NULL REFERENCES craftsmen(id) ON DELETE CASCADE,
        url          TEXT NOT NULL,
        type         TEXT DEFAULT 'work',
        created_at   TIMESTAMPTZ DEFAULT NOW()
    )''')

    # ── REQUESTS ───────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS requests (
        id             TEXT PRIMARY KEY,
        client_id      TEXT NOT NULL REFERENCES users(id),
        craftsman_id   TEXT REFERENCES craftsmen(id),
        specialty_id   INTEGER REFERENCES specialties(id),
        title          TEXT,
        description    TEXT,
        status         TEXT DEFAULT 'pending'
                       CHECK(status IN ('pending','accepted','in_progress','completed','cancelled','disputed')),
        lat            REAL,
        lng            REAL,
        address_text   TEXT,
        city           TEXT,
        scheduled_at   TIMESTAMPTZ,
        started_at     TIMESTAMPTZ,
        completed_at   TIMESTAMPTZ,
        price_agreed   INTEGER,
        payment_method TEXT DEFAULT 'cash',
        payment_status TEXT DEFAULT 'pending',
        notes          TEXT,
        created_at     TIMESTAMPTZ DEFAULT NOW(),
        updated_at     TIMESTAMPTZ DEFAULT NOW()
    )''')

    # ── REVIEWS ────────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id          SERIAL PRIMARY KEY,
        request_id  TEXT NOT NULL REFERENCES requests(id),
        reviewer_id TEXT NOT NULL REFERENCES users(id),
        reviewee_id TEXT NOT NULL REFERENCES users(id),
        rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        comment     TEXT,
        created_at  TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(request_id, reviewer_id)
    )''')

    # ── TRANSACTIONS ───────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id           TEXT PRIMARY KEY,
        craftsman_id TEXT NOT NULL REFERENCES craftsmen(id),
        request_id   TEXT REFERENCES requests(id),
        type         TEXT NOT NULL CHECK(type IN ('subscription','commission','top_up','withdrawal','refund')),
        amount       INTEGER NOT NULL,
        status       TEXT DEFAULT 'completed',
        reference    TEXT,
        created_at   TIMESTAMPTZ DEFAULT NOW()
    )''')

    # ── SUBSCRIPTIONS ──────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
        id           SERIAL PRIMARY KEY,
        craftsman_id TEXT NOT NULL REFERENCES craftsmen(id),
        plan         TEXT DEFAULT 'basic',
        price        INTEGER NOT NULL,
        start_date   TIMESTAMPTZ NOT NULL,
        end_date     TIMESTAMPTZ NOT NULL,
        is_active    INTEGER DEFAULT 1,
        created_at   TIMESTAMPTZ DEFAULT NOW()
    )''')

    # ── SUBSCRIPTION REQUESTS ─────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS subscription_requests (
        id           TEXT PRIMARY KEY,
        craftsman_id TEXT NOT NULL REFERENCES craftsmen(id),
        user_id      TEXT NOT NULL REFERENCES users(id),
        plan         TEXT DEFAULT 'basic',
        amount       INTEGER NOT NULL,
        payment_method TEXT DEFAULT 'baridimob',
        reference    TEXT,
        status       TEXT DEFAULT 'pending'
                     CHECK(status IN ('pending','approved','rejected')),
        admin_note   TEXT,
        created_at   TIMESTAMPTZ DEFAULT NOW(),
        reviewed_at  TIMESTAMPTZ
    )''')

    # ── NOTIFICATIONS ──────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id         TEXT PRIMARY KEY,
        user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        type       TEXT NOT NULL,
        title      TEXT,
        body       TEXT,
        data_json  TEXT,
        is_read    INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )''')

    # ── MESSAGES ───────────────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id         TEXT PRIMARY KEY,
        request_id TEXT NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
        sender_id  TEXT NOT NULL REFERENCES users(id),
        content    TEXT NOT NULL,
        type       TEXT DEFAULT 'text',
        read_at    TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )''')

    # ── INDEXES ────────────────────────────────────────────────
    c.execute("CREATE INDEX IF NOT EXISTS idx_craftsmen_city ON craftsmen(city)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_craftsmen_avail ON craftsmen(is_available, is_verified, subscription_active)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_requests_client ON requests(client_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_requests_craftsman ON requests(craftsman_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_requests_status ON requests(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read)")

    # ── SEED ADMIN ─────────────────────────────────────────────
    c.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
    if c.fetchone()['count'] == 0:
        admin_id = str(uuid.uuid4())
        c.execute(
            "INSERT INTO users(id,phone,name,role,is_verified) VALUES(%s,%s,%s,%s,%s)",
            (admin_id, '+213000000000', 'مدير حرفيكم', 'admin', 1)
        )
        print(f"[DB] Admin user created: {admin_id}")

    conn.commit()
    conn.close()
    print("[DB] Hirafi database initialized successfully")

if __name__ == '__main__':
    init_db()