const logger = {
  info: (event, data = {}) => {
    console.log(JSON.stringify({
      level: 'info',
      event,
      data,
      timestamp: new Date().toISOString()
    }));
  },

  error: (event, error, data = {}) => {
    console.log(JSON.stringify({
      level: 'error',
      event,
      message: error.message,
      stack: error.stack,
      data,
      timestamp: new Date().toISOString()
    }));
  }
};

module.exports = logger;