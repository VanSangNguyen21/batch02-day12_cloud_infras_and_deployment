# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
Trong file `01-localhost-vs-production/develop/app.py`, ta phát hiện các anti-patterns sau:
1. **Hardcoded secrets**: `OPENAI_API_KEY` và `DATABASE_URL` bị hardcode trực tiếp trong mã nguồn. Nếu commit lên Git sẽ bị lộ thông tin nhạy cảm ngay lập tức.
2. **Thiếu Configuration Management**: Các cấu hình (`DEBUG`, `MAX_TOKENS`) được khai báo dạng biến tĩnh trong file thay vì đọc động từ environment variables.
3. **Sử dụng print thay vì Logging**: In thông tin bằng `print()` thay vì thư viện logging tiêu chuẩn. Ngoài ra, việc print cả API Key (`OPENAI_API_KEY`) ra logs rất không an toàn.
4. **Không có Health Check endpoint**: Thiếu các endpoint `/health` (Liveness) và `/ready` (Readiness), khiến orchestrator (như K8s, Docker Swarm, hay Railway) không thể tự động restart container khi bị crash.
5. **Cứng Port và Host**: Host đặt cứng là `localhost` và port `8000`. Khi deploy lên cloud, port cần được inject qua env var `PORT` và host phải bind vào `0.0.0.0` để bên ngoài truy cập được.
6. **Bật debug mode trong production**: Tham số `reload=True` được bật mặc định, làm tiêu tốn thêm tài nguyên CPU không cần thiết và tạo ra rủi ro bảo mật lớn.

### Exercise 1.3: Comparison table
| Feature | Basic (Develop) | Advanced (Production) | Tại sao quan trọng? |
|---------|---------|------------|----------------|
| **Config**  | Hardcoded trong code | Load từ Environment Variables | Giúp cấu hình linh hoạt mà không cần build lại code; tránh lộ secrets. |
| **Health Check** | Không có | Có `/health` & `/ready` | Giúp platform biết khi nào container sống/chết (để tự restart) hoặc sẵn sàng nhận traffic. |
| **Logging** | Dùng `print()`, thiếu cấu trúc | Dùng JSON structured logs | Dễ gom logs về hệ thống tập trung (Loki, Datadog) và parse/search tự động. |
| **Shutdown** | Tắt đột ngột (Hard termination) | Graceful shutdown (SIGTERM handler) | Cho phép các request đang xử lý được hoàn thành và đóng kết nối DB sạch sẽ trước khi tắt. |
| **Binding Host** | `localhost` | `0.0.0.0` | Để Docker container/Cloud router có thể chuyển tiếp traffic từ ngoài vào container. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. **Base image:** `python:3.11` (full Debian-based image chứa đầy đủ bộ compilers và development tools).
2. **Working directory:** `/app` (thư mục làm việc mặc định trong container).
3. **Tại sao COPY requirements.txt trước?** Để tối ưu hóa **Docker Layer Caching**. Các dependency ít thay đổi hơn code ứng dụng. Bằng cách copy `requirements.txt` và chạy `pip install` trước, Docker sẽ cache layer này. Nếu chỉ sửa code, Docker sẽ không phải chạy lại lệnh cài đặt dependencies rất mất thời gian.
4. **CMD vs ENTRYPOINT:**
   - `CMD` định nghĩa command và/hoặc arguments mặc định cho container. Có thể dễ dàng bị ghi đè khi chạy lệnh `docker run <image> <command_moi>`.
   - `ENTRYPOINT` định nghĩa executable chạy chính của container. Khó bị ghi đè hơn (phải dùng `--entrypoint`), và các tham số truyền thêm sau `docker run` sẽ được append tiếp sau `ENTRYPOINT`.

### Exercise 2.3: Image size comparison
- **Develop (Single-stage):** ~1.02 GB (Do dùng base `python:3.11` và giữ lại toàn bộ build tools, cache).
- **Production (Multi-stage):** ~145 MB (Do dùng base `python:3.11-slim`, chỉ copy những gì cần chạy và chạy dưới dạng non-root user).
- **Difference:** Giảm khoảng **85.7%** kích thước image.

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
- **URL:** https://batch02-day12-cloud-infras.up.railway.app
- **Screenshot:** Xem screenshots cấu hình trong thư mục `screenshots/`

---

## Part 4: API Security

### Exercise 4.1-4.3: Test results
- Khi gọi `/ask` không truyền header `X-API-Key`:
  ```json
  {
    "detail": "Invalid or missing API key. Include header: X-API-Key: <key>"
  }
  ```
  *(Mã lỗi HTTP: 401 Unauthorized)*

- Khi truyền đúng `X-API-Key` nhưng vượt quá Rate Limit (10 req/min):
  ```json
  {
    "detail": "Rate limit exceeded: 10 req/min. Please try again later."
  }
  ```
  *(Mã lỗi HTTP: 429 Too Many Requests, header `Retry-After: 60`)*

### Exercise 4.4: Cost guard implementation
- Chúng tôi đã viết một module bảo vệ chi phí (`cost_guard.py`) hoàn chỉnh:
  - Tính toán chi phí ước tính dựa trên số lượng token của câu hỏi ($0.15/1M input tokens) và câu trả lời ($0.60/1M output tokens).
  - Sử dụng Redis (với in-memory fallback nếu không có Redis) để lưu trữ lượng ngân sách đã sử dụng của từng `user_id` theo ngày và tháng.
  - Thiết lập ngân sách tối đa là **$5.0/ngày** (load từ settings) và **$10.0/tháng** per user.
  - Khi vượt ngân sách, trả về lỗi `402 Payment Required` để bảo vệ hệ thống tránh bị spam và phát sinh hóa đơn LLM lớn đột biến.

---

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes
- **Stateless Design:** Đã chuyển đổi hoàn toàn hệ thống sang stateless. Trạng thái lịch sử hội thoại (conversation history), thông tin rate limit và cost tracking đều được lưu giữ trong Redis (hoặc fallback bộ nhớ tạm nếu chạy local không có Redis). Điều này đảm bảo khi scale lên N instances đằng sau Load Balancer (Nginx/Railway Gateway), bất kỳ instance nào cũng có thể xử lý request tiếp theo của user mà không bị mất context hay lệch rate limit.
- **Health & Readiness Check:**
  - `/health` (liveness check) trả về 200 OK khi ứng dụng chạy, đồng thời kiểm tra nhanh xem Redis còn kết nối được không để báo trạng thái `degraded` nếu hỏng bộ lưu trữ.
  - `/ready` (readiness check) chỉ sẵn sàng khi app đã khởi chạy xong và kết nối Redis hoạt động tốt. Nếu mất kết nối Redis, sẽ lập tức trả về `503 Service Unavailable` để load balancer ngừng route traffic vào instance bị lỗi này.
- **Graceful Shutdown:** Lắng nghe tín hiệu `SIGTERM`. Khi nhận tín hiệu tắt máy, app sẽ chuyển trạng thái ready thành `False` (để load balancer ngừng đẩy traffic mới) và cho phép các request hiện tại hoàn thành trước khi uvicorn shutdown sạch sẽ.
