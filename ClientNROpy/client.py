# -*- coding: utf-8 -*-
"""
Lớp điều khiển cấp cao (ClientNRO).
Đóng gói toàn bộ kiến trúc Session_ME, Controller, Service
thành một API dễ sử dụng cho các tool và bot game headless.
"""

import threading
import time
from typing import Optional, List, Callable, Union, Tuple, Any, Dict, Set
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
from .auto_manager import AutoManager
from .xmap import XmapController, MapNext
from .data_collector import DataCollector, get_data_collector


class ClientNRO:
    """
    ClientNRO cung cấp giao diện lập trình cấp cao (High-Level API)
    cho các công cụ game / bot tự động hoá không cần đồ hoạ.
    """

    def __init__(
        self,
        host: str = "51.79.163.109",
        port: int = 12457,
        version: str = "2.1.4",
        proxy: Optional[str] = None,
        account_id: str = "",
        username: str = "",
    ):
        self.account_id: str = account_id or username or "Client"
        self.username: str = username
        self.host: str = host
        self.port: int = port
        self.version: str = version
        self.proxy: Optional[str] = proxy

        # Khởi tạo đối tượng độc lập cho từng client (không chia sẻ Singleton!)
        self.session: Session_ME = Session_ME(proxy=proxy)
        self.myChar: Char = Char()
        self.service: Service = Service(session=self.session, client=self)
        self.service.version = version
        self.controller: Controller = Controller(client=self)

        # Đăng ký Controller làm IMessageHandler
        self.session.setHandler(self.controller)

        # Bộ điều khiển tìm đường tự động Xmap
        self.xmap_controller: XmapController = XmapController(self)

        # Module Tự Động Hóa Hợp Nhất (Unified Auto Engine - 1 Worker Thread)
        self.auto: AutoManager = AutoManager(self)

        # Module Thu Thập Dữ Liệu Tự Động (Data Collector) Cho AI
        self.data_collector: DataCollector = get_data_collector(client=self)

        # Các thuộc tính bí danh giữ tương thích ngược 100%
        self.combat_manager: AutoManager = self.auto
        self.boss_manager: AutoManager = self.auto
        self.boss_hunter: AutoManager = self.auto
        self.auto_quest: AutoManager = self.auto
        self.auto_quest_manager: AutoManager = self.auto
        self.auto_revive_manager: AutoManager = self.auto
        self.auto_use_item_manager: AutoManager = self.auto
        self.shuttle_manager: AutoManager = self.auto



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

    def change_to_least_populated_zone(self, excluded_zones: Optional[Set[int]] = None) -> Optional[int]:
        """
        Tìm và tự động chuyển sang khu vực có ít người chơi nhất trong map hiện tại.
        - Nếu khu hiện tại đã là khu ít người nhất (hoặc bằng min), giữ nguyên không đổi.
        - Tham số excluded_zones: loại trừ các khu đã có tài khoản khác chiếm (tránh đụng nhau).
        Trả về zoneId được chọn hoặc None nếu thất bại.
        """
        try:
            self.request_zones()
            time.sleep(0.35)
            zones = getattr(self.myChar.mapInfo, "zones", [])
            if not zones:
                time.sleep(0.25)
                zones = getattr(self.myChar.mapInfo, "zones", [])

            if not zones:
                return None

            current_zone = getattr(self.myChar.mapInfo, "zoneID", -1)
            # Lọc các khu còn chỗ trống
            valid_zones = [z for z in zones if getattr(z, "numPlayer", 0) < getattr(z, "maxPlayer", 15)]
            if not valid_zones:
                valid_zones = list(zones)

            min_player_count = min(getattr(z, "numPlayer", 0) for z in valid_zones)

            # Nếu khu đang đứng đã là khu ít người nhất (<= min_player_count)
            # và không bị loại trừ thì giữ nguyên, không đổi đi đâu hết
            curr_obj = next((z for z in valid_zones if getattr(z, "zoneId", -1) == current_zone), None)
            if (
                curr_obj is not None
                and getattr(curr_obj, "numPlayer", 0) <= min_player_count
                and (not excluded_zones or current_zone not in excluded_zones)
            ):
                return current_zone

            # Lọc các khu ứng viên không nằm trong danh sách loại trừ (tránh đụng nhau)
            candidate_zones = [z for z in valid_zones if not excluded_zones or getattr(z, "zoneId", 0) not in excluded_zones]
            if not candidate_zones:
                candidate_zones = valid_zones

            # Sắp xếp tăng dần theo số lượng người
            candidate_zones.sort(key=lambda z: getattr(z, "numPlayer", 0))
            best = candidate_zones[0]
            best_id = getattr(best, "zoneId", 0)

            if best_id != current_zone:
                self.change_zone(best_id)
            return best_id
        except Exception:
            return None

    def request_pet_info(self) -> None:
        """Yêu cầu máy chủ gửi thông tin đệ tử / pet (cmd -107)."""
        self.service.petInfo()

    def set_pet_status(self, status: int) -> None:
        """
        Thay đổi trạng thái đệ tử (cmd -108).
        0: Đi theo, 1: Bảo vệ, 2: Tấn công, 3: Về nhà, 4: Hợp thể, 5: Hợp thể Porata
        """
        self.service.petStatus(status)

    def change_pet_status(self, status: int) -> None:
        """Thay đổi trạng thái đệ tử (alias cho set_pet_status)."""
        self.set_pet_status(status)

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
        - Đặt lại dữ liệu nhân vật
        """
        from .logger import logger
        logger.system("Đang đăng xuất an toàn...", account_tag=self.account_id)
        self.disconnect()
        self.myChar = Char()

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

    def on_disconnected(self, callback: Callable[[], None]) -> None:
        """Lắng nghe sự kiện ngắt kết nối với máy chủ."""
        self.controller.on_disconnected_callbacks.append(callback)

    def on_connection_fail(self, callback: Callable[[], None]) -> None:
        """Lắng nghe sự kiện kết nối máy chủ thất bại."""
        self.controller.on_connection_fail_callbacks.append(callback)

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

    def execute_chain(self, commands: List[str], on_finish: Optional[Callable[[bool, str], None]] = None) -> None:
        """
        Thực thi một chuỗi các hành động liên tiếp trong một background thread.
        Nếu gặp lệnh Xmap, sẽ tự động chờ nhân vật đến đúng map đích rồi mới tiếp tục các bước kế tiếp.
        """
        def _chain_worker():
            from .command_handler import execute_client_command
            tag = getattr(self, "account_id", "Client")
            for idx, cmd in enumerate(commands):
                cmd_clean = cmd.strip()
                if not cmd_clean:
                    continue
                parts = cmd_clean.split()
                head = parts[0].lower()

                if head == "xmap":
                    execute_client_command(self, cmd_clean)
                    time.sleep(0.6)
                    start_t = time.time()
                    timeout = 180.0
                    while (getattr(self.xmap_controller, "is_acting", False) or getattr(self.xmap_controller, "is_running", False)) and (time.time() - start_t < timeout):
                        time.sleep(0.4)
                    time.sleep(1.0)
                elif head == "zone" and len(parts) > 1 and parts[1].lower() in ("min", "least", "itnguoi", "vang"):
                    self.change_to_least_populated_zone()
                    time.sleep(0.6)
                else:
                    execute_client_command(self, cmd_clean)
                    time.sleep(0.5)

            if on_finish:
                try:
                    on_finish(True, f"Đã hoàn thành chuỗi {len(commands)} lệnh cho [{tag}]")
                except Exception:
                    pass

        t = threading.Thread(target=_chain_worker, daemon=True, name=f"ChainWorker-{getattr(self, 'account_id', 'Client')}")
        t.start()

    # --------------------------------------------------------------------------
    # Các hàm hồi sinh nhân vật (Mô phỏng Service.wakeUpFromDead & returnTownFromDead)
    # --------------------------------------------------------------------------
    def is_dead(self) -> bool:
        """Kiểm tra nhân vật có đang trong trạng thái chết hay không."""
        c = self.myChar
        return c.is_dead if c else False

    def revive(self, at_place: bool = False) -> Tuple[bool, str]:
        """
        Gửi lệnh hồi sinh nhân vật:
        - at_place = False: Hồi sinh về nhà / làng (miễn phí, cmd -15).
        - at_place = True: Hồi sinh tại chỗ bằng 1 ngọc (cmd -16).
        """
        if at_place:
            self.service.wakeUpFromDead()
            return True, "Đã gửi lệnh hồi sinh tại chỗ bằng 1 ngọc (cmd -16)!"
        else:
            self.service.returnTownFromDead()
            return True, "Đã gửi lệnh hồi sinh về thành / nhà (cmd -15)!"

    def toggle_auto_revive(self, enable: Optional[bool] = None) -> bool:
        """Bật / Tắt tính năng tự động hồi sinh khi chết."""
        return self.auto_revive_manager.toggle(enable)

    def set_auto_revive_mode(self, mode: str) -> bool:
        """Cài đặt chế độ tự hồi sinh ('gem' = ngọc tại chỗ, 'town' = về thành)."""
        return self.auto_revive_manager.set_mode(mode)

    def get_auto_revive_status(self) -> dict:
        """Lấy thông tin trạng thái Auto Hồi Sinh."""
        return self.auto.get_auto_revive_status()

    def start_auto_use_item(self, item_id: int, interval_minutes: float) -> Tuple[bool, str]:
        """Bắt đầu tự động sử dụng item Template ID theo chu kỳ phút."""
        return self.auto.start_auto_use_item(item_id, interval_minutes)

    def stop_auto_use_item(self) -> Tuple[bool, str]:
        """Dừng tự động dùng item."""
        return self.auto.stop_auto_use_item()

    def get_auto_use_item_status(self) -> dict:
        """Lấy thông tin trạng thái Auto dùng item."""
        return self.auto.get_auto_use_item_status()

    # --------------------------------------------------------------------------
    # Các hàm quản lý và săn Boss (Mô phỏng Mod/Boss.cs)
    # --------------------------------------------------------------------------
    def get_bosses(self) -> List[Boss]:
        """Lấy toàn bộ danh sách Boss đã ghi nhận (tối đa 100)."""
        return self.boss_manager.get_all_bosses()

    def get_alive_bosses(self) -> List[Boss]:
        """Lấy danh sách các Boss hiện đang còn sống."""
        return self.boss_manager.get_alive_bosses()

    def clear_bosses(self) -> None:
        """Xóa toàn bộ lịch sử Boss đã ghi nhận."""
        self.boss_manager.clear()

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
        return self.auto.get_combat_status()

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
        return self.auto.get_hunt_status()

    def set_combo_skills(self, skill_ids: List[int]) -> Tuple[bool, str]:
        """Cài đặt bộ 3 skill xoay vòng để pem boss / tàn sát."""
        return self.auto.set_combo_skills(skill_ids)

    def refresh_char_info(self) -> None:
        """Chủ động gửi yêu cầu cập nhật thông tin nhân vật và đệ tử mới nhất từ máy chủ."""
        try:
            if self.isConnected() and self.myChar and self.myChar.charID != 0:
                self.service.getPlayerMenu(self.myChar.charID)
                if getattr(self.myChar, "pet", None) and getattr(self.myChar.pet, "isHavePet", False):
                    self.service.petInfo()
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # AUTO NHIỆM VỤ BÒ MỘNG HẰNG NGÀY (AUTO QUEST)
    # --------------------------------------------------------------------------
    def start_auto_quest(self) -> None:
        """Bắt đầu auto nhiệm vụ Bò Mộng."""
        self.auto.start_auto_quest()

    def stop_auto_quest(self) -> None:
        """Dừng auto nhiệm vụ Bò Mộng."""
        self.auto.stop_auto_quest()

    def toggle_auto_quest(self) -> bool:
        """Bật / Tắt auto nhiệm vụ Bò Mộng."""
        return self.auto.toggle_auto_quest()

    def get_quest_status(self) -> Dict[str, Any]:
        """Lấy trạng thái auto nhiệm vụ Bò Mộng."""
        return self.auto.get_quest_status()

    # --------------------------------------------------------------------------
    # AUTO CHUỖI NHIỆM VỤ CHÍNH TUYẾN / NHIỆM VỤ MỚI (MAIN TASK)
    # --------------------------------------------------------------------------
    def start_auto_main_task(self) -> Tuple[bool, str]:
        """Bắt đầu auto chuỗi nhiệm vụ chính tuyến."""
        return self.auto.start_auto_main_task()

    def stop_auto_main_task(self) -> Tuple[bool, str]:
        """Dừng auto chuỗi nhiệm vụ chính tuyến."""
        return self.auto.stop_auto_main_task()

    def toggle_auto_main_task(self, enable: Optional[bool] = None) -> bool:
        """Bật / Tắt auto chuỗi nhiệm vụ chính tuyến."""
        return self.auto.toggle_auto_main_task(enable)

    def get_main_task_status(self) -> Dict[str, Any]:
        """Lấy trạng thái chuỗi nhiệm vụ chính tuyến."""
        return self.auto.get_main_task_status()

    # --------------------------------------------------------------------------
    # AUTO SHUTTLE (Di chuyển qua lại giữa 2 map)
    # --------------------------------------------------------------------------
    def start_shuttle(self, map_a: int, map_b: int, rounds: int = 0) -> bool:
        """Bắt đầu tự động di chuyển qua lại giữa 2 map (A <-> B)."""
        return self.auto.start_shuttle(map_a, map_b, rounds)

    def stop_shuttle(self) -> None:
        """Dừng di chuyển qua lại 2 map."""
        self.auto.stop_shuttle()

    def get_shuttle_status(self) -> Dict[str, Any]:
        """Lấy thông tin trạng thái shuttle hiện tại."""
        return self.auto.get_shuttle_status()

    def get_combat_status(self) -> Dict[str, Any]:
        """Lấy thông tin trạng thái chiến đấu và tàn sát."""
        return self.auto.get_combat_status()

    def get_hunt_status(self) -> Dict[str, Any]:
        """Lấy thông tin trạng thái săn Boss."""
        return self.auto.get_hunt_status()

    def get_auto_revive_status(self) -> Dict[str, Any]:
        """Lấy thông tin trạng thái tự động hồi sinh."""
        return self.auto.get_auto_revive_status()

    def get_auto_use_item_status(self) -> Dict[str, Any]:
        """Lấy thông tin trạng thái tự động dùng vật phẩm."""
        return self.auto.get_auto_use_item_status()



