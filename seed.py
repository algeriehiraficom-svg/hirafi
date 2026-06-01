#!/usr/bin/env python3
"""
حرفيكم — Seed Script
Realistic test data: craftsmen, clients, requests, reviews in Oran (وهران)
Run: DB_PATH=/tmp/hirafi.db python3 seed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from database import get_conn, init_db, DB_PATH
from auth_utils import generate_id, create_token, hash_otp
from datetime import datetime, timedelta
import random, json

print(f"[Seed] Using DB: {DB_PATH}")
init_db()
conn = get_conn()

# ── Helpers ────────────────────────────────────────────────────────
def uid(): return generate_id()
def now(): return datetime.utcnow().isoformat()
def days_ago(n): return (datetime.utcnow() - timedelta(days=n)).isoformat()
def rand_oran_coords():
    """Random coords around Oran city center"""
    return (
        35.6969 + random.uniform(-0.08, 0.08),
        -0.6331 + random.uniform(-0.10, 0.10)
    )

# ── Clear existing seed data ───────────────────────────────────────
conn.execute("DELETE FROM reviews")
conn.execute("DELETE FROM messages")
conn.execute("DELETE FROM notifications")
conn.execute("DELETE FROM transactions")
conn.execute("DELETE FROM subscriptions")
conn.execute("DELETE FROM requests")
conn.execute("DELETE FROM craftsman_specialties")
conn.execute("DELETE FROM craftsman_photos")
conn.execute("DELETE FROM craftsmen WHERE id != 'PLACEHOLDER'")
conn.execute("DELETE FROM users WHERE role != 'admin'")
conn.commit()
print("[Seed] Cleared existing data")

# ── Specialties (already seeded) ──────────────────────────────────
specs = {row['id']: row for row in conn.execute("SELECT * FROM specialties").fetchall()}

# ── CLIENTS ───────────────────────────────────────────────────────
clients_data = [
    ("+213551000001", "أحمد بن علي"),
    ("+213551000002", "فاطمة الزهراء"),
    ("+213551000003", "محمد كريم"),
    ("+213551000004", "سارة بوزيد"),
    ("+213551000005", "يوسف مصطفى"),
    ("+213551000006", "نور الهدى"),
    ("+213551000007", "رضا بلقاسم"),
    ("+213551000008", "سمية حمودة"),
]

clients = []
for phone, name in clients_data:
    cid = uid()
    lat, lng = rand_oran_coords()
    conn.execute(
        "INSERT INTO users(id,phone,name,role,is_verified) VALUES(?,?,?,?,?)",
        (cid, phone, name, 'client', 1)
    )
    clients.append({"id": cid, "name": name, "phone": phone, "lat": lat, "lng": lng})
conn.commit()
print(f"[Seed] Created {len(clients)} clients")

# ── CRAFTSMEN ─────────────────────────────────────────────────────
craftsmen_data = [
    {
        "phone": "+213661000001", "name": "عبد الرحمن سعيدي",
        "bio": "سباك محترف بخبرة 15 سنة في وهران. متخصص في إصلاح التسربات وتركيب الحمامات.",
        "specs": [1], "exp": 15, "min": 1500, "max": 6000,
        "rating": 4.8, "jobs": 142, "wallet": 45000,
    },
    {
        "phone": "+213661000002", "name": "حسين مزاوي",
        "bio": "كهربائي معتمد، خبرة 10 سنوات. تركيب لوحات كهربائية وإصلاح الأعطال.",
        "specs": [2], "exp": 10, "min": 2000, "max": 8000,
        "rating": 4.6, "jobs": 89, "wallet": 32000,
    },
    {
        "phone": "+213661000003", "name": "عمر بن سالم",
        "bio": "نجار ماهر، أعمال خشبية عالية الجودة. أبواب، نوافذ، خزائن.",
        "specs": [3], "exp": 12, "min": 3000, "max": 15000,
        "rating": 4.9, "jobs": 67, "wallet": 28000,
    },
    {
        "phone": "+213661000004", "name": "كمال تواتي",
        "bio": "دهان محترف. طلاء داخلي وخارجي. خبرة 8 سنوات.",
        "specs": [4], "exp": 8, "min": 1000, "max": 5000,
        "rating": 4.4, "jobs": 201, "wallet": 18000,
    },
    {
        "phone": "+213661000005", "name": "نبيل حمداوي",
        "bio": "تقني تكييف وتبريد. تركيب وصيانة كل أنواع المكيفات.",
        "specs": [5], "exp": 7, "min": 2500, "max": 10000,
        "rating": 4.7, "jobs": 115, "wallet": 52000,
    },
    {
        "phone": "+213661000006", "name": "فريد مسعودي",
        "bio": "بلاط وسيراميك. تركيب احترافي للبلاط والسيراميك والموزاييك.",
        "specs": [6], "exp": 11, "min": 2000, "max": 9000,
        "rating": 4.5, "jobs": 78, "wallet": 21000,
    },
    {
        "phone": "+213661000007", "name": "سليم خالدي",
        "bio": "لحام ومعادن. خبرة 14 سنة في لحام الحديد والإنوكس.",
        "specs": [7], "exp": 14, "min": 2000, "max": 12000,
        "rating": 4.3, "jobs": 54, "wallet": 15000,
    },
    {
        "phone": "+213661000008", "name": "وليد عيسى",
        "bio": "تقني أجهزة كهرومنزلية. إصلاح غسالات، ثلاجات، مايكرو.",
        "specs": [8], "exp": 6, "min": 800, "max": 3000,
        "rating": 4.6, "jobs": 234, "wallet": 38000,
    },
    {
        "phone": "+213661000009", "name": "رشيد بوشامة",
        "bio": "بناء وإسمنت. بناء، هدم، ترميم. خبرة 20 سنة.",
        "specs": [9, 6], "exp": 20, "min": 5000, "max": 30000,
        "rating": 4.7, "jobs": 43, "wallet": 67000,
    },
    {
        "phone": "+213661000010", "name": "أمين درار",
        "bio": "سباكة وكهرباء. ثنائي الاختصاص لخدمة أفضل.",
        "specs": [1, 2], "exp": 9, "min": 1500, "max": 7000,
        "rating": 4.5, "jobs": 163, "wallet": 41000,
    },
]

craftsmen = []
for cd in craftsmen_data:
    user_id = uid()
    craft_id = uid()
    lat, lng = rand_oran_coords()

    conn.execute(
        "INSERT INTO users(id,phone,name,role,is_verified) VALUES(?,?,?,?,?)",
        (user_id, cd['phone'], cd['name'], 'craftsman', 1)
    )
    conn.execute("""
        INSERT INTO craftsmen(id,user_id,bio,experience_years,price_min,price_max,
            rating,total_reviews,total_jobs,is_available,is_verified,
            lat,lng,city,wilaya,subscription_active,wallet_balance)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        craft_id, user_id, cd['bio'], cd['exp'], cd['min'], cd['max'],
        cd['rating'], int(cd['jobs'] * 0.6), cd['jobs'],
        1, 1, lat, lng, 'وهران', 'وهران', 1, cd['wallet']
    ))

    for sid in cd['specs']:
        conn.execute("INSERT OR IGNORE INTO craftsman_specialties VALUES(?,?)", (craft_id, sid))

    # Subscription record
    sub_id = uid()
    start = days_ago(15)
    end = (datetime.utcnow() + timedelta(days=15)).isoformat()
    conn.execute(
        "INSERT INTO subscriptions(craftsman_id,plan,price,start_date,end_date,is_active) VALUES(?,?,?,?,?,?)",
        (craft_id, 'basic', 1500, start, end, 1)
    )
    conn.execute(
        "INSERT INTO transactions(id,craftsman_id,type,amount,status,reference) VALUES(?,?,?,?,?,?)",
        (uid(), craft_id, 'subscription', -1500, 'completed', 'AUTO-SUB')
    )

    craftsmen.append({**cd, "id": craft_id, "user_id": user_id, "lat": lat, "lng": lng})

conn.commit()
print(f"[Seed] Created {len(craftsmen)} craftsmen")

# ── REQUESTS + MESSAGES + REVIEWS ─────────────────────────────────
statuses_history = [
    ('completed', 'completed'),
    ('completed', 'completed'),
    ('completed', 'completed'),
    ('in_progress', None),
    ('accepted', None),
    ('pending', None),
    ('cancelled', None),
]

request_templates = [
    (1, "إصلاح تسرب في الحمام", "يوجد تسرب مياه تحت الحوض منذ أسبوعين"),
    (2, "تركيب مكيف جديد", "أحتاج لتركيب مكيف في غرفة النوم"),
    (3, "صنع باب خشبي", "أريد باباً خشبياً للغرفة مقاس 90×210"),
    (4, "دهان شقة كاملة", "شقة 3 غرف، أحتاج دهاناً داخلياً"),
    (2, "قاطع كهرباء معطل", "الكهرباء تنقطع في المطبخ"),
    (1, "صنبور يقطر", "صنبور المطبخ يقطر ماء"),
    (5, "صيانة مكيف", "المكيف لا يبرد بشكل كافٍ"),
    (8, "إصلاح غسالة", "الغسالة توقفت فجأة"),
    (6, "تركيب بلاط للحمام", "الحمام يحتاج بلاطاً جديداً"),
    (9, "ترميم جدار", "شقوق في الجدار الخارجي"),
]

comments = [
    "عمل ممتاز ومحترف، أنصح به",
    "سريع في التنفيذ ونظيف في العمل",
    "جودة عالية وسعر معقول",
    "التزم بالوقت وأنجز العمل بإتقان",
    "محترف جداً، سأتصل به مجدداً",
    "عمل جيد وخدمة ممتازة",
    "متميز في مجاله",
]

requests_created = 0
reviews_created = 0

for i, client in enumerate(clients):
    # Each client gets 2-3 requests
    num_req = random.randint(2, 3)
    for j in range(num_req):
        template = request_templates[(i * 3 + j) % len(request_templates)]
        spec_id, title, desc = template
        craftsman = craftsmen[(i + j) % len(craftsmen)]
        status_pair = statuses_history[(i + j) % len(statuses_history)]
        status, payment_status = status_pair

        req_id = uid()
        days_back = random.randint(1, 45)
        created = days_ago(days_back)
        completed_at = None
        price = random.randint(2000, 15000)

        if status == 'completed':
            completed_at = days_ago(max(0, days_back - 2))

        conn.execute("""
            INSERT INTO requests(id,client_id,craftsman_id,specialty_id,title,description,
                status,lat,lng,address_text,city,price_agreed,payment_method,payment_status,
                completed_at,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            req_id, client['id'], craftsman['id'], spec_id,
            title, desc, status,
            client['lat'], client['lng'],
            f"حي {random.choice(['السلامة','النصر','الأمير','الرياض','المطار'])}, وهران",
            'وهران', price if status == 'completed' else None,
            random.choice(['cash', 'cash', 'electronic']),
            'paid' if status == 'completed' else 'pending',
            completed_at, created, created
        ))

        # Messages
        msg_count = random.randint(2, 4)
        senders = [client['id'], craftsman['user_id']]
        messages_text = [
            "مرحبا، هل أنت متاح هذا الأسبوع؟",
            "نعم، أنا متاح يوم الثلاثاء",
            "ممتاز، ما هو السعر التقريبي؟",
            "بين 3000 و 5000 دج حسب الوضع",
            "شكرا، سأتصل بك للتأكيد",
        ]
        for k in range(msg_count):
            conn.execute(
                "INSERT INTO messages(id,request_id,sender_id,content,created_at) VALUES(?,?,?,?,?)",
                (uid(), req_id, senders[k % 2], messages_text[k % len(messages_text)], days_ago(days_back - k))
            )

        # Review if completed
        if status == 'completed':
            rating = random.randint(4, 5)
            conn.execute("""
                INSERT OR IGNORE INTO reviews(request_id,reviewer_id,reviewee_id,rating,comment,created_at)
                VALUES(?,?,?,?,?,?)
            """, (req_id, client['id'], craftsman['user_id'], rating,
                  random.choice(comments), completed_at))

            # Commission transaction
            if price:
                commission = int(price * 0.10)
                conn.execute(
                    "INSERT INTO transactions(id,craftsman_id,request_id,type,amount,status) VALUES(?,?,?,?,?,?)",
                    (uid(), craftsman['id'], req_id, 'commission', commission, 'completed')
                )

            reviews_created += 1

        requests_created += 1

conn.commit()
print(f"[Seed] Created {requests_created} requests, {reviews_created} reviews")

# ── Update craftsman ratings from reviews ─────────────────────────
for c in craftsmen:
    row = conn.execute("""
        SELECT AVG(rating) AS avg, COUNT(*) AS cnt
        FROM reviews WHERE reviewee_id=?
    """, (c['user_id'],)).fetchone()
    if row and row['cnt'] > 0:
        conn.execute(
            "UPDATE craftsmen SET rating=ROUND(?,1), total_reviews=? WHERE id=?",
            (row['avg'], row['cnt'], c['id'])
        )
conn.commit()

# ── Notifications ──────────────────────────────────────────────────
notif_templates = [
    ('new_request', '🔔 طلب جديد', 'لديك طلب خدمة جديد'),
    ('review',      '⭐ تقييم جديد', 'حصلت على تقييم 5 نجوم'),
    ('payment',     '💰 دفعة واردة', 'تم إضافة 3500 دج لمحفظتك'),
]
for c in craftsmen[:5]:
    for ntype, ntitle, nbody in notif_templates[:2]:
        conn.execute(
            "INSERT INTO notifications(id,user_id,type,title,body,is_read) VALUES(?,?,?,?,?,?)",
            (uid(), c['user_id'], ntype, ntitle, nbody, random.randint(0,1))
        )
for cl in clients[:4]:
    conn.execute(
        "INSERT INTO notifications(id,user_id,type,title,body,is_read) VALUES(?,?,?,?,?,?)",
        (uid(), cl['id'], 'status_update', '✅ طلبك تم قبوله', 'قبل الحرفي طلبك', 0)
    )
conn.commit()

# ── Summary ────────────────────────────────────────────────────────
print("\n" + "="*45)
print("  حرفيكم — Seed Data Summary")
print("="*45)
print(f"  Clients:    {conn.execute('SELECT COUNT(*) FROM users WHERE role=?',('client',)).fetchone()[0]}")
print(f"  Craftsmen:  {conn.execute('SELECT COUNT(*) FROM craftsmen').fetchone()[0]}")
print(f"  Requests:   {conn.execute('SELECT COUNT(*) FROM requests').fetchone()[0]}")
print(f"  Reviews:    {conn.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]}")
print(f"  Messages:   {conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0]}")
print(f"  Notifs:     {conn.execute('SELECT COUNT(*) FROM notifications').fetchone()[0]}")
print(f"  Transactions:{conn.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]}")
rev_row = conn.execute("SELECT SUM(amount) FROM transactions WHERE type='commission'").fetchone()[0]
print(f"  Commission: {rev_row or 0:,} DZD")
print("="*45)
print("  [Seed] Done! حرفيكم is ready to demo.")
print("="*45)

conn.close()
