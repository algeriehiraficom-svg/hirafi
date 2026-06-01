const router = require('express').Router();
const db = require('../config/db');
const { auth, requireRole } = require('../middleware/auth');

// ── GET /api/craftsmen/nearby ────────────────────────────────
// Query: lat, lng, radius (km, default 10), specialty_id
router.get('/nearby', auth, async (req, res) => {
  const { lat, lng, radius = 10, specialty_id } = req.query;
  if (!lat || !lng) return res.status(400).json({ error: 'lat and lng are required' });

  let q = `
    SELECT
      c.id, c.rating, c.total_jobs, c.price_min, c.price_max,
      c.is_available, c.city,
      u.name, u.avatar_url,
      ST_Distance(c.location, ST_MakePoint($1, $2)::geography) AS distance_meters,
      ARRAY_AGG(DISTINCT s.name_ar) FILTER (WHERE s.name_ar IS NOT NULL) AS specialties
    FROM craftsmen c
    JOIN users u ON u.id = c.user_id
    LEFT JOIN craftsman_specialties cs ON cs.craftsman_id = c.id
    LEFT JOIN specialties s ON s.id = cs.specialty_id
    WHERE c.is_verified = TRUE
      AND c.is_available = TRUE
      AND c.subscription_active = TRUE
      AND ST_DWithin(c.location, ST_MakePoint($1, $2)::geography, $3)
  `;
  const params = [parseFloat(lng), parseFloat(lat), parseFloat(radius) * 1000];

  if (specialty_id) {
    q += ` AND cs.specialty_id = $4`;
    params.push(parseInt(specialty_id));
  }

  q += `
    GROUP BY c.id, u.name, u.avatar_url
    ORDER BY distance_meters ASC
    LIMIT 30
  `;

  const { rows } = await db.query(q, params);
  res.json(rows.map(r => ({ ...r, distance_km: (r.distance_meters / 1000).toFixed(1) })));
});

// ── GET /api/craftsmen/:id ───────────────────────────────────
router.get('/:id', async (req, res) => {
  const { rows } = await db.query(`
    SELECT
      c.*, u.name, u.phone, u.avatar_url,
      ARRAY_AGG(DISTINCT jsonb_build_object('id', s.id, 'name_ar', s.name_ar, 'icon', s.icon))
        FILTER (WHERE s.id IS NOT NULL) AS specialties,
      ARRAY_AGG(DISTINCT cp.url) FILTER (WHERE cp.type = 'work') AS work_photos
    FROM craftsmen c
    JOIN users u ON u.id = c.user_id
    LEFT JOIN craftsman_specialties cs ON cs.craftsman_id = c.id
    LEFT JOIN specialties s ON s.id = cs.specialty_id
    LEFT JOIN craftsman_photos cp ON cp.craftsman_id = c.id
    WHERE c.id = $1
    GROUP BY c.id, u.name, u.phone, u.avatar_url
  `, [req.params.id]);

  if (!rows.length) return res.status(404).json({ error: 'Craftsman not found' });
  res.json(rows[0]);
});

// ── PATCH /api/craftsmen/me ──────────────────────────────────
router.patch('/me', auth, requireRole('craftsman'), async (req, res) => {
  const { bio, experience_years, price_min, price_max, city, wilaya, is_available, specialties } = req.body;

  const { rows } = await db.query(`
    UPDATE craftsmen SET
      bio=$1, experience_years=$2, price_min=$3, price_max=$4,
      city=$5, wilaya=$6, is_available=$7, updated_at=NOW()
    WHERE user_id=$8 RETURNING *
  `, [bio, experience_years, price_min, price_max, city, wilaya, is_available, req.user.id]);

  if (!rows.length) return res.status(404).json({ error: 'Craftsman profile not found' });

  // Update specialties
  if (Array.isArray(specialties)) {
    const craftsman_id = rows[0].id;
    await db.query('DELETE FROM craftsman_specialties WHERE craftsman_id = $1', [craftsman_id]);
    for (const sid of specialties) {
      await db.query(
        'INSERT INTO craftsman_specialties (craftsman_id, specialty_id) VALUES ($1, $2) ON CONFLICT DO NOTHING',
        [craftsman_id, sid]
      );
    }
  }

  res.json(rows[0]);
});

// ── PATCH /api/craftsmen/me/location ────────────────────────
router.patch('/me/location', auth, requireRole('craftsman'), async (req, res) => {
  const { lat, lng } = req.body;
  if (!lat || !lng) return res.status(400).json({ error: 'lat and lng required' });

  await db.query(
    `UPDATE craftsmen SET location = ST_MakePoint($1, $2)::geography WHERE user_id = $3`,
    [parseFloat(lng), parseFloat(lat), req.user.id]
  );
  res.json({ message: 'Location updated' });
});

// ── GET /api/craftsmen/specialties/all ──────────────────────
router.get('/specialties/all', async (req, res) => {
  const { rows } = await db.query('SELECT * FROM specialties ORDER BY id');
  res.json(rows);
});

module.exports = router;
