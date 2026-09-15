# -*- coding: utf-8 -*-
"""
Lớp điều khiển cấp cao (ClientNRO).
Đóng gói toàn bộ kiến trúc Session_ME, Controller, Service
thành một API dễ sử dụng cho các tool và bot game headless.
"""

from typing import Optional, List, Callable, Union
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
