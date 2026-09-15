# ClientNROpy - Xmap & Boss Hunting Mod

> **ClientNROpy** là bộ công cụ client game Chú Bé Rồng Online (NRO) chạy chế độ dòng lệnh headless bằng Python, tích hợp hệ thống **Xmap** (Auto Map Navigation) và hệ thống **Săn Boss** mô phỏng chuẩn xác từ mod `Mod/Boss.cs` và `Mod/Xmap/` của Dragonboy C#.

---

## 📍 Vị Trí Mã Nguồn (Nó Ở Đâu?)

### 1. Hệ thống Quản Lý & Săn Boss (`Mod/Boss.cs`)
- [`ClientNROpy/boss.py`](file:///c:/data/nro/ClientNROpy/boss.py): Thực thể dữ liệu `Boss` lưu trữ tên, map, khu vực, thời gian sống (`Xh Ym Zs`), trạng thái sống/chết và người hạ gục.
- [`ClientNROpy/boss_manager.py`](file:///c:/data/nro/ClientNROpy/boss_manager.py): Bộ quản lý `BossManager`, xử lý bóc tách thông báo ChatVip (cmd 93), cập nhật trạng thái khi người chơi vào map, và điều khiển Xmap tự động bay tới map + đổi khu của Boss.
- [`ClientNROpy/chat_vip.py`](file:///c:/data/nro/ClientNROpy/chat_vip.py): Đối tượng tin nhắn ChatVip (cmd 93), tách biệt hoàn toàn logic bóc tách Boss sang `BossManager`.
- [`ClientNROpy/tests_boss.py`](file:///c:/data/nro/ClientNROpy/tests_boss.py): Bộ kiểm thử tự động toàn diện cho hệ thống Boss.

### 2. Hệ thống Tìm Đường Xmap (`Mod/Xmap/`)
Toàn bộ mã nguồn nằm tại thư mục: [`ClientNROpy/xmap/`](file:///c:/data/nro/ClientNROpy/xmap)
- [`xmap_controller.py`](file:///c:/data/nro/ClientNROpy/xmap/xmap_controller.py): Vòng đời điều khiển máy trạng thái di chuyển đa luồng (Background Thread).
- [`xmap_data.py`](file:///c:/data/nro/ClientNROpy/xmap/xmap_data.py): Dữ liệu liên kết đồ thị (chuỗi AutoWaypoint, tàu vũ trụ, menu NPC, Capsule).
- [`xmap_algorithm.py`](file:///c:/data/nro/ClientNROpy/xmap/xmap_algorithm.py): Thuật toán Dijkstra tìm kiếm lộ trình tối ưu.
- [`xmap_executor.py`](file:///c:/data/nro/ClientNROpy/xmap/xmap_executor.py): Thực thi các bước di chuyển nhân vật và gửi gói tin qua map.
- [`map_data.py`](file:///c:/data/nro/ClientNROpy/xmap/map_data.py): Danh bạ 160 map tiếng Việt và bộ phân giải alias (`nha`, `lang`, `cold`, `ttvt`...).
- [`xmap_cli.py`](file:///c:/data/nro/ClientNROpy/xmap_cli.py): Công cụ dòng lệnh tra cứu đường đi ngoại tuyến.
- [`tests_xmap.py`](file:///c:/data/nro/ClientNROpy/tests_xmap.py): Bộ kiểm thử tự động Xmap qua các map yêu cầu.

---

## 🎯 Tính Năng Săn Boss (Tương Tự Boss.cs Trong Mod)

1. **Bóc tách thông báo tự động (cmd 93 - ChatVip)**:
   - Tự động phát hiện Boss xuất hiện: Tên Boss, Tên Map, Số Khu vực (đa ngôn ngữ Việt/Anh/Indo).
   - Tự động phát hiện Boss bị hạ gục: Người chơi tiêu diệt và thời gian kết thúc.
   - Bỏ qua ngoại lệ Tiểu đội sát thủ Ginyu ở các map Nappa (79, 82, 83).
2. **Quy tắc ánh xạ Map ID đặc biệt**:
   - `"Vách núi Aru"` $\rightarrow$ Map 42 (Vách núi đen)
   - `"Vách núi Moori"` $\rightarrow$ Map 43 (Vách núi Namếc)
   - `"Trạm tàu vũ trụ"`:
     - Nhóm Tiểu đội sát thủ (`Số 1`, `Tiểu đội trưởng`...) $\rightarrow$ Map 25 (Namếc)
     - Nhóm Bojack (`Bojack`, `Bujin`, `Bido`, `Zangya`) $\rightarrow$ Map 24 (Trái Đất)
3. **Theo dõi trạng thái thời gian thực**:
   - Tự động tính thời gian sống của Boss: định dạng chuẩn `{hours}h{minutes}m{seconds}s`.
   - Khi vào cùng map với Boss: Tự phát hiện khu vực nếu Boss chưa có khu, hoặc đánh dấu đã chết nếu Boss đã bị tiêu diệt / không còn trong khu.
4. **Tự động bay đến Boss (`boss go <stt|tên>`)**:
   - Kết hợp chặt chẽ với Xmap: Tự động tính đường và kích hoạt bay tới map của Boss.
   - Khi tới nơi: Tự động gửi lệnh đổi sang đúng khu vực của Boss!

---

## 🚀 Cách Sử Dụng Dòng Lệnh (CLI)

Khởi động client:
```powershell
python -m ClientNROpy.main
```

Tại dấu nhắc `nro> `, các lệnh hỗ trợ:

### 👑 Lệnh Săn Boss:
- `boss`: Xem danh sách các Boss đang còn sống (STT, Tên, Map, Khu, Thời gian đã xuất hiện).
- `boss all` (hoặc `boss history`): Xem toàn bộ lịch sử Boss (kể cả Boss đã chết và tên người hạ).
- `boss go <stt|tên>`: Tự động Xmap bay đến map của Boss và tự đổi sang đúng khu vực của Boss.
  - Ví dụ: `boss go 1`, `boss go Broly`, `boss go Fide`, `boss go Cooler`.
- `boss clear`: Xóa danh sách lịch sử Boss đã lưu.

### 🗺️ Lệnh Xmap:
- `xmap <id|tên>`: Di chuyển đến map chỉ định (Ví dụ: `xmap 0`, `xmap 6`, `xmap 109`, `xmap nha`, `xmap cold`).
- `xmap status`: Xem trạng thái, tiến độ và cấu hình Capsule.
- `xmap csvip`: Bật / Tắt dùng **Capsule Đặc Biệt (ID 194)** bay thẳng (mặc định: BẬT).
- `xmap cs`: Bật / Tắt dùng **Capsule Thường (ID 193)** (mặc định: TẮT).
- `xmap stop`: Dừng tiến trình Xmap.
- `xmap path <from> <to>`: Tra cứu lộ trình tối ưu giữa 2 map (Ví dụ: `xmap path 0 109`).
- `xmap list`: Xem danh sách tất cả các map theo hành tinh.

### 🛠️ Lệnh Khác:
- `map`: Xem thông tin map hiện tại, toạ độ x, y và waypoints.
- `zone [id]`: Xem danh sách khu vực hoặc đổi khu (Ví dụ: `zone 5`).
- `chat <nội dung>`: Gửi tin nhắn chat trong bản đồ.
- `info`: In thông tin nhân vật, balo hành trang, đệ tử.
- `help`: Xem hướng dẫn toàn bộ lệnh.
- `exit`: Đăng xuất an toàn và thoát chương trình.

---

## 🧪 Chạy Kiểm Thử Tự Động (Unit Tests)

Chạy toàn bộ 32 unit tests của hệ thống:
```powershell
python -m unittest discover -s ClientNROpy -p "tests*.py"
```
