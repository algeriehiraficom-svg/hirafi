const router = require('express').Router();
const db = require('../config/db');
const { auth, requireRole } = require('../middleware/auth');

const adminOnly = [auth, requireRole('admin')];

// ── GET /api/admin/stats ─────────────────────────────────────
router.get('/stats', ...adminOnly, async (req, res) => {
  const [clients, craftsmen, activeRequests, pendingRequests, revenue, specialtiesDist] = await Promise.all([
    db.query('SELECT COUNT(*) FROM users WHERE role = $1', ['client']),
    db.query('SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE subscription_active = true) as subscribed FROM craftsmen'),
    db.query("SELECT COUNT(*) FROM requests WHERE status IN ('accepted', 'in_progress')"),
    db.query("SELECT COUNT(*) FROM requests WHERE status = 'pending'"),
    db.query("SELECT COUNT(*) FROM requests WHERE status = 'completed'"),
    db.query("SELECT COALESCE(SUM(amount),0) AS total FROM transactions WHERE type IN ('subscription','commission') AND created_at >= date_trunc('month', NOW())"),
    db.query(`
      SELECT s.name_ar, COUNT(cs.craftsman_id) as count
      FROM specialties s
      LEFT JOIN craftsman_specialties cs ON cs.specialty_id = s.id
      GROUP BY s.id, s.name_ar
      ORDER BY count DESC
    `),
  ]);
  res.json({
    clients: parseInt(clients.rows[0].count),
    craftsmen: parseInt(craftsmen.rows[0].total),
    craftsmen_subscribed: parseInt(craftsmen.rows[0].subscribed),
    requests_active: parseInt(activeRequests.rows[0].count),
    requests_pending: parseInt(pendingRequests.rows[0].count),
    revenue_month: parseInt(revenue.rows[0].total),
    specialtiesDistribution: specialtiesDist.rows.map(r => ({ name: r.name_ar, count: parseInt(r.count) })),
  });
});

// ── GET /api/admin/craftsmen ─────────────────────────────────
router.get('/craftsmen', ...adminOnly, async (req, res) => {
  const { city, page = 1, limit = 20 } = req.query;
  const offset = (page - 1) * limit;

  let q = `
    SELECT c.*, u.name, u.phone, u.email,
           ARRAY_AGG(s.name_ar) FILTER (WHERE s.name_ar IS NOT NULL) AS specialties
    FROM craftsmen c
    JOIN users u ON u.id = c.user_id
    LEFT JOIN craftsman_specialties cs ON cs.craftsman_id = c.id
    LEFT JOIN specialties s ON s.id = cs.specialty_id
    WHERE 1=1
  `;
  const params = [];
  if (city) { params.push(city); q += ` AND c.city = $${params.length}`; }

  q += ` GROUP BY c.id, u.name, u.phone, u.email ORDER BY c.created_at DESC LIMIT $${params.length+1} OFFSET $${params.length+2}`;
  params.push(limit, offset);

  const { rows } = await db.query(q, params);
  
  // Convert specialties array to comma-separated string for frontend
  const result = rows.map(c => ({
    ...c,
    specialties_str: c.specialties ? c.specialties.join(', ') : '',
  }));
  
  res.json(result);
});

// ── POST /api/admin/craftsmen/:id/approve ───────────────────
router.post('/craftsmen/:id/approve', ...adminOnly, async (req, res) => {
  const craftsmanId = req.params.id;

  const { rows: cm } = await db.query(
    'SELECT user_id FROM craftsmen WHERE id = $1',
    [craftsmanId]
  );

  if (!cm.length) {
    return res.status(404).json({ error: 'Craftsman not found' });
  }

  await db.query(
    'UPDATE craftsmen SET is_verified = true, is_available = true WHERE id = $1',
    [craftsmanId]
  );

  res.json({ message: 'Craftsman approved and activated' });
});

// ── POST /api/admin/craftsmen/:id/reject ───────────────────
router.post('/craftsmen/:id/reject', ...adminOnly, async (req, res) => {
  const craftsmanId = req.params.id;

  await db.query(
    'UPDATE craftsmen SET is_verified = false, is_available = false WHERE id = $1',
    [craftsmanId]
  );

  res.json({ message: 'Craftsman rejected' });
});

// ── POST /api/admin/craftsmen/:id/suspend ───────────────────
router.post('/craftsmen/:id/suspend', ...adminOnly, async (req, res) => {
  const craftsmanId = req.params.id;

  await db.query(
    'UPDATE craftsmen SET is_verified = false, is_available = false WHERE id = $1',
    [craftsmanId]
  );

  res.json({ message: 'Craftsman suspended' });
});

// ── PATCH /api/admin/users/:id/suspend ──────────────────────
router.patch('/users/:id/suspend', ...adminOnly, async (req, res) => {
  await db.query('UPDATE users SET is_active = false WHERE id = $1', [req.params.id]);
  res.json({ message: 'User suspended' });
});

// ── GET /api/admin/requests ──────────────────────────────────
router.get('/requests', ...adminOnly, async (req, res) => {
  const { status } = req.query;
  const { rows } = await db.query(`
    SELECT r.*, uc.name AS client_name, uh.name AS craftsman_name
    FROM requests r
    JOIN users uc ON uc.id = r.client_id
    LEFT JOIN craftsmen c ON c.id = r.craftsman_id
    LEFT JOIN users uh ON uh.id = c.user_id
    ${status ? 'WHERE r.status = $1' : ''}
    ORDER BY r.created_at DESC LIMIT 50
  `, status ? [status] : []);
  res.json(rows);
});

// ── GET /api/admin/revenue ───────────────────────────────────
router.get('/revenue', ...adminOnly, async (req, res) => {
  const { rows } = await db.query(`
    SELECT type,
           SUM(amount) AS total,
           COUNT(*) AS count
    FROM transactions
    WHERE created_at >= date_trunc('month', NOW())
    GROUP BY type
  `);
  res.json(rows);
});

// ── PATCH /api/admin/craftsmen/:id/verify ───────────────────────
router.patch('/craftsmen/:id/verify', ...adminOnly, async (req, res) => {
  const { id } = req.params;
  const { rows } = await db.query(
    'UPDATE craftsmen SET is_verified = true, is_available = true WHERE id = $1 RETURNING *',
    [id]
  );
  if (!rows.length) return res.status(404).json({ error: 'Craftsman not found' });
  res.json({ message: 'Craftsman verified', craftsman: rows[0] });
});

// ── GET /api/admin/users ───────────────────────────────────────
router.get('/users', ...adminOnly, async (req, res) => {
  const { role } = req.query;
  let q = 'SELECT id, name, phone, created_at, is_active FROM users';
  const params = [];
  if (role) {
    q += ' WHERE role = $1';
    params.push(role);
  }
  const { rows } = await db.query(q + ' ORDER BY created_at DESC', params);
  res.json(rows);
});

// ── GET /api/admin/subscription-requests ───────────────────────────
router.get('/subscription-requests', ...adminOnly, async (req, res) => {
  const { status } = req.query;
  const { rows } = await db.query(
    `SELECT sr.*, u.name, u.phone, u.city
     FROM subscription_requests sr
     JOIN users u ON u.id = sr.user_id
     ${status ? 'WHERE sr.status = $1' : ''}
     ORDER BY sr.created_at DESC`,
    status ? [status] : []
  );
  res.json({ requests: rows });
});

// ── PATCH /api/admin/subscription-requests/:id ───────────────────
router.patch('/subscription-requests/:id', ...adminOnly, async (req, res) => {
  const { id } = req.params;
  const { action, note } = req.body;
  const status = action === 'approve' ? 'approved' : 'rejected';

  const { rows } = await db.query(
    'UPDATE subscription_requests SET status = $1, admin_note = $2 WHERE id = $3 RETURNING *',
    [status, note || null, id]
  );

  if (!rows.length) return res.status(404).json({ error: 'Request not found' });

  // If approved, activate subscription
  if (action === 'approve') {
    const { user_id } = rows[0];
    await db.query(
      'UPDATE craftsmen SET subscription_active = true, subscription_status = $1 WHERE user_id = $2',
      ['active', user_id]
    );
  }

  res.json({ message: action === 'approve' ? 'Subscription activated' : 'Request rejected' });
});

module.exports = router;
