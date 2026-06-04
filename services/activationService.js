const db = require('../config/db');

class ActivationService {
  async approveCraftsman(userId) {
    await db.query(`
      UPDATE craftsmen
      SET status = 'approved',
          is_verified = true
      WHERE user_id = $1
    `, [userId]);

    return this.activateIfEligible(userId);
  }

  async activateIfEligible(userId) {
    const { rows } = await db.query(`
      SELECT * FROM craftsmen WHERE user_id = $1
    `, [userId]);

    const c = rows[0];
    if (!c) return;

    if (c.status !== 'approved') return;

    if (c.subscription_status === 'active') {
      await db.query(`
        UPDATE craftsmen
        SET is_active = true
        WHERE user_id = $1
      `, [userId]);
    }
  }

  async suspendCraftsman(userId) {
    await db.query(`
      UPDATE craftsmen
      SET status = 'suspended',
          is_active = false
      WHERE user_id = $1
    `, [userId]);
  }

  async rejectCraftsman(userId) {
    await db.query(`
      UPDATE craftsmen
      SET status = 'rejected',
          is_active = false
      WHERE user_id = $1
    `, [userId]);
  }
}

module.exports = new ActivationService();