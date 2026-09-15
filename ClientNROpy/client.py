# -*- coding: utf-8 -*-
"""
Lớp điều khiển cấp cao (ClientNRO).
Đóng gói toàn bộ kiến trúc Session_ME, Controller, Service
thành một API dễ sử dụng cho các tool và bot game headless.
"""

import threading
import time
from typing import Optional, List, Callable, Union, Tuple, Any, Dict
from .session import Session_ME
from .controller import Controller
from .service import Service
from .char import Char
from .pet import Pet
from .magic_tree import MagicTree
from .item import Item
from .zone_info import ZoneInfo
from .map_info import MapInfo
from .player_data import PlayerData
from .chat_vip import ChatVip
from .boss import Boss
from .boss_manager import BossManager
from .boss_hunter import BossHunter
from .combat_manager import CombatManager
from .auto_quest_bomong import AutoQuest
from .xmap import XmapController, MapNext


class ClientNRO:
    """
    ClientNRO cung cấp giao diện lập trình cấp cao (High-Level API)
    cho các công cụ game / bot tự động hoá không cần đồ hoạ.
    """

    def __init__(self, host: str = "51.79.163.109", port: int = 12457, version: str = "2.1.4"):
        self.host: str = host
        self.port: int = port
        self.version: str = version
        self.session: Session_ME = Session_ME.gI()
        self.controller: Controller = Controller.gI()
        self.service: Service = Service.gI()
        self.service.version = version

        # Đăng ký Controller làm IMessageHandler
        self.session.setHandler(self.controller)

        # Tham chiếu trạng thái nhân vật
        self.myChar: Char = Char.myCharz()

        # Bộ điều khiển tìm đường tự động Xmap
        self.xmap_controller: XmapController = XmapController(self)

        # Bộ quản lý và săn Boss (Mod/Boss.cs)
        self.boss_manager: BossManager = BossManager(self)

        # Bộ điều khiển chiến đấu: Focus, Teleport, AK, Tàn Sát
        self.combat_manager: CombatManager = CombatManager(self)

        # Bộ máy tự động săn Boss hoàn chỉnh (BossHunter FSM)
        self.boss_hunter: BossHunter = BossHunter(self)

        # Auto nhiệm vụ Bò Mộng hằng ngày (AutoQuest FSM)
        self.auto_quest: AutoQuest = AutoQuest(self)

        # Shuttle tự động di chuyển qua lại 2 map (ShuttleManager)
        self.shuttle_manager: ShuttleManager = ShuttleManager(self)



    def connect(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        """Kết nối tới server game."""
        target_host = host or self.host
        target_port = port or self.port
        self.session.connect(target_host, target_port)

    def isConnected(self) -> bool:
        """Kiểm tra xem client có đang kết nối không."""
        return self.session.isConnected()

    def login(self, username: str, password: str, version: Optional[str] = None) -> None:
        """Đăng nhập tài khoản."""
        ver = version or self.version
        self.service.login(username, password, version=ver)

    def selectChar(self, charname: str) -> None:
        """Chọn nhân vật để vào map."""
        self.service.selectCharToPlay(charname)

    def moveTo(self, cx: int, cy: int, flying: bool = False) -> None:
        """Di chuyển nhân vật tới toạ độ (cx, cy)."""
        self.service.charMove(cx, cy, flying=flying)

    def chat(self, text: str) -> None:
        """Gửi tin nhắn chat trong bản đồ."""
        self.service.chat(text)

    def chatGlobal(self, text: str) -> None:
        """Gửi tin nhắn chat kênh thế giới."""
        self.service.chatGlobal(text)

    def chatPlayer(self, text: str, player_id: int) -> None:
        """Chat với người chơi theo ID."""
        self.service.chatPlayer(text, player_id)

    def chatPrivate(self, to: str, text: str) -> None:
        """Chat riêng tư."""
        self.service.chatPrivate(to, text)

    # --------------------------------------------------------------------------
    # Các hàm yêu cầu và thao tác tính năng game
    # --------------------------------------------------------------------------
    def request_zones(self) -> None:
        """Yêu cầu máy chủ gửi danh sách các khu vực trong map (cmd 29)."""
        self.service.openUIZone()

    def change_zone(self, zone_id: int) -> None:
        """Yêu cầu đổi sang khu vực chỉ định (cmd 21)."""
        self.service.requestChangeZone(zone_id)

    def request_pet_info(self) -> None:
        """Yêu cầu máy chủ gửi thông tin đệ tử / pet (cmd -107)."""
        self.service.petInfo()

    def set_pet_status(self, status: int) -> None:
        """
        Thay đổi trạng thái đệ tử (cmd -108).
        0: Đi theo, 1: Bảo vệ, 2: Tấn công, 3: Về nhà, 4: Hợp thể, 5: Hợp thể Porata
        """
        self.service.petStatus(status)

    def request_magic_tree(self, action: int = 1) -> None:
        """
        Tương tác cây đậu thần (cmd -34).
        action=1: Xem thông tin, action=2: Thu hoạch
        """
        self.service.magicTree(action)

    # --------------------------------------------------------------------------
    # Các hàm Getter lấy dữ liệu đã bóc tách
    # --------------------------------------------------------------------------
    def get_my_char(self) -> Char:
        """Lấy toàn bộ thông tin nhân vật chính."""
        return self.myChar

    def get_bag_items(self) -> List[Item]:
        """Lấy danh sách vật phẩm trong hành trang Balo."""
        return self.myChar.arrItemBag

    def get_box_items(self) -> List[Item]:
        """Lấy danh sách vật phẩm trong Rương đồ."""
        return self.myChar.arrItemBox

    def get_body_items(self) -> List[Item]:
        """Lấy danh sách trang bị đang mặc trên người."""
        return self.myChar.arrItemBody

    def get_pet(self) -> Pet:
        """Lấy thông tin đệ tử / pet."""
        return self.myChar.pet

    def get_magic_tree(self) -> MagicTree:
        """Lấy thông tin Cây đậu thần."""
        return self.myChar.magicTree

    def get_map_info(self) -> MapInfo:
        """Lấy thông tin bản đồ hiện tại, quái vật, NPC và người chơi trong map."""
        return self.myChar.mapInfo

    def get_zones(self) -> List[ZoneInfo]:
        """Lấy danh sách các khu vực của map hiện tại."""
        return self.myChar.mapInfo.zones

    def disconnect(self) -> None:
        """Ngắt kết nối mạng an toàn."""
        self.session.close()

    def logout(self) -> None:
        """
        Đăng xuất tài khoản an toàn (mô phỏng Logout trong GameScr / LoginScr):
        - Đóng phiên kết nối Session_ME
        - Đặt lại dữ liệu nhân vật Char.clearMyChar()
        """
        print("[ClientNRO] Logging out...")
        self.disconnect()
        Char.clearMyChar()
        self.myChar = Char.myCharz()

    # --------------------------------------------------------------------------
    # Đăng ký các callback sự kiện
    # --------------------------------------------------------------------------
    def on_login_ok(self, callback: Callable[[List[PlayerData]], None]) -> None:
        """Lắng nghe sự kiện đăng nhập thành công."""
        self.controller.on_login_ok_callbacks.append(callback)

    def on_cooldown(self, callback: Callable[[int], None]) -> None:
        """Lắng nghe sự kiện hàng đợi / đếm ngược thời gian chờ đăng nhập (cmd 122)."""
        self.controller.on_cooldown_callbacks.append(callback)

    def on_chat(self, callback: Callable[[int, str], None]) -> None:
        """Lắng nghe tin nhắn chat trong bản đồ."""
        self.controller.on_chat_callbacks.append(callback)

    def on_server_message(self, callback: Callable[[str], None]) -> None:
        """Lắng nghe thông báo từ máy chủ."""
        self.controller.on_server_message_callbacks.append(callback)

    def on_char_info(self, callback: Callable[[Char], None]) -> None:
        """Lắng nghe thông tin nhân vật chính khi vào game."""
        self.controller.on_char_info_callbacks.append(callback)

    def on_map_info(self, callback: Callable[[MapInfo], None]) -> None:
        """Lắng nghe thông tin map khi chuyển map hoặc vừa vào game."""
        self.controller.on_map_info_callbacks.append(callback)

    def on_zone_info(self, callback: Callable[[List[ZoneInfo]], None]) -> None:
        """Lắng nghe danh sách khu vực khi nhận từ server."""
        self.controller.on_zone_info_callbacks.append(callback)

    def on_bag_update(self, callback: Callable[[List[Item]], None]) -> None:
        """Lắng nghe cập nhật hành trang balo."""
        self.controller.on_bag_update_callbacks.append(callback)

    def on_pet_info(self, callback: Callable[[Pet], None]) -> None:
        """Lắng nghe cập nhật thông tin đệ tử."""
        self.controller.on_pet_info_callbacks.append(callback)

    def on_magic_tree(self, callback: Callable[[MagicTree], None]) -> None:
        """Lắng nghe cập nhật thông tin cây đậu thần."""
        self.controller.on_magic_tree_callbacks.append(callback)

    def on_chat_vip(self, callback: Callable[[ChatVip], None]) -> None:
        """Lắng nghe tin nhắn ChatVip, thông báo Boss xuất hiện và Boss bị tiêu diệt (cmd 93)."""
        self.controller.on_chat_vip_callbacks.append(callback)

    def on_chat_world(self, callback: Callable[[str], None]) -> None:
        """Lắng nghe tin nhắn chat thế giới từ máy chủ (cmd 92)."""
        self.controller.on_chat_world_callbacks.append(callback)

    def get_chat_vip_history(self) -> List[ChatVip]:
        """Lấy danh sách lịch sử tin ChatVip và thông báo Boss đã nhận."""
        return self.controller.chat_vip_list

    # --------------------------------------------------------------------------
    # Các hàm điều khiển tính năng Xmap (Tự động tìm đường và chuyển map)
    # --------------------------------------------------------------------------
    def xmap(self, target: Union[int, str]) -> bool:
        """
        Bắt đầu Xmap tự động di chuyển tới map chỉ định.
        target có thể là ID (vd: 0, 6, 7, 19, 45, 82, 100, 109)
        hoặc tên map / alias (vd: 'nhà', 'home', 'đông karin', 'cold').
        """
        return self.xmap_controller.start(target)

    def xmap_stop(self) -> None:
        """Dừng tiến trình Xmap đang thực hiện."""
        self.xmap_controller.stop()

    def xmap_status(self) -> dict:
        """Lấy thông tin trạng thái Xmap hiện tại."""
        return self.xmap_controller.get_status()

    def find_path(self, start_map: int, end_map: int) -> Optional[List[MapNext]]:
        """Tra cứu lộ trình chuyển map ngắn nhất từ start_map đến end_map."""
        return self.xmap_controller.find_path(start_map, end_map)

    def on_xmap_status(self, callback: Callable[[str], None]) -> None:
        """Lắng nghe thông điệp trạng thái từ Xmap."""
        self.xmap_controller.on_status_callbacks.append(callback)

    def on_xmap_finish(self, callback: Callable[[bool, str], None]) -> None:
        """Lắng nghe sự kiện kết thúc Xmap (thành công hoặc thất bại)."""
        self.xmap_controller.on_finish_callbacks.append(callback)

    # --------------------------------------------------------------------------
    # Các hàm quản lý và săn Boss (Mô phỏng Mod/Boss.cs)
    # --------------------------------------------------------------------------
    def get_bosses(self) -> List[Boss]:
        """Lấy toàn bộ danh sách Boss đã ghi nhận (tối đa 100)."""
        return self.boss_manager.get_all_bosses()

    def get_alive_bosses(self) -> List[Boss]:
        """Lấy danh sách các Boss hiện đang còn sống."""
        return self.boss_manager.get_alive_bosses()

    def go_to_boss(self, target: Union[int, str]) -> Tuple[bool, str]:
        """
        Tự động di chuyển tới vị trí Boss bằng Xmap và tự đổi sang đúng khu của Boss.
        target có thể là STT trong danh sách hoặc tên Boss (ví dụ: 1, 'Broly', 'Fide').
        """
        return self.boss_manager.go_to_boss(target)

    def on_boss_spawn(self, callback: Callable[[Boss], None]) -> None:
        """Lắng nghe thông báo Boss xuất hiện mới."""
        self.boss_manager.on_boss_appeared_callbacks.append(callback)

    def on_boss_killed(self, callback: Callable[[Boss], None]) -> None:
        """Lắng nghe thông báo Boss bị tiêu diệt."""
        self.boss_manager.on_boss_killed_callbacks.append(callback)

    # --------------------------------------------------------------------------
    # Các hàm chiến đấu: Focus, Teleport, AK, Tàn Sát (Auto Attack / Auto PK)
    # --------------------------------------------------------------------------
    def focus(self, target_type: str = "", query: Optional[Union[int, str]] = None) -> Tuple[bool, str]:
        """
        Nhắm tiêu điểm (focus) vào quái, người chơi, hoặc vật phẩm.
        target_type: 'mob', 'char'/'player', 'item', 'clear', hoặc rỗng để xem hiện tại.
        """
        return self.combat_manager.focus(target_type, query)

    def teleport(self, x: int, y: int) -> bool:
        """Dịch chuyển tức thời đến toạ độ (x, y) không cần đồ hoạ."""
        return self.combat_manager.teleport(x, y)

    def teleport_to(self, target: Any) -> Tuple[bool, str]:
        """Dịch chuyển tức thời tới đối tượng (Mob, Char, ItemMap, Waypoint, hoặc chuỗi truy vấn)."""
        return self.combat_manager.teleport_to(target)

    def attack(self, target: Any = None) -> bool:
        """Tấn công mục tiêu (hoặc mục tiêu đang focus)."""
        return self.combat_manager.attack_target(target)

    def pick_item(self, item_map_id: int) -> None:
        """Nhặt vật phẩm rơi dưới đất theo ID."""
        self.service.pickItem(item_map_id)

    def toggle_ak(self, enable: Optional[bool] = None) -> bool:
        """Bật / Tắt chế độ tự động đánh (AK - Auto Attack)."""
        return self.combat_manager.toggle_ak(enable)

    def toggle_tansat(self, enable: Optional[bool] = None, mode: str = "mob") -> bool:
        """
        Bật / Tắt chế độ tàn sát tự động.
        mode: 'mob' (quái), 'player'/'char' (người chơi), 'all' (cả hai).
        """
        return self.combat_manager.toggle_tansat(enable, mode=mode)

    def toggle_auto_pick(self, enable: Optional[bool] = None) -> bool:
        """Bật / Tắt tự động nhặt vật phẩm rơi trên đất."""
        if enable is not None:
            self.combat_manager.auto_pick = enable
        else:
            self.combat_manager.auto_pick = not self.combat_manager.auto_pick
        return self.combat_manager.auto_pick

    def toggle_auto_pean(self, enable: Optional[bool] = None) -> bool:
        """Bật / Tắt tự động dùng đậu thần khi HP/KI thấp."""
        if enable is not None:
            self.combat_manager.auto_pean = enable
        else:
            self.combat_manager.auto_pean = not self.combat_manager.auto_pean
        return self.combat_manager.auto_pean

    def combat_status(self) -> Dict[str, Any]:
        """Lấy toàn bộ trạng thái cấu hình chiến đấu hiện tại."""
        return self.combat_manager.get_status()

    # --------------------------------------------------------------------------
    # HỆ THỐNG AUTO SĂN BOSS HOÀN CHỈNH (AUTONOMOUS BOSS HUNTER)
    # --------------------------------------------------------------------------
    def start_auto_hunt(self, targets: Optional[List[str]] = None) -> None:
        """Bắt đầu tính năng Auto Săn Boss hoàn chỉnh."""
        self.boss_hunter.start(targets=targets)

    def stop_auto_hunt(self) -> None:
        """Dừng tính năng Auto Săn Boss."""
        self.boss_hunter.stop()

    def toggle_auto_hunt(self) -> bool:
        """Bật / Tắt tính năng Auto Săn Boss."""
        return self.boss_hunter.toggle()

    def add_hunt_target(self, name: str) -> None:
        """Thêm một Boss vào danh sách săn (whitelist)."""
        self.boss_hunter.add_target(name)

    def remove_hunt_target(self, name: str) -> None:
        """Xóa một Boss khỏi danh sách săn."""
        self.boss_hunter.remove_target(name)

    def clear_hunt_targets(self) -> None:
        """Xóa toàn bộ danh sách Boss mục tiêu (chuyển sang săn tất cả)."""
        self.boss_hunter.clear_targets()

    def get_hunt_status(self) -> Dict[str, Any]:
        """Lấy toàn bộ trạng thái máy trạng thái săn Boss."""
        return self.boss_hunter.get_status()

    # --------------------------------------------------------------------------
    # AUTO NHIỆM VỤ BÒ MỘNG HẰNG NGÀY (AUTO QUEST)
    # --------------------------------------------------------------------------
    def start_auto_quest(self) -> None:
        """Bắt đầu auto nhiệm vụ Bò Mộng."""
        self.auto_quest.start()

    def stop_auto_quest(self) -> None:
        """Dừng auto nhiệm vụ Bò Mộng."""
        self.auto_quest.stop()

    def toggle_auto_quest(self) -> bool:
        """Bật / Tắt auto nhiệm vụ Bò Mộng."""
        return self.auto_quest.toggle()

    def get_quest_status(self) -> Dict[str, Any]:
        """Lấy trạng thái auto nhiệm vụ Bò Mộng."""
        return self.auto_quest.get_status()

    # --------------------------------------------------------------------------
    # AUTO SHUTTLE (Di chuyển qua lại giữa 2 map)
    # --------------------------------------------------------------------------
    def start_shuttle(self, map_a: int, map_b: int, rounds: int = 0) -> bool:
        """Bắt đầu tự động di chuyển qua lại giữa 2 map (A <-> B)."""
        return self.shuttle_manager.start(map_a, map_b, rounds)

    def stop_shuttle(self) -> None:
        """Dừng di chuyển qua lại 2 map."""
        self.shuttle_manager.stop()

    def get_shuttle_status(self) -> Dict[str, Any]:
        """Lấy thông tin trạng thái shuttle hiện tại."""
        return self.shuttle_manager.get_status()


class ShuttleManager:
    """Quản lý tiến trình di chuyển liên tục qua lại giữa 2 map."""

    def __init__(self, client: "ClientNRO"):
        self.client: "ClientNRO" = client
        self.is_running: bool = False
        self.map_a: Optional[int] = None
        self.map_b: Optional[int] = None
        self.rounds: int = 0
        self.legs_done: int = 0
        self.current_target: Optional[int] = None
        self.status_message: str = "Đã dừng"
        self._thread: Optional[threading.Thread] = None
        self._lock: threading.RLock = threading.RLock()

    def start(self, map_a: int, map_b: int, rounds: int = 0) -> bool:
        if map_a == map_b:
            return False
        with self._lock:
            self.is_running = False
            self.map_a = map_a
            self.map_b = map_b
            self.rounds = rounds
            self.legs_done = 0
            self.is_running = True
            self.status_message = "Đang khởi động"
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            return True

    def stop(self) -> None:
        with self._lock:
            self.is_running = False
            self.status_message = "Đã dừng"

    def get_status(self) -> Dict[str, Any]:
        from .xmap.map_data import get_map_name
        return {
            "is_running": self.is_running,
            "map_a": f"{get_map_name(self.map_a)} ({self.map_a})" if self.map_a is not None else "?",
            "map_b": f"{get_map_name(self.map_b)} ({self.map_b})" if self.map_b is not None else "?",
            "legs_done": self.legs_done,
            "rounds": self.rounds,
            "current_target": f"{get_map_name(self.current_target)} ({self.current_target})" if self.current_target is not None else "Không",
            "status_message": self.status_message,
        }

    def _run_loop(self) -> None:
        from .xmap.map_data import get_map_name
        try:
            time.sleep(0.5)
            while self.is_running:
                curr_map = self.client.myChar.mapInfo.mapID
                # Quyết định map tiếp theo
                if curr_map == self.map_a:
                    target = self.map_b
                elif curr_map == self.map_b:
                    target = self.map_a
                else:
                    target = self.map_a

                self.current_target = target
                t_name = get_map_name(target)
                self.status_message = f"Đang di chuyển tới {t_name} ({target})"
                print(f"\n[Shuttle] >>> Lượt {self.legs_done + 1}: Chuyển map từ {curr_map} ({get_map_name(curr_map)}) tới {t_name} (ID: {target})...", flush=True)

                self.client.xmap(target)
                time.sleep(1.0)

                # Chờ đến đích
                while self.is_running:
                    time.sleep(0.5)
                    if self.client.myChar.mapInfo.mapID == target and not self.client.xmap_controller.is_acting:
                        break

                if not self.is_running:
                    break

                self.legs_done += 1
                print(f"[Shuttle] [Lượt {self.legs_done}] Đã đến thành công {t_name} (ID: {target})!", flush=True)

                if self.rounds > 0 and self.legs_done >= self.rounds:
                    print(f"[Shuttle] Hoàn thành đủ {self.rounds} lượt!", flush=True)
                    self.is_running = False
                    self.status_message = f"Hoàn thành {self.rounds} lượt"
                    break

                time.sleep(2.0)
        except Exception as ex:
            print(f"[Shuttle] Lỗi ngoại lệ trong ShuttleManager: {ex}", flush=True)
            import traceback
            traceback.print_exc()
            self.is_running = False


