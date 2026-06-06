require('dotenv').config();
const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const morgan = require('morgan');
const rateLimit = require('express-rate-limit');
const db = require('./config/db');

const app = express();

console.log('SERVER FILE = server.js');
console.log('NODE_ENV =', process.env.NODE_ENV);
console.log('PORT ENV =', process.env.PORT);

// Railway test route - BEFORE all middleware
app.get('/railway-test', (req, res) => {
  res.status(200).json({
    ok: true,
    service: 'railway-test'
  });
});

// ── Middleware ──────────────────────────────────────────────
app.use(helmet());
app.use(cors({ origin: process.env.ALLOWED_ORIGINS?.split(',') || '*' }));
app.use(express.json({ limit: '10mb' }));
app.set('trust proxy', 1);

// Rate limiting;
app.use(morgan('dev'));

// Rate limiting
const limiter = rateLimit({ windowMs: 15 * 60 * 1000, max: 100 });
app.use('/api/', limiter);

const authLimiter = rateLimit({ windowMs: 15 * 60 * 1000, max: 10 });
app.use('/api/auth/', authLimiter);

// ── Routes ──────────────────────────────────────────────────
app.use('/api/auth', require('./routes/auth'));
app.use('/api/craftsmen', require('./routes/craftsmen'));
app.use('/api/requests', require('./routes/requests'));
app.use('/api/reviews', require('./routes/reviews'));
app.use('/api/payments', require('./routes/payments'));
app.use('/api/notifications', require('./routes/notifications'));
app.use('/api/upload', require('./routes/upload'));
app.use('/api/admin', require('./routes/admin'));
app.use('/api/chat', require('./routes/chat'));

// Admin dashboard static files
app.use('/admin', express.static('public/admin'));

// Socket.io setup
const http = require('http');
const server = http.createServer(app);
const { Server } = require('socket.io');
const io = new Server(server, {
  cors: {
    origin: process.env.ALLOWED_ORIGINS?.split(',') || '*'
  }
});

io.on('connection', (socket) => {
  console.log('User connected:', socket.id);

  socket.on('join_chat', ({ chatId }) => {
    socket.join(`chat_${chatId}`);
  });

  socket.on('send_message', async (data) => {
    const { chatId, senderId, message } = data;

    await db.query(
      'INSERT INTO chat_messages (chat_id, sender_id, message) VALUES ($1, $2, $3)',
      [chatId, senderId, message]
    );

    io.to(`chat_${chatId}`).emit('new_message', {
      chatId,
      senderId,
      message,
      created_at: new Date().toISOString()
    });
  });

  socket.on('disconnect', () => {
    console.log('User disconnected:', socket.id);
  });
});

// Health check
app.get('/health', (req, res) => res.json({ status: 'ok', version: '1.0.0' }));

// System health endpoint
app.get('/system/health', (req, res) => {
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    timestamp: new Date().toISOString()
  });
});

// API test route
app.get('/api/test', (req, res) => {
  res.json({ ok: true });
});

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
console.log("PORT ENV =", process.env.PORT || 8080);
const PORT = process.env.PORT || 8080;
server.listen(PORT, '0.0.0.0', () => console.log(`🚀 CraftsConnect API running on port ${PORT}`));
