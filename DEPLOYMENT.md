# Deployment Information

> **Trạng thái:** Đã deploy `06-lab-complete/` lên Railway kèm Redis và kiểm chứng đủ 4 endpoint (`200 / 200 / 401 / 200`) + `check_production_ready.py --public-url` (`PASS 12/12 · 44/44 checks passed`). Còn bổ sung 3 ảnh deploy vào `screenshots/`.

## Public URL
https://k5-l3a-day14-tranquocdong-2a202603643-deployment-production.up.railway.app

## Platform
Railway (Root Directory: `06-lab-complete`, cấu hình [06-lab-complete/railway.toml](06-lab-complete/railway.toml) + dịch vụ Redis trên Railway)

## Test Commands

Đặt biến môi trường trước khi chạy (thay `<YOUR_AGENT_API_KEY>` bằng key đã đặt trên Railway Variables):

```bash
export BASE="https://k5-l3a-day14-tranquocdong-2a202603643-deployment-production.up.railway.app"
export AGENT_API_KEY="<YOUR_AGENT_API_KEY>"
```

### 1. Health Check (`/health` → 200)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS "$BASE/health"
```
Kết quả đo thực tế: `200` (`{"status":"ok","environment":"production",...}`).

### 2. Readiness Check (`/ready` → 200 khi Redis hoạt động)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS "$BASE/ready"
```
Kết quả đo thực tế: `200` (`{"ready":true,"redis":"connected",...}`).

### 3. Auth Required (`/ask` không có key → 401)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
```
Kết quả đo thực tế: `401` (`{"detail":"Invalid or missing API key. Include header: X-API-Key: <your-key>"}`).

### 4. API Test với `X-API-Key` (`/ask` đúng key → 200)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"user_id": "test", "question": "Hello"}'
```
Kết quả đo thực tế: `200` (`{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","user_id":"test","cost_usd":1.59e-05}`).

### 5. Kiểm tra tự động bằng script chấm
```bash
cd 06-lab-complete
python check_production_ready.py --public-url "$BASE"
```
Kết quả đo thực tế (WSL2): `Result: 12/12 tiêu chí đạt · 44/44 checks passed`.

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
