# Deployment Information

## Public URL
https://batch02-day12-cloud-infras.up.railway.app

## Platform
Railway

## Test Commands

### Health Check
```bash
curl https://batch02-day12-cloud-infras.up.railway.app/health
# Expected response structure:
# {"status":"ok","version":"1.0.0","environment":"production","uptime_seconds":123.4,"checks":{"llm":"mock","redis":"ok"},"timestamp":"..."}
```

### Readiness Check
```bash
curl https://batch02-day12-cloud-infras.up.railway.app/ready
# Expected response: {"ready":true}
```

### API Test (with authentication)
```bash
curl -X POST https://batch02-day12-cloud-infras.up.railway.app/ask \
  -H "X-API-Key: dev-key-change-me-in-production" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "student_test_user", "question": "What is Docker?"}'
```

### Session History Check
```bash
curl https://batch02-day12-cloud-infras.up.railway.app/chat/student_test_user/history \
  -H "X-API-Key: dev-key-change-me-in-production"
```

## Environment Variables Set
- `PORT` (automatically injected by Railway, e.g., `8000`)
- `ENVIRONMENT` (`production`)
- `AGENT_API_KEY` (secret key used for header validation)
- `REDIS_URL` (injected via Railway Redis attachment, e.g., `redis://default:...@...:6379`)
- `RATE_LIMIT_PER_MINUTE` (`10`)
- `DAILY_BUDGET_USD` (`5.0`)

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png) (Simulated / To be attached by student)
- [Service running](screenshots/running.png) (Simulated / To be attached by student)
- [Test results](screenshots/test.png) (Simulated / To be attached by student)
