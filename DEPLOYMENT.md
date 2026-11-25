# Deployment Information

> **Trạng thái:** Chưa deploy lên cloud (cần hoàn tất deploy `06-lab-complete/` lên Railway hoặc Render, thay `<PUBLIC_URL>` bằng domain thực tế, chạy 4 lệnh kiểm tra bên dưới và bổ sung 3 ảnh vào `screenshots/`).

## Public URL
https://<your-agent-domain>

## Platform
Railway / Render (cấu hình sẵn trong [06-lab-complete/railway.toml](06-lab-complete/railway.toml) và [06-lab-complete/render.yaml](06-lab-complete/render.yaml))

## Test Commands

Đặt biến môi trường trước khi chạy (thay `<PUBLIC_URL>` và `<YOUR_AGENT_API_KEY>`):

```bash
export BASE="https://<your-agent-domain>"
export AGENT_API_KEY="<YOUR_AGENT_API_KEY>"
```

### 1. Health Check (`/health` → 200)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS "$BASE/health"
```

### 2. Readiness Check (`/ready` → 200 khi Redis hoạt động)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS "$BASE/ready"
```

### 3. Auth Required (`/ask` không có key → 401)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```

### 4. API Test với `X-API-Key` (`/ask` đúng key → 200)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"user_id": "test", "question": "Hello"}'
```

### 5. Kiểm tra tự động bằng script chấm
```bash
cd 06-lab-complete
python check_production_ready.py --public-url "$BASE"
```

## Environment Variables Set (trên Railway / Render Dashboard — không commit giá trị thật)
- `PORT` (do nền tảng cấp tự động, mặc định `8000`)
- `ENVIRONMENT=production`
- `REDIS_URL` (trỏ tới service Redis trên cloud)
- `AGENT_API_KEY` (secret đặt trên Dashboard hoặc `generateValue: true` ở Render)
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=1.0`
- `MONTHLY_BUDGET_USD=10.0`
- `LOG_LEVEL=INFO`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
