const metrics = {
  eventsProcessed: 0,
  eventsFailed: 0,
  eventLatency: []
};

function recordSuccess(duration) {
  metrics.eventsProcessed++;
  metrics.eventLatency.push(duration);
}

function recordFailure() {
  metrics.eventsFailed++;
}

function getMetrics() {
  const avgLatency = metrics.eventLatency.length
    ? metrics.eventLatency.reduce((a, b) => a + b, 0) / metrics.eventLatency.length
    : 0;

  return {
    eventsProcessed: metrics.eventsProcessed,
    eventsFailed: metrics.eventsFailed,
    avgLatency: Math.round(avgLatency)
  };
}

module.exports = { recordSuccess, recordFailure, getMetrics };