const jwt = require('jsonwebtoken');
const db = require('../config/db');

const auth = async (req, res, next) => {
  try {
    const token = req.headers.authorization?.replace('Bearer ', '');
    console.log('TOKEN RECEIVED=', token ? token.substring(0, 50) + '...' : null);
    console.log('JWT_SECRET EXISTS=', !!process.env.JWT_SECRET);
    
    if (!token) return res.status(401).json({ error: 'No token provided' });

    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    console.log('DECODED TOKEN =', decoded);

    // ADMIN FLOW (clean separation)
    if (decoded.role === 'admin') {
      req.user = {
        role: 'admin',
        isAdmin: true
      };
      return next();
    }

    // USER FLOW ONLY
    if (!decoded.id) {
      return res.status(401).json({ error: 'Invalid token payload' });
    }

    const { rows } = await db.query(
      'SELECT id, phone, name, role, is_active FROM users WHERE id = $1',
      [decoded.id]
    );

    if (!rows.length || !rows[0].is_active) {
      return res.status(401).json({ error: 'Account not found or suspended' });
    }

    req.user = rows[0];
    next();

  } catch (err) {
    console.error('JWT ERROR =', err.message);
    return res.status(401).json({ error: 'Invalid or expired token' });
  }
};

const requireRole = (...roles) => (req, res, next) => {
  if (!roles.includes(req.user.role)) {
    return res.status(403).json({ error: 'Insufficient permissions' });
  }
  next();
};

const requireAdmin = (req, res, next) => {
  if (!req.user) {
    return res.status(401).json({ error: 'Unauthenticated' });
  }

  if (req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Admin only' });
  }

  next();
};

module.exports = { auth, requireRole, requireAdmin };