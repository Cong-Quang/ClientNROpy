# -*- coding: utf-8 -*-
"""
Bộ gửi yêu cầu dịch vụ (Service).
Mô phỏng chính xác Service.cs trong C#.
Cung cấp các hàm đóng gói Message và gửi qua Session_ME.
"""

from typing import Optional, List
from .message import Message
from .session import Session_ME
from .char import Char


class Service:
    """
    Service mô phỏng class Service trong C#.
    Đóng gói các hành động của client thành Message gửi lên server.
    """

    instance: Optional["Service"] = None

    def __init__(self):
        self.session: Session_ME = Session_ME.gI()
        self.version: str = "2.1.4"

    @classmethod
    def gI(cls) -> "Service":
        """Singleton getter tương đương Service.gI() trong C#."""
        if cls.instance is None:
            cls.instance = Service()
        return cls.instance

    def messageNotLogin(self, command: int) -> Message:
        m = Message(-29)
        m.writer().writeByte(command)
        return m

    def messageNotMap(self, command: int) -> Message:
        m = Message(-28)
        m.writer().writeByte(command)
        return m

    def messageSubCommand(self, command: int) -> Message:
        m = Message(-30)
        m.writer().writeByte(command)
        return m

    def clientOk(self) -> None:
        """Gửi thông báo Client OK (cmd -28, sub 13) để hoàn tất đồng bộ dữ liệu."""
        try:
            m = self.messageNotMap(13)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] clientOk error: {ex}")

    def setClientType(self, typeClient: int = 4, zoomLevel: int = 2) -> None:
        """Khai báo cấu hình máy khách (mặc định PC headless)."""
        try:
            m = self.messageNotLogin(2)
            m.writer().writeByte(typeClient)   # 4: PC
            m.writer().writeByte(zoomLevel)    # 2: zoom 2
            m.writer().writeBoolean(False)
            m.writer().writeInt(1024)          # Canvas.w
            m.writer().writeInt(600)           # Canvas.h
            m.writer().writeBoolean(True)      # isQwerty
            m.writer().writeBoolean(False)     # isTouch
            m.writer().writeUTF(f"Pc platform xxx|{self.version}")
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] setClientType error: {ex}")

    def getResource(self, action: int = 3, vResourceIndex: Optional[List[int]] = None) -> None:
        """
        Gửi gói tin tài nguyên (-74).
        action=3: Hoàn tất / bỏ qua tải tài nguyên (dành cho headless simulation).
        """
        try:
            m = Message(-74)
            m.writer().writeByte(action)
            if action == 2 and vResourceIndex is not None:
                m.writer().writeShort(len(vResourceIndex))
                for idx in vResourceIndex:
                    m.writer().writeShort(idx)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] getResource error: {ex}")

    def login(self, username: str, password: str, version: Optional[str] = None, type_login: int = 0) -> None:
        """Gửi gói tin đăng nhập tài khoản."""
        try:
            ver = version or self.version
            from .controller import Controller
            Controller.gI().last_login_creds = (username, password, ver)
            print(f"[Service] Logging in as '{username}' (version {ver})...")
            m = self.messageNotLogin(0)
            m.writer().writeUTF(username)
            m.writer().writeUTF(password)
            m.writer().writeUTF(ver)
            m.writer().writeByte(type_login)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] login error: {ex}")

    def selectCharToPlay(self, charname: str) -> None:
        """Chọn nhân vật để vào thế giới game."""
        try:
            print(f"[Service] Selecting character '{charname}' to enter game...")
            m = Message(-28)
            m.writer().writeByte(1)
            m.writer().writeUTF(charname)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] selectCharToPlay error: {ex}")

    def charMove(self, cx: int, cy: int, flying: bool = False) -> None:
        """Gửi tọa độ di chuyển nhân vật."""
        try:
            m = Message(-7)
            m.writer().writeByte(1 if flying else 0)
            m.writer().writeShort(cx)
            m.writer().writeShort(cy)
            self.session.sendMessage(m)
            Char.myCharz().cx = cx
            Char.myCharz().cy = cy
        except Exception as ex:
            print(f"[Service] charMove error: {ex}")

    def chat(self, text: str) -> None:
        """Gửi tin nhắn công cộng trong map."""
        try:
            m = Message(44)
            m.writer().writeUTF(text)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] chat error: {ex}")

    def chatGlobal(self, text: str) -> None:
        """Gửi tin nhắn kênh thế giới."""
        try:
            m = Message(-71)
            m.writer().writeUTF(text)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] chatGlobal error: {ex}")

    def chatPlayer(self, text: str, player_id: int) -> None:
        """Chat với người chơi."""
        try:
            m = Message(-72)
            m.writer().writeInt(player_id)
            m.writer().writeUTF(text)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] chatPlayer error: {ex}")

    def chatPrivate(self, to: str, text: str) -> None:
        """Chat mật/riêng tư."""
        try:
            m = Message(91)
            m.writer().writeUTF(to)
            m.writer().writeUTF(text)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] chatPrivate error: {ex}")

    def requestChangeMap(self) -> None:
        """Yêu cầu đổi map qua waypoint."""
        try:
            m = Message(-23)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] requestChangeMap error: {ex}")

    def openUIZone(self) -> None:
        """Yêu cầu danh sách các khu vực (Zone) trong map hiện tại (cmd 29)."""
        try:
            m = Message(29)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] openUIZone error: {ex}")

    def requestChangeZone(self, zone_id: int, indexUI: int = -1) -> None:
        """Yêu cầu đổi khu vực (zone) (cmd 21 trong Service.cs)."""
        try:
            m = Message(21)
            m.writer().writeByte(zone_id)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] requestChangeZone error: {ex}")

    def magicTree(self, action: int = 1) -> None:
        """
        Tương tác với cây đậu thần (cmd -34).
        action=1: Xem thông tin / menu thu hoạch
        action=2: Thu hoạch đậu
        """
        try:
            m = Message(-34)
            m.writer().writeByte(action)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] magicTree error: {ex}")

    def petInfo(self) -> None:
        """Yêu cầu thông tin đệ tử / pet (cmd -107)."""
        try:
            m = Message(-107)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] petInfo error: {ex}")

    def petStatus(self, status: int) -> None:
        """
        Thay đổi trạng thái đệ tử (cmd -108).
        0: Đi theo, 1: Bảo vệ, 2: Tấn công, 3: Về nhà, 4: Hợp thể, 5: Hợp thể Porata
        """
        try:
            m = Message(-108)
            m.writer().writeByte(status)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] petStatus error: {ex}")

    def sendCheckController(self) -> None:
        """Phản hồi ping controller (-120)."""
        try:
            m = Message(-120)
            self.session.sendMessage(m)
        except Exception:
            pass

    def sendCheckMap(self) -> None:
        """Phản hồi ping map (-121)."""
        try:
            m = Message(-121)
            self.session.sendMessage(m)
        except Exception:
            pass

    def openMenu(self, npcId: int) -> None:
        """Mở menu tương tác NPC (cmd 33 trong C# Service.cs)."""
        try:
            m = Message(33)
            m.writer().writeShort(npcId)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] openMenu error: {ex}")

    def confirmMenu(self, npcId: int, select: int) -> None:
        """Chọn dòng tuỳ chọn trong menu NPC (cmd 32 trong C# Service.cs)."""
        try:
            m = Message(32)
            m.writer().writeShort(npcId)
            m.writer().writeByte(select)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] confirmMenu error: {ex}")

    def requestMapSelect(self, selected: int) -> None:
        """Gửi yêu cầu chọn map từ panel danh sách map / capsule (cmd -91 trong C# Service.cs)."""
        try:
            m = Message(-91)
            m.writer().writeByte(selected)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] requestMapSelect error: {ex}")

    def getMapOffline(self) -> None:
        """Yêu cầu load map offline / chuyển map không đồng bộ (cmd -33 trong C# Service.cs)."""
        try:
            m = Message(-33)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] getMapOffline error: {ex}")

    def returnTownFromDead(self) -> None:
        """Hồi sinh về làng / nhà khi nhân vật chết (cmd -15 trong C# Service.cs)."""
        try:
            m = Message(-15)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] returnTownFromDead error: {ex}")

    def useItem(self, item_type: int = 0, where: int = 1, index: int = -1, template: int = -1) -> None:
        """Sử dụng vật phẩm trong hành trang (cmd -43 trong C# Service.cs)."""
        try:
            m = Message(-43)
            m.writer().writeByte(item_type)
            m.writer().writeByte(where)
            m.writer().writeByte(index)
            if index == -1:
                m.writer().writeShort(template)
            self.session.sendMessage(m)
        except Exception as ex:
            print(f"[Service] useItem error: {ex}")
