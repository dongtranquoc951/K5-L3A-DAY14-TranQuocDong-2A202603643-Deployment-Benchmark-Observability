# Benchmark & Observability Report — Day 14

> Mọi con số trong báo cáo này đều được trích trực tiếp từ các file report JSON trong `reports/` (và sẽ bổ sung dữ liệu stack production từ CSV/screenshot ở CP8).

**Họ tên:** Tran Quoc Dong (`2A202603643`, lớp `K5-L3A`)  
**Ngày chạy:** 2026-11-25  
**Môi trường:** Windows 11, Python 3.12.10 (CP7 Bước 1 local trong `06-lab-complete/benchmark-observability/develop/`)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | `< 500 ms` | Với mock LLM có base latency 120ms + jitter 60ms + retrieval 20ms (~190–240ms bình thường), ngưỡng 500ms đảm bảo 95% request trả lời trong nửa giây và bắt được tình trạng nghẽn concurrency hoặc tail latency tăng trên 5% |
| Error rate `/ask` | `< 2.0 %` | Mock LLM có tỷ lệ lỗi upstream ngẫu nhiên mặc định `MOCK_ERROR_RATE=0.01` (1%); cho error budget 2% để tránh alert nhiễu vì dao động mẫu 300 request nhưng vẫn chặn suy giảm nặng |
| Accuracy trên golden dataset | `>= 85 %` (mục tiêu sau sửa KB: `100 %`, 0 regression) | Golden dataset 23 câu kiểm tra kiến thức cốt lõi của agent RAG (v2); ngưỡng 85% trong CI giúp phát hiện lỗi retrieval/prompt và chặn regression so với baseline |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.0 Quan sát `/metrics` (Exercise 7.1)

Đã chạy agent **v1** trên cổng `8001` và **v2** trên cổng `8002`, kiểm tra `GET http://127.0.0.1:8002/metrics`:

- **Counter** (chỉ tăng, dùng với `rate()`): `http_requests_total{method="POST",route="/ask",status="200"} 1.0`, `llm_requests_total{model="mock-llm-small",status="ok"} 1.0`, `llm_tokens_total{model="mock-llm-small",type="input"} 91.0`, `llm_cost_usd_total{model="mock-llm-small"} 4.665e-05`.
- **Gauge** (lên xuống theo trạng thái): `agent_in_flight_requests 0.0`, `agent_info{model="mock-llm-small",version="v2"} 1.0`.
- **Histogram** (chia bucket để tính quantile): `http_request_duration_seconds_bucket{...}`, `llm_request_duration_seconds_bucket{...}`, và metric đã thêm trong `develop/app.py`: `agent_question_length_chars` (`buckets=(20, 50, 100, 200, 500, 1000, 2000)`), ghi nhận `agent_question_length_chars_count 1.0`, `agent_question_length_chars_sum 40.0` sau câu hỏi mẫu dài 40 ký tự.
- **Vì sao label `route` dùng `route.path` thay vì `request.url.path`?** Nếu dùng URL thô khi bot quét hàng nghìn đường dẫn lạ (`/wp-admin`, `/.env`, `/a1b2c3`...), mỗi URL tạo ra một time series mới (high cardinality) làm Prometheus phình RAM và chậm truy vấn. Gom URL không khớp về `"unmatched"` giúp số lượng series bị chặn cố định.

### 2.1 Concurrency vs latency (agent v2, 300 requests mỗi mức)

Nguồn: `reports/load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json`.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO (`p95 <= 500ms`, `err <= 2%`) |
|---|---|---|---|---|---|---|
| 1 | 3.52 | 202.0 | 1676.6 | 1723.4 | 0.67% | FAIL (`p95 > 500ms`) |
| 10 | 35.36 | 198.1 | 236.1 | 1727.0 | 1.67% | PASS |
| 50 | 100.75 | 210.4 | 419.6 | 1732.9 | 1.00% | PASS |
| 100 | 66.09 | 713.3 | 3755.0 | 4102.1 | 0.67% | FAIL (`p95 > 500ms`) |

**Nhận xét:** RPS **không** tăng tuyến tính theo concurrency:
- Từ concurrency `1 → 10`, RPS tăng gần đúng 10 lần (`3.52 → 35.36 req/s`) vì mock LLM chạy bất đồng bộ (`asyncio.sleep`) nên thời gian chờ được chồng lấp hiệu quả.
- Từ `10 → 50`, concurrency tăng 5 lần nhưng RPS chỉ tăng ~2.85 lần (`35.36 → 100.75 req/s`) và `p95` bắt đầu nhích từ `236.1ms` lên `419.6ms`.
- Tại `concurrency = 100`, 1 process uvicorn duy nhất bị quá tải hàng đợi event loop / socket nên **RPS tụt xuống `66.09 req/s`** trong khi `p50` nhảy lên `713.3ms` và `p95` vọt lên `3755.0ms` (vi phạm SLO).
- Ở `concurrency = 1`, `p95 = 1676.6ms` vượt SLO do tỷ lệ slow ngẫu nhiên `MOCK_SLOW_RATE=0.03` tình cờ rơi nhiều hơn 5% vào vùng đuôi của tập 298 mẫu hợp lệ trong lượt chạy tuần tự đó.

### 2.2 Tail latency (`MOCK_SLOW_RATE`, 300 requests, concurrency=20)

Nguồn: `reports/load_v2_slow_0.json`, `load_v2_slow_0.03.json`, `load_v2_slow_0.1.json`.

| `MOCK_SLOW_RATE` | RPS | avg (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 0 | 100.70 | 193.1 | 230.6 | 272.1 | 1.00% | PASS |
| 0.03 (mặc định) | 61.00 | 260.2 | 253.4 | 1711.7 | 1.33% | PASS |
| 0.1 | 55.07 | 294.1 | 1673.9 | 1719.2 | 0.33% | FAIL |

**Nhận xét:**
- **`p99` và `p95` nhạy nhất** với các request chậm bất thường: khi `MOCK_SLOW_RATE` tăng từ `0` lên `0.03`, `avg` chỉ tăng `+67.1 ms` (`193.1 → 260.2 ms`) nhưng **`p99` nhảy vọt `+1439.6 ms`** (`272.1 → 1711.7 ms`). Khi tăng lên `0.1` (> 5% request bị chậm), cả **`p95` cũng vọt lên `1673.9 ms`** (vi phạm SLO `500 ms`), trong khi `avg` mới chỉ là `294.1 ms`.
- Vì vậy **SLO không nên đặt theo average**: giá trị trung bình bị 90–97% request nhanh "kéo xuống" và che giấu trải nghiệm rất tệ của nhóm 1–10% người dùng ở phần đuôi (tail latency).

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Nguồn: `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`.

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.7 | 109.3 | 113.7 |
| Tổng cost (USD) | $0.000413 | $0.000764 | $0.000790 |
| Cost / câu đúng (USD) | $0.00041295 | $0.00003639 | $0.00003436 |
| Latency p50 / p95 (ms) | 172.4 / 199.2 | 202.8 / 229.5 | 215.4 / 220.4 |
| Quality gate | FAIL | PASS (baseline v1, min 80%) | PASS (baseline v2, min 100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách sửa:**

| ID | Keyword bị thiếu | Đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry `(["jwt", "api key"], ...)` mô tả API key cố định vs JWT có chữ ký số và thời điểm hết hạn vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` (và đồng bộ sang `production/utils/mock_llm.py`) |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry `(["hpa", "kubernetes", "autoscal"], ...)` mô tả Kubernetes HPA scale theo CPU, memory và custom metrics vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` (và `production/utils/mock_llm.py`) |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**
- **v2** thêm bước retrieval nên `avg_tokens` tăng ~1.9× (`57.7 → 109.3` và `113.7` sau khi sửa KB) và tổng chi phí tăng gần gấp đôi (`$0.000413 → $0.000790`), đồng thời `p50` latency tăng nhẹ ~30–40ms (`172.4ms → 202.8–215.4ms`).
- Tuy nhiên accuracy nhảy từ **4.3%** (1/23) lên **91.3%** rồi **100.0%** (23/23), khiến chỉ số **cost / câu đúng giảm ~12 lần** (`$0.00041295 → $0.00003436`). Đánh đổi thêm ~30–40ms và < \$0.0004 cho 23 câu để đạt độ chính xác 100% là hoàn toàn xứng đáng; `cost / câu đúng` phản ánh hiệu quả kinh tế thực chất tốt hơn `cost / câu`.

**CI Quality Gate (Exercise 7.3):**
- Đã thêm workflow [.github/workflows/eval.yml](.github/workflows/eval.yml) chạy `eval/run_eval.py --url http://localhost:8000 --min-accuracy 0.85 --baseline reports/eval_v2.json` trên sự kiện `pull_request`.
- Kiểm chứng thực tế: khi chạy `eval/run_eval.py --url http://127.0.0.1:8001 --min-accuracy 0.85 --baseline reports/eval_v2.json` trên agent v1, script phát hiện `20` câu bị regression, accuracy `4.3% < 85%`, in `Quality gate ... ❌ FAIL` và trả **exit code `1`** — GitHub Actions dựa vào exit code khác 0 này để đánh dấu check fail và chặn merge PR.

---

## 4. Observability stack (production)

### 4.1 Screenshot & Quan sát Exercise 7.4

> Unit test alert rules (`promtool test rules /p/alert_rules_test.yml`) đã chạy và đạt **`SUCCESS`**.  
> Kết quả truy vấn từ Prometheus (`[5m]` trên lượt chạy `scale_3` với 3 instance) và kiểm tra endpoint qua Nginx:
> - **p95 vs avg (`/ask`):** `p95 = 724.4 ms` (`0.724 s`) so với `avg = 288.4 ms` (`0.288 s`), error rate `0.72%`. Khoảng cách ~2.5× giữa avg và p95 phản ánh phần tail latency (~1.7s) do 3% request chậm từ LLM.
> - **Requests/s theo instance:** `172.18.0.7:8000` đạt **`7.56 req/s`**, `172.18.0.8:8000` đạt **`7.33 req/s`**, `172.18.0.9:8000` đạt **`7.39 req/s`** — Nginx chia đều tải theo round-robin cho cả 3 instance.
> - **Input vs Output tokens/s:** `input = 1712.1 tokens/s` lớn gần gấp đôi `output = 894.0 tokens/s` vì bản v2 (RAG) chèn thêm `SYSTEM_PROMPT` và tài liệu retrieve vào prompt gửi lên LLM.
> - **`GET http://localhost:8080/metrics`:** Trả về **`404 Not Found`** vì `nginx.conf` chặn tường minh (`location = /metrics { return 404; }`) để tránh lộ thông tin hệ thống ra ngoài; chỉ Prometheus ở mạng nội bộ `obs_net` mới scrape trực tiếp `agent:8000/metrics`.

Checklist 4 ảnh trong `screenshots/` (đã chụp trước khi dọn stack `down -v`):
- [x] `screenshots/grafana-dashboard.png` — Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [x] `screenshots/jaeger-slow-trace.png` — Trace chậm `b7a89db16d17c20d6fffd27b287dba8f` trong Jaeger
- [x] `screenshots/jaeger-error-trace.png` — Trace lỗi `6cbad66fbe9f0ab08944b146f6637786` trong Jaeger (503 trên `POST /ask`, `agent.run`, `chat mock-llm-small`)
- [x] `screenshots/prometheus-alert-firing.png` — Trang Alerts của Prometheus thấy `FIRING (2)` (`AgentHighErrorRate` + `AgentInstanceDown`) và `PENDING (1)` (`AgentHighLatencyP95`)

### 4.2 Thí nghiệm "phá hệ thống"

Nguồn: `reports/cp8_chaos_results.json` (chạy trên stack `k5-day14-observability` với 2 agent instance và Locust 30 users).

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (`severity: critical`) | `96.9s` từ lúc `up -d` (pending ở `36.7s`, vượt `5%` trong `1m`; error rate đo được `18.38%`) | Golden Signals → **Error rate** & **LLM calls ok/error** |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (`severity: warning`) | `162.1s` từ lúc `up -d` (pending ở `41.8s`, vượt `1s` trong `2m`; p95 đo được `1.901s`) | Golden Signals → **p95** & **Latency & Traffic (p50/p95/p99/avg)** |
| C | `LLM_MODEL=mock-llm-large` | *(Chưa chạy riêng; theo `alert_rules.yml`, `LLMCostBurnRateHigh` firing khi chi phí ước tính > `$2/giờ` trong `2m`)* | — | LLM → **Cost USD/giờ** & **LLM p95** |
| D | `docker pause` 1 instance (`k5-day14-observability-agent-1`, đồng thời giữ A & B) | `AgentInstanceDown` (`severity: critical`) — lúc này **3 alert cùng firing** | `41.1s` sau `docker pause` (pending ở `11.0s`, `up == 0` trong `30s`) | Golden Signals → **Instances** & **Requests/s theo instance** |
| E | `AGENT_VERSION=v1` (khôi phục error `0.01`, slow `0.03`) | **Không có alert nào firing** (`{}`) sau `95s` tải liên tục | — | **Retrieval hit ratio** & bảng **Version (`agent_info` chuyển `v1`)** |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**
- Các metric hạ tầng (HTTP 2xx, latency, CPU, `up`) vẫn hoàn toàn xanh khi agent rơi về v1 trả lời sai/chung chung. Để phát hiện sớm trong production cần: (1) chạy **eval định kỳ** trên golden dataset / shadow traffic và gắn **CI quality gate** trước khi deploy; (2) theo dõi **retrieval hit ratio** (`agent_retrieval_hits_total`) và cảnh báo khi tỉ lệ miss tăng vọt hoặc metric mất chuỗi; (3) thu thập **phản hồi người dùng** hoặc chấm mẫu online bằng LLM-as-judge.

**Ghi chú Thí nghiệm D (`docker pause`):**
- Khi thử gọi trực tiếp `POST /ask` qua Nginx trong lúc `agent-1` bị pause, nhận các mã HTTP `[504, 200, 503, 200, 200]`. Lỗi **504 Gateway Timeout** xảy ra tại Nginx (chờ quá `proxy_read_timeout 10s` trên container bị đóng băng) nên không được ghi nhận vào `http_requests_total` của agent; do đó cần giám sát thêm access log / metric ở tầng load balancer hoặc synthetic check từ bên ngoài.

### 4.3 Debug bằng trace

Nguồn: `reports/cp8_traces_and_metrics.json`.

**1. Trace chậm nhất (`trace_id`: `b7a89db16d17c20d6fffd27b287dba8f`):**
- `trace_id`: `b7a89db16d17c20d6fffd27b287dba8f`
- Tổng thời gian (`POST /ask`): **`1723.37 ms`** (`agent.run`: `1717.29 ms` / `99.6%`; `agent.retrieve_context`: `17.47 ms` / `1.0%`)
- Span chiếm nhiều thời gian nhất: **`chat mock-llm-small`** (**`1699.52 ms`**, chiếm **`98.6%`** tổng thời gian request — nguyên nhân nằm ở cuộc gọi LLM chậm, không phải code retrieval hay FastAPI)
- Dòng log JSON tương ứng (lấy từ `docker compose -p k5-day14-observability logs agent`):

```json
{"ts": "2026-11-25T09:47:56.458979+00:00", "level": "INFO", "service": "observable-agent", "instance": "1cff567e73a8", "event": "llm_call", "trace_id": "b7a89db16d17c20d6fffd27b287dba8f", "span_id": "cfc621382f15506c", "request_id": "88d56667b841", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 95, "output_tokens": 55, "cost_usd": 4.7e-05, "llm_ms": 1697.9}
```

**2. Trace lỗi (`trace_id`: `6cbad66fbe9f0ab08944b146f6637786`):**
- `trace_id`: `6cbad66fbe9f0ab08944b146f6637786`
- Tổng thời gian (`POST /ask`, HTTP `503`): **`873.63 ms`** (`agent.run`: `860.43 ms`, `agent.retrieve_context`: `18.41 ms`, `chat mock-llm-small`: `837.34 ms` kèm event `exception`: `utils.mock_llm.LLMError: Upstream LLM error: 503 Service Unavailable (mock)`)
- Dòng log JSON tương ứng:

```json
{"ts": "2026-11-25T09:48:07.852529+00:00", "level": "INFO", "service": "observable-agent", "instance": "81180ba075b4", "event": "llm_error", "trace_id": "6cbad66fbe9f0ab08944b146f6637786", "span_id": "13cafac4bf9126a1", "request_id": "162f233449fd", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Nguồn: `benchmark-results/scale_1_stats.csv` và `benchmark-results/scale_3_stats.csv` (dòng `Aggregated`, đồng thời ghi chú riêng `POST /ask` trong ngoặc).

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | `48.78` (`POST /ask`: `44.36`) | `390` (`POST /ask`: `430`) | `2700` (`POST /ask`: `2800`) | `4100` (`POST /ask`: `4100`) | `48 / 5730` (`0.84%`) |
| 3 | `60.91` (`POST /ask`: `55.33`) | `210` (`POST /ask`: `210`) | `1300` (`POST /ask`: `1500`) | `2700` (`POST /ask`: `2700`) | `49 / 7231` (`0.68%`) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?
- **Có cải thiện rõ ở phần xếp hàng (queuing):** Khi tăng từ 1 lên 3 instance, tổng thông lượng tăng từ `48.78 → 60.91 req/s` (+24.9%), **`p50` giảm gần một nửa** (`390ms → 210ms`) và **`p95` giảm hơn một nửa** (`2700ms → 1300ms`; riêng `GET /health` giảm từ `77ms` xuống `10ms` ở `p50`). Lý do là với 100 user đồng thời, 1 container giới hạn `0.5 CPU / 256MB` bị dồn hàng đợi xử lý nên ngay cả `/health` cũng chậm; scale ra 3 container giải tỏa hàng đợi này và Nginx chia đều tải sang cả 3 instance.
- **Tuy nhiên `p95` vẫn dừng ở `1300–1500ms` và `p99` ở `2700ms`** chứ không giảm xuống ~200ms, và RPS chỉ tăng +25% (một phần vì mỗi user Locust tự nghỉ `between(0.5, 2)` giây). **Nút thắt còn lại nằm ở cuộc gọi upstream LLM (`chat mock-llm-small`)**: 3% request chậm vẫn tốn ~1.7 giây ở phía LLM (như trace `b7a89db16d17c20d6fffd27b287dba8f` cho thấy `98.6%` thời gian nằm trong span LLM), nên tăng số container agent không làm bản thân LLM trả lời nhanh hơn. Muốn giảm tiếp tail latency cần timeout/hedged request/streaming, cache câu hỏi phổ biến hoặc tối ưu/đổi model LLM.

---

## 6. Kết luận

- 3 điều học được về benchmark & observability:
  1. **Average che giấu tail latency:** SLO và alert độ trễ phải đặt theo `p95`/`p99`, không dựa vào giá trị trung bình.
  2. **Observability hạ tầng không thay thế Eval chất lượng:** Các metric HTTP/latency/cost có thể hoàn toàn xanh khi model hoặc retrieval suy giảm (thí nghiệm E), nên cần kết hợp golden dataset eval + CI quality gate với chỉ số `cost / câu đúng`.
  3. **3 trụ cột Metrics + Traces + Logs liên kết giúp tìm đúng nút thắt:** Prometheus/Grafana phát hiện `p95` hoặc error rate tăng, Jaeger chỉ ra chính xác span gây chậm/lỗi (`chat mock-llm-small` chiếm `98.6%`), và `trace_id` giúp grep đúng dòng log JSON tương ứng; đồng thời cần giám sát cả tầng proxy/LB vì lỗi như Nginx `504` không hiện trong metric nội bộ của agent.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - Thêm metric & alert ở tầng **Nginx/Load Balancer** (`502/504`, upstream timeout), alert **Redis down / connection error**, cảnh báo **tỉ lệ retrieval miss tăng đột biến** (`agent_retrieval_hits_total{result="miss"}`), cảnh báo **budget burn-rate theo tenant/API key**, và **synthetic probe / online eval score** để phát hiện suy giảm chất lượng trả lời.
