const router = require('express').Router();
const db = require('../config/db');
const { auth, requireRole } = require('../middleware/auth');
const { sendPushNotification } = require('../middleware/notifications');

// ── POST /api/requests ───────────────────────────────────────
router.post('/', auth, requireRole('client'), async (req, res) => {
  const { craftsman_id, specialty_id, title, description, lat, lng, address_text, city, scheduled_at, notes } = req.body;

  const { rows } = await db.query(`
    INSERT INTO requests
      (client_id, craftsman_id, specialty_id, title, description,
       location, address_text, city, scheduled_at, notes)
    VALUES ($1,$2,$3,$4,$5, ST_MakePoint($6,$7)::geography, $8,$9,$10,$11)
    RETURNING *
  `, [req.user.id, craftsman_id, specialty_id, title, description,
      parseFloat(lng), parseFloat(lat), address_text, city, scheduled_at, notes]);

  const request = rows[0];

  // Notify craftsman
  const { rows: craftsmanRows } = await db.query(
    'SELECT u.fcm_token, u.name FROM craftsmen c JOIN users u ON u.id = c.user_id WHERE c.id = $1',
    [craftsman_id]
  );
  if (craftsmanRows[0]?.fcm_token) {
    await sendPushNotification(craftsmanRows[0].fcm_token, {
      title: '🔔 طلب خدمة جديد!',
      body: `${title} — ${city}`,
      data: { type: 'new_request', request_id: request.id }
    });
  }

  res.status(201).json(request);
});

// ── GET /api/requests ─────────────────────────────────────────
// Client: sees their requests | Craftsman: sees incoming requests
router.get('/', auth, async (req, res) => {
  const { status } = req.query;
  let q, params;

  if (req.user.role === 'client') {
    q = `
      SELECT r.*, u.name AS craftsman_name, u.avatar_url AS craftsman_avatar,
             s.name_ar AS specialty
      FROM requests r
      LEFT JOIN craftsmen c ON c.id = r.craftsman_id
      LEFT JOIN users u ON u.id = c.user_id
      LEFT JOIN specialties s ON s.id = r.specialty_id
      WHERE r.client_id = $1
      ${status ? 'AND r.status = $2' : ''}
      ORDER BY r.created_at DESC
    `;
    params = status ? [req.user.id, status] : [req.user.id];
  } else if (req.user.role === 'craftsman') {
    const { rows: craft } = await db.query('SELECT id FROM craftsmen WHERE user_id=$1', [req.user.id]);
    const craftsmanId = craft[0]?.id;
    q = `
      SELECT r.*, u.name AS client_name, u.avatar_url AS client_avatar,
             s.name_ar AS specialty
      FROM requests r
      JOIN users u ON u.id = r.client_id
      LEFT JOIN specialties s ON s.id = r.specialty_id
      WHERE r.craftsman_id = $1
      ${status ? 'AND r.status = $2' : ''}
      ORDER BY r.created_at DESC
    `;
    params = status ? [craftsmanId, status] : [craftsmanId];
  }

  const { rows } = await db.query(q, params);
  res.json(rows);
});

// ── GET /api/requests/:id ────────────────────────────────────
router.get('/:id', auth, async (req, res) => {
  const { rows } = await db.query(`
    SELECT r.*,
           uc.name AS client_name, uc.phone AS client_phone, uc.avatar_url AS client_avatar,
           uh.name AS craftsman_name, uh.phone AS craftsman_phone, uh.avatar_url AS craftsman_avatar,
           s.name_ar AS specialty, s.icon AS specialty_icon
    FROM requests r
    JOIN users uc ON uc.id = r.client_id
    LEFT JOIN craftsmen c ON c.id = r.craftsman_id
    LEFT JOIN users uh ON uh.id = c.user_id
    LEFT JOIN specialties s ON s.id = r.specialty_id
    WHERE r.id = $1
  `, [req.params.id]);

  if (!rows.length) return res.status(404).json({ error: 'Request not found' });
  res.json(rows[0]);
});

// ── PATCH /api/requests/:id/status ──────────────────────────
router.patch('/:id/status', auth, async (req, res) => {
  const { status, price_agreed } = req.body;
  const allowed = {
    craftsman: ['accepted', 'in_progress', 'completed'],
    client:    ['cancelled'],
    admin:     ['cancelled', 'disputed']
  };

  if (!allowed[req.user.role]?.includes(status)) {
    return res.status(403).json({ error: 'Status transition not allowed' });
  }

  const extra = {};
  if (status === 'in_progress') extra.started_at = new Date();
  if (status === 'completed')   extra.completed_at = new Date();

  const { rows } = await db.query(`
    UPDATE requests SET status=$1, price_agreed=COALESCE($2, price_agreed),
    ${status === 'in_progress' ? 'started_at=NOW(),' : ''}
    ${status === 'completed'   ? 'completed_at=NOW(),' : ''}
    updated_at=NOW()
    WHERE id=$3 RETURNING *
  `, [status, price_agreed || null, req.params.id]);

  if (!rows.length) return res.status(404).json({ error: 'Request not found' });

  // If completed + electronic payment → auto-deduct commission
  if (status === 'completed' && rows[0].payment_method === 'electronic' && rows[0].price_agreed) {
    const commission = Math.round(rows[0].price_agreed * parseFloat(process.env.COMMISSION_RATE || 0.10));
    const { rows: craft } = await db.query('SELECT id FROM craftsmen WHERE user_id=$1', [req.user.id]);
    if (craft[0]) {
      await db.query(
        'UPDATE craftsmen SET wallet_balance = wallet_balance - $1 WHERE id = $2',
        [commission, craft[0].id]
      );
      await db.query(
        'INSERT INTO transactions (craftsman_id, request_id, type, amount) VALUES ($1,$2,$3,$4)',
        [craft[0].id, req.params.id, 'commission', -commission]
      );
    }
  }

  res.json(rows[0]);
});

module.exports = router;
