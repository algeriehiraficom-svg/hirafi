# HIRAFICOM Backend API

Node.js + Express API connected to Neon PostgreSQL.

## Quick Setup

1. Clone repo
2. `npm install`
3. Copy `.env.example` to `.env`
4. Add your Neon DATABASE_URL
5. `npm start`

## Environment Variables

DATABASE_URL=postgresql://... (from Neon)
JWT_SECRET=your_secret_key
PORT=5000
ALLOWED_ORIGINS=*
COMMISSION_RATE=0.10

## Deploy to Railway

Railway auto-detects Node.js. Just:
- Connect GitHub repo
- Set environment variables
- Deploy

## API Endpoints

GET /health
POST /api/auth/send-otp
POST /api/auth/verify-otp
GET /api/auth/me
GET /api/specialties
GET /api/craftsmen/nearby
POST /api/requests
GET/PATCH /api/requests
POST /api/reviews