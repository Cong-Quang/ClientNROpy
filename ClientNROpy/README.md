# ClientNROpy - Xmap (Auto Map Navigation)

> **Xmap** là cơ chế tự động tìm đường ngắn nhất (Dijkstra) và điều khiển nhân vật chuyển map liên hành tinh không cần đồ hoạ, mô phỏng chuẩn xác hệ thống mod Xmap của Dragonboy C#.

---

## 📍 Vị Trí Mã Nguồn (Nó Ở Đâu?)

Toàn bộ mã nguồn của tính năng Xmap nằm tại thư mục: [`ClientNROpy/xmap/`](file:///c:/data/nro/ClientNROpy/xmap)

- [`xmap_controller.py`](file:///c:/data/nro/ClientNROpy/xmap/xmap_controller.py): Vòng đời điều khiển máy trạng thái di chuyển đa luồng (Background Thread).
- [`xmap_data.py`](file:///c:/data/nro/ClientNROpy/xmap/xmap_data.py): Dữ liệu liên kết đồ thị (chuỗi AutoWaypoint, tàu vũ trụ, menu NPC, nhảy toạ độ).
- [`xmap_algorithm.py`](file:///c:/data/nro/ClientNROpy/xmap/xmap_algorithm.py): Thuật toán Dijkstra tìm kiếm lộ trình tối ưu.
- [`xmap_executor.py`](file:///c:/data/nro/ClientNROpy/xmap/xmap_executor.py): Thực thi các bước di chuyển nhân vật và gửi gói tin qua map.
- [`map_data.py`](file:///c:/data/nro/ClientNROpy/xmap/map_data.py): Danh bạ 160 map tiếng Việt và bộ phân giải alias (`nha`, `lang`, `cold`, `ttvt`...).
- [`xmap_cli.py`](file:///c:/data/nro/ClientNROpy/xmap_cli.py): Công cụ dòng lệnh độc lập tra cứu đường đi ngoại tuyến.
- [`tests_xmap.py`](file:///c:/data/nro/ClientNROpy/tests_xmap.py): Bộ kiểm thử tự động toàn diện qua các map yêu cầu.

---

## 🚀 Cách Sử Dụng

### 1. Dòng lệnh tương tác trong game (CLI REPL)
Khởi động client:
```powershell
python -m ClientNROpy.main
```
Tại dấu nhắc `nro> `, nhập các lệnh sau:
- `xmap <id|tên>`: Di chuyển đến map chỉ định (Ví dụ: `xmap 0`, `xmap 6`, `xmap 7`, `xmap 19`, `xmap 45`, `xmap 82`, `xmap 100`, `xmap 109`, `xmap nha`, `xmap cold`).
- `xmap status`: Xem trạng thái, tiến độ và cấu hình Capsule.
- `xmap csvip`: Bật / Tắt dùng **Capsule Đặc Biệt (ID 194)** để bay thẳng tới map (mặc định: BẬT).
- `xmap cs`: Bật / Tắt dùng **Capsule Thường (ID 193)** (mặc định: TẮT).
- `xmap stop` (hoặc `cancel`): Dừng tiến trình Xmap.
- `xmap path <from> <to>`: Xem trước lộ trình giữa 2 map (Ví dụ: `xmap path 0 109`).
- `xmap list`: Xem danh sách tất cả các map theo hành tinh.
- `help`: Xem hướng dẫn toàn bộ lệnh.
- `exit`: Đăng xuất và thoát.

---

### 2. Tra cứu đường đi ngoại tuyến (Offline CLI)
Không cần đăng nhập game, dùng trực tiếp công cụ `xmap_cli`:
```powershell
# Chạy kiểm thử tự động đường đi qua các map trọng điểm:
python -m ClientNROpy.xmap_cli test

# Tra cứu lộ trình chi tiết giữa 2 map bất kỳ:
python -m ClientNROpy.xmap_cli path 0 "thần điện"
python -m ClientNROpy.xmap_cli path 19 109
```

---

### 3. Gọi từ mã nguồn Python
```python
from ClientNROpy import ClientNRO

client = ClientNRO()
client.connect()
client.login("username", "password")

# Bắt đầu Xmap
client.xmap("cold")       # hoặc client.xmap(109), client.xmap("nha")

# Tra cứu lộ trình không di chuyển
way = client.find_path(0, 109)

# Hủy Xmap
client.xmap_stop()
```
