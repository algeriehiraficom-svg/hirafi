const router = require('express').Router();
const db = require('../config/db');
const { auth } = require('../middleware/auth');

router.get('/', auth, async (req, res) => {
  const { rows } = await db.query(
    'SELECT * FROM notifications WHERE user_id=$1 ORDER BY created_at DESC LIMIT 30',
    [req.user.id]
  );
  res.json(rows);
});

router.patch('/read-all', auth, async (req, res) => {
  await db.query('UPDATE notifications SET is_read=TRUE WHERE user_id=$1', [req.user.id]);
  res.json({ message: 'All notifications marked as read' });
});

router.patch('/:id/read', auth, async (req, res) => {
  await db.query('UPDATE notifications SET is_read=TRUE WHERE id=$1 AND user_id=$2', [req.params.id, req.user.id]);
  res.json({ message: 'Notification marked as read' });
});

module.exports = router;
