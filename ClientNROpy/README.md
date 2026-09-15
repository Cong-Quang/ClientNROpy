# ClientNROpy - Headless NRO Client & Mod Toolkit

> **ClientNROpy** là bộ công cụ client game Chú Bé Rồng Online (Dragon Boy) chạy chế độ dòng lệnh headless hoàn toàn bằng Python. Tích hợp đầy đủ các tính năng mod cao cấp từ C# (`Mod/Xmap/`, `Mod/Boss.cs`, `Mod/PickMob/`, `Mod/Auto/AutoSendAttack.cs`, `Mod/Utils.cs`).

---

## 📍 Cấu Trúc Mã Nguồn (Nó Ở Đâu?)

### 1. Hệ thống Chiến Đấu & Tàn Sát (`Mod/PickMob/`, `Mod/Auto/`, `Mod/Utils.cs`)
- [`ClientNROpy/combat_manager.py`](file:///c:/data/nro/ClientNROpy/combat_manager.py): Bộ điều khiển trung tâm `CombatManager` quản lý:
  - **Focus**: Tiêu điểm nhắm mục tiêu quái, người chơi, vật phẩm, NPC.
  - **Teleport**: Dịch chuyển tức thời toạ độ `(x, y)` hoặc dịch chuyển đến thực thể.
  - **AK (Auto Attack)**: Tự động đánh mục tiêu đang focus theo chu kỳ.
  - **Tàn Sát (Slaughter / Auto Mob / Auto PK)**: Tự động đánh toàn bộ quái hoặc lọc theo loại quái, né siêu quái, tàn sát người chơi, tự nhặt đồ rơi và tự ăn đậu thần khi HP/KI thấp.
- [`ClientNROpy/tests_combat.py`](file:///c:/data/nro/ClientNROpy/tests_combat.py): Bộ kiểm thử tự động toàn diện cho hệ thống chiến đấu và tàn sát (10 unit tests).

### 2. Hệ thống Quản Lý & Săn Boss (`Mod/Boss.cs`)
- [`ClientNROpy/boss.py`](file:///c:/data/nro/ClientNROpy/boss.py): Thực thể dữ liệu `Boss` lưu trữ tên, map, khu vực, thời gian sống (`Xh Ym Zs`), trạng thái sống/chết và người hạ gục.
- [`ClientNROpy/boss_manager.py`](file:///c:/data/nro/ClientNROpy/boss_manager.py): Xử lý bóc tách thông báo ChatVip (cmd 93), quy tắc ánh xạ Map ID đặc biệt (Aru, Moori, Bojack, Ginyu Force), cập nhật thời gian thực khi vào cùng map, và tự động gọi Xmap bay tới Boss + đổi khu.
- [`ClientNROpy/chat_vip.py`](file:///c:/data/nro/ClientNROpy/chat_vip.py): Đối tượng tin nhắn ChatVip (cmd 93), tách bạch sạch sẽ khỏi logic Boss.
- [`ClientNROpy/tests_boss.py`](file:///c:/data/nro/ClientNROpy/tests_boss.py): Bộ kiểm thử độc lập cho tính năng Boss (8 unit tests).

### 3. Hệ thống Tìm Đường Xmap (`Mod/Xmap/`)
Toàn bộ mã nguồn nằm tại thư mục: [`ClientNROpy/xmap/`](file:///c:/data/nro/ClientNROpy/xmap)
- [`xmap_controller.py`](file:///c:/data/nro/ClientNROpy/xmap/xmap_controller.py): Vòng đời điều khiển máy trạng thái di chuyển đa luồng.
- [`xmap_data.py`](file:///c:/data/nro/ClientNROpy/xmap/xmap_data.py): Dữ liệu liên kết đồ thị (AutoWaypoint, tàu vũ trụ, NPC, Capsule Đặc Biệt/Thường).
- [`xmap_algorithm.py`](file:///c:/data/nro/ClientNROpy/xmap/xmap_algorithm.py): Thuật toán Dijkstra tìm kiếm lộ trình ngắn nhất.
- [`xmap_executor.py`](file:///c:/data/nro/ClientNROpy/xmap/xmap_executor.py): Thực thi di chuyển nhân vật và chuyển map.
- [`map_data.py`](file:///c:/data/nro/ClientNROpy/xmap/map_data.py): Danh bạ 160 map và bộ phân giải alias (`nha`, `lang`, `cold`, `ttvt`...).
- [`tests_xmap.py`](file:///c:/data/nro/ClientNROpy/tests_xmap.py): Bộ kiểm thử tự động Xmap (14 unit tests).

---

## 🎯 Chi Tiết Tính Năng Chiến Đấu & Tàn Sát

| Tính Năng | Lệnh CLI | Mô Tả |
| :--- | :--- | :--- |
| **Focus** | `focus [mob\|char\|item\|clear]` | Nhắm tiêu điểm vào quái vật, người chơi, hoặc vật phẩm rơi dưới đất. |
| **Teleport** | `tele [x y\|mob\|char\|item\|wp]` | Dịch chuyển tức thời không cần đồ họa chuẩn mod NRO (bước đệm gửi `charMove`). |
| **AK (Auto Attack)** | `ak [on\|off]` | Tự động đánh liên tục mục tiêu đang nhắm (focus) sau mỗi ~150ms. |
| **Tàn Sát Quái** | `ts` hoặc `ts mob` | Quét và tự động dịch chuyển áp sát tiêu diệt toàn bộ quái trong bản đồ. |
| **Lọc Loại Quái** | `ts type <template_id>` | Chỉ tàn sát 1 loại quái nhất định (tương ứng `addtm` trong mod C#). |
| **Lọc Quái Cụ Thể** | `ts id <mob_id>` | Chỉ tàn sát quái có ID chỉ định (tương ứng `addm` trong mod C#). |
| **Tàn Sát Người (PK)** | `ts player` hoặc `ts pk` | Tự động quét người chơi khác trong map, tele áp sát và gửi gói tin tấn công. |
| **Né Siêu Quái** | `nsq` | Bỏ qua quái có lượng HP bất thường / siêu quái (mặc định Bật). |
| **Tự Nhặt Đồ** | `anhat` | Tự động phát hiện đồ rơi trên đất, tele tới nhặt (`pickItem` cmd -20). |
| **Chỉ Nhặt Ngọc** | `cnn` | Cài đặt nhanh chỉ nhặt ngọc xanh / ngọc khoá (ID 77, 861). |
| **Tự Ăn Đậu** | `abf [ngưỡng %]` | Tự động thu hoạch và dùng đậu thần khi HP hoặc KI thấp hơn ngưỡng (mặc định 20%). |
| **Xem Cấu Hình** | `combat` | In toàn bộ bảng trạng thái cấu hình chiến đấu và tàn sát hiện tại. |

---

## 🚀 Cách Sử Dụng Dòng Lệnh (CLI)

Khởi động client:
```powershell
python -m ClientNROpy.main
```

Tại dấu nhắc `nro> `, các lệnh hỗ trợ:

### ⚔️ Chiến Đấu & Tàn Sát:
- `focus mob`: Focus vào con quái gần nhất trong map.
- `focus char Broly`: Focus vào nhân vật có tên chứa 'Broly'.
- `focus clear`: Bỏ chọn mục tiêu focus.
- `tele 500 300`: Dịch chuyển đến toạ độ (500, 300).
- `tele mob 2`: Dịch chuyển đến con quái ID 2.
- `tele`: Dịch chuyển đến mục tiêu đang focus.
- `ak`: Bật / Tắt tự động đánh.
- `ts`: Bật / Tắt tàn sát quái trong map.
- `ts type 1`: Chỉ đánh loại quái có template ID 1.
- `ts clear`: Xoá bộ lọc quái (đánh tất cả quái).
- `ts pk`: Bật tàn sát người chơi (Auto PK).
- `nsq`: Bật / Tắt né siêu quái.
- `anhat`: Bật / Tắt tự động nhặt đồ.
- `cnn`: Chế độ chỉ nhặt ngọc.
- `abf 30`: Bật tự động dùng đậu khi HP/KI dưới 30%.
- `combat`: Xem bảng trạng thái cấu hình chiến đấu.

### 👑 Quản Lý & Săn Boss:
- `boss`: Xem danh sách các Boss đang còn sống (STT, Tên, Map, Khu, Thời gian).
- `boss all`: Xem toàn bộ lịch sử các Boss (kể cả đã bị tiêu diệt và người hạ).
- `boss go <stt|tên>`: Tự động dùng Xmap bay đến map của Boss và tự chuyển sang đúng khu của Boss!
- `boss clear`: Xóa danh sách lịch sử Boss đã lưu.

### 🗺️ Tự Động Tìm Đường Xmap:
- `xmap <id|tên>`: Di chuyển đến map chỉ định (Ví dụ: `xmap 0`, `xmap 6`, `xmap 109`, `xmap nha`, `xmap cold`).
- `xmap status`: Xem trạng thái, tiến độ và cấu hình Capsule.
- `xmap csvip`: Bật / Tắt dùng **Capsule Đặc Biệt (ID 194)** bay thẳng (mặc định: BẬT).
- `xmap cs`: Bật / Tắt dùng **Capsule Thường (ID 193)** (mặc định: TẮT).
- `xmap stop`: Dừng tiến trình Xmap.
- `xmap path <from> <to>`: Tra cứu lộ trình tối ưu giữa 2 map (Ví dụ: `xmap path 0 109`).
- `xmap list`: Xem danh sách tất cả các map theo hành tinh.

### 🛠️ Tiện Ích Khác:
- `map`: Xem thông tin map hiện tại, toạ độ x, y và waypoints.
- `zone [id]`: Xem danh sách khu vực hoặc đổi khu (Ví dụ: `zone 5`).
- `chat <nội dung>`: Gửi tin nhắn chat trong bản đồ.
- `info`: In thông tin nhân vật, balo hành trang, đệ tử.
- `help`: Xem hướng dẫn toàn bộ lệnh.
- `exit`: Đăng xuất an toàn và thoát chương trình.

---

## 🧪 Chạy Toàn Bộ Kiểm Thử Tự Động (Unit Tests)

Hệ thống có tổng cộng **42 unit tests** kiểm thử tự động toàn bộ tính năng:
```powershell
python -m unittest discover -s ClientNROpy -p "tests*.py"
```
Kết quả kiểm thử: **42/42 tests PASSED (OK)**.
