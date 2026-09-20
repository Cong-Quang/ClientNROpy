# -*- coding: utf-8 -*-
"""
Bộ điều khiển xử lý sự kiện mạng (Controller).
Mô phỏng chính xác Controller.cs trong C#.
Đặc biệt: Bỏ qua toàn bộ các gói tin tải tài nguyên (hình ảnh, map tile, icon, âm thanh)
vì chạy môi trường giả lập Headless không cần đồ hoạ.
"""

from typing import Optional, List, Dict, Callable, Any
from .imessage_handler import IMessageHandler
from .message import Message
from .player_data import PlayerData
from .char import Char
from .pet import Pet
from .magic_tree import MagicTree
from .item import Item
from .item_option import ItemOption
from .zone_info import ZoneInfo
from .map_info import MapInfo
from .waypoint import Waypoint
from .mob import Mob
from .item_map import ItemMap
from .service import Service
from .chat_vip import ChatVip
from .task import Task


class Controller(IMessageHandler):
    """
    Controller mô phỏng Controller.cs trong C#.
    Tiếp nhận và bóc tách các gói tin server gửi về.
    """

    me: Optional["Controller"] = None

    def __init__(self, client: Optional[Any] = None):
        self.client: Optional[Any] = client
        self.isConnectOK: bool = False
        self.isConnectionFail: bool = False
        self.isDisconnected: bool = False
        self.isMain: bool = True
        self.isStopReadMessage: bool = False
        self.debug: bool = False
        self.playerDataList: List[PlayerData] = []

        # Các callback đăng ký từ bên ngoài
        self.on_login_ok_callbacks: List[Callable[[List[PlayerData]], None]] = []
        self.on_chat_callbacks: List[Callable[[int, str], None]] = []
        self.on_server_message_callbacks: List[Callable[[str], None]] = []
        self.on_char_info_callbacks: List[Callable[[Char], None]] = []
        self.on_char_in_map_callbacks: List[Callable[[Char], None]] = []
        self.on_map_info_callbacks: List[Callable[[MapInfo], None]] = []
        self.on_zone_info_callbacks: List[Callable[[List[ZoneInfo]], None]] = []
        self.on_bag_update_callbacks: List[Callable[[List[Item]], None]] = []
        self.on_pet_info_callbacks: List[Callable[[Pet], None]] = []
        self.on_magic_tree_callbacks: List[Callable[[MagicTree], None]] = []
        self.on_cooldown_callbacks: List[Callable[[int], None]] = []
        self.server_wait_time: int = 0
        self.on_chat_vip_callbacks: List[Callable[[ChatVip], None]] = []
        self.on_chat_world_callbacks: List[Callable[[str], None]] = []
        self.chat_vip_list: List[ChatVip] = []
        self.capsule_map_names: List[str] = []
        self.capsule_planet_names: List[str] = []
        self.on_capsule_maps_callbacks: List[Callable[[List[str], List[str]], None]] = []
        # Callback menu NPC (cmd 32: npc_template_id, chat_text, menu_options)
        self.on_npc_menu_callbacks: List[Callable[[int, str, List[str]], None]] = []
        # Callback quái bị hạ (mob_template_id)
        self.on_mob_killed_callbacks: List[Callable[[int], None]] = []
        # Callback tàu vũ trụ / tàu thời gian (cmd -105: max_time, trans_type)
        self.on_transport_callbacks: List[Callable[[int, int], None]] = []
        # Callback nhiệm vụ chính tuyến Task (cmd 40, 41, 43)
        self.on_task_callbacks: List[Callable[[Task], None]] = []
        # Callback tin nhắn chat từ đệ tử
        self.on_pet_chat_callbacks: List[Callable[[str], None]] = []
        # Callback mất kết nối và kết nối thất bại
        self.on_disconnected_callbacks: List[Callable[[], None]] = []
        self.on_connection_fail_callbacks: List[Callable[[], None]] = []

    @property
    def myChar(self) -> Char:
        if self.client and hasattr(self.client, "myChar") and self.client.myChar is not None:
            return self.client.myChar
        return Char.myCharz()

    @property
    def service(self):
        if self.client and hasattr(self.client, "service") and self.client.service is not None:
            return self.client.service
        from .service import Service
        return Service.gI()

    @property
    def account_tag(self) -> str:
        if self.client and hasattr(self.client, "account_id") and self.client.account_id:
            return self.client.account_id
        return "Client"

    @classmethod
    def gI(cls) -> "Controller":
        """Singleton getter tương đương Controller.gI() trong C#."""
        if cls.me is None:
            cls.me = Controller()
        return cls.me

    def onConnectOK(self, isMain: bool) -> None:
        self.isConnectOK = True
        self.isDisconnected = False
        self.isConnectionFail = False
        self.isMain = isMain
        from .logger import logger
        logger.system("Kết nối tới máy chủ thành công! Đang thiết lập kết nối...", account_tag=self.account_tag)
        self.service.setClientType()

    def onConnectionFail(self, isMain: bool) -> None:
        self.isConnectionFail = True
        self.isConnectOK = False
        from .logger import logger
        logger.error("Kết nối tới máy chủ thất bại!", account_tag=self.account_tag)
        for cb in list(self.on_connection_fail_callbacks):
            try:
                cb()
            except Exception as ex:
                logger.debug(f"[Controller] onConnectionFail error: {ex}", account_tag=self.account_tag)

    def onDisconnected(self, isMain: bool) -> None:
        self.isDisconnected = True
        self.isConnectOK = False
        from .logger import logger
        logger.warn("Đã ngắt kết nối với máy chủ!", account_tag=self.account_tag)
        for cb in list(self.on_disconnected_callbacks):
            try:
                cb()
            except Exception as ex:
                logger.debug(f"[Controller] onDisconnected error: {ex}", account_tag=self.account_tag)

    def read_item(self, reader) -> Optional[Item]:
        """Bóc tách cấu trúc 1 Item và các ItemOption đính kèm tương tự C#."""
        template_id = reader.readShort()
        if template_id == -1:
            return None
        item = Item(template_id=template_id)
        item.quantity = reader.readInt()
        item.info = reader.readUTF()
        item.content = reader.readUTF()
        opt_count = reader.readUnsignedByte()
        if opt_count > 0:
            for _ in range(opt_count):
                opt_id = reader.readUnsignedByte()
                param = reader.readUnsignedShort()
                if opt_id != -1:
                    item.addOption(opt_id, param)
        return item

    def _handle_npc_menu(self, msg: Message) -> None:
        """Xử lý thông tin menu NPC (cmd 32, OpenMenu trong C#)."""
        try:
            t_id = msg.reader().readShort()
            text = msg.reader().readUTF()
            size = msg.reader().readByte()
            options = []
            for _ in range(size):
                options.append(msg.reader().readUTF())
            
            from .logger import logger
            logger.debug(f"[Controller] Nhận menu từ NPC {t_id}: {options}", account_tag=self.account_tag)
            
            for cb in self.on_npc_menu_callbacks:
                try:
                    cb(t_id, text, options)
                except Exception as ex:
                    logger.debug(f"[Controller] on_npc_menu callback error: {ex}", account_tag=self.account_tag)
        except Exception as ex:
            from .logger import logger
            logger.debug(f"[Controller] _handle_npc_menu error: {ex}", account_tag=self.account_tag)

    def onMessage(self, msg: Message) -> None:
        cmd = msg.command
        if self.debug:
            from .logger import logger
            logger.debug(f"[RECV CMD] cmd={cmd}", account_tag=self.account_tag)
        try:
            # ------------------------------------------------------------------
            # BỎ QUA GÓI TIN TÀI NGUYÊN (Hình ảnh, map tiles, icon, effect data)
            # Theo yêu cầu giả lập Headless: không tải đồ hoạ, tiết kiệm băng thông
            # ------------------------------------------------------------------
            if cmd == -74:
                try:
                    b_act = msg.reader().readByte()
                    if b_act == 0:
                        self.service.getResource(3, None)
                except Exception:
                    pass
                return

            if cmd in (66, -87, -67, -66, -32, 11, -111, -114, -77, -78):
                return

            # ------------------------------------------------------------------
            # 1. PING / HEARTBEAT
            # ------------------------------------------------------------------
            if cmd == -120:
                self.service.sendCheckController()
                return
            if cmd == -121:
                self.service.sendCheckMap()
                return

            # ------------------------------------------------------------------
            # 2. CẤU HÌNH VÀ SUBCOMMANDS
            # ------------------------------------------------------------------
            if cmd == -29:
                self.messageNotLogin(msg)
                return
            if cmd == -28:
                self.messageNotMap(msg)
                return
            if cmd == -30:
                self.messageSubCommand(msg)
                return

            # ------------------------------------------------------------------
            # 3. ĐĂNG NHẬP THÀNH CÔNG (Danh sách nhân vật)
            # ------------------------------------------------------------------
            if cmd == 0:
                self.readLogin(msg)
                return

            # ------------------------------------------------------------------
            # 3b. HÀNG ĐỢI / CHỜ ĐĂNG NHẬP (cmd 122: second login countdown)
            # ------------------------------------------------------------------
            if cmd == 122:
                time_wait = msg.reader().readShort()
                self.server_wait_time = time_wait
                from .logger import logger
                logger.system(f"Hàng đợi server: chờ {time_wait}s. Tự động đăng nhập lại sau {time_wait}s...", account_tag=self.account_tag)
                for cb in self.on_cooldown_callbacks:
                    try:
                        cb(time_wait)
                    except Exception as ex:
                        logger.debug(f"[Controller] on_cooldown_callback error: {ex}", account_tag=self.account_tag)
                if hasattr(self, "last_login_creds") and self.last_login_creds:
                    u, p, v = self.last_login_creds
                    def delayed_relogin():
                        import time
                        time.sleep(time_wait + 0.5)
                        logger.system(f"Đang tự động đăng nhập lại cho '{u}'...", account_tag=self.account_tag)
                        self.service.login(u, p, version=v)
                    import threading
                    threading.Thread(target=delayed_relogin, daemon=True).start()
                return

            # ------------------------------------------------------------------
            # 3c. TÀI KHOẢN CHƯA CÓ NHÂN VẬT (cmd 2: CreateCharScr)
            # ------------------------------------------------------------------
            if cmd == 2:
                from .logger import logger
                logger.alert("Đăng nhập thành công nhưng tài khoản chưa tạo nhân vật!", account_tag=self.account_tag)
                for cb in self.on_server_message_callbacks:
                    cb("Tài khoản chưa có nhân vật. Cần tạo nhân vật mới.")
                return

            # ------------------------------------------------------------------
            # 4. THÔNG BÁO / DIALOG TỪ SERVER (-26, -25, 94)
            # ------------------------------------------------------------------
            if cmd in (-26, -25, 94):
                text = msg.reader().readUTF()
                for cb in self.on_server_message_callbacks:
                    try:
                        cb(text)
                    except Exception:
                        pass
                return

            # ------------------------------------------------------------------
            # 4b. CHAT VIP / THÔNG BÁO BOSS / TIN THẾ GIỚI (cmd 93 - CHAT_VIP)
            # ------------------------------------------------------------------
            if cmd == 93:
                raw_chat = msg.reader().readUTF()
                chat_vip = ChatVip.parse(raw_chat)
                self.chat_vip_list.append(chat_vip)
                for cb in self.on_chat_vip_callbacks:
                    try:
                        cb(chat_vip)
                    except Exception as ex:
                        pass
                return

            # ------------------------------------------------------------------
            # 4c. MÀN HÌNH TÀU VŨ TRỤ / TÀU THỜI GIAN (cmd -105: TransportScr)
            # ------------------------------------------------------------------
            if cmd == -105:
                try:
                    max_time = msg.reader().readShort()
                    trans_type = msg.reader().readByte()
                    for cb in self.on_transport_callbacks:
                        try:
                            cb(max_time, trans_type)
                        except Exception as ex:
                            from .logger import logger
                            logger.debug(f"[Controller] on_transport_callback error: {ex}", account_tag=self.account_tag)
                except Exception as ex:
                    from .logger import logger
                    logger.debug(f"[Controller] cmd -105 parse error: {ex}", account_tag=self.account_tag)
                return

            # ------------------------------------------------------------------
            # 4c. CHAT THẾ GIỚI MÁY CHỦ (cmd 92 - CHAT_THEGIOI_SERVER)
            # ------------------------------------------------------------------
            if cmd == 92:
                text = msg.reader().readUTF()
                from .logger import logger
                logger.chat(f"[THẾ GIỚI] {text}", account_tag=self.account_tag)
                for cb in self.on_chat_world_callbacks:
                    try:
                        cb(text)
                    except Exception:
                        pass
                return

            # ------------------------------------------------------------------
            # 4d. TIN NHẮN LỚN TỪ HỆ THỐNG / SƯ PHỤ (cmd -70 - BIG_MESSAGE)
            # ------------------------------------------------------------------
            if cmd == -70:
                avatar_id = msg.reader().readShort()
                chat_t1 = msg.reader().readUTF()
                chat_t2 = msg.reader().readUTF()
                from .logger import logger
                logger.debug(f"[BIG MESSAGE (Avatar {avatar_id})] {chat_t1} - {chat_t2}", account_tag=self.account_tag)
                for cb in self.on_server_message_callbacks:
                    try:
                        cb(f"{chat_t1} - {chat_t2}")
                    except Exception:
                        pass
                return

            # ------------------------------------------------------------------
            # 4e. DANH SÁCH MAP CAPSULE / MAP TRANS (cmd -91)
            # ------------------------------------------------------------------
            if cmd == -91:
                count = msg.reader().readByte()
                self.capsule_map_names.clear()
                self.capsule_planet_names.clear()
                for _ in range(count):
                    self.capsule_map_names.append(msg.reader().readUTF())
                    self.capsule_planet_names.append(msg.reader().readUTF())
                if self.debug:
                    from .logger import logger
                    logger.debug(f"[Controller] Capsule map list ({count} maps): {self.capsule_map_names}", account_tag=self.account_tag)
                for cb in self.on_capsule_maps_callbacks:
                    try:
                        cb(self.capsule_map_names, self.capsule_planet_names)
                    except Exception:
                        pass
                return

            # ------------------------------------------------------------------
            # 5. TIN NHẮN CHAT TRONG BẢN ĐỒ (cmd 44)
            # ------------------------------------------------------------------
            if cmd == 44:
                char_id = msg.reader().readInt()
                text = msg.reader().readUTF()
                from .logger import logger
                logger.chat(f"[{char_id}]: {text}", account_tag=self.account_tag)
                for cb in self.on_chat_callbacks:
                    cb(char_id, text)

                # Kiểm tra nếu là chat từ đệ tử (ID âm của charID hoặc đệ kêu lười)
                is_pet_chat = False
                if self.myChar and self.myChar.charID != 0:
                    if char_id == -self.myChar.charID:
                        is_pet_chat = True
                lower_text = text.lower()
                if "lười" in lower_text or "luoi the" in lower_text or "lười thế" in lower_text:
                    is_pet_chat = True

                if is_pet_chat:
                    for cb in self.on_pet_chat_callbacks:
                        try:
                            cb(text)
                        except Exception:
                            pass
                return

            # ------------------------------------------------------------------
            # 5b. NHIỆM VỤ CHÍNH TUYẾN TASK (cmd 40, 41, 43)
            # ------------------------------------------------------------------
            if cmd == 40:
                try:
                    task_id = msg.reader().readShort()
                    index = msg.reader().readByte()
                    name = msg.reader().readUTF()
                    detail = msg.reader().readUTF()
                    n_sub = msg.reader().readByte()
                    sub_names = []
                    sub_tasks = []
                    map_tasks = []
                    content_info = []
                    for _ in range(n_sub):
                        s_name = msg.reader().readUTF()
                        s_type = msg.reader().readByte()
                        m_id = msg.reader().readShort()
                        c_info = msg.reader().readUTF()
                        sub_names.append(s_name)
                        sub_tasks.append(s_type)
                        map_tasks.append(m_id)
                        content_info.append(c_info)

                    count = -1
                    counts = []
                    try:
                        count = msg.reader().readShort()
                        for _ in range(n_sub):
                            counts.append(msg.reader().readShort())
                    except Exception:
                        pass

                    old_task_id = getattr(self.myChar, "ctaskId", -1)
                    old_task_index = getattr(self.myChar.task, "index", -1) if (self.myChar and self.myChar.task) else -1
                    is_new_task = (self.myChar.task is None) or (old_task_id != task_id) or (old_task_index != index)

                    new_task = Task(
                        task_id=task_id,
                        index=index,
                        name=name,
                        detail=detail,
                        sub_names=sub_names,
                        counts=counts,
                        count=count,
                        content_info=content_info,
                        map_tasks=map_tasks,
                        task_types=sub_tasks,
                    )
                    self.myChar.task = new_task
                    self.myChar.ctaskId = task_id
                    self.myChar.task_name = new_task.clean_name

                    if is_new_task:
                        from .logger import logger
                        prog_info = f" - {new_task.progress_str}" if new_task.progress_str else ""
                        logger.system(f"Nhận nhiệm vụ: [{task_id}] {new_task.clean_name}{prog_info} (Bước {index + 1}/{max(1, n_sub)})", account_tag=self.account_tag)

                    for cb in self.on_task_callbacks:
                        try:
                            cb(new_task)
                        except Exception:
                            pass
                except Exception as ex:
                    from .logger import logger
                    logger.debug(f"[Controller] CMD 40 TASK_GET error: {ex}", account_tag=self.account_tag)
                return

            if cmd == 41:
                try:
                    if self.myChar.task:
                        self.myChar.task.index += 1
                        self.myChar.task.count = 0
                        from .logger import logger
                        prog_info = f": {self.myChar.task.progress_str}" if self.myChar.task.progress_str else ""
                        logger.system(f"Nhiệm vụ bước tiếp theo: Bước {self.myChar.task.index + 1}{prog_info}", account_tag=self.account_tag)
                        for cb in self.on_task_callbacks:
                            try:
                                cb(self.myChar.task)
                            except Exception:
                                pass
                except Exception as ex:
                    from .logger import logger
                    logger.debug(f"[Controller] CMD 41 TASK_NEXT error: {ex}", account_tag=self.account_tag)
                return

            if cmd == 43:
                try:
                    count = msg.reader().readShort()
                    if self.myChar.task:
                        self.myChar.task.count = count
                        from .logger import logger
                        prog_info = f": {self.myChar.task.progress_str}" if self.myChar.task.progress_str else f": {count}"
                        logger.system(f"Cập nhật nhiệm vụ{prog_info}", account_tag=self.account_tag)
                        for cb in self.on_task_callbacks:
                            try:
                                cb(self.myChar.task)
                            except Exception:
                                pass
                except Exception as ex:
                    from .logger import logger
                    logger.debug(f"[Controller] CMD 43 TASK_UPDATE error: {ex}", account_tag=self.account_tag)
                return

            # ------------------------------------------------------------------
            # 6. CẬP NHẬT TRANG BỊ TRÊN NGƯỜI (cmd -37)
            # ------------------------------------------------------------------
            if cmd == -37:
                b63 = msg.reader().readByte()
                if b63 == 0:
                    char = self.myChar
                    char.head = msg.reader().readShort()
                    n_body = msg.reader().readUnsignedByte()
                    char.arrItemBody.clear()
                    for _ in range(n_body):
                        it = self.read_item(msg.reader())
                        if it is not None:
                            char.arrItemBody.append(it)
                return

            # ------------------------------------------------------------------
            # 7. CẬP NHẬT HÀNH TRANG BALO (cmd -36)
            # ------------------------------------------------------------------
            if cmd == -36:
                b38 = msg.reader().readByte()
                char = self.myChar
                if b38 == 0:
                    n_bag = msg.reader().readUnsignedByte()
                    char.arrItemBag.clear()
                    for idx in range(n_bag):
                        try:
                            if msg.reader().available() <= 0:
                                break
                            it = self.read_item(msg.reader())
                        except Exception as ex:
                            # Một số server gửi capacity (vd 80) nhưng chỉ liệt kê
                            # slot đã dùng (vd 37) rồi hết buffer -> dừng êm.
                            try:
                                rest = msg.reader().available()
                            except Exception:
                                rest = -1
                            if rest != 0:
                                from .logger import logger
                                logger.debug(f"[Controller] -36 bọc balo lỗi ở slot {idx}/{n_bag}: {ex} (còn {rest} bytes). Giữ {len(char.arrItemBag)} món đã đọc.", account_tag=self.account_tag)
                            break
                        if it is not None:
                            it.index_ui = idx
                            char.arrItemBag.append(it)
                    for cb in self.on_bag_update_callbacks:
                        cb(char.arrItemBag)
                elif b38 == 2:
                    idx = msg.reader().readByte()
                    qty = msg.reader().readInt()
                    for it in char.arrItemBag:
                        if it.index_ui == idx:
                            it.quantity = qty
                            if qty <= 0:
                                char.arrItemBag.remove(it)
                            break
                    for cb in self.on_bag_update_callbacks:
                        cb(char.arrItemBag)
                else:
                    # Biến thể -36 chưa biết: log để bổ sung cấu trúc
                    try:
                        rest = msg.reader().available()
                    except Exception:
                        rest = -1
                    from .logger import logger
                    logger.debug(f"[Controller] -36 sub={b38} chưa hỗ trợ (còn {rest} bytes). Bỏ qua.", account_tag=self.account_tag)
                return

            # ------------------------------------------------------------------
            # 8. CẬP NHẬT RƯƠNG ĐỒ (cmd -35)
            # ------------------------------------------------------------------
            if cmd == -35:
                b35 = msg.reader().readByte()
                char = self.myChar
                if b35 == 0:
                    n_box = msg.reader().readUnsignedByte()
                    char.arrItemBox.clear()
                    for idx in range(n_box):
                        try:
                            if msg.reader().available() <= 0:
                                break
                            it = self.read_item(msg.reader())
                        except Exception:
                            break
                        if it is not None:
                            it.index_ui = idx
                            char.arrItemBox.append(it)
                    for cb in self.on_box_update_callbacks:
                        cb(char.arrItemBox)
                return

            # ------------------------------------------------------------------
            # 9. THÔNG TIN ĐỆ TỬ / PET (cmd -107)
            # ------------------------------------------------------------------
            if cmd == -107:
                b107 = msg.reader().readByte()
                if b107 == 0:
                    pet = self.myChar.pet
                    pet.isHavePet = True
                    pet.cgender = msg.reader().readByte()
                    pet.head = msg.reader().readShort()
                    pet.body = msg.reader().readShort()
                    pet.leg = msg.reader().readShort()
                    pet.cName = msg.reader().readUTF()
                    pet.cHP = msg.reader().readInt()
                    pet.cHPFull = msg.reader().readInt()
                    pet.cMP = msg.reader().readInt()
                    pet.cMPFull = msg.reader().readInt()
                    pet.cDamFull = msg.reader().readInt()
                    pet.cPower = msg.reader().readLong()
                    pet.cTiemNang = msg.reader().readLong()
                    pet.cStamina = msg.reader().readShort()
                    pet.cMaxStamina = msg.reader().readShort()
                    pet.cCriticalFull = msg.reader().readByte()
                    pet.cDefull = msg.reader().readShort()
                    n_skills = msg.reader().readByte()
                    pet.arrPetSkill.clear()
                    for _ in range(n_skills):
                        sk_id = msg.reader().readShort()
                        if sk_id != -1:
                            pet.arrPetSkill.append(sk_id)
                    from .logger import logger
                    logger.debug(f"[Controller] Pet/Disciple loaded: {pet}", account_tag=self.account_tag)
                    for cb in self.on_pet_info_callbacks:
                        cb(pet)
                return

            # ------------------------------------------------------------------
            # 10. THÔNG TIN CÂY ĐẬU THẦN (cmd -34)
            # ------------------------------------------------------------------
            if cmd == -34:
                b10 = msg.reader().readByte()
                char = self.myChar
                if b10 == 0:
                    tree = char.magicTree
                    tree.id = msg.reader().readShort()
                    tree.name = msg.reader().readUTF()
                    tree.x = msg.reader().readShort()
                    tree.y = msg.reader().readShort()
                    tree.level = msg.reader().readByte()
                    tree.currPeas = msg.reader().readShort()
                    tree.maxPeas = msg.reader().readShort()
                    tree.strInfo = msg.reader().readUTF()
                    tree.seconds = msg.reader().readInt()
                    b11 = msg.reader().readByte()
                    for _ in range(b11):
                        msg.reader().readByte()
                        msg.reader().readByte()
                    tree.isUpdate = msg.reader().readBool()
                    from .logger import logger
                    logger.debug(f"[Controller] MagicTree loaded: {tree}", account_tag=self.account_tag)
                    for cb in self.on_magic_tree_callbacks:
                        cb(tree)
                return

            # ------------------------------------------------------------------
            # 11. DANH SÁCH KHU VỰC TRONG BẢN ĐỒ (cmd 29: openUIZone)
            # ------------------------------------------------------------------
            if cmd == 29:
                n_zones = msg.reader().readByte()
                char = self.myChar
                char.mapInfo.zones.clear()
                for _ in range(n_zones):
                    z_id = msg.reader().readByte()
                    pts = msg.reader().readByte()
                    num_p = msg.reader().readByte()
                    max_p = msg.reader().readByte()
                    if msg.reader().readByte() == 1:
                        msg.reader().readUTF()
                        msg.reader().readInt()
                        msg.reader().readUTF()
                        msg.reader().readInt()
                    zone = ZoneInfo(zoneId=z_id, numPlayer=num_p, maxPlayer=max_p, pts=pts)
                    char.mapInfo.zones.append(zone)
                from .logger import logger
                logger.debug(f"[Controller] Zones list loaded: {len(char.mapInfo.zones)} zones", account_tag=self.account_tag)
                for cb in self.on_zone_info_callbacks:
                    cb(char.mapInfo.zones)
                return

            # ------------------------------------------------------------------
            # 12. THÔNG TIN MAP & CÁC THỰC THỂ (cmd -24: loadInfoMap)
            # ------------------------------------------------------------------
            if cmd == -24:
                char = self.myChar
                char.mapInfo.mapID = msg.reader().readUnsignedByte()
                char.mapInfo.planetID = msg.reader().readByte()
                msg.reader().readByte()  # tileID
                msg.reader().readByte()  # bgID
                char.mapInfo.typeMap = msg.reader().readByte()
                char.mapInfo.mapName = msg.reader().readUTF()
                char.mapInfo.zoneID = msg.reader().readByte()

                # Vị trí nhân vật chính
                char.cx = msg.reader().readShort()
                char.cy = msg.reader().readShort()

                char.mapInfo.waypoints.clear()
                char.mapInfo.mobs.clear()
                char.mapInfo.items.clear()
                char.mapInfo.chars.clear()

                # Cổng dịch chuyển (Waypoints)
                num_wp = msg.reader().readByte()
                for _ in range(num_wp):
                    wp = Waypoint(
                        minX=msg.reader().readShort(),
                        minY=msg.reader().readShort(),
                        maxX=msg.reader().readShort(),
                        maxY=msg.reader().readShort(),
                        isEnter=msg.reader().readBoolean(),
                        isOffline=msg.reader().readBoolean(),
                        name=msg.reader().readUTF(),
                    )
                    char.mapInfo.waypoints.append(wp)

                # Quái vật trong map (Mobs)
                num_mobs = msg.reader().readByte()
                for b in range(num_mobs):
                    msg.reader().readBoolean()
                    msg.reader().readBoolean()
                    msg.reader().readBoolean()
                    msg.reader().readBoolean()
                    msg.reader().readBoolean()
                    t_id = msg.reader().readByte()
                    sys = msg.reader().readByte()
                    hp = msg.reader().readInt()
                    lvl = msg.reader().readByte()
                    max_hp = msg.reader().readInt()
                    mx = msg.reader().readShort()
                    my = msg.reader().readShort()
                    status = msg.reader().readByte()
                    lvl_boss = msg.reader().readByte()
                    is_boss = msg.reader().readBoolean()
                    mob = Mob(mobId=b, templateId=t_id, hp=hp, maxHp=max_hp, x=mx, y=my, status=status, isBoss=is_boss)
                    char.mapInfo.mobs[b] = mob

                # Skip loop
                skip_n = msg.reader().readByte()
                for _ in range(skip_n):
                    pass

                # NPCs
                num_npc = msg.reader().readByte()
                char.mapInfo.npcs.clear()
                for _ in range(num_npc):
                    st = msg.reader().readByte()
                    nx = msg.reader().readShort()
                    ny = msg.reader().readShort()
                    nt = msg.reader().readByte()
                    nav = msg.reader().readShort()
                    char.mapInfo.npcs.append({
                        "status": st,
                        "x": nx,
                        "y": ny,
                        "template_id": nt,
                        "avatar": nav,
                    })
                    if nt == 4:
                        char.magicTree.x = nx
                        char.magicTree.y = ny

                # Vật phẩm dưới đất (Items on ground)
                num_items = msg.reader().readByte()
                for _ in range(num_items):
                    itemMapID = msg.reader().readShort()
                    itemTemplateID = msg.reader().readShort()
                    ix = msg.reader().readShort()
                    iy = msg.reader().readShort()
                    pId = msg.reader().readInt()
                    if pId == -2:
                        msg.reader().readShort()
                    char.mapInfo.items[itemMapID] = ItemMap(itemMapID, itemTemplateID, ix, iy, pId)

                try:
                    msg.reader().readByte()  # isMapDouble
                except Exception:
                    pass

                from .logger import logger
                logger.debug(f"Map loaded: {char.mapInfo}", account_tag=self.account_tag)
                try:
                    self.service.finishLoadMap()
                except Exception as ex:
                    logger.debug(f"[Controller] finishLoadMap error: {ex}", account_tag=self.account_tag)
                for cb in list(self.on_map_info_callbacks):
                    try:
                        cb(char.mapInfo)
                    except Exception as ex:
                        logger.debug(f"[Controller] on_map_info callback error: {ex}", account_tag=self.account_tag)
                return

            # ------------------------------------------------------------------
            # 13. NGƯỜI CHƠI KHÁC VÀO BẢN ĐỒ (cmd -5: PLAYER_IN_MAP)
            # ------------------------------------------------------------------
            if cmd == -5:
                charID = msg.reader().readInt()
                clanID = msg.reader().readInt()
                c = Char()
                c.charID = charID
                c.clevel = msg.reader().readByte()
                c.isInvisiblez = msg.reader().readBoolean()
                c.cTypePk = msg.reader().readByte()
                c.nClass = msg.reader().readByte()
                c.cgender = msg.reader().readByte()
                c.head = msg.reader().readShort()
                c.cName = msg.reader().readUTF()
                if c.cName.startswith("$"):
                    c.cName = c.cName[1:]
                    c.isPet = True
                elif c.cName.startswith("#"):
                    c.cName = c.cName[1:]
                    c.isMiniPet = True
                c.cHP = msg.readInt3Byte()
                c.cHPFull = msg.readInt3Byte()
                c.body = msg.reader().readShort()
                c.leg = msg.reader().readShort()
                c.bag = msg.reader().readUnsignedByte()
                msg.reader().readByte()  # wp
                c.cx = msg.reader().readShort()
                c.cy = msg.reader().readShort()
                c.eff5BuffHp = msg.reader().readShort()
                c.eff5BuffMp = msg.reader().readShort()
                num_eff = msg.reader().readByte()
                for _ in range(num_eff):
                    msg.reader().readByte()
                    msg.reader().readInt()
                    msg.reader().readInt()
                    msg.reader().readShort()
                msg.reader().readByte()  # teleport
                c.isMonkey = msg.reader().readByte()
                msg.reader().readShort()  # mount
                c.cFlag = msg.reader().readByte()
                msg.reader().readByte()  # isNhapThe
                try:
                    msg.reader().readShort()  # idAuraEff
                    msg.reader().readSByte()  # idEff_Set_Item
                    msg.reader().readShort()  # idHat
                except Exception:
                    pass
                char = self.myChar
                char.mapInfo.chars[charID] = c
                if self.debug:
                    from .logger import logger
                    logger.debug(f"[Controller] Player entered map: '{c.cName}' (ID={charID}) at ({c.cx},{c.cy})", account_tag=self.account_tag)
                for cb in self.on_char_in_map_callbacks:
                    try:
                        cb(c)
                    except Exception:
                        pass
                return

            # ------------------------------------------------------------------
            # 14. NGƯỜI CHƠI KHÁC RỜI BẢN ĐỒ (cmd -6: PLAYER_OUT_MAP)
            # ------------------------------------------------------------------
            if cmd == -6:
                charID = msg.reader().readInt()
                char = self.myChar
                if charID in char.mapInfo.chars:
                    removed = char.mapInfo.chars.pop(charID)
                    if self.debug:
                        from .logger import logger
                        logger.debug(f"[Controller] Player left map: '{removed.cName}' (ID={charID})", account_tag=self.account_tag)
                    for cb in self.on_char_in_map_callbacks:
                        try:
                            cb(removed)
                        except Exception:
                            pass
                return

            # ------------------------------------------------------------------
            # 15. NGƯỜI CHƠI KHÁC DI CHUYỂN (cmd -7: PLAYER_MOVE)
            # ------------------------------------------------------------------
            if cmd == -7:
                charID = msg.reader().readInt()
                cx = msg.reader().readShort()
                cy = msg.reader().readShort()
                char = self.myChar
                if charID in char.mapInfo.chars:
                    char.mapInfo.chars[charID].cx = cx
                    char.mapInfo.chars[charID].cy = cy
                return

            # ------------------------------------------------------------------
            # 16. VẬT PHẨM RƠI XUỐNG ĐẤT (cmd 68)
            # ------------------------------------------------------------------
            if cmd == 68:
                itemMapID = msg.reader().readShort()
                itemTemplateID = msg.reader().readShort()
                x = msg.reader().readShort()
                y = msg.reader().readShort()
                pId = msg.reader().readInt()
                if pId == -2:
                    msg.reader().readShort()
                char = self.myChar
                char.mapInfo.items[itemMapID] = ItemMap(itemMapID, itemTemplateID, x, y, pId)
                return

            # ------------------------------------------------------------------
            # 17. VẬT PHẨM BIẾN MẤT / BỊ NHẶT (cmd -21, -20, -19)
            # ------------------------------------------------------------------
            if cmd in (-21, -20):
                itemMapID = msg.reader().readShort()
                char = self.myChar
                char.mapInfo.items.pop(itemMapID, None)
                return
            if cmd == -19:
                itemMapID = msg.reader().readShort()
                msg.reader().readInt()  # nhặt bởi player ID
                char = self.myChar
                char.mapInfo.items.pop(itemMapID, None)
                return

            # ------------------------------------------------------------------
            # 18. QUÁI BỊ ĐÁNH / CHẾT / HỒI SINH (cmd -9, -12, -13)
            # ------------------------------------------------------------------
            if cmd == -9:
                mob_idx = msg.reader().readUnsignedByte()
                char = self.myChar
                if mob_idx in char.mapInfo.mobs:
                    char.mapInfo.mobs[mob_idx].hp = msg.readInt3Byte()
                return

            if cmd == -12:
                mob_idx = msg.reader().readUnsignedByte()
                char = self.myChar
                if mob_idx in char.mapInfo.mobs:
                    mob = char.mapInfo.mobs[mob_idx]
                    template_id = getattr(mob, "templateId", -1)
                    mob.hp = 0
                    mob.status = 0
                    for cb in self.on_mob_killed_callbacks:
                        try:
                            cb(template_id)
                        except Exception as ex:
                            if self.debug:
                                from .logger import logger
                                logger.debug(f"[Controller] on_mob_killed callback error: {ex}", account_tag=self.account_tag)
                return

            if cmd == -13:
                mob_idx = msg.reader().readUnsignedByte()
                char = self.myChar
                if mob_idx in char.mapInfo.mobs:
                    m = char.mapInfo.mobs[mob_idx]
                    msg.reader().readByte()  # sys
                    msg.reader().readByte()  # levelBoss
                    m.hp = msg.reader().readInt()
                    m.maxHp = m.hp
                    m.status = 5
                return

            # ------------------------------------------------------------------
            # 18a. CỘNG SỨC MẠNH & TIỀM NĂNG KHI ĐÁNH QUÁI (cmd -3: UP_POWER/TIEMNANG)
            # ------------------------------------------------------------------
            if cmd == -3:
                try:
                    b_type = msg.reader().readByte()
                    val = msg.reader().readInt()
                    char = self.myChar
                    if b_type == 0:
                        char.cPower += val
                    elif b_type == 1:
                        char.cTiemNang += val
                    elif b_type == 2:
                        char.cPower += val
                        char.cTiemNang += val
                    if self.debug:
                        from .logger import logger
                        logger.debug(f"[Controller] UP_POWER: type={b_type}, val=+{val:,} -> Power={char.cPower:,}, TN={char.cTiemNang:,}", account_tag=self.account_tag)
                except Exception as ex:
                    if self.debug:
                        from .logger import logger
                        logger.debug(f"[Controller] cmd -3 parse error: {ex}", account_tag=self.account_tag)
                return

            # ------------------------------------------------------------------
            # 18b. THÔNG TIN SỨC MẠNH / MENU NGƯỜI CHƠI (cmd -79: PLAYER_MENU)
            # ------------------------------------------------------------------
            if cmd == -79:
                try:
                    char_id = msg.reader().readInt()
                    power = msg.reader().readLong()
                    str_level = msg.reader().readUTF()
                    char = self.myChar
                    if char_id == char.charID:
                        char.cPower = power
                        char.currStrLevel = str_level
                        if self.debug:
                            from .logger import logger
                            logger.debug(f"[Controller] PlayerMenu Sync: Power={power:,} ({str_level})", account_tag=self.account_tag)
                    elif char_id in char.mapInfo.chars:
                        target = char.mapInfo.chars[char_id]
                        target.cPower = power
                        target.currStrLevel = str_level
                except Exception as ex:
                    if self.debug:
                        from .logger import logger
                        logger.debug(f"[Controller] cmd -79 parse error: {ex}", account_tag=self.account_tag)
                return

            # ------------------------------------------------------------------
            # 18c. CỘNG VÀNG / YÊN RƠI (cmd -1, -2, 95)
            # ------------------------------------------------------------------
            if cmd in (-1, 95):
                try:
                    num = msg.reader().readInt()
                    self.myChar.xu += num
                except Exception:
                    pass
                return

            if cmd == -2:
                try:
                    num = msg.reader().readInt()
                    # yen += num
                except Exception:
                    pass
                return

            # ------------------------------------------------------------------
            # 18d. NHÂN VẬT TỬ VONG / MẤT SỨC MẠNH (cmd -17: ME_DIE)
            # ------------------------------------------------------------------
            if cmd == -17:
                try:
                    char = self.myChar
                    char.isDie = True
                    char.cHP = 0
                    char.cPk = msg.reader().readByte()
                    msg.reader().readShort()
                    msg.reader().readShort()
                    char.cPower = msg.reader().readLong()
                except Exception:
                    pass
                return

            # ------------------------------------------------------------------
            # 18b. MENU NPC / CHAT POPUP (cmd 32: Bò Mộng, nhiệm vụ...)
            # ------------------------------------------------------------------
            if cmd == 32:
                try:
                    npc_template_id = msg.reader().readShort()
                    chat_text = msg.reader().readUTF()
                    n_opts = msg.reader().readByte()
                    options = []
                    for _ in range(n_opts):
                        options.append(msg.reader().readUTF())
                    try:
                        avatar = msg.reader().readShort()
                    except Exception:
                        avatar = -1
                    if self.debug:
                        from .logger import logger
                        logger.debug(f"[Controller] NPC menu {npc_template_id}: {chat_text[:120]}... opts={options}", account_tag=self.account_tag)
                    for cb in self.on_npc_menu_callbacks:
                        try:
                            cb(npc_template_id, chat_text, options)
                        except Exception as ex:
                            if self.debug:
                                from .logger import logger
                                logger.debug(f"[Controller] on_npc_menu callback error: {ex}", account_tag=self.account_tag)
                except Exception as ex:
                    if self.debug:
                        from .logger import logger
                        logger.debug(f"[Controller] parse NPC menu error: {ex}", account_tag=self.account_tag)
                return

            # ------------------------------------------------------------------
            # 19. CẬP NHẬT TIỀN TỆ (cmd 6)
            # ------------------------------------------------------------------
            if cmd == 6:
                char = self.myChar
                char.xu = msg.reader().readLong()
                char.luong = msg.reader().readInt()
                char.luongKhoa = msg.reader().readInt()
                return

            # ------------------------------------------------------------------
            # 19b. THÔNG TIN CHỈ SỐ BẢN THÂN (cmd -42: MY_INFO / ME_LOAD_INFO)
            # ------------------------------------------------------------------
            if cmd == -42:
                char = self.myChar
                char.cHPGoc = msg.readInt3Byte()
                char.cMPGoc = msg.readInt3Byte()
                char.cDamGoc = msg.reader().readInt()
                char.cHPFull = msg.readInt3Byte()
                char.cMPFull = msg.readInt3Byte()
                char.cHP = msg.readInt3Byte()
                char.cMP = msg.readInt3Byte()
                char.cspeed = msg.reader().readByte()
                msg.reader().readByte()  # hpFrom1000TiemNang
                msg.reader().readByte()  # mpFrom1000TiemNang
                msg.reader().readByte()  # damFrom1000TiemNang
                char.cDamFull = msg.reader().readInt()
                char.cDefull = msg.reader().readInt()
                char.cCriticalFull = msg.reader().readByte()
                char.cTiemNang = msg.reader().readLong()
                char.expForOneAdd = msg.reader().readShort()
                char.cDefGoc = msg.reader().readShort()
                char.cCriticalGoc = msg.reader().readByte()
                try:
                    last = getattr(self, "_last_myinfo_log", None)
                    hp_pct = (char.cHP / char.cHPFull) if char.cHPFull else 1.0
                    mp_pct = (char.cMP / char.cMPFull) if char.cMPFull else 1.0
                    import time as _t
                    now = _t.time()
                    if (last is None or abs(hp_pct - last[0]) >= 0.05 or abs(mp_pct - last[1]) >= 0.05
                            or now - last[2] >= 30.0):
                        self._last_myinfo_log = (hp_pct, mp_pct, now)
                        from .logger import logger
                        logger.debug(f"My Info loaded: HP={char.cHP:,}/{char.cHPFull:,}, MP={char.cMP:,}/{char.cMPFull:,}, Dam={char.cDamFull:,}", account_tag=self.account_tag)
                except Exception:
                    pass
                return

            # ------------------------------------------------------------------
            # 19c. NHÂN VẬT HỒI SINH SỐNG LẠI (cmd 84: LIVE_FROM_DEAD)
            # ------------------------------------------------------------------
            if cmd == 84:
                charID = msg.reader().readInt()
                char = self.myChar
                if charID == char.charID:
                    char.cHP = char.cHPFull
                    char.cMP = char.cMPFull
                    char.cx = msg.reader().readShort()
                    char.cy = msg.reader().readShort()
                    char.statusMe = 1
                elif charID in char.mapInfo.chars:
                    c = char.mapInfo.chars[charID]
                    c.cHP = c.cHPFull
                    c.cMP = c.cMPFull
                    c.cx = msg.reader().readShort()
                    c.cy = msg.reader().readShort()
                    c.statusMe = 1
                return

            # ------------------------------------------------------------------
            # 20. HỒI SINH SỐNG LẠI (cmd -16)
            # ------------------------------------------------------------------
            if cmd == -16:
                c_id = msg.reader().readInt()
                if c_id == self.myChar.charID:
                    c = self.myChar
                    c.isDie = False
                    c.cHP = c.cHPFull
                    c.cMP = c.cMPFull
                    c.cx = msg.reader().readShort()
                    c.cy = msg.reader().readShort()
                    c.statusMe = 1
                return

        except Exception as ex:
            if self.debug:
                from .logger import logger
                logger.debug(f"[Controller] Error parsing message {cmd}: {ex}", account_tag=self.account_tag)

    def readLogin(self, msg: Message) -> None:
        """Đọc danh sách nhân vật sau khi đăng nhập thành công."""
        try:
            count = msg.reader().readByte()
            self.playerDataList.clear()
            from .logger import logger
            logger.debug(f"Login SUCCESS! Number of characters: {count}", account_tag=self.account_tag)
            for _ in range(count):
                player_id = msg.reader().readInt()
                name = msg.reader().readUTF()
                head = msg.reader().readShort()
                body = msg.reader().readShort()
                leg = msg.reader().readShort()
                ppoint = msg.reader().readLong()
                player = PlayerData(player_id, name, head, body, leg, ppoint)
                self.playerDataList.append(player)
                logger.debug(f"  -> {player}", account_tag=self.account_tag)

            if self.on_login_ok_callbacks:
                for cb in self.on_login_ok_callbacks:
                    cb(self.playerDataList)
            elif self.playerDataList:
                self.service.selectCharToPlay(self.playerDataList[0].name)
        except Exception as ex:
            from .logger import logger
            logger.error(f"readLogin error: {ex}", account_tag=self.account_tag)

    def messageNotLogin(self, msg: Message) -> None:
        try:
            sub = msg.reader().readByte()
            if sub == 2:
                link_default = msg.reader().readUTF()
                from .logger import logger
                logger.debug(f"Server LinkDefault: {link_default}", account_tag=self.account_tag)
        except Exception:
            pass

    def messageNotMap(self, msg: Message) -> None:
        try:
            sub = msg.reader().readByte()
            if self.debug:
                from .logger import logger
                logger.debug(f"[Controller] messageNotMap sub={sub}", account_tag=self.account_tag)
            if sub == 4:
                # Báo cho server biết client đã sẵn sàng (bỏ qua tải resource map/data)
                self.service.clientOk()
            elif sub == 35:
                text = msg.reader().readUTF()
                if self.debug:
                    from .logger import logger
                    logger.debug(f"[Controller] NotMap 35: {text}", account_tag=self.account_tag)
        except Exception as ex:
            from .logger import logger
            logger.debug(f"[Controller] messageNotMap error: {ex}", account_tag=self.account_tag)

    def messageSubCommand(self, msg: Message) -> None:
        """Đọc thông tin nhân vật chi tiết, túi đồ, trang bị, rương (cmd -30)."""
        try:
            sub = msg.reader().readByte()
            if self.debug:
                from .logger import logger
                logger.debug(f"[RECV CMD -30] sub={sub}", account_tag=self.account_tag)
            if sub == 0:
                char = self.myChar
                char.charID = msg.reader().readInt()
                char.ctaskId = msg.reader().readByte()
                char.cgender = msg.reader().readByte()
                char.head = msg.reader().readShort()
                char.cName = msg.reader().readUTF()
                char.cPk = msg.reader().readByte()
                char.cTypePk = msg.reader().readByte()
                char.cPower = msg.reader().readLong()
                msg.reader().readShort()  # eff5BuffHp
                msg.reader().readShort()  # eff5BuffMp
                char.nClass = msg.reader().readByte()

                # Danh sách kỹ năng
                n_skills = msg.reader().readByte()
                char.skills.clear()
                for _ in range(n_skills):
                    char.skills.append(msg.reader().readShort())

                # Tiền tệ
                char.xu = msg.reader().readLong()
                char.luongKhoa = msg.reader().readInt()
                char.luong = msg.reader().readInt()

                # 1. Trang bị trên người (arrItemBody)
                char.arrItemBody.clear()
                n_body = msg.reader().readByte()
                for _ in range(n_body):
                    it = self.read_item(msg.reader())
                    if it is not None:
                        char.arrItemBody.append(it)

                # 2. Hành trang Balo (arrItemBag)
                char.arrItemBag.clear()
                n_bag = msg.reader().readByte()
                for l in range(n_bag):
                    it = self.read_item(msg.reader())
                    if it is not None:
                        it.index_ui = l
                        char.arrItemBag.append(it)

                # 3. Rương đồ (arrItemBox)
                char.arrItemBox.clear()
                n_box = msg.reader().readByte()
                for _ in range(n_box):
                    it = self.read_item(msg.reader())
                    if it is not None:
                        char.arrItemBox.append(it)

                char.statusMe = 4

                # Bỏ qua phần header avatar/part mở rộng nếu có
                try:
                    num12 = msg.reader().readShort()
                    for _ in range(num12):
                        msg.reader().readShort()
                        msg.reader().readShort()
                    for _ in range(3):
                        msg.reader().readShort()
                    msg.reader().readByte()  # isNhapThe
                    msg.reader().readInt()   # deltaTime
                    msg.reader().readByte()  # isNewMember
                except Exception:
                    pass

                from .logger import logger
                logger.debug(
                    f"In-game Char loaded: Name='{char.cName}', "
                    f"Power={char.cPower:,}, Xu={char.xu:,}, Luong={char.luong:,} | "
                    f"Body: {len(char.arrItemBody)} items, Bag: {len(char.arrItemBag)} items, Box: {len(char.arrItemBox)} items",
                    account_tag=self.account_tag,
                )

                for cb in self.on_char_info_callbacks:
                    cb(char)
                for cb in self.on_bag_update_callbacks:
                    cb(char.arrItemBag)

            elif sub == 1:
                char = self.myChar
                char.nClass = msg.reader().readByte()
                char.cTiemNang = msg.reader().readLong()

            elif sub == 4:
                char = self.myChar
                char.xu = msg.reader().readLong()
                char.luong = msg.reader().readInt()
                char.cHP = msg.readInt3Byte()
                char.cMP = msg.readInt3Byte()
                char.luongKhoa = msg.reader().readInt()

            elif sub == 5:
                char = self.myChar
                char.cHP = msg.readInt3Byte()

            elif sub == 6:
                # ME_LOAD_MP: cập nhật KI bản thân
                char = self.myChar
                char.cMP = msg.readInt3Byte()

            elif sub == 13:
                # Cập nhật HP người chơi (bản thân hoặc người khác)
                cid = msg.reader().readInt()
                char = self.myChar
                target = char if cid == char.charID else char.mapInfo.chars.get(cid)
                if target is not None:
                    target.cHP = msg.readInt3Byte()
                    target.cHPFull = msg.readInt3Byte()
                    msg.reader().readShort()  # eff5BuffHp
                    msg.reader().readShort()  # eff5BuffMp
                    for cb in self.on_char_in_map_callbacks:
                        try:
                            cb(target)
                        except Exception:
                            pass
                return

            elif sub == 14:
                # HP người chơi khác + hiệu ứng trúng đòn
                cid = msg.reader().readInt()
                char = self.myChar
                target = char.mapInfo.chars.get(cid)
                if target is not None:
                    target.cHP = msg.readInt3Byte()
                    msg.reader().readByte()  # injure type
                    try:
                        target.cHPFull = msg.readInt3Byte()
                    except Exception:
                        pass
                    for cb in self.on_char_in_map_callbacks:
                        try:
                            cb(target)
                        except Exception:
                            pass
                return

            elif sub == 15:
                # Người chơi khác hồi sinh
                cid = msg.reader().readInt()
                char = self.myChar
                target = char.mapInfo.chars.get(cid)
                if target is not None:
                    target.cHP = msg.readInt3Byte()
                    target.cHPFull = msg.readInt3Byte()
                    target.cx = msg.reader().readShort()
                    target.cy = msg.reader().readShort()
                    target.statusMe = 1
                return

            elif sub == 23:
                # Học skill mới -> thêm vào danh sách skill
                char = self.myChar
                sk_id = msg.reader().readShort()
                if sk_id not in char.skills:
                    char.skills.append(sk_id)
                    from .logger import logger
                    logger.debug(f"[Controller] Học skill mới: skillId={sk_id} (tổng {len(char.skills)} skill)", account_tag=self.account_tag)
                return

            elif sub == 35:
                # Cập nhật trạng thái PK
                cid = msg.reader().readInt()
                char = self.myChar
                pk_type = msg.reader().readByte()
                if cid == char.charID:
                    char.cTypePk = pk_type
                elif cid in char.mapInfo.chars:
                    char.mapInfo.chars[cid].cTypePk = pk_type
                return
        except Exception as ex:
            if self.debug:
                from .logger import logger
                logger.debug(f"[Controller] messageSubCommand error: {ex}", account_tag=self.account_tag)
