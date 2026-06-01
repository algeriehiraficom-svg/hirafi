const admin = require('firebase-admin');

let initialized = false;
const initFirebase = () => {
  if (!initialized && process.env.FIREBASE_PROJECT_ID) {
    admin.initializeApp({
      credential: admin.credential.cert({
        projectId:    process.env.FIREBASE_PROJECT_ID,
        privateKey:   process.env.FIREBASE_PRIVATE_KEY?.replace(/\\n/g, '\n'),
        clientEmail:  process.env.FIREBASE_CLIENT_EMAIL,
      }),
    });
    initialized = true;
  }
};

const sendPushNotification = async (token, { title, body, data = {} }) => {
  try {
    initFirebase();
    await admin.messaging().send({ token, notification: { title, body }, data });
  } catch (err) {
    console.error('[FCM] Push notification error:', err.message);
  }
};

module.exports = { sendPushNotification };
