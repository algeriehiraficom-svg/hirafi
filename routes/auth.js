const router = require('express').Router();
const jwt = require('jsonwebtoken');
const db = require('../config/db');
const { body, validationResult } = require('express-validator');
const { auth } = require('../middleware/auth');

// Helper: generate JWT
const generateToken = (id) =>
  jwt.sign({ id }, process.env.JWT_SECRET, { expiresIn: process.env.JWT_EXPIRES_IN || '30d' });

// Helper: send OTP (stub — replace with real SMS provider)
const sendOTP = async (phone, code) => {
  console.log(`[OTP] ${phone} → ${code}`);
  return code;
};

// ── POST /api/auth/send-otp ──────────────────────────────────
router.post('/send-otp',
  body('phone').matches(/^\+213[5-7]\d{8}$/).withMessage('Invalid Algerian phone number'),
  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) return res.status(400).json({ errors: errors.array() });

    const { phone } = req.body;
    const code = Math.floor(100000 + Math.random() * 900000).toString();
    const expiresAt = new Date(Date.now() + 5 * 60 * 1000); // 5 minutes

    await db.query(
      'INSERT INTO otp_codes (phone, code, expires_at) VALUES ($1, $2, $3)',
      [phone, code, expiresAt]
    );

    await sendOTP(phone, code);
    res.json({
      message: 'OTP sent successfully',
      otp: code
    });
  }
);

// ── POST /api/auth/verify-otp ────────────────────────────────
router.post('/verify-otp',
  body('phone').notEmpty(),
  body('code').isLength({ min: 6, max: 6 }),
  body('role').isIn(['client', 'craftsman']),
  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) return res.status(400).json({ errors: errors.array() });

    const { phone, code, role, name } = req.body;

    // Verify OTP
    const { rows: otpRows } = await db.query(
      `SELECT * FROM otp_codes
       WHERE phone = $1 AND code = $2 AND used = FALSE AND expires_at > NOW()
       ORDER BY created_at DESC LIMIT 1`,
      [phone, code]
    );
    if (!otpRows.length) return res.status(400).json({ error: 'Invalid or expired OTP' });

    // Mark OTP used
    await db.query('UPDATE otp_codes SET used = TRUE WHERE id = $1', [otpRows[0].id]);

    // Find or create user
    let { rows: userRows } = await db.query('SELECT * FROM users WHERE phone = $1', [phone]);
    let user = userRows[0];
    let isNew = false;

    if (!user) {
      const { rows } = await db.query(
        'INSERT INTO users (phone, name, role) VALUES ($1, $2, $3) RETURNING *',
        [phone, name || null, role]
      );
      user = rows[0];
      isNew = true;

      // If craftsman, create craftsmen profile
      if (role === 'craftsman') {
        await db.query('INSERT INTO craftsmen (user_id) VALUES ($1)', [user.id]);
      }
    }

    const token = generateToken(user.id);
    res.json({ token, user: { id: user.id, phone: user.phone, name: user.name, role: user.role }, isNew });
  }
);

// ── GET /api/auth/me ─────────────────────────────────────────
router.get('/me', auth, async (req, res) => {
  const { rows } = await db.query(`
    SELECT u.id, u.phone, u.name, u.email, u.avatar_url, u.role,
           c.id AS craftsman_id, c.rating, c.total_jobs, c.is_available,
           c.subscription_active, c.wallet_balance, c.city, c.wilaya
    FROM users u
    LEFT JOIN craftsmen c ON c.user_id = u.id
    WHERE u.id = $1
  `, [req.user.id]);
  res.json(rows[0]);
});

// ── PATCH /api/auth/profile ──────────────────────────────────
router.patch('/profile', auth, async (req, res) => {
  const { name, email, fcm_token } = req.body;
  const { rows } = await db.query(
    'UPDATE users SET name=$1, email=$2, fcm_token=$3 WHERE id=$4 RETURNING *',
    [name, email, fcm_token, req.user.id]
  );
  res.json(rows[0]);
});

module.exports = router;
