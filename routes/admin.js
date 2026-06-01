const router = require('express').Router();
const db = require('../config/db');
const { auth, requireRole } = require('../middleware/auth');

const adminOnly = [auth, requireRole('admin')];

// ── GET /api/admin/stats ─────────────────────────────────────
router.get('/stats', ...adminOnly, async (req, res) => {
  const [users, craftsmen, requests, revenue] = await Promise.all([
    db.query('SELECT COUNT(*) FROM users WHERE role = $1', ['client']),
    db.query('SELECT COUNT(*) FROM craftsmen'),
    db.query("SELECT COUNT(*) FROM requests WHERE status = 'completed'"),
    db.query("SELECT COALESCE(SUM(amount),0) AS total FROM transactions WHERE type IN ('subscription','commission') AND created_at >= date_trunc('month', NOW())"),
  ]);
  res.json({
    total_clients:     parseInt(users.rows[0].count),
    total_craftsmen:   parseInt(craftsmen.rows[0].count),
    completed_requests: parseInt(requests.rows[0].count),
    monthly_revenue:   parseInt(revenue.rows[0].total),
  });
});

// ── GET /api/admin/craftsmen ─────────────────────────────────
router.get('/craftsmen', ...adminOnly, async (req, res) => {
  const { status, city, page = 1, limit = 20 } = req.query;
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
  if (status === 'pending')  { q += ` AND c.is_verified = FALSE AND u.is_active = TRUE`; }
  if (status === 'active')   { q += ` AND c.is_verified = TRUE AND u.is_active = TRUE`; }
  if (status === 'suspended'){ q += ` AND u.is_active = FALSE`; }
  if (city) { params.push(city); q += ` AND c.city = $${params.length}`; }

  q += ` GROUP BY c.id, u.name, u.phone, u.email ORDER BY c.created_at DESC LIMIT $${params.length+1} OFFSET $${params.length+2}`;
  params.push(limit, offset);

  const { rows } = await db.query(q, params);
  res.json(rows);
});

// ── PATCH /api/admin/craftsmen/:id/verify ───────────────────
router.patch('/craftsmen/:id/verify', ...adminOnly, async (req, res) => {
  await db.query('UPDATE craftsmen SET is_verified=TRUE WHERE id=$1', [req.params.id]);
  res.json({ message: 'Craftsman verified' });
});

// ── PATCH /api/admin/users/:id/suspend ──────────────────────
router.patch('/users/:id/suspend', ...adminOnly, async (req, res) => {
  await db.query('UPDATE users SET is_active=FALSE WHERE id=$1', [req.params.id]);
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

module.exports = router;
