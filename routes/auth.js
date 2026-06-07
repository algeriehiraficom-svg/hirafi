const router = require('express').Router();
const db = require('../config/db');

// Direct activation handler (no queue dependency)
const handleCraftsmanActivation = async (userId) => {
  const { rows } = await db.query(
    'SELECT subscription_status FROM craftsmen WHERE user_id = $1',
    [userId]
  );
  const subStatus = rows[0]?.subscription_status;
  if (subStatus === 'active' || !subStatus || subStatus === 'inactive') {
    await db.query('UPDATE craftsmen SET is_active = true WHERE user_id = $1', [userId]);
  }
};

// Helper: generate JWT
const generateToken = (id) =>
  require('jsonwebtoken').sign({ id }, process.env.JWT_SECRET, { expiresIn: process.env.JWT_EXPIRES_IN || '30d' });

// ── POST /api/auth/send-otp ──────────────────────────────────
router.post('/send-otp',
  require('express-validator').body('phone').matches(/^\+213[5-7]\d{8}$/).withMessage('Invalid Algerian phone number'),
  async (req, res) => {
    const errors = require('express-validator').validationResult(req);
    if (!errors.isEmpty()) return res.status(400).json({ errors: errors.array() });

    const { phone } = req.body;
    const code = Math.floor(100000 + Math.random() * 900000).toString();
    const expiresAt = new Date(Date.now() + 5 * 60 * 1000);

    await db.query(
      'INSERT INTO otp_codes (phone, code, expires_at) VALUES ($1, $2, $3)',
      [phone, code, expiresAt]
    );

    console.log(`[OTP] ${phone} → ${code}`);
    res.json({ message: 'OTP sent successfully' });
  }
);

// ── POST /api/auth/verify-otp ────────────────────────────────
router.post('/verify-otp',
  require('express-validator').body('phone').notEmpty(),
  require('express-validator').body('code').isLength({ min: 6, max: 6 }),
  require('express-validator').body('role').isIn(['client', 'craftsman']),
  async (req, res) => {
    const errors = require('express-validator').validationResult(req);
    if (!errors.isEmpty()) return res.status(400).json({ errors: errors.array() });

    const { phone, code, role, name } = req.body;
    const client = await db.getClient();

    try {
      await client.query('BEGIN');

      const { rows: otpRows } = await client.query(
        `SELECT * FROM otp_codes WHERE phone = $1 AND code = $2 AND used = FALSE AND expires_at > NOW()
         ORDER BY created_at DESC LIMIT 1`,
        [phone, code]
      );

      if (!otpRows.length) {
        await client.query('ROLLBACK');
        return res.status(400).json({ error: 'Invalid or expired OTP' });
      }

      await client.query('UPDATE otp_codes SET used = TRUE WHERE id = $1', [otpRows[0].id]);

      let { rows: userRows } = await client.query(
        'SELECT * FROM users WHERE phone = $1 FOR UPDATE',
        [phone]
      );

      let user = userRows[0];

      if (!user) {
        const { rows } = await client.query(
          'INSERT INTO users (phone, name, role, is_active) VALUES ($1, $2, $3, TRUE) RETURNING *',
          [phone, name || null, role || 'client']
        );
        user = rows[0];
      } else {
        const updateRole = role || user.role;
        const { rows } = await client.query(
          'UPDATE users SET role = $1, is_active = TRUE WHERE id = $2 RETURNING *',
          [updateRole, user.id]
        );
        user = rows[0];
      }

      if (user.role === 'craftsman') {
        await client.query(
          `INSERT INTO craftsmen (
              user_id,
              is_verified,
              is_available,
              subscription_active,
              wallet_balance,
              total_reviews,
              total_jobs
          )
          VALUES (
              $1,
              FALSE,
              FALSE,
              FALSE,
              0,
              0,
              0
          )
          ON CONFLICT (user_id)
          DO NOTHING`,
          [user.id]
        );
      }

      await client.query('COMMIT');

      const token = generateToken(user.id);
      res.json({
        token,
        user: { id: user.id, phone: user.phone, name: user.name, role: user.role },
        isNew: userRows.length === 0
      });

    } catch (err) {
      await client.query('ROLLBACK');
      console.error(err);
      res.status(500).json({ error: 'Server error' });
    } finally {
      client.release();
    }
  }
);

// ── GET /api/auth/me ─────────────────────────────────────────
router.get('/me', require('../middleware/auth').auth, async (req, res) => {
  if (req.user.role === 'admin') {
    return res.json({ role: 'admin', is_admin: true });
  }
  const { rows } = await db.query(`
    SELECT u.id, u.phone, u.name, u.email, u.avatar_url, u.role,
           c.id AS craftsman_id, c.rating, c.total_jobs, c.is_available,
           c.subscription_active, c.wallet_balance, c.city, c.wilaya,
           c.status as craftsman_status
    FROM users u LEFT JOIN craftsmen c ON c.user_id = u.id WHERE u.id = $1`,
    [req.user.id]
  );
  res.json(rows[0]);
});

// ── PATCH /api/auth/profile ──────────────────────────────────
router.patch('/profile', require('../middleware/auth').auth, (req, res, next) => {
  if (req.user.role === 'admin') {
    return res.status(403).json({ error: 'Admins cannot update profile' });
  }
  next();
}, async (req, res) => {
  const { name, email, fcm_token } = req.body;
  const { rows } = await db.query(
    'UPDATE users SET name=$1, email=$2, fcm_token=$3 WHERE id=$4 RETURNING *',
    [name, email, fcm_token, req.user.id]
  );
  res.json(rows[0]);
});

// ── POST /api/auth/admin-login ─────────────────────────────────
router.post('/admin-login', async (req, res) => {
  const { username, password } = req.body;

  if (username !== process.env.ADMIN_USER ||
      password !== process.env.ADMIN_PASS) {
    return res.status(401).json({ error: 'Invalid admin credentials' });
  }

  console.log('ADMIN LOGIN SECRET EXISTS=', !!process.env.JWT_SECRET);
  
  const token = require('jsonwebtoken').sign(
    { role: 'admin' },
    process.env.JWT_SECRET,
    { expiresIn: '7d' }
  );

  console.log('ADMIN TOKEN GENERATED');
  
  res.json({ token });
});

module.exports = router;
