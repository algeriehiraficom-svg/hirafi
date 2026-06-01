const router = require('express').Router();
const db = require('../config/db');
const { auth, requireRole } = require('../middleware/auth');

// ── GET /api/payments/wallet ─────────────────────────────────
router.get('/wallet', auth, requireRole('craftsman'), async (req, res) => {
  const { rows } = await db.query(`
    SELECT c.wallet_balance, c.subscription_active,
           (SELECT json_agg(t ORDER BY t.created_at DESC)
            FROM (SELECT * FROM transactions WHERE craftsman_id = c.id LIMIT 20) t) AS transactions
    FROM craftsmen c WHERE c.user_id = $1
  `, [req.user.id]);
  if (!rows.length) return res.status(404).json({ error: 'Craftsman not found' });
  res.json(rows[0]);
});

// ── POST /api/payments/top-up ────────────────────────────────
// Stub: in production, integrate Chargily payment gateway
router.post('/top-up', auth, requireRole('craftsman'), async (req, res) => {
  const { amount } = req.body;
  if (!amount || amount < 500) return res.status(400).json({ error: 'Minimum top-up is 500 DZD' });

  const { rows: craft } = await db.query('SELECT id FROM craftsmen WHERE user_id=$1', [req.user.id]);
  if (!craft.length) return res.status(404).json({ error: 'Craftsman not found' });

  // TODO: Integrate Chargily payment — redirect to payment page and verify webhook
  // For now: simulate successful payment
  await db.query('UPDATE craftsmen SET wallet_balance = wallet_balance + $1 WHERE id = $2', [amount, craft[0].id]);
  await db.query(
    'INSERT INTO transactions (craftsman_id, type, amount, status) VALUES ($1,$2,$3,$4)',
    [craft[0].id, 'top_up', amount, 'completed']
  );

  res.json({ message: 'Wallet topped up successfully', amount });
});

// ── POST /api/payments/subscribe ────────────────────────────
router.post('/subscribe', auth, requireRole('craftsman'), async (req, res) => {
  const { plan = 'basic' } = req.body;
  const price = plan === 'premium' ? 2000 : 1000;

  const { rows: craft } = await db.query('SELECT * FROM craftsmen WHERE user_id=$1', [req.user.id]);
  if (!craft.length) return res.status(404).json({ error: 'Craftsman not found' });

  if (craft[0].wallet_balance < price) {
    return res.status(400).json({ error: 'Insufficient wallet balance. Please top up first.' });
  }

  const startDate = new Date();
  const endDate = new Date(startDate);
  endDate.setMonth(endDate.getMonth() + 1);

  // Deduct + create subscription
  await db.query('UPDATE craftsmen SET wallet_balance = wallet_balance - $1, subscription_active = TRUE WHERE id = $2',
    [price, craft[0].id]);
  await db.query(
    'INSERT INTO subscriptions (craftsman_id, plan, price, start_date, end_date) VALUES ($1,$2,$3,$4,$5)',
    [craft[0].id, plan, price, startDate.toISOString().split('T')[0], endDate.toISOString().split('T')[0]]
  );
  await db.query(
    'INSERT INTO transactions (craftsman_id, type, amount) VALUES ($1,$2,$3)',
    [craft[0].id, 'subscription', -price]
  );

  res.json({ message: 'Subscription activated successfully', plan, expires: endDate });
});

// ── POST /api/payments/withdraw ──────────────────────────────
router.post('/withdraw', auth, requireRole('craftsman'), async (req, res) => {
  const { amount } = req.body;
  const { rows: craft } = await db.query('SELECT * FROM craftsmen WHERE user_id=$1', [req.user.id]);
  if (!craft.length) return res.status(404).json({ error: 'Craftsman not found' });
  if (craft[0].wallet_balance < amount) return res.status(400).json({ error: 'Insufficient balance' });

  await db.query('UPDATE craftsmen SET wallet_balance = wallet_balance - $1 WHERE id = $2', [amount, craft[0].id]);
  await db.query(
    'INSERT INTO transactions (craftsman_id, type, amount, status) VALUES ($1,$2,$3,$4)',
    [craft[0].id, 'withdrawal', -amount, 'pending']
  );

  res.json({ message: 'Withdrawal request submitted. Processing within 48 hours.' });
});

module.exports = router;
