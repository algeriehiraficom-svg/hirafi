const router = require('express').Router();
const db = require('../config/db');
const { auth: requireAuth } = require('../middleware/auth');

const validateCoordinates = (lat, lng) => {
  const numLat = parseFloat(lat);
  const numLng = parseFloat(lng);
  if (isNaN(numLat) || isNaN(numLng)) return false;
  if (numLat < -90 || numLat > 90) return false;
  if (numLng < -180 || numLng > 180) return false;
  return true;
};

const requireCraftsman = async (req, res, next) => {
  const { rows } = await db.query(
    'SELECT role FROM users WHERE id = $1',
    [req.user.id]
  );

  if (!rows.length) {
    return res.status(401).json({ error: 'User not found' });
  }

  if (rows[0].role !== 'craftsman') {
    return res.status(403).json({ error: 'Craftsman only' });
  }

  req.user.role = 'craftsman';
  next();
};

// ── POST /api/craftsmen/register ───────────────────────────────
router.post('/register', requireAuth, async (req, res) => {
  console.log('REGISTER BODY =', req.body);
  const { specialties, wilayaCode, address, description } = req.body;
  console.log('PARSED VALUES =', {
    specialties,
    wilayaCode,
    address,
    description
  });

  // Set user role to craftsman
  await db.query(
    'UPDATE users SET role = $1, is_active = TRUE WHERE id = $2',
    ['craftsman', req.user.id]
  );

  // Insert or update craftsman profile
  const { rows } = await db.query(
    `INSERT INTO craftsmen (user_id, wilaya, city, bio)
     VALUES ($1, $2, $3, $4)
     ON CONFLICT (user_id) DO UPDATE SET
       wilaya = EXCLUDED.wilaya,
       city = EXCLUDED.city,
       bio = EXCLUDED.bio
     RETURNING *`,
    [req.user.id, wilayaCode, address, description]
  );

  // Link specialties (array of codes)
  console.log('SPECIALTIES RECEIVED =', specialties);
  if (Array.isArray(specialties) && specialties.length) {
    await db.query('DELETE FROM craftsman_specialties WHERE craftsman_id = $1', [rows[0].id]);
    for (const code of specialties) {
      const { rows: specRows } = await db.query(
        'SELECT id FROM specialties WHERE code = $1',
        [code]
      );
      if (specRows.length) {
        await db.query(
          'INSERT INTO craftsman_specialties (craftsman_id, specialty_id) VALUES ($1, $2) ON CONFLICT (craftsman_id, specialty_id) DO NOTHING',
          [rows[0].id, specRows[0].id]
        );
      }
    }
  }

  res.json({ success: true, craftsman: rows[0] });
});

// ── GET /api/craftsmen/nearby ────────────────────────────────
router.get('/nearby', requireAuth, async (req, res) => {
  try {
    const { lat, lng, radius = 10, specialty_id } = req.query;
    if (!validateCoordinates(lat, lng)) {
      return res.status(400).json({ error: 'Invalid GPS coordinates' });
    }

    const lngNum = parseFloat(lng);
    const latNum = parseFloat(lat);
    const radiusMeters = parseFloat(radius) * 1000;

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
    const params = [lngNum, latNum, radiusMeters];

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
  } catch (err) {
    console.error("NEARBY ERROR:", err);
    res.status(500).json({ error: "Failed to fetch nearby craftsmen" });
  }
});

// ── GET /api/craftsmen/me ───────────────────────────────────
router.get('/me', requireAuth, async (req, res) => {
  try {
    const { rows } = await db.query(`
      SELECT c.*, 
             ARRAY_AGG(DISTINCT jsonb_build_object('id', s.id, 'name_ar', s.name_ar, 'icon', s.icon))
               FILTER (WHERE s.id IS NOT NULL) AS specialties
      FROM craftsmen c
      LEFT JOIN craftsman_specialties cs ON cs.craftsman_id = c.id
      LEFT JOIN specialties s ON s.id = cs.specialty_id
      WHERE c.user_id = $1
      GROUP BY c.id
    `, [req.user.id]);

    if (rows.length === 0) {
      return res.status(404).json({ error: "Craftsman profile not found" });
    }

    const craftsman = rows[0];
    const approved = craftsman.is_verified ? 'approved' : 'pending';
    const status = craftsman.is_verified ? 'approved' : 'pending';
    res.json({ ...craftsman, approved, status });
  } catch (err) {
    console.error("Craftsman /me error:", err.message);
    res.status(500).json({ error: "Failed to fetch craftsman profile" });
  }
});

// ── GET /api/craftsmen/:id ───────────────────────────────────
router.get('/:id', async (req, res) => {
  const { id } = req.params;
  
  // Validate UUID format
  const uuidRegex = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;
  if (!uuidRegex.test(id)) {
    return res.status(400).json({ error: "Invalid craftsman ID" });
  }

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
router.patch('/me', requireAuth, requireCraftsman, async (req, res) => {
  const { bio, experience_years, price_min, price_max, city, wilaya, is_available, specialties } = req.body;

  let { rows } = await db.query(
    'SELECT * FROM craftsmen WHERE user_id = $1',
    [req.user.id]
  );

  if (!rows.length) {
    await db.query('INSERT INTO craftsmen (user_id) VALUES ($1)', [req.user.id]);
    const newResult = await db.query('SELECT * FROM craftsmen WHERE user_id = $1', [req.user.id]);
    rows = newResult.rows;
  }

  const craftsman_id = rows[0].id;

  await db.query(`
    UPDATE craftsmen SET
      bio=$1, experience_years=$2, price_min=$3, price_max=$4,
      city=$5, wilaya=$6, is_available=$7, updated_at=NOW()
    WHERE user_id=$8`,
    [bio, experience_years, price_min, price_max, city, wilaya, is_available, req.user.id]
  );

  if (Array.isArray(specialties)) {
    await db.query('DELETE FROM craftsman_specialties WHERE craftsman_id = $1', [craftsman_id]);
    for (const sid of specialties) {
      await db.query(
        'INSERT INTO craftsman_specialties (craftsman_id, specialty_id) VALUES ($1, $2) ON CONFLICT DO NOTHING',
        [craftsman_id, sid]
      );
    }
  }

  const { rows: updated } = await db.query('SELECT * FROM craftsmen WHERE id = $1', [craftsman_id]);
  res.json(updated[0]);
});

// ── PUT /api/craftsmen/me/location ─────────────────────────────
router.put('/me/location', requireAuth, requireCraftsman, async (req, res) => {
  const userId = req.user.id;
  const { lat, lng } = req.body;

  if (!validateCoordinates(lat, lng)) {
    return res.status(400).json({ error: 'Invalid GPS coordinates' });
  }

  let { rows } = await db.query(
    'SELECT * FROM craftsmen WHERE user_id = $1',
    [userId]
  );

  if (!rows.length) {
    await db.query(
      `INSERT INTO craftsmen (user_id, location)
       VALUES ($1, ST_MakePoint($2, $3)::geography)`,
      [userId, parseFloat(lng), parseFloat(lat)]
    );
  } else {
    await db.query(
      `UPDATE craftsmen
       SET location = ST_MakePoint($1, $2)::geography,
           updated_at = NOW()
       WHERE user_id = $3`,
      [parseFloat(lng), parseFloat(lat), userId]
    );
  }

  return res.json({ success: true, location: { lat, lng } });
});

// ── POST /api/craftsmen/profile ──────────────────────────────
router.post('/profile', requireAuth, requireCraftsman, async (req, res) => {
  const userId = req.user.id;
  const { lat, lng, category, specialties } = req.body;

  if (!validateCoordinates(lat, lng)) {
    return res.status(400).json({ error: 'Invalid GPS coordinates' });
  }

  const { rows: existing } = await db.query(
    'SELECT id FROM craftsmen WHERE user_id = $1',
    [userId]
  );

  if (existing.length) {
    await db.query(`
      UPDATE craftsmen SET
        profile_completed = true,
        gps_lat = $1,
        gps_lng = $2,
        category = $3,
        status = 'pending',
        location = ST_MakePoint($2, $1)::geography,
        updated_at = NOW()
      WHERE user_id = $4
    `, [lat, lng, category, userId]);
  } else {
    await db.query(`
      INSERT INTO craftsmen (
        user_id,
        status,
        profile_completed,
        gps_lat,
        gps_lng,
        category,
        location
      ) VALUES ($1, 'pending', true, $2, $3, $4, ST_MakePoint($3, $2)::geography)
    `, [userId, lat, lng, category]);
  }

  if (Array.isArray(specialties)) {
    const { rows: cm } = await db.query('SELECT id FROM craftsmen WHERE user_id = $1', [userId]);
    const craftsmanId = cm[0]?.id;

    if (craftsmanId) {
      await db.query('DELETE FROM craftsman_specialties WHERE craftsman_id = $1', [craftsmanId]);
      for (const sid of specialties) {
        await db.query(
          'INSERT INTO craftsman_specialties (craftsman_id, specialty_id) VALUES ($1, $2) ON CONFLICT DO NOTHING',
          [craftsmanId, sid]
        );
      }
    }
  }

  res.json({ success: true });
});

// ── GET /api/craftsmen/specialties/all ──────────────────────
router.get('/specialties/all', async (req, res) => {
  const { rows } = await db.query('SELECT * FROM specialties ORDER BY id');
  res.json(rows);
});

// ── GET /api/craftsmen/search ────────────────────────────────
router.get('/search', async (req, res) => {
  const { lat, lng, radius = 20 } = req.query;

  if (!validateCoordinates(lat, lng)) {
    return res.status(400).json({ error: 'Invalid GPS coordinates' });
  }

  const latNum = parseFloat(lat);
  const lngNum = parseFloat(lng);
  const radiusKm = parseFloat(radius);

  const { rows } = await db.query(
    `SELECT
      c.id, c.rating, c.total_jobs, c.price_min, c.price_max,
      c.is_available, c.city,
      u.name, u.avatar_url,
      (6371 * acos(
        cos(radians($1)) *
        cos(radians(ST_Y(c.location::geometry))) *
        cos(radians(ST_X(c.location::geometry) - radians($2)) +
        sin(radians($1)) *
        sin(radians(ST_Y(c.location::geometry))
      )) AS distance
    FROM craftsmen c
    JOIN users u ON u.id = c.user_id
    WHERE c.status = 'active'
      AND (6371 * acos(
        cos(radians($1)) *
        cos(radians(ST_Y(c.location::geometry))) *
        cos(radians(ST_X(c.location::geometry) - radians($2)) +
        sin(radians($1)) *
        sin(radians(ST_Y(c.location::geometry))
      )) < $3
    ORDER BY distance ASC
    LIMIT 50`,
    [latNum, lngNum, radiusKm]
  );

  res.json(rows);
});

module.exports = router;