# Dragonboy & ClientNROpy

Workspace chứa mã nguồn game Dragonboy (C# Unity) và thư viện giả lập headless ClientNROpy (Python).

- **Mô tả & Hướng dẫn Xmap**: Xem chi tiết tại [ClientNROpy/README.md](file:///c:/data/nro/ClientNROpy/README.md)
- **Mã nguồn Xmap**: Thư mục [ClientNROpy/xmap/](file:///c:/data/nro/ClientNROpy/xmap)

## Tính năng mới

- **Tàn sát xoay skill theo hành tinh**: `ClientNROpy/combat_manager.py`
  (`TANSAT_SKILLS_BY_GENDER` + `_select_and_attack`) và
  `Dragonboy/.../Mod/Auto/AutoTrainNewAccount.cs` (`TanSat` + `GetTanSatSkill`).
  Trái Đất `(9, 1, 0)`, Namek `(12, 3, 2)`, Xayda `(13, 5, 4)` — fix lỗi TS chỉ xài 1 skill.
- **Auto nhiệm vụ Bò Mộng hằng ngày**: [`ClientNROpy/auto_quest_bomong.py`](file:///c:/data/nro/ClientNROpy/auto_quest_bomong.py)
  (FSM nhận NV Siêu khó → Xmap tới map → chọn khu → farm → trả NV).
  Lệnh CLI: `nvbm [on|off|status]`.
- **Hạ tầng menu NPC**: `Controller` parse menu NPC (cmd 32), lưu tọa độ NPC trong
  `MapInfo.npcs`, callback hạ quái — phục vụ AutoQuest.
