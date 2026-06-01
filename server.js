require('dotenv').config();
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const rateLimit = require('express-rate-limit');

const app = express();

// ── Middleware ──────────────────────────────────────────────
app.use(helmet());
app.use(cors({ origin: process.env.ALLOWED_ORIGINS?.split(',') || '*' }));
app.use(express.json({ limit: '10mb' }));
app.use(morgan('dev'));

// Rate limiting
const limiter = rateLimit({ windowMs: 15 * 60 * 1000, max: 100 });
app.use('/api/', limiter);

const authLimiter = rateLimit({ windowMs: 15 * 60 * 1000, max: 10 });
app.use('/api/auth/', authLimiter);

// ── Routes ──────────────────────────────────────────────────
app.use('/api/auth',       require('./routes/auth'));
app.use('/api/craftsmen',  require('./routes/craftsmen'));
app.use('/api/requests',   require('./routes/requests'));
app.use('/api/reviews',    require('./routes/reviews'));
app.use('/api/payments',   require('./routes/payments'));
app.use('/api/notifications', require('./routes/notifications'));
app.use('/api/upload',     require('./routes/upload'));
app.use('/api/admin',      require('./routes/admin'));

// Health check
app.get('/health', (req, res) => res.json({ status: 'ok', version: '1.0.0' }));

// Root route
app.get('/', (req, res) => {
  res.status(200).json({
    application: 'HIRAFICOM API',
    status: 'online',
    version: '1.0.0'
  });
});

// Favicon
app.get('/favicon.ico', (req, res) => res.status(204).end());

// 404
app.use((req, res) => res.status(404).json({ error: 'Route not found' }));

// Global error handler
app.use((err, req, res, next) => {
  console.error(err.stack);
  res.status(err.status || 500).json({
    error: process.env.NODE_ENV === 'production' ? 'Internal server error' : err.message
  });
});

// ── Start ───────────────────────────────────────────────────
const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`🚀 CraftsConnect API running on port ${PORT}`));
