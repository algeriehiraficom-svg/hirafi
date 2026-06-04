-- ============================================================
--  CraftsConnect — Database Schema
--  PostgreSQL
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgis;  -- for GPS distance queries

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE users (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  phone        VARCHAR(20) UNIQUE NOT NULL,
  name         VARCHAR(100),
  email        VARCHAR(150),
  avatar_url   TEXT,
  role         VARCHAR(20) NOT NULL CHECK (role IN ('client','craftsman','admin')),
  is_active    BOOLEAN DEFAULT TRUE,
  is_verified  BOOLEAN DEFAULT FALSE,
  fcm_token    TEXT,          -- Firebase push notification token
  created_at   TIMESTAMPTZ DEFAULT NOW(),
  updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- OTP (phone verification)
-- ============================================================
CREATE TABLE otp_codes (
  id         SERIAL PRIMARY KEY,
  phone      VARCHAR(20) NOT NULL,
  code       VARCHAR(6) NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  used       BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- CRAFTSMEN (extends users where role = 'craftsman')
-- ============================================================
CREATE TABLE craftsmen (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id         UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  bio             TEXT,
  experience_years INT DEFAULT 0,
  price_min       INT DEFAULT 0,    -- in DZD
  price_max       INT DEFAULT 0,
  rating          NUMERIC(2,1) DEFAULT 0.0,
  total_reviews   INT DEFAULT 0,
  total_jobs      INT DEFAULT 0,
  is_available    BOOLEAN DEFAULT TRUE,
  is_verified     BOOLEAN DEFAULT FALSE,
  is_active       BOOLEAN DEFAULT FALSE,
  location        GEOGRAPHY(POINT, 4326),  -- GPS: lng, lat
  gps_lat         NUMERIC(10, 8),
  gps_lng         NUMERIC(11, 8),
  city            VARCHAR(100),
  wilaya          VARCHAR(100),
  subscription_active BOOLEAN DEFAULT FALSE,
  subscription_status VARCHAR(20) DEFAULT 'inactive',
  profile_completed BOOLEAN DEFAULT FALSE,
  wallet_balance  INT DEFAULT 0,    -- in DZD
  status          VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft','pending','approved','active','rejected','suspended')),
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- SPECIALTIES
-- ============================================================
CREATE TABLE specialties (
  id       SERIAL PRIMARY KEY,
  name_ar  VARCHAR(100) NOT NULL,
  name_fr  VARCHAR(100),
  icon     VARCHAR(10),
  category VARCHAR(50)
);

INSERT INTO specialties (name_ar, name_fr, icon, category) VALUES
  ('سباكة', 'Plomberie', '🔧', 'construction'),
  ('كهرباء', 'Électricité', '⚡', 'construction'),
  ('نجارة', 'Menuiserie', '🪵', 'construction'),
  ('دهان', 'Peinture', '🎨', 'construction'),
  ('تكييف وتبريد', 'Climatisation', '❄️', 'appliances'),
  ('بلاط وسيراميك', 'Carrelage', '🏠', 'construction'),
  ('لحام', 'Soudure', '🔩', 'construction'),
  ('إصلاح أجهزة', 'Électroménager', '📺', 'appliances'),
  ('بناء وإسمنت', 'Maçonnerie', '🧱', 'construction'),
  ('تنظيف', 'Nettoyage', '🧹', 'cleaning');

-- Craftsman ↔ Specialty (many-to-many)
CREATE TABLE craftsman_specialties (
  craftsman_id UUID REFERENCES craftsmen(id) ON DELETE CASCADE,
  specialty_id INT  REFERENCES specialties(id) ON DELETE CASCADE,
  PRIMARY KEY (craftsman_id, specialty_id)
);

-- ============================================================
-- CRAFTSMAN PHOTOS
-- ============================================================
CREATE TABLE craftsman_photos (
  id           SERIAL PRIMARY KEY,
  craftsman_id UUID NOT NULL REFERENCES craftsmen(id) ON DELETE CASCADE,
  url          TEXT NOT NULL,
  type         VARCHAR(20) DEFAULT 'work',  -- 'work' | 'identity'
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- SERVICE REQUESTS
-- ============================================================
CREATE TABLE requests (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  client_id       UUID NOT NULL REFERENCES users(id),
  craftsman_id    UUID REFERENCES craftsmen(id),
  specialty_id    INT  REFERENCES specialties(id),
  title           VARCHAR(200),
  description     TEXT,
  status          VARCHAR(30) DEFAULT 'pending'
                  CHECK (status IN ('pending','accepted','in_progress','completed','cancelled','disputed')),
  location        GEOGRAPHY(POINT, 4326),
  address_text    TEXT,
  city            VARCHAR(100),
  scheduled_at    TIMESTAMPTZ,
  started_at      TIMESTAMPTZ,
  completed_at    TIMESTAMPTZ,
  price_agreed    INT,           -- DZD agreed price
  payment_method  VARCHAR(20) DEFAULT 'cash'  CHECK (payment_method IN ('cash','electronic')),
  payment_status  VARCHAR(20) DEFAULT 'pending' CHECK (payment_status IN ('pending','paid','refunded')),
  notes           TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- REVIEWS
-- ============================================================
CREATE TABLE reviews (
  id            SERIAL PRIMARY KEY,
  request_id    UUID NOT NULL REFERENCES requests(id),
  reviewer_id   UUID NOT NULL REFERENCES users(id),
  reviewee_id   UUID NOT NULL REFERENCES users(id),
  rating        SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment       TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (request_id, reviewer_id)
);

-- ============================================================
-- TRANSACTIONS
-- ============================================================
CREATE TABLE transactions (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  craftsman_id    UUID NOT NULL REFERENCES craftsmen(id),
  request_id      UUID REFERENCES requests(id),
  type            VARCHAR(30) NOT NULL
                  CHECK (type IN ('subscription','commission','top_up','withdrawal','refund')),
  amount          INT NOT NULL,    -- positive = credit, negative = debit
  status          VARCHAR(20) DEFAULT 'completed'
                  CHECK (status IN ('pending','completed','failed')),
  reference       VARCHAR(100),
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- SUBSCRIPTIONS
-- ============================================================
CREATE TABLE subscriptions (
  id            SERIAL PRIMARY KEY,
  craftsman_id  UUID NOT NULL REFERENCES craftsmen(id),
  plan          VARCHAR(20) DEFAULT 'basic' CHECK (plan IN ('basic','premium')),
  price         INT NOT NULL,
  start_date    DATE NOT NULL,
  end_date      DATE NOT NULL,
  is_active     BOOLEAN DEFAULT TRUE,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- NOTIFICATIONS
-- ============================================================
CREATE TABLE notifications (
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type       VARCHAR(50) NOT NULL,
  title      VARCHAR(200),
  body       TEXT,
  data       JSONB,
  is_read    BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- CHATS (user ↔ craftsman conversations)
-- ============================================================
CREATE TABLE IF NOT EXISTS chats (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  craftsman_id UUID NOT NULL REFERENCES craftsmen(id) ON DELETE CASCADE,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(user_id);
CREATE INDEX IF NOT EXISTS idx_chats_craftsman ON chats(craftsman_id);

-- ============================================================
-- MESSAGES (chat per request) - UPDATED FOR CHAT SUPPORT
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_messages (
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  chat_id    UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  sender_id  UUID NOT NULL REFERENCES users(id),
  message    TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_chat ON chat_messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_sender ON chat_messages(sender_id);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX idx_craftsmen_location   ON craftsmen USING GIST(location);
CREATE INDEX idx_craftsmen_city       ON craftsmen(city);
CREATE INDEX idx_craftsmen_available  ON craftsmen(is_available, is_verified, subscription_active);
CREATE INDEX idx_requests_client      ON requests(client_id);
CREATE INDEX idx_requests_craftsman   ON requests(craftsman_id);
CREATE INDEX idx_requests_status      ON requests(status);
CREATE INDEX idx_notifications_user   ON notifications(user_id, is_read);
CREATE INDEX idx_messages_request     ON messages(request_id);

-- ============================================================
-- AUTO-UPDATE updated_at
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated    BEFORE UPDATE ON users    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_craftsmen_updated BEFORE UPDATE ON craftsmen FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_requests_updated BEFORE UPDATE ON requests  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- UPDATE CRAFTSMAN RATING ON NEW REVIEW
-- ============================================================
CREATE OR REPLACE FUNCTION refresh_craftsman_rating()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE craftsmen
  SET rating        = (SELECT ROUND(AVG(rating)::numeric, 1) FROM reviews WHERE reviewee_id = NEW.reviewee_id),
      total_reviews = (SELECT COUNT(*) FROM reviews WHERE reviewee_id = NEW.reviewee_id)
  WHERE user_id = NEW.reviewee_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_rating
AFTER INSERT ON reviews
FOR EACH ROW EXECUTE FUNCTION refresh_craftsman_rating();

-- ============================================================
-- FAILED EVENTS (Observability)
-- ============================================================
CREATE TABLE IF NOT EXISTS failed_events (
  id         SERIAL PRIMARY KEY,
  type       VARCHAR(100) NOT NULL,
  payload    JSONB,
  error      TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
