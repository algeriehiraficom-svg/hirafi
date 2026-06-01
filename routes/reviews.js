const router = require('express').Router();
const db = require('../config/db');
const { auth } = require('../middleware/auth');

// ── POST /api/reviews ────────────────────────────────────────
router.post('/', auth, async (req, res) => {
  const { request_id, reviewee_id, rating, comment } = req.body;

  // Verify request is completed
  const { rows: reqRows } = await db.query(
    `SELECT * FROM requests WHERE id=$1 AND (client_id=$2 OR craftsman_id IN
     (SELECT id FROM craftsmen WHERE user_id=$2))`,
    [request_id, req.user.id]
  );
  if (!reqRows.length) return res.status(404).json({ error: 'Request not found' });
  if (reqRows[0].status !== 'completed') return res.status(400).json({ error: 'Request must be completed first' });

  const { rows } = await db.query(`
    INSERT INTO reviews (request_id, reviewer_id, reviewee_id, rating, comment)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (request_id, reviewer_id) DO UPDATE SET rating=$4, comment=$5
    RETURNING *
  `, [request_id, req.user.id, reviewee_id, rating, comment]);

  res.status(201).json(rows[0]);
});

// ── GET /api/reviews/craftsman/:id ───────────────────────────
router.get('/craftsman/:id', async (req, res) => {
  const { rows } = await db.query(`
    SELECT rv.*, u.name AS reviewer_name, u.avatar_url AS reviewer_avatar
    FROM reviews rv
    JOIN users u ON u.id = rv.reviewer_id
    WHERE rv.reviewee_id = $1
    ORDER BY rv.created_at DESC
    LIMIT 20
  `, [req.params.id]);
  res.json(rows);
});

module.exports = router;
