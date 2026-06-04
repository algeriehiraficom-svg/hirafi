const { Worker } = require('bullmq');
const Redis = require('ioredis');
const db = require('../config/db');
const logger = require('../services/logger');
const metrics = require('../services/metrics');

const connection = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

const worker = new Worker(
  'events',
  async job => {
    const start = Date.now();
    const traceId = job.data.traceId || job.id;

    logger.info('EVENT_START', {
      event: job.name,
      id: job.id,
      traceId
    });

    try {
      await handleEvent(job.name, job.data);

      const duration = Date.now() - start;
      metrics.recordSuccess(duration);

      logger.info('EVENT_SUCCESS', {
        event: job.name,
        traceId,
        duration
      });

    } catch (err) {
      metrics.recordFailure();

      await db.query(
        `INSERT INTO failed_events (type, payload, error) VALUES ($1, $2, $3)`,
        [job.name, JSON.stringify(job.data), err.message]
      );

      logger.error('EVENT_FAILED', err, {
        event: job.name,
        id: job.id,
        traceId
      });

      throw err;
    }
  },
  { connection }
);

async function handleEvent(type, payload) {
  switch (type) {
    case 'user.created':
      return handleUserCreated(payload);
    case 'craftsman.profile.submitted':
      return handleProfileSubmitted(payload);
    case 'craftsman.approved':
      return handleApproved(payload);
    case 'craftsman.activated':
      return handleActivated(payload);
    default:
      logger.error('EVENT_UNKNOWN', new Error('Unknown event type'), { type });
  }
}

async function handleUserCreated(user) {
  if (user.role === 'craftsman') {
    await db.query(
      `INSERT INTO craftsmen (user_id, status) VALUES ($1, 'draft') ON CONFLICT DO NOTHING`,
      [user.id]
    );
  }
}

async function handleProfileSubmitted(data) {
  await db.query(
    `UPDATE craftsmen
     SET status = 'pending',
         gps_lat = $1,
         gps_lng = $2,
         category = $3,
         location = ST_MakePoint($2, $1)::geography,
         updated_at = NOW()
     WHERE user_id = $4`,
    [data.lat, data.lng, data.category, data.userId]
  );
}

async function handleApproved(craftsmanId) {
  // craftsmanId is the craftsman.id, we need to find user_id
  const { rows } = await db.query(
    'UPDATE craftsmen SET status = 'approved' WHERE id = $1 RETURNING user_id',
    [craftsmanId]
  );

  const userId = rows[0]?.user_id;

  if (userId) {
    const { emitEvent } = require('../services/eventQueue');
    await emitEvent('craftsman.activated', userId);
  }
}

async function handleActivated(userId) {
  // Check subscription status before activation
  const { rows } = await db.query(
    'SELECT subscription_status FROM craftsmen WHERE user_id = $1',
    [userId]
  );

  const subStatus = rows[0]?.subscription_status;

  // Only activate if subscription is active or free (auto-activate)
  if (subStatus === 'active' || !subStatus || subStatus === 'inactive') {
    await db.query(
      'UPDATE craftsmen SET is_active = true WHERE user_id = $1',
      [userId]
    );
  }
}

worker.on('completed', job => {
  console.log(`[Worker] Event ${job.name} completed`);
});

worker.on('failed', (job, err) => {
  console.error(`[Worker] Event ${job?.name} failed:`, err);
});

module.exports = worker;