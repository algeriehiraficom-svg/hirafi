const router = require('express').Router();
const db = require('../config/db');
const { auth } = require('../middleware/auth');

// ── POST /api/chat/start ─────────────────────────────────────
router.post('/start', auth, async (req, res) => {
  const { craftsmanId } = req.body;
  const userId = req.user.id;

  // Verify craftsman exists and is active
  const { rows: cmCheck } = await db.query(
    'SELECT user_id FROM craftsmen WHERE id = $1 AND status = \'active\'',
    [craftsmanId]
  );

  if (!cmCheck.length) {
    return res.status(404).json({ error: 'Craftsman not found or not available' });
  }

  // Check if chat already exists
  let { rows: existing } = await db.query(
    'SELECT * FROM chats WHERE user_id = $1 AND craftsman_id = $2',
    [userId, craftsmanId]
  );

  if (!existing.length) {
    const { rows } = await db.query(
      'INSERT INTO chats (user_id, craftsman_id) VALUES ($1, $2) RETURNING *',
      [userId, craftsmanId]
    );
    existing = rows;
  }

  res.json(existing[0]);
});

// ── GET /api/chat/:id ────────────────────────────────────────
router.get('/:id', auth, async (req, res) => {
  const chatId = req.params.id;
  const userId = req.user.id;

  // Verify user has access to this chat
  const { rows: chat } = await db.query(
    'SELECT * FROM chats WHERE id = $1 AND (user_id = $2 OR craftsman_id IN (SELECT id FROM craftsmen WHERE user_id = $2))',
    [chatId, userId]
  );

  if (!chat.length) {
    return res.status(404).json({ error: 'Chat not found' });
  }

  // Get messages
  const { rows: messages } = await db.query(
    `SELECT m.*, u.name as sender_name, u.avatar_url as sender_avatar
     FROM chat_messages m
     JOIN users u ON u.id = m.sender_id
     WHERE m.chat_id = $1
     ORDER BY m.created_at ASC`,
    [chatId]
  );

  res.json({ chat: chat[0], messages });
});

// ── GET /api/chat/:id/messages ───────────────────────────────
router.get('/:id/messages', auth, async (req, res) => {
  const chatId = req.params.id;
  const userId = req.user.id;

  // Verify user has access to this chat
  const { rows: chat } = await db.query(
    'SELECT * FROM chats WHERE id = $1 AND (user_id = $2 OR craftsman_id IN (SELECT id FROM craftsmen WHERE user_id = $2))',
    [chatId, userId]
  );

  if (!chat.length) {
    return res.status(404).json({ error: 'Chat not found' });
  }

  // Get messages
  const { rows: messages } = await db.query(
    `SELECT m.*, u.name as sender_name, u.avatar_url as sender_avatar
     FROM chat_messages m
     JOIN users u ON u.id = m.sender_id
     WHERE m.chat_id = $1
     ORDER BY m.created_at ASC`,
    [chatId]
  );

  res.json(messages);
});

// ── GET /api/chat/user ───────────────────────────────────────
router.get('/user', auth, async (req, res) => {
  const userId = req.user.id;

  const { rows } = await db.query(
    `SELECT c.*, u.name as craftsman_name, u.avatar_url as craftsman_avatar
     FROM chats c
     JOIN craftsmen cm ON cm.id = c.craftsman_id
     JOIN users u ON u.id = cm.user_id
     WHERE c.user_id = $1
     ORDER BY c.created_at DESC`,
    [userId]
  );

  res.json(rows);
});

// ── GET /api/chat/craftsman ──────────────────────────────────
router.get('/craftsman', auth, async (req, res) => {
  const userId = req.user.id;

  const { rows } = await db.query(
    `SELECT c.*, uc.name as client_name
     FROM chats c
     JOIN users uc ON uc.id = c.user_id
     WHERE c.craftsman_id = (SELECT id FROM craftsmen WHERE user_id = $1)
     ORDER BY c.created_at DESC`,
    [userId]
  );

  res.json(rows);
});

module.exports = router;