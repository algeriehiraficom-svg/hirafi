const { Queue } = require('bullmq');
const Redis = require('ioredis');

const connection = new Redis(process.env.REDIS_URL || 'redis://localhost:6379');

const eventQueue = new Queue('events', {
  connection
});

async function emitEvent(type, payload) {
  await eventQueue.add(type, payload, {
    attempts: 5,
    backoff: {
      type: 'exponential',
      delay: 2000
    },
    removeOnComplete: true
  });
}

module.exports = { emitEvent };