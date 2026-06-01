const router = require('express').Router();
const multer = require('multer');
const cloudinary = require('cloudinary').v2;
const db = require('../config/db');
const { auth, requireRole } = require('../middleware/auth');

cloudinary.config({
  cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
  api_key:    process.env.CLOUDINARY_API_KEY,
  api_secret: process.env.CLOUDINARY_API_SECRET,
});

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 5 * 1024 * 1024 } });

const uploadToCloudinary = (buffer, folder) =>
  new Promise((resolve, reject) => {
    const stream = cloudinary.uploader.upload_stream({ folder }, (err, result) =>
      err ? reject(err) : resolve(result)
    );
    stream.end(buffer);
  });

// ── POST /api/upload/avatar ──────────────────────────────────
router.post('/avatar', auth, upload.single('image'), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No file provided' });
  const result = await uploadToCloudinary(req.file.buffer, 'craftsconnect/avatars');
  await db.query('UPDATE users SET avatar_url=$1 WHERE id=$2', [result.secure_url, req.user.id]);
  res.json({ url: result.secure_url });
});

// ── POST /api/upload/work-photo ──────────────────────────────
router.post('/work-photo', auth, requireRole('craftsman'), upload.single('image'), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No file provided' });
  const result = await uploadToCloudinary(req.file.buffer, 'craftsconnect/work-photos');
  const { rows: craft } = await db.query('SELECT id FROM craftsmen WHERE user_id=$1', [req.user.id]);
  if (!craft.length) return res.status(404).json({ error: 'Craftsman not found' });
  await db.query(
    'INSERT INTO craftsman_photos (craftsman_id, url, type) VALUES ($1,$2,$3)',
    [craft[0].id, result.secure_url, 'work']
  );
  res.json({ url: result.secure_url });
});

module.exports = router;
