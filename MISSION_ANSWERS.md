# Day 14 — Mission Answers

## Part 1: Localhost vs Production (CP1)

### Exercise 1.1: Anti-patterns trong bản develop

Các dòng dưới đây tham chiếu `01-localhost-vs-production/develop/app.py`.

| # | Vị trí | Anti-pattern | Vì sao có vấn đề khi đưa lên production? |
|---|---|---|---|
| 1 | Dòng 17–18 | API key và URL database chứa thông tin đăng nhập được hardcode. | Nếu dùng secret thật, đẩy code lên Git sẽ làm lộ quyền truy cập; thay secret còn cần sửa code. Các giá trị trong ví dụ là dữ liệu minh họa. |
| 2 | Dòng 21–22 | `DEBUG` và `MAX_TOKENS` là hằng số trong source. | Không thể cấu hình riêng cho dev/staging/production bằng môi trường. Biến `DEBUG` cũng chưa được nối với tham số `reload`. |
| 3 | Dòng 33–38 | Dùng `print()` cho log, không có timestamp, mức độ hoặc cấu trúc thống nhất. | Khó lọc lỗi, gom log và phân tích tự động khi có nhiều instance. |
| 4 | Dòng 34 | In API key vào log. | Log có thể được chuyển sang hệ thống giám sát hoặc chia sẻ để debug, mở rộng phạm vi lộ secret. |
| 5 | Dòng 25–39 | Chỉ có `/` và `/ask`, không có `/health` hoặc `/ready`. | Thiếu endpoint chuyên dụng để nền tảng kiểm tra process còn sống và load balancer quyết định có nên gửi traffic tới instance. Đã kiểm chứng hai đường dẫn này trả 404. |
| 6 | Dòng 51 | Bind vào `localhost`. | Chỉ nhận kết nối loopback; trong container, traffic từ bên ngoài container không tới được app qua giao diện mạng của container. |
| 7 | Dòng 52 | Cổng 8000 cố định. | Không dùng được cổng do nền tảng cloud truyền qua biến `PORT` nếu không đổi cách khởi động. |
| 8 | Dòng 53 | `reload=True` được bật cố định. | Chế độ tự nạp lại code dành cho phát triển, tạo thêm tiến trình và có thể restart app ngoài ý muốn khi file thay đổi. |
| 9 | Không có lifecycle riêng cho app | Không có bước startup/shutdown để mở và đóng tài nguyên của ứng dụng. | Khi bổ sung database hoặc kết nối ngoài, cần quản lý việc khởi tạo, ngừng nhận việc mới và giải phóng tài nguyên. Uvicorn vẫn có cơ chế shutdown riêng; không thể kết luận bản develop luôn cắt ngang request chỉ vì app không tự đăng ký SIGTERM. |

### Exercise 1.2: Chạy và gọi API bản develop

Đã chạy kiểm chứng ngày **25/11/2026, 15:06 GMT+7**, trong Ubuntu WSL2:

- `os.name`: `posix`.
- Python: `3.14.4`; FastAPI: `0.115.0`; Uvicorn: `0.30.0`.
- Môi trường có sẵn `python-dotenv==1.2.4`; chưa cài lại theo requirements production (`1.0.1`). Module này không được app CP1 import.
- Mock LLM, không gọi dịch vụ LLM thật.
- Dùng cổng **18001/18002** để không chiếm cổng 8000 có thể đang được dùng. Source ví dụ không được sửa.

Từ gốc repo, kích hoạt môi trường và chạy bản develop:

```bash
source .venv-wsl/bin/activate
cd 01-localhost-vs-production/develop
python -m uvicorn app:app --host 127.0.0.1 --port 18001
```

Lệnh trên import cùng ứng dụng `app:app`, bỏ qua launcher hardcode cổng 8000 của `python app.py`. Đây là cách khởi động dùng trong lần kiểm chứng; không phải bằng chứng launcher đã đọc `PORT`.

Trong terminal khác:

```bash
curl -i -X POST 'http://127.0.0.1:18001/ask?question=Hello'
```

Mã HTTP và body quan sát được, trích từ [bằng chứng chạy CP1](reports/cp1_results.json):

```text
HTTP status: 200
Content-Type: application/json
```

```json
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Mock có thể chọn câu trả lời khác ở lần chạy sau. Kết quả này xác nhận endpoint hoạt động, chưa chứng minh app đã đủ điều kiện production.

| Request đã chạy | HTTP thực tế | Nhận xét |
|---|---:|---|
| `GET /` | 200 | Process đã phục vụ request. |
| `POST /ask?question=Hello` | 200 | Bản develop nhận `question` qua query. |
| `POST /ask`, JSON `{"question":"Hello"}` | 422 | Thiếu query `question`; JSON trong Exercise 1.2 của `CODE_LAB.md` không khớp bản develop. Làm theo lưu ý K5 trong `README.md`. |
| `GET /health` | 404 | Chưa có health endpoint. |
| `GET /ready` | 404 | Chưa có readiness endpoint. |

Trong PowerShell, dùng `curl.exe` thay cho `curl` để tránh alias `Invoke-WebRequest`.

### Exercise 1.3: So sánh develop với production

Các đường dẫn trong bảng tương đối với `01-localhost-vs-production/`.

| Feature | Develop | Production | Vì sao quan trọng? |
|---|---|---|---|
| Config | Hằng số trong `develop/app.py:17–22`. | `production/config.py:17–35` đọc env, tập trung trong `Settings`. | Thay cấu hình giữa các môi trường mà không phải sửa source hoặc tạo image khác. |
| Secrets | Giá trị mẫu nằm trong code, còn bị in ra log. | Đọc `OPENAI_API_KEY` và `AGENT_API_KEY` từ env; endpoint không in chúng. | Có thể cấp và thay secret ngoài source, giảm nguy cơ lộ qua Git hoặc log. |
| Port | Launcher cố định 8000 (`develop/app.py:52`). | Đọc `PORT` (`production/config.py:18`), dùng `settings.port` (`production/app.py:197`). | Nền tảng cloud có thể quyết định cổng. Đã chạy thực tế với `PORT=18002`. |
| Network binding | `localhost` (`develop/app.py:51`). | Mặc định `0.0.0.0`, có thể đổi bằng `HOST` (`production/config.py:17`). | Có thể nhận traffic từ ngoài container; lần kiểm chứng chỉ bind loopback để gọi local. |
| Debug/reload | `reload=True` cố định. | `DEBUG` từ env, mặc định false. | Chỉ bật reload khi phát triển; tránh quá trình theo dõi file khi phục vụ thật. |
| Health check | Không có; gọi thực tế trả 404. | `/health` trả 200, có status, uptime, version và environment (`production/app.py:135`). | Cho hệ thống vận hành một endpoint kiểm tra process. |
| Readiness | Không có; gọi thực tế trả 404. | `/ready` trả 200 sau startup; 503 nếu `is_ready` false (`production/app.py:152`). | Load balancer có thể ngừng chuyển traffic khi instance chưa sẵn sàng. Mẫu này chỉ dùng cờ lifecycle, chưa kiểm tra Redis/database. |
| Logging | `print()` và in cả key. | Dùng `logging` và có ý định định dạng JSON (`production/app.py:28–31`); còn hạn chế được ghi bên dưới. | Log có cấu trúc giúp tìm lỗi, tổng hợp và đối chiếu request; phải bảo đảm mỗi dòng thực sự parse được. |
| Shutdown | Chưa có cleanup riêng trong app; Uvicorn vẫn xử lý shutdown. | Có `lifespan`, chuyển readiness sang false và có bước cleanup (`production/app.py:40–67`). | Cho phép app kết thúc có kiểm soát và giải phóng tài nguyên; cần kiểm tra thêm request đang chạy khi làm bài production hoàn chỉnh. |
| Input `/ask` | Tham số query bắt buộc. | Đọc JSON, thiếu/nội dung question rỗng trả 422 (`production/app.py:102–108`). | Client cần tuân theo đúng hợp đồng request để tránh lỗi 422. |
| CORS | Không cấu hình middleware. | Có `CORSMiddleware`, origins từ env; mặc định là `*`. | Giới hạn origins của trình duyệt nếu cấu hình danh sách cụ thể; CORS không thay thế xác thực API. |

Chạy bản production từ terminal đã kích hoạt `.venv-wsl`, bắt đầu tại gốc repo:

```bash
cd 01-localhost-vs-production/production
HOST=127.0.0.1 PORT=18002 ENVIRONMENT=staging DEBUG=false python app.py
```

Ví dụ gọi từ terminal khác:

```bash
curl -i http://127.0.0.1:18002/health
curl -i http://127.0.0.1:18002/ready
curl -i -X POST http://127.0.0.1:18002/ask \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'
```

| Kiểm chứng production | Kết quả thực tế |
|---|---|
| `GET /` | 200, `environment` là `staging`. |
| `POST /ask`, JSON có question | 200, có `question`, `answer`, `model`. |
| `POST /ask`, JSON `{}` | 422, `question field is required`. |
| `GET /health` | 200, `status` là `ok`, `environment` là `staging`. |
| `GET /ready` | 200, `ready` là true. |
| Gửi SIGTERM sau các request | Production thoát với exit code 0; thấy Uvicorn ghi hoàn tất shutdown. |

**Phạm vi và điểm cần lưu ý từ lần chạy:**

- Đã gửi SIGTERM lúc không còn request đang chạy. Chưa kiểm chứng việc giữ request đang xử lý hoặc Docker stop dưới 10 giây; các yêu cầu đó thuộc bài production hoàn chỉnh ở CP5.
- Bản develop cũng ghi hoàn tất shutdown của Uvicorn, nhưng return code của subprocess trong lần chạy là `-15` (SIGTERM). Không coi bản develop luôn tắt đột ngột hoặc coi phép kiểm tra này chứng minh request đang chạy được giữ lại.
- Logging mẫu production chưa đạt log JSON đúng nghĩa: khi không đặt `OPENAI_API_KEY`, `config.validate()` gọi `logging.warning()` trước `logging.basicConfig()` của app. Kiểm tra thực tế cho thấy root logger giữ formatter mặc định và mức `WARNING`, nên log `INFO` của app không được bật. Kiểm tra riêng formatter khai báo trong source với message từ `json.dumps()` cũng thất bại khi parse JSON vì dấu ngoặc kép bên trong không được escape. Chi tiết có trong `production_logging_probe` của file bằng chứng.
- `python-dotenv` được liệt kê nhưng không có `load_dotenv()` trong app/config CP1. Các lần chạy trên truyền env trực tiếp, không dựa vào việc copy `.env` sẽ tự được đọc.
- CP1 so sánh ví dụ có sẵn, không sửa lại code mẫu để giải quyết các hạn chế trên.

### Giải thích khái niệm

1. **Vì sao hardcode secret nguy hiểm?** Secret có thể nằm lâu dài trong lịch sử Git, bản sao repo hoặc log. Xóa dòng hiện tại không thu hồi được secret đã lộ; cần thay/revoke key. Secret phải được cấp qua môi trường hoặc hệ thống quản lý secret.
2. **Vì sao cần health check?** Nền tảng cần biết app còn phản hồi để phát hiện instance lỗi. Liveness kiểm tra process; readiness kiểm tra có nên nhận traffic. Với agent phụ thuộc Redis ở CP5, Redis lỗi phải làm `/ready` trả 503, trong khi `/health` vẫn 200 nếu process còn sống.
3. **Graceful shutdown là gì?** Khi nhận yêu cầu tắt, ngừng nhận việc mới, cho request đang chạy hoàn tất trong thời hạn phù hợp rồi đóng tài nguyên và thoát. Chỉ log thông báo shutdown chưa chứng minh được toàn bộ hành vi này.
4. **Vì sao stateless quan trọng khi scale?** Các request liên tiếp có thể đến các instance khác nhau. State dùng chung cần ở Redis/database để không mất session hoặc hạn mức khi đổi instance/restart; app CP1 chưa triển khai phần state dùng chung này.
5. **Dev/prod parity là gì?** Giữ phiên bản runtime, dependencies, cách khởi động và backing services giữa môi trường phát triển và production tương đồng để giảm lỗi chỉ xuất hiện sau deploy. Cấu hình và secret vẫn được cấp riêng qua env cho từng môi trường.

## Part 2: Docker (CP2)

### Exercise 2.1: Đọc Dockerfile

Tham chiếu `02-docker/develop/Dockerfile` đang có trong repo:

1. **Base image:** `python:3.11`, bản Python đầy đủ, khai báo bằng `FROM python:3.11`. Bản production mới dùng `python:3.11-slim`. Trả lời theo Dockerfile thực tế, vì ví dụ đáp án trong `INSTRUCTOR_GUIDE.md` ghi slim cho câu hỏi này.
2. **Working directory:** `/app`. `WORKDIR /app` đặt thư mục hiện hành cho các lệnh `RUN`, đích tương đối của `COPY` và lệnh khởi động container.
3. **Vì sao copy requirements trước source?** Dependencies thường thay đổi ít hơn code. Nếu requirements và các bước trước đó không đổi, Docker có thể dùng lại layer `pip install` khi chỉ sửa source phía sau. Đổi requirements làm layer cài dependencies và các bước phụ thuộc phải chạy lại. `pip --no-cache-dir` tắt cache tải package của pip, không tắt Docker layer cache.
4. **CMD khác ENTRYPOINT thế nào?** `CMD` cung cấp lệnh/tham số mặc định và có thể được thay bằng phần command sau tên image trong `docker run`. `ENTRYPOINT` ở dạng exec chỉ định chương trình chính; command truyền thêm thường thay `CMD` và trở thành tham số cho entrypoint. Có thể thay entrypoint bằng `docker run --entrypoint`, nên nó không phải cấu hình bất biến. Dockerfile develop dùng `CMD ["python", "app.py"]`, không tự khai báo `ENTRYPOINT`.

### Exercise 2.2: Build và chạy container develop

Build từ **gốc repo**, vì các đường dẫn `COPY 02-docker/...` và `COPY utils/...` được tính từ build context:

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -d --name k5-day14-cp2-develop \
  -p 127.0.0.1:18010:8000 my-agent:develop
curl -i http://127.0.0.1:18010/health
curl -i -X POST 'http://127.0.0.1:18010/ask?question=What%20is%20Docker%3F'
```

Bản develop nhận `question` qua query, không nhận JSON. `EXPOSE 8000` là thông tin về cổng trong image, không tự mở cổng trên host; `-p` mới tạo ánh xạ. Lần kiểm chứng dùng host port 18010 để tránh cổng 8000 của các phần khác.

Đã build và chạy ngày **25/11/2026**, bằng Docker Desktop Linux engine `29.9.3`, Compose `v5.7.0`. Python bên trong container là `3.11.18`; các app chạy trong Linux, không dùng Python Windows để phục vụ API.

| Request đã chạy | HTTP thực tế | Kết quả |
|---|---:|---|
| `GET /health` trên cổng 18010 | 200 | `status: ok`, `container: true`. |
| `POST /ask?question=What%20is%20Docker%3F` | 200 | Có trường `answer` với câu trả lời mock về container. |
| `POST /ask`, JSON `{"question":"What is Docker?"}` | 422 | Thiếu query `question`, đúng với hợp đồng của bản develop. |

Body của request query trong lần chạy:

```json
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

Bằng chứng: [reports/cp2_results.json](reports/cp2_results.json), [log build develop](reports/cp2_build_develop.log).

### Exercise 2.3: Multi-stage và kích thước image

```bash
docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
docker images my-agent
docker image inspect my-agent:develop my-agent:advanced
```

- **Builder:** bắt đầu từ `python:3.11-slim`, cài `gcc`, `libpq-dev` và dependencies Python dưới `/root/.local` bằng `pip install --user`.
- **Runtime:** bắt đầu từ một base slim mới, copy packages sang `/home/appuser/.local`, copy source và mock utils, chạy bằng user `appuser`, thêm `HEALTHCHECK` và khởi động Uvicorn với 2 worker.
- **Vì sao nhỏ hơn?** Base slim loại bớt thành phần của bản Python đầy đủ; multi-stage giữ compiler và build dependencies ở builder, không mang cả filesystem builder vào final image. Dependencies cần lúc chạy vẫn được copy sang. Không kết luận runtime không có pip chỉ từ việc dùng multi-stage.
- **Bảo mật và vận hành:** user non-root giảm quyền của process; healthcheck cung cấp trạng thái `healthy/unhealthy`. Docker Engine không tự restart container chỉ vì `unhealthy`; restart policy xử lý lúc process thoát, hoặc cần bộ điều phối bổ sung.

Số đo sau khi **cả hai build đã hoàn tất**, lấy từ `docker images` và trường `Size` của `docker image inspect`:

| Image | `docker images` hiển thị | Kích thước chính xác (byte) | MB thập phân (1 MB = 1.000.000 byte) |
|---|---:|---:|---:|
| `my-agent:develop` | 1.67 GB | 1.667.783.905 | 1.667,78 |
| `my-agent:advanced` | 240 MB | 239.815.442 | 239,82 |

```text
Giảm (%) = (Size_develop - Size_advanced) / Size_develop * 100
         = (1667783905 - 239815442) / 1667783905 * 100
         = 85,62%
```

Đây là kích thước image Docker báo trên máy thực hành, không phải dung lượng tải qua mạng hoặc phần disk độc quyền sau khi trừ các layer dùng chung. Không dùng số ước lượng trong tài liệu.

Đã chạy độc lập `my-agent:advanced` trên cổng 18011: `/health`, `/ready` và `POST /ask` với JSON đều trả **200**. Kiểm tra `docker exec` xác nhận UID **999**, `os.name=posix`, FastAPI `0.115.0`, Uvicorn `0.30.0`; CMD của image có `--workers 2`.

Bằng chứng: [log build advanced](reports/cp2_build_advanced.log) và các mục `images`, `docker_images`, `advanced_runtime` trong [cp2_results.json](reports/cp2_results.json).

### Exercise 2.4: Compose stack và giao tiếp giữa service

Compose có **4 service**: `nginx`, `agent`, `redis`, `qdrant`, cùng network bridge `internal`.

```mermaid
flowchart LR
    Client[Client] -->|HTTP host port 18080| Nginx[Nginx listen 80]
    Nginx -->|agent:8000| Agent[Agent: 2 Uvicorn workers]
    Agent -.->|REDIS_URL: redis:6379| Redis[Redis]
    Agent -.->|QDRANT_URL: qdrant:6333| Qdrant[Qdrant]
    Redis --> RedisData[(redis_data)]
    Qdrant --> QdrantData[(qdrant_data)]
```

- Client gọi Nginx; upstream `agent_backend` chuyển request tới `agent:8000` qua DNS service trên network Compose.
- Agent không publish cổng trực tiếp ra host. Redis và Qdrant cũng chỉ nằm trong network này; agent nhận URL qua env.
- `depends_on` yêu cầu Redis và Qdrant healthy trước khi agent được khởi động. Nginx phụ thuộc thứ tự khởi động agent; cấu hình này không chờ health của agent.
- Hai đường nét đứt biểu diễn cấu hình kết nối: `main.py` CP2 chỉ gọi mock LLM, chưa thực sự đọc/ghi Redis hoặc truy vấn Qdrant. Kiểm tra stack khỏe không chứng minh tích hợp RAG/session đã hoạt động.
- Compose không khai báo replicas; chạy mặc định tạo **1 container agent**, trong đó CMD chạy **2 worker**. Hai worker không phải hai container. Nginx có thể cân bằng giữa các địa chỉ upstream nếu scale và cấu hình DNS phù hợp; CP2 không đo hiệu quả scale.
- Nginx cấu hình giới hạn 10 request/giây/IP, burst 20. Compose gốc publish cả 80 và 443, nhưng file Nginx mẫu chỉ có `listen 80`, chưa có TLS/certificate cho HTTPS.

Lần khởi động đầu bằng Compose gốc bị Windows từ chối bind cổng 80 (`bind: An attempt was made to access a socket in a way forbidden by its access permissions`). Đã thêm [docker-compose.cp2.yml](02-docker/production/docker-compose.cp2.yml) để thay danh sách publish bằng `127.0.0.1:18080:80`, giữ nguyên file Compose gốc. Cú pháp `!override` đã được `docker compose config` kiểm tra thành công với Compose v5.7.0 của máy.

Tạo `.env.local` trống nếu chưa có (file được Git bỏ qua), rồi dùng project name riêng để không lẫn với các bài khác cũng có thư mục `production`:

```bash
cd 02-docker/production
touch .env.local
docker compose -p k5-day14-docker -f docker-compose.yml -f docker-compose.cp2.yml config --quiet
docker compose -p k5-day14-docker -f docker-compose.yml -f docker-compose.cp2.yml \
  up -d --build --wait --wait-timeout 180
docker compose -p k5-day14-docker -f docker-compose.yml -f docker-compose.cp2.yml ps
curl -i http://127.0.0.1:18080/health
curl -i -X POST http://127.0.0.1:18080/ask \
  -H 'Content-Type: application/json' -d '{"question":"Explain microservices"}'
```

Trong lượt kiểm chứng, sau khi build advanced ở Exercise 2.3, đã tag cùng image thành `k5-day14-docker-agent:latest` và chạy Compose bằng `--no-build`. Không dùng image của phần khác. Các lệnh ở trên dùng `--build` để có thể tự chạy lại từ đầu; Compose sẽ tận dụng layer cache.

| Kiểm chứng | Kết quả thực tế |
|---|---|
| `docker compose config --quiet` với file override | Exit code 0; chỉ publish `127.0.0.1:18080 → nginx:80`. |
| Compose startup với override | Exit code 0, đủ 4 service chạy. |
| Agent | `running`, `healthy`, 1 container / 2 Uvicorn worker. |
| Redis | `running`, `healthy`; `redis-cli ping` trả `PONG`. |
| Qdrant | `running`, `healthy`, phiên bản `1.9.0`. |
| Nginx | `running`; không có Docker healthcheck riêng trong cấu hình này. |
| `GET /health` qua Nginx | 200, `status: ok`, version `2.0.0`. |
| `GET /ready` qua Nginx | 200, `ready: true`. |
| `POST /ask` JSON qua Nginx | 200, có `answer`; header `Server: nginx` xác nhận đường đi qua proxy. |
| Từ container agent kết nối `redis:6379`, gửi Redis PING | `+PONG`, xác nhận DNS service và kết nối TCP nội bộ. |
| Từ container agent gọi `http://qdrant:6333/` | JSON metadata Qdrant `1.9.0`, xác nhận kết nối HTTP nội bộ. |

Các kiểm tra kết nối nội bộ là probe riêng, không phải app đã sử dụng Redis/Qdrant trong xử lý `/ask`. Compose có cảnh báo trường `version` đã lỗi thời; cảnh báo này không làm kiểm tra cấu hình hoặc khởi động thất bại.

Đã lưu số đo, 9 kết quả HTTP, trạng thái service, lệnh debug và kết quả cleanup vào [reports/cp2_results.json](reports/cp2_results.json). Log tải service nằm ở [reports/cp2_pull.log](reports/cp2_pull.log).

### Debug và dọn tài nguyên

```bash
# Container develop, chạy từ bất kỳ thư mục nào:
docker logs k5-day14-cp2-develop
docker exec k5-day14-cp2-develop python --version
docker stop k5-day14-cp2-develop
docker rm k5-day14-cp2-develop

# Compose, chạy trong 02-docker/production/:
docker compose -p k5-day14-docker -f docker-compose.yml -f docker-compose.cp2.yml logs agent nginx
docker compose -p k5-day14-docker -f docker-compose.yml -f docker-compose.cp2.yml exec -T redis redis-cli ping
docker compose -p k5-day14-docker -f docker-compose.yml -f docker-compose.cp2.yml down -v
```

Chỉ dọn container/volume của lượt CP2 này. Giữ image đã build để dùng lại; không prune Docker hay tác động stack khác.

Đã dọn cả hai container độc lập develop/advanced và Compose project CP2 cùng network/volume sau khi lưu bằng chứng. Giữ hai image `my-agent:develop`, `my-agent:advanced` và tag Compose để có thể chạy lại.

**Thay đổi phục vụ CP2:** thêm `.venv-wsl/` vào `.dockerignore` để loại môi trường Python local khỏi build context; tạo `.env.local` trống được Git bỏ qua; thêm override cổng Nginx. Không sửa source app, Dockerfile mẫu, Compose gốc hay các phần lab tiếp theo.

## Part 4: API Security (CP3)

Kiểm chứng thực hiện ngày **25/11/2026, 15:30 GMT+7** trong Ubuntu WSL2 (`.venv-wsl`, Python `3.14.4`, `os.name=posix`), sau khi cài thêm `pyjwt==2.15.1` theo `04-api-gateway/production/requirements.txt`. Vì cổng `8000` trên máy đang có tiến trình Python khác lắng nghe, bản `develop` chạy trên cổng `18021` và bản `production` chạy trên cổng `18022` (tắt bản `develop` trước khi bật bản `production`). Không sửa source mẫu trong `04-api-gateway/`. Bằng chứng đầy đủ được lưu tại [reports/cp3_results.json](reports/cp3_results.json).

### Exercise 4.1: API Key Authentication (`04-api-gateway/develop/`)

Đọc `04-api-gateway/develop/app.py`:

- **Kiểm tra API key ở đâu?** Hàm `verify_api_key` (dòng `39–54`) dùng `APIKeyHeader(name="X-API-Key", auto_error=False)` và được inject vào endpoint `POST /ask` qua dependency `_key: str = Depends(verify_api_key)` (dòng `70`). `GET /` và `GET /health` để public để nền tảng kiểm tra trạng thái.
- **Thiếu hoặc sai key xảy ra gì?** Thiếu header `X-API-Key` (`not api_key`, dòng `44–48`) trả **`401 Unauthorized`**; có header nhưng sai giá trị (`api_key != API_KEY`, dòng `49–53`) trả **`403 Forbidden`** trong bản `develop` này. *(Lưu ý: ở bài hoàn thiện Part 6, hợp đồng yêu cầu cả thiếu và sai key đều trả `401`.)*
- **Cách rotate API key:** Cập nhật biến môi trường `AGENT_API_KEY` trong secret manager / cấu hình nền tảng rồi restart/rollout instance; để rotate không gián đoạn (zero-downtime), app nên hỗ trợ danh sách key hợp lệ (key mới + key cũ trong thời gian chuyển tiếp) trước khi thu hồi key cũ.

Khởi động bản `develop`:

```bash
cd 04-api-gateway/develop
AGENT_API_KEY=secret-key-123 PORT=8000 python app.py
# Trong lần kiểm chứng thực tế dùng cổng 18021 để tránh đụng cổng 8000 đang bận
```

Kết quả `curl -i` thực tế:

1. **Thiếu `X-API-Key` → `401 Unauthorized`:**

```http
HTTP/1.1 401 Unauthorized
date: Wed, 25 Nov 2026 08:30:26 GMT
server: uvicorn
content-length: 67
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

2. **Sai `X-API-Key` → `403 Forbidden`:**

```http
HTTP/1.1 403 Forbidden
date: Wed, 25 Nov 2026 08:30:26 GMT
server: uvicorn
content-length: 29
content-type: application/json

{"detail":"Invalid API key."}
```

3. **Đúng `X-API-Key: secret-key-123` → `200 OK`:**

```http
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:30:26 GMT
server: uvicorn
content-length: 122
content-type: application/json

{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

### Exercise 4.2: JWT Authentication (`04-api-gateway/production/`)

Đọc `04-api-gateway/production/auth.py` và `app.py`:

- **Luồng JWT:**
  1. Client gửi `POST /auth/token` với `username` và `password` (`student`/`demo123` role `user`, hoặc `teacher`/`teach456` role `admin`). `authenticate_user` (`auth.py:70–75`) kiểm tra thông tin đăng nhập (sai → `401`).
  2. `create_token` (`auth.py:35–43`) ký JWT bằng thuật toán `HS256` với `SECRET_KEY` từ biến môi trường `JWT_SECRET`, payload gồm `sub`, `role`, `iat`, `exp` (hết hạn sau `60` phút).
  3. Client gọi `POST /ask` kèm header `Authorization: Bearer <token>`. Dependency `verify_token` (`auth.py:46–67`) kiểm tra chữ ký và hạn dùng: thiếu token hoặc hết hạn → `401`, token không hợp lệ → `403`.
  4. Role-based access: `GET /admin/stats` kiểm tra `user["role"] != "admin"` → `403` với `student` và `200` với `teacher`.
- Bản `production` còn gắn middleware `security_headers` thêm các header `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`.

Khởi động bản `production` (sau khi đã tắt bản `develop`):

```bash
cd 04-api-gateway/production
PORT=8000 python app.py
# Trong lần kiểm chứng thực tế dùng cổng 18022
```

Kết quả `curl -i` thực tế (token đã được che):

1. **Gọi `POST /ask` không có token → `401 Unauthorized`:**

```http
HTTP/1.1 401 Unauthorized
date: Wed, 25 Nov 2026 08:30:32 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 76
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":"Authentication required. Include: Authorization: Bearer <token>"}
```

2. **Gọi `POST /ask` với token sai → `403 Forbidden`:**

```http
HTTP/1.1 403 Forbidden
date: Wed, 25 Nov 2026 08:30:32 GMT
server: uvicorn
content-length: 27
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":"Invalid token."}
```

3. **Lấy JWT tại `POST /auth/token` với `student` / `demo123` → `200 OK`:**

```bash
curl -i -X POST http://localhost:8000/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username": "student", "password": "demo123"}'
```

```http
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:30:32 GMT
server: uvicorn
content-length: 307
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"access_token":"eyJhbGciOiJIUzI1...<REDACTED>...3APXCE48","token_type":"bearer","expires_in_minutes":60,"hint":"Include in header: Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."}
```

4. **Gọi `POST /ask` với `Authorization: Bearer <TOKEN>` hợp lệ (lần 1) → `200 OK`:**

```http
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:30:32 GMT
server: uvicorn
content-length: 192
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"question":"Explain JWT","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

*(Ghi chú code mẫu: ở `04-api-gateway/production/app.py:160`, field `usage.budget_remaining_usd` gán nhầm `usage.total_cost_usd` nên in `1.9e-05`; số dư ngân sách thực tế xem ở `GET /me/usage` bên dưới.)*

### Exercise 4.3: Rate Limiting (`04-api-gateway/production/rate_limiter.py`)

Trả lời câu hỏi đọc code `rate_limiter.py`:

- **Thuật toán:** Sliding Window (cửa sổ trượt lưu timestamp từng request của mỗi `user_id` trong `deque` tại `self._windows`, loại bỏ các timestamp cũ hơn `now - window_seconds` rồi so sánh `len(window) >= max_requests`).
- **Giới hạn:** `rate_limiter_user` cho phép **10 requests / 60 giây** (tài khoản `student`); `rate_limiter_admin` cho phép **100 requests / 60 giây** (tài khoản `teacher`).
- **Cách phân biệt / bypass cho admin:** Trong `app.py:141`, nếu `role == "admin"` thì chọn `rate_limiter_admin` (hạn mức cao hơn gấp 10 lần), hoặc trong thực tế có thể bỏ qua bước `limiter.check(...)` cho role đặc quyền.
- **Hạn chế khi scale:** `self._windows` nằm trong RAM tiến trình Python, nên khi chạy nhiều worker/instance các instance không chia sẻ bộ đếm; phần Part 5/6 khắc phục bằng Redis.

Kết quả vòng lặp 15 request liên tiếp bằng token của `student`:
- **Lần 1 → 10:** đều trả **`200 OK`**, `usage.requests_remaining` giảm dần từ `9` về `0`.
- **Lần 11 → 15:** đều bị chặn với **`429 Too Many Requests`**, kèm các header `x-ratelimit-limit: 10`, `x-ratelimit-remaining: 0`, `x-ratelimit-reset`, `retry-after: 59`.

Output `curl -i` ở request thứ **10** (`200 OK`) và thứ **11** (`429 Too Many Requests`):

```http
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:30:34 GMT
server: uvicorn
content-length: 212
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"question":"Test 10","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","usage":{"requests_remaining":0,"budget_remaining_usd":0.000186}}
```

```http
HTTP/1.1 429 Too Many Requests
date: Wed, 25 Nov 2026 08:30:34 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795595494
retry-after: 59
content-length: 98
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4: Cost Guard (`04-api-gateway/production/cost_guard.py`)

- **Cách hoạt động của `cost_guard.py`:**
  - Định nghĩa đơn giá theo token (`PRICE_PER_1K_INPUT_TOKENS = 0.00015`, `PRICE_PER_1K_OUTPUT_TOKENS = 0.0006`) và `UsageRecord` tích luỹ `input_tokens`, `output_tokens`, `request_count` theo ngày (`YYYY-MM-DD`).
  - **Trước khi gọi LLM (`check_budget`):** kiểm tra ngân sách toàn cục (`$10.0/ngày` → vượt trả **`503`**), ngân sách từng user (`$1.0/ngày` → vượt trả **`402 Payment Required`**), và ghi log cảnh báo khi dùng đạt **`80%`** (`warn_at_pct = 0.8`).
  - **Sau khi gọi LLM (`record_usage`):** cộng dồn input/output tokens và chi phí USD cho user lẫn bộ đếm global.
  - Kiểm chứng `GET /me/usage` sau 10 request của `student` trả **`200 OK`**: `requests: 10`, `input_tokens: 40`, `output_tokens: 300`, `cost_usd: 0.000186`, `budget_usd: 1.0`, `budget_remaining_usd: 0.999814`.
  - Kiểm chứng RBAC trên `GET /admin/stats`: `student` bị **`403 Forbidden`** (`Admin only`), `teacher` trả **`200 OK`** (`global_cost_usd: 0.00018599999999999997`, `global_budget_usd: 10.0`).
- **Phân biệt Cost Guard với Rate Limiting và vì sao cần cả hai:**
  - **Rate limit (`429`)** giới hạn **tần suất gọi** (số request trong một cửa sổ thời gian, ví dụ 10 req/phút) để chống spam/DDoS và bảo vệ tài nguyên xử lý.
  - **Cost guard (`402` / `503`)** giới hạn **chi phí tiền tệ / lượng token tiêu thụ** theo ngày hoặc tháng để chống bùng nổ hóa đơn LLM API.
  - Một user không vượt rate limit (ví dụ gửi đều đặn 10 req/phút suốt cả ngày với prompt và câu trả lời rất dài) vẫn có thể tiêu tốn vượt xa ngân sách; ngược lại, một user còn nhiều ngân sách nhưng gửi ồ ạt hàng nghìn request cùng lúc vẫn làm quá tải hệ thống nếu thiếu rate limit.
- **Triển khai production (stateless):** `cost_guard.py` mẫu lưu `_records` trong RAM nên chỉ đúng trên 1 instance. Ở Part 6 (`06-lab-complete`), state chi phí được đưa vào Redis (ví dụ key theo kỳ như `budget:{user_id}:{YYYY-MM}`, cộng bằng `INCRBYFLOAT` và đặt `EXPIRE`) để mọi instance chia sẻ cùng một ngân sách.

## Part 5: Scaling & Reliability (CP4)

Kiểm chứng thực hiện ngày **25/11/2026, 15:34–15:40 GMT+7** trên `05-scaling-reliability/` bằng Python WSL2 (`3.14.4`, `os.name=posix`, cài thêm `psutil==6.0.0`) và Docker Compose `v5.7.0`. Không sửa source mẫu; bằng chứng đầy đủ lưu tại [reports/cp4_develop_results.json](reports/cp4_develop_results.json) và [reports/cp4_production_results.json](reports/cp4_production_results.json).

### Exercise 5.1: Phân biệt `/health` và `/ready`

| Endpoint | Mục đích (Probe) | Hành vi trong `05-scaling-reliability/develop/app.py` | Hành vi trong `05-scaling-reliability/production/app.py` | Khi nào nền tảng dùng? |
|---|---|---|---|---|
| `GET /health` | **Liveness probe** — kiểm tra process còn sống không | Trả **200** với `status` (`ok`/`degraded`), `uptime_seconds`, `version`, `checks.memory` | Kiểm tra Redis nếu bật; trả **200** với `status: "ok"` hoặc `"degraded"` và `redis_connected` | Nếu fail hoặc timeout → nền tảng restart container |
| `GET /ready` | **Readiness probe** — kiểm tra instance sẵn sàng nhận traffic chưa | Kiểm tra cờ `_is_ready`: trả **200** (`ready`, `in_flight_requests`), hoặc **503** khi đang startup/shutdown | Gọi `_redis.ping()`: trả **200** nếu OK, hoặc **503** (`Redis not available`) nếu mất Redis | Nếu trả 503 → load balancer ngừng chuyển request mới vào instance đó |

Kết quả gọi thực tế trên `05-scaling-reliability/develop/app.py` (cổng `18025` để tránh đụng cổng `8000`):

- `GET /health` → **200 OK**: `{"status":"ok","uptime_seconds":4.5,"version":"1.0.0","environment":"development",...,"checks":{"memory":{"status":"ok","used_percent":16.9}}}`
- `GET /ready` → **200 OK**: `{"ready":true,"in_flight_requests":1}`

### Exercise 5.2: Graceful Shutdown

Cơ chế trong `05-scaling-reliability/develop/app.py`:
- Middleware `track_requests` tăng/giảm `_in_flight_requests` cho mỗi request.
- `signal.signal(signal.SIGTERM, handle_sigterm)` ghi log khi nhận tín hiệu `15`, đồng thời Uvicorn (`timeout_graceful_shutdown=30`) kích hoạt phần shutdown của `lifespan`: đặt `_is_ready = False` để `/ready` trả 503, chờ `_in_flight_requests == 0` (tối đa 30 giây), rồi mới kết thúc.

Kiểm chứng thực tế khi gửi 2 request `POST /ask?question=hello` song song (mock delay `3.0s`) và gửi `SIGTERM` sau `0.5s`:
- **Request 1** (đang thực thi `ask()`) vẫn hoàn tất trọn vẹn với **`200 OK`** sau `3.297s` dù `SIGTERM` đã được gửi trước đó.
- Server thoát sạch với **`exit_code=0`** và ghi log: `Shutting down` → `POST /ask?question=hello 200 OK` → `Waiting for application shutdown.` → `🔄 Graceful shutdown initiated...` → `✅ Shutdown complete` → `Received signal 15 — uvicorn will handle graceful shutdown`.
- **Ghi chú kỹ thuật quan sát được:** `ask_agent` khai báo `async def` nhưng gọi `ask()` dùng `time.sleep(3.0)` đồng bộ (blocking event loop), nên khi 2 request đến cùng lúc, request 2 nằm chờ ở socket trước khi vào ASGI và nhận `curl: (56) Connection reset by peer` khi Uvicorn đóng kết nối chờ lúc shutdown. Nếu xử lý non-blocking hoặc sync endpoint chạy trên threadpool, cả hai request đang vào đều được đợi hoàn thành.

### Exercise 5.3: Vì sao phải đưa state vào Redis khi scale?

- Khi giữ state trong RAM (`conversation_history = {}`), mỗi container/worker có vùng nhớ riêng: request 1 vào `Instance 1` tạo session trong RAM của `Instance 1`, nhưng request 2 được Nginx điều phối sang `Instance 2` sẽ không thấy lịch sử hội thoại.
- Trong `05-scaling-reliability/production/app.py`, mọi instance đều kết nối tới `redis://redis:6379/0`: `save_session()` dùng `setex("session:{session_id}", 3600, ...)` và `append_to_history()` giữ tối đa 20 message gần nhất trong Redis, nên bất kỳ instance nào nhận request đều đọc/ghi đúng một lịch sử hội thoại thống nhất.

### Exercise 5.4 & 5.5: Chạy stack 3 instance với Nginx và `test_stateless.py`

Tạo file `.env.local` rỗng trong `05-scaling-reliability/production/` (đã nằm trong `.gitignore`), khởi động stack với project name riêng, chạy `test_stateless.py` và dọn stack:

```bash
cd 05-scaling-reliability/production
touch .env.local
docker compose -p k5-day14-scaling up -d --build --scale agent=3
python test_stateless.py
docker compose -p k5-day14-scaling down
```

Kiểm chứng thực tế qua Nginx trên cổng **`8080`**:
- `docker compose -p k5-day14-scaling ps`: đủ 5 container chạy khỏe mạnh (`k5-day14-scaling-agent-1..3` healthy, `redis` healthy, `nginx` publish `0.0.0.0:8080->80/tcp`).
- `GET http://127.0.0.1:8080/health` → **200 OK** (`status: ok`, `storage: redis`, `redis_connected: true`, `X-Served-By: 172.18.0.5:8000`).
- `GET http://127.0.0.1:8080/ready` → **200 OK** (`ready: true`, `X-Served-By: 172.18.0.3:8000`).
- Output thực tế của `python test_stateless.py`:

```text
Session ID: 31469528-cc73-4ff0-aa97-ecb05c95e9d4

Request 1: [instance-8003fe]
Request 2: [instance-6c4951]
Request 3: [instance-f18a1c]
Request 4: [instance-8003fe]
Request 5: [instance-6c4951]

Total requests: 5
Instances used: {'instance-f18a1c', 'instance-8003fe', 'instance-6c4951'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

- **Kiểm tra bổ sung (`multi_instance_probe` & `failover_probe`):**
  - 6 lượt `POST /chat` kế tiếp cho thấy header `X-Served-By` từ Nginx xoay vòng đều giữa 3 container (`172.18.0.4:8000`, `172.18.0.5:8000`, `172.18.0.3:8000`), tổng `12` message lưu trong Redis.
  - Khi thử `docker stop k5-day14-scaling-agent-1`, các request tiếp theo đi qua 2 instance còn lại (`instance-6c4951`, `instance-8003fe`) vẫn trả 200 trong `0.12–0.13s` và giữ nguyên `16` message trong `GET /chat/{session_id}/history`. Tuy nhiên một lượt rơi trúng IP container vừa dừng bị `TimeoutError` ở mốc timeout 12s của client do `nginx.conf` cấu hình `upstream agent_cluster { server agent:8000; }` với `proxy_connect_timeout` mặc định `60s` trước khi `proxy_next_upstream` chuyển sang upstream khác.
- Đã chạy `docker compose -p k5-day14-scaling down` để dừng và xoá toàn bộ container, network của CP4, trả lại cổng `8080`.

## Part 6: Final Project — Production-Ready Agent (CP5)

Đã hoàn thiện toàn bộ `TODO` trong [06-lab-complete/](06-lab-complete/):

- [06-lab-complete/app/config.py](06-lab-complete/app/config.py): `Settings` đọc `PORT`, `ENVIRONMENT`, `AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`, `MONTHLY_BUDGET_USD`, `LOG_LEVEL` từ biến môi trường (có `load_dotenv(override=False)` cho local).
- [06-lab-complete/app/redis_client.py](06-lab-complete/app/redis_client.py): tạo client Redis từ `REDIS_URL` (không ping lúc import để container vẫn khởi động được khi thiếu Redis) và hàm `redis_healthy()`.
- [06-lab-complete/app/auth.py](06-lab-complete/app/auth.py): `verify_api_key` dùng `APIKeyHeader(name="X-API-Key", auto_error=False)` + `secrets.compare_digest`, thiếu hoặc sai key đều trả **`401`**.
- [06-lab-complete/app/rate_limiter.py](06-lab-complete/app/rate_limiter.py): sliding window 60s bằng Redis Sorted Set (`ZREMRANGEBYSCORE`, `ZCARD`, `ZADD`, `EXPIRE`), vượt ngưỡng trả **`429`** kèm header `Retry-After`.
- [06-lab-complete/app/cost_guard.py](06-lab-complete/app/cost_guard.py): theo dõi chi phí ngày/tháng trong Redis (`INCRBYFLOAT`, `EXPIRE`), vượt `DAILY_BUDGET_USD` hoặc `MONTHLY_BUDGET_USD` trả **`402`**.
- [06-lab-complete/app/main.py](06-lab-complete/app/main.py): `JsonFormatter` xuất 1 JSON object/dòng log, `lifespan` + `track_and_log_requests` hỗ trợ graceful shutdown, `/health` luôn trả `200`, `/ready` trả `200`/`503` theo Redis, `/ask` nối `verify_api_key` → `check_rate_limit` → `check_budget` → `llm_ask` → `record_cost`, global exception handler tránh lộ stack trace.
- [06-lab-complete/Dockerfile](06-lab-complete/Dockerfile), [06-lab-complete/.dockerignore](06-lab-complete/.dockerignore), [06-lab-complete/docker-compose.yml](06-lab-complete/docker-compose.yml), [06-lab-complete/.env.example](06-lab-complete/.env.example), [06-lab-complete/railway.toml](06-lab-complete/railway.toml), [06-lab-complete/render.yaml](06-lab-complete/render.yaml): multi-stage `python:3.11-slim`, user non-root `appuser`, `HEALTHCHECK`, `CMD` dùng `exec uvicorn ... --port ${PORT:-8000} --workers 2`, build **11s** (khi có `--public-url`), image đo được **297 MB** (< 500 MB), `docker stop` thoát `exit code 0` trong **1.1s**.

### Kết quả `check_production_ready.py` đã chạy

Chạy `../.venv-wsl/bin/python check_production_ready.py --public-url https://k5-l3a-day14-tranquocdong-2a202603643-deployment-production.up.railway.app` trong Ubuntu WSL2 (`os.name == 'posix'`, kết nối Docker Engine `29.9.3` qua Docker Desktop WSL Integration) đạt **`12/12` tiêu chí · `44/44` checks passed** (tất cả sub-checks pass: build image `11s`, image `297 MB`, rate limit `429` sau `5` request khi `RATE_LIMIT_PER_MINUTE=5`, cost guard `402` ở request thứ `1`, `12` dòng JSON log hợp lệ, `SIGTERM` mid-request trả `200` + thoát `exit code 0`, `docker stop` thoát `exit code 0` trong `1.1s`, `GET <Public URL>/health → 200`):

```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 44/44 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

## Part 3: Cloud Deployment (CP6)

### Exercise 3.1 / 3.2: Deploy agent `06-lab-complete/`

- **Nền tảng chính:** **Railway** (deploy thư mục `06-lab-complete/` theo [06-lab-complete/railway.toml](06-lab-complete/railway.toml), gắn service **Redis** và cấu hình biến môi trường `ENVIRONMENT`, `REDIS_URL`, `AGENT_API_KEY`, `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD`, `MONTHLY_BUDGET_USD`, `LOG_LEVEL` trên Railway Dashboard).
- **Public URL:** `https://k5-l3a-day14-tranquocdong-2a202603643-deployment-production.up.railway.app`
- **Kiểm chứng 4 lệnh CP6 (và `check_production_ready.py --public-url`):**
  - `GET /health` → **`200`** (`{"status":"ok","environment":"production",...}`)
  - `GET /ready` → **`200`** (`{"ready":true,"redis":"connected",...}`)
  - `POST /ask` không có `X-API-Key` → **`401`** (`{"detail":"Invalid or missing API key. Include header: X-API-Key: <your-key>"}`)
  - `POST /ask` có `X-API-Key` hợp lệ → **`200`** (`{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.","user_id":"test","cost_usd":1.59e-05}`)
  - `python check_production_ready.py --public-url https://k5-l3a-day14-tranquocdong-2a202603643-deployment-production.up.railway.app` → **`PASS 12/12 · 44/44 checks passed`**.

### So sánh `railway.toml` với `render.yaml`

Tham chiếu [06-lab-complete/railway.toml](06-lab-complete/railway.toml) và [06-lab-complete/render.yaml](06-lab-complete/render.yaml):

| Tiêu chí | `railway.toml` (Railway) | `render.yaml` (Render Blueprint) | Vì sao khác nhau? |
|---|---|---|---|
| **Định dạng & phạm vi** | TOML (`[build]`, `[deploy]`), cấu hình cho **1 service** hiện tại | YAML (`services:`), là Infrastructure-as-Code cho **cả hệ thống nhiều service** | Railway quản lý từng service trong project riêng lẻ trên dashboard/CLI; Render Blueprint cho phép khai báo đồng bộ web service, database/Redis, env trong một file |
| **Cách build & runtime** | `[build] builder = "DOCKERFILE"`, `dockerfilePath = "Dockerfile"` | `type: web`, `runtime: docker`, `plan: free`, `autoDeploy: true` | Render yêu cầu khai báo rõ loại service (`web`), gói tài nguyên (`plan`) và runtime trong file Blueprint; Railway tách phần tài nguyên/service ra dashboard |
| **Health check & restart** | `healthcheckPath = "/health"`, `healthcheckTimeout = 30`, `restartPolicyType = "ON_FAILURE"`, `restartPolicyMaxRetries = 3` | `healthCheckPath: /health` | Cả hai đều probe `/health` để kiểm tra container sống; Railway hỗ trợ cấu hình thêm timeout và chính sách retry ngay trong file TOML |
| **Quản lý biến môi trường & secret** | Không khai báo env/secret trong `railway.toml`; đặt qua CLI (`railway variables set`) hoặc Dashboard | Khai báo `envVars:` trực tiếp trong YAML; secret dùng `generateValue: true` (tự sinh random) hoặc `sync: false` (nhập tay trên dashboard) | Render Blueprint muốn tái lập hạ tầng khi connect repo Git mà không lộ secret trên Git; Railway tách hoàn toàn cấu hình deploy khỏi biến môi trường |
| **Cung cấp Redis** | Tạo plugin/service Redis trên Railway Dashboard rồi tham chiếu `REDIS_URL` | Có thể thêm service `type: redis` trong cùng `render.yaml` hoặc trỏ `REDIS_URL` (`sync: false`) tới Redis bên ngoài | Do `render.yaml` hỗ trợ multi-service IaC nên có thể gom web + Redis cùng file, còn `railway.toml` chỉ mô tả build/deploy của 1 service |

### Exercise 3.3: Pipeline CI/CD trên GCP Cloud Run

Tham chiếu [03-cloud-deployment/production-cloud-run/cloudbuild.yaml](03-cloud-deployment/production-cloud-run/cloudbuild.yaml) và [service.yaml](03-cloud-deployment/production-cloud-run/service.yaml):

1. **Test (`test`):** Khi push lên nhánh `main`, Cloud Build chạy container `python:3.11-slim`, cài `requirements.txt` cùng `pytest` và chạy toàn bộ test (`pytest tests/`) để chặn build nếu code lỗi.
2. **Build (`build`):** Dùng `gcr.io/cloud-builders/docker` build image gắn 2 tag (`$COMMIT_SHA` và `latest`), tận dụng `--cache-from` từ image `latest` trước đó để tăng tốc.
3. **Push (`push`):** Đẩy cả hai tag image lên Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **Deploy (`deploy`):** Dùng `gcloud run deploy` triển khai image `$COMMIT_SHA` lên Cloud Run (`asia-southeast1`), cấu hình public ingress (`--allow-unauthenticated`), autoscale (`min-instances=1`, `max-instances=10`, trong `service.yaml` thêm `containerConcurrency: 80`, CPU/RAM limits, `livenessProbe` `/health` và `startupProbe` `/ready`) và gắn secret từ Google Secret Manager (`--set-secrets`) thay vì hardcode.

## AI log

### 2026-11-25 — CP1

- **Yêu cầu:** Thực hiện CP1: nhận diện anti-pattern, chạy develop và so sánh với production.
- **Hỗ trợ nhận được:** Codex đọc code, soạn phần trả lời, chạy các app bằng Python trong Ubuntu WSL2, gọi API trên cổng 18001/18002, kiểm tra SIGTERM lúc rảnh và cấu hình logging; lưu kết quả tại `reports/cp1_results.json`.
- **Thay đổi:** Tạo `MISSION_ANSWERS.md` và file bằng chứng. Không sửa code ví dụ, script chấm hoặc golden dataset.
- **Kiểm chứng do Codex chạy:** Các mã HTTP khớp bảng trên; production đọc env staging/cổng 18002 và thoát code 0 sau SIGTERM. Đây là kiểm chứng CP1, không phải kết quả PASS 12/12 của CP5.
- **Phần học viên tự sửa/tự kiểm tra:** Chưa ghi nhận học viên tự sửa hoặc chạy lại sau lượt hỗ trợ này; học viên cần đọc, giải thích và cập nhật mục này theo việc thực sự đã làm.

### 2026-11-25 — CP2

- **Yêu cầu:** Thực hiện CP2: đọc Dockerfile, build/run develop và advanced, so sánh kích thước, vẽ sơ đồ và test Compose qua Nginx.
- **Hỗ trợ nhận được:** Codex soạn câu trả lời, chạy Docker build từ gốc repo, đo image, gọi API trong container Linux, kiểm tra DNS/kết nối Redis/Qdrant và lưu bằng chứng. Khi host port 80 bị Windows chặn, thêm file override để dùng cổng loopback 18080.
- **Thay đổi:** Bổ sung Part 2 và AI log trong file này, tạo các file bằng chứng `reports/cp2_*`, thêm `.venv-wsl/` vào `.dockerignore`, tạo `02-docker/production/docker-compose.cp2.yml`. `.env.local` chỉ là file trống tại máy, không nộp lên Git.
- **Kiểm chứng do Codex chạy:** Hai image build thành công; develop 1.667,78 MB, advanced 239,82 MB, giảm 85,62%; 9 request HTTP đúng kỳ vọng; 4 service chạy và các kết nối nội bộ phản hồi. Đã dọn tài nguyên chạy của CP2, giữ image. Không coi đây là kiểm chứng CP5 hoặc benchmark scaling.
- **Phần học viên tự sửa/tự kiểm tra:** Chưa ghi nhận học viên tự sửa hoặc chạy lại CP2 sau lượt hỗ trợ này; cần đọc bảng, hiểu các lệnh và cập nhật việc tự kiểm tra theo thực tế.

### 2026-11-25 — CP3

- **Yêu cầu:** Thực hiện CP3 (Part 4: API Security, Exercise 4.1–4.4 trong `04-api-gateway/`).
- **Hỗ trợ nhận được:** Antigravity đọc code `develop/` và `production/`, cài `pyjwt==2.15.1` vào `.venv-wsl` từ `04-api-gateway/production/requirements.txt`, chạy kiểm thử `curl -i` qua WSL2 trên cổng `18021`/`18022` (do cổng `8000` đang bận), lưu bằng chứng tại `reports/cp3_results.json` và soạn mục Part 4 trong file này.
- **Thay đổi:** Bổ sung `Part 4` và mục AI log trong `MISSION_ANSWERS.md`, lưu `reports/cp3_results.json` (đã che JWT token). Không sửa code mẫu trong `04-api-gateway/`, script chấm hoặc golden dataset.
- **Kiểm chứng đã chạy:** `develop` trả 401 (thiếu key), 403 (sai key), 200 (đúng key); `production` trả 401 (thiếu token), 403 (token sai), 200 khi lấy JWT `student`/`demo123` tại `POST /auth/token`, 200 ở các request 1–10 và 429 ở các request 11–15, `GET /me/usage` ghi nhận 10 requests (`$0.000186`), `GET /admin/stats` trả 403 cho `student` và 200 cho `teacher`. Đã tắt cả hai server sau khi đo.
- **Phần học viên tự sửa/tự kiểm tra:** Học viên cần tự rà soát các output `curl -i`, phân biệt rate limit vs cost guard và cập nhật mục này theo phần tự kiểm tra của mình.

### 2026-11-25 — CP4

- **Yêu cầu:** Thực hiện CP4 (Part 5: Scaling & Reliability, Exercise 5.1–5.5 trong `05-scaling-reliability/`).
- **Hỗ trợ nhận được:** Antigravity đọc code `develop/` và `production/`, cài `psutil==6.0.0` vào `.venv-wsl`, kiểm thử `/health`, `/ready` và `SIGTERM` graceful shutdown trên cổng `18025` (WSL2 `os.name=posix`), tạo `.env.local`, chạy Compose `k5-day14-scaling` (`--scale agent=3`), chạy `test_stateless.py`, đo xoay vòng `X-Served-By` + dừng 1 container, dọn stack và lưu bằng chứng vào `reports/cp4_develop_results.json`, `reports/cp4_production_results.json`.
- **Thay đổi:** Bổ sung `Part 5` và mục AI log trong `MISSION_ANSWERS.md`, tạo `.env.local` rỗng tại máy (đã được `.gitignore` bỏ qua) và lưu 2 file bằng chứng `reports/cp4_*.json`. Không sửa source mẫu, script chấm hoặc golden dataset.
- **Kiểm chứng đã chạy:** `develop` trả `/health` 200, `/ready` 200, hoàn tất request đang chạy (`200 OK`) khi nhận `SIGTERM` và thoát code 0; Compose `k5-day14-scaling` chạy 3 instance + Redis + Nginx cổng `8080`, `test_stateless.py` qua đủ 3 instance (`instance-8003fe`, `instance-6c4951`, `instance-f18a1c`) với `Total messages: 10`, rồi `docker compose -p k5-day14-scaling down` dọn sạch.
- **Phần học viên tự sửa/tự kiểm tra:** Học viên cần đọc lại phần phân biệt `/health` với `/ready`, cơ chế Redis session và cập nhật mục này theo phần tự kiểm tra của mình.

### 2026-11-25 — CP5

- **Yêu cầu:** Hoàn thiện toàn bộ `TODO` trong `06-lab-complete/` (Part 6 / CP5) và kiểm tra bằng `check_production_ready.py`.
- **Hỗ trợ nhận được:** Antigravity triển khai `app/config.py`, `app/redis_client.py`, `app/auth.py`, `app/rate_limiter.py`, `app/cost_guard.py`, `app/main.py`, `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `.env.example`, `railway.toml`, `render.yaml`; cài `redis==5.1.0` vào `.venv-wsl` và môi trường Python Windows để chạy `check_production_ready.py`, đồng thời kiểm tra riêng `SIGTERM` với 2 worker trong WSL2 (`os.name=posix`).
- **Thay đổi:** Sửa các file khung `TODO` trong `06-lab-complete/` và cập nhật mục Part 6 + AI log trong `MISSION_ANSWERS.md`. Không sửa `check_production_ready.py` hoặc `utils/mock_llm.py`.
- **Kiểm chứng đã chạy:** Chạy trọn gói `../.venv-wsl/bin/python check_production_ready.py` trong Ubuntu WSL2 (sau khi bật Docker Desktop WSL Integration) đạt `PASS 12/12` tiêu chí · `43/43 checks passed` (build image `21s`, image `297 MB`, rate limit `429` sau `5` request, cost guard `402` ở request thứ `1`, `12` dòng JSON log, `SIGTERM` trả `200` + `exit code 0`, `docker stop` `exit code 0` trong `1.0s`).
- **Phần học viên tự sửa/tự kiểm tra:** Học viên đã bật Docker Desktop WSL Integration cho Ubuntu, kiểm tra lại toàn bộ `PASS 12/12 · 43/43 checks passed` và đối chiếu checklist trước khi chuẩn bị deploy CP6.

### 2026-11-25 — CP6 (phần cấu hình & đối chiếu) & CP7

- **Yêu cầu:** Tiếp tục thực hiện CP6 (so sánh `railway.toml` vs `render.yaml`, đọc Cloud Run CI/CD) và CP7 (Benchmark local `06-lab-complete/benchmark-observability/develop/`).
- **Hỗ trợ nhận được:** Antigravity soạn phần so sánh `railway.toml` vs `render.yaml` và tóm tắt pipeline Cloud Run vào Part 3 của `MISSION_ANSWERS.md`; thêm Histogram `agent_question_length_chars` vào `develop/app.py`; cài `prometheus-client==0.26.0`; chạy load test 4 mức concurrency (`1/10/50/100`), so sánh `MOCK_SLOW_RATE` (`0/0.03/0.1`), eval `v1` và `v2`, sửa `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` và `production/utils/mock_llm.py`, chạy lại eval đạt `23/23` (`0` regression), kiểm chứng CI quality gate (`exit code 1`), tạo `.github/workflows/eval.yml`, copy 10 file JSON sang `reports/` và điền Mục 1–3 của `BENCHMARK_REPORT.md`.
- **Thay đổi:** Cập nhật `MISSION_ANSWERS.md` (Part 3 + AI log), `06-lab-complete/benchmark-observability/develop/app.py`, `develop/utils/mock_llm.py`, `production/utils/mock_llm.py`, tạo `.github/workflows/eval.yml`, tạo `BENCHMARK_REPORT.md`, lưu 10 file JSON kết quả vào `develop/reports/` và `reports/`. Không sửa golden dataset hoặc script chấm/eval/load test.
- **Kiểm chứng đã chạy:**
  - `/metrics` hiển thị đủ Counter, Gauge, Histogram và `agent_question_length_chars` (`sum=40.0, count=1.0`).
  - `load_v2_c1..c100`: c1 `3.52 RPS / p95 1676.6ms` (FAIL), c10 `35.36 RPS / p95 236.1ms` (PASS), c50 `100.75 RPS / p95 419.6ms` (PASS), c100 `66.09 RPS / p95 3755.0ms` (FAIL).
  - `MOCK_SLOW_RATE`: `0` (`avg 193.1 / p95 230.6 / p99 272.1`), `0.03` (`avg 260.2 / p95 253.4 / p99 1711.7`), `0.1` (`avg 294.1 / p95 1673.9 / p99 1719.2`, FAIL).
  - Eval: `v1` `4.3% (1/23)` FAIL; `v2` `91.3% (21/23)` PASS; `v2_fixed` `100.0% (23/23)`, `0` regression, `Quality gate ... ✅ PASS`; chạy v1 với `--baseline eval_v2.json` trả exit code `1`.
- **Phần học viên tự sửa/tự kiểm tra:** Học viên cần tự đẩy repo lên GitHub, deploy `06-lab-complete/` lên Railway hoặc Render kèm Redis để lấy URL public, điền URL/ảnh cho CP6 (`DEPLOYMENT.md`, Part 3) và tiếp tục chạy stack CP8 (`production/`).

### 2026-11-25 — CP8 (Observability stack, Chaos, Tracing & Benchmark Scaling)

- **Yêu cầu:** Tiếp tục chạy CP8 trong `06-lab-complete/benchmark-observability/production/` (Exercise 7.4–7.7).
- **Hỗ trợ nhận được:** Antigravity chạy `promtool test rules` (`SUCCESS`), phát hiện và sửa lỗi thiếu `ENV PYTHONUSERBASE=/home/agent/.local` trong `06-lab-complete/benchmark-observability/production/Dockerfile` (khiến `uvicorn` crash `ModuleNotFoundError`), khởi động stack `k5-day14-observability`, chạy Locust headless `--no-deps` với 1 instance (`scale_1`) và 3 instance (`scale_3`) để giữ đúng số replica trong benchmark, trích xuất metrics Prometheus + 1 trace chậm + 1 trace lỗi trong Jaeger v3 API + log JSON theo `trace_id`, chạy thí nghiệm phá hệ thống A, B, D, E, copy CSV sang `benchmark-results/` và điền đầy đủ Mục 4–6 trong `BENCHMARK_REPORT.md`.
- **Thay đổi:** Thêm `ENV PYTHONUSERBASE=/home/agent/.local` vào `06-lab-complete/benchmark-observability/production/Dockerfile`, tạo `.env` tạm trong `production/` (được `.gitignore` bỏ qua, đã khôi phục cấu hình mặc định `v2`), lưu CSV trong `production/benchmark-results/` và `benchmark-results/`, lưu bằng chứng `reports/cp8_traces_and_metrics.json`, `reports/cp8_chaos_results.json` và hoàn thiện `BENCHMARK_REPORT.md`.
- **Kiểm chứng đã chạy:** `promtool test rules` đạt `SUCCESS`; `GET :8080/metrics` trả `404`; `scale_1` đạt `48.78 RPS / p95 2700ms` (5730 reqs), `scale_3` đạt `60.91 RPS / p95 1300ms` (7231 reqs); 3 alert (`AgentHighErrorRate` 96.9s, `AgentHighLatencyP95` 162.1s, `AgentInstanceDown` 41.1s) cùng `firing` đồng thời; thí nghiệm E (`v1`) không làm alert nào firing; xác định slow trace `b7a89db16d17c20d6fffd27b287dba8f` (`chat mock-llm-small` `1699.52 ms` / `98.6%`) và error trace `6cbad66fbe9f0ab08944b146f6637786` khớp dòng log JSON.
- **Phần học viên tự sửa/tự kiểm tra:** Học viên đã tự chụp và kiểm tra đủ 4 ảnh CP8 (`grafana-dashboard.png`, `jaeger-slow-trace.png`, `jaeger-error-trace.png`, `prometheus-alert-firing.png` thấy `FIRING (2)` + `PENDING (1)`), đã lưu vào `screenshots/` và dọn stack `k5-day14-observability` (`down -v`).

### 2026-11-25 — CP6 (Deploy Railway & kiểm chứng Public URL)

- **Yêu cầu:** Kiểm tra deploy `06-lab-complete/` trên Railway, chạy 4 lệnh test CP6 + `check_production_ready.py --public-url`, và cập nhật `DEPLOYMENT.md` cùng `MISSION_ANSWERS.md`.
- **Hỗ trợ nhận được:** Antigravity giải thích nguyên nhân `GET /` trả `404 {"detail":"Not Found"}` (`main.py` chỉ định nghĩa `/health`, `/ready`, `/ask`), gọi kiểm chứng 4 endpoint trên Public URL Railway (`https://k5-l3a-day14-tranquocdong-2a202603643-deployment-production.up.railway.app`), chạy lại `check_production_ready.py --public-url` trong WSL2, cập nhật `DEPLOYMENT.md` và `MISSION_ANSWERS.md` (không ghi giá trị `AGENT_API_KEY` vào repo).
- **Thay đổi:** Cập nhật `DEPLOYMENT.md` và `MISSION_ANSWERS.md` (mục Part 6, Part 3 và AI log). Không commit `.env` hay secret.
- **Kiểm chứng đã chạy:** `GET /health` → `200`, `GET /ready` → `200` (`redis: connected`), `POST /ask` không key → `401`, `POST /ask` có `X-API-Key` → `200` (`cost_usd: 1.59e-05`); `../.venv-wsl/bin/python check_production_ready.py --public-url https://k5-l3a-day14-tranquocdong-2a202603643-deployment-production.up.railway.app` đạt **`PASS 12/12` · `44/44 checks passed`**.
- **Phần học viên tự sửa/tự kiểm tra:** Học viên tự cấu hình project Railway (`Root Directory = 06-lab-complete`), thêm service Redis, đặt biến môi trường (`ENVIRONMENT`, `REDIS_URL`, `AGENT_API_KEY`, ...), bật Public Networking và gửi Public URL + key test. Còn bổ sung 3 ảnh deploy (`screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`) trước khi commit/push bản nộp cuối.
