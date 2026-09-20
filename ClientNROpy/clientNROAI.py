# -*- coding: utf-8 -*-
"""
clientNROAI.py - Client NRO Thuần Dành Cho Mô Hình AI Tự Chơi (Headless AI Client)
===================================================================================
Đóng gói độc lập toàn bộ:
1. Mạng & Bắt tay (myReader, myWriter, Message, Sender, MessageCollector, Session_ME)
2. Trao đổi khóa XOR dynamic (cmd -27), Ping/Pong (-120/-121), ClientOk, FinishLoadMap
3. Dữ liệu trạng thái thế giới (Char, Mob, Item, ItemMap, Waypoint, MapInfo, ZoneInfo, PlayerData)
4. Bộ giải mã giao thức mạng Controller & Bộ điều phối lệnh Service
5. Giao diện cấp cao ClientNROAI tối ưu cho mô hình học tăng cường (RL) / LLM Agent:
   - get_state() / get_observation(): Trả về toàn cảnh thế giới game dạng dictionary / tensor-friendly.
   - Các hàm hành động nguyên bản: move_to, attack, pick_item, change_zone, use_item, chat, revive...
   - HOÀN TOÀN KHÔNG chứa các module auto hỗ trợ chơi game (như Xmap, AutoManager, CombatManager, BossHunter...).
"""

import math
import socket
import struct
import sys
import threading
import time
from typing import Optional, List, Dict, Any, Union, Callable

# Đảm bảo console Windows hỗ trợ in Unicode tiếng Việt
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ==============================================================================
# PHẦN 1: BỘ ĐỌC / GHI DỮ LIỆU NHỊ PHÂN & GÓI TIN MẠNG (NETWORK BINARY STACK)
# ==============================================================================

class myReader:
    """Đọc dữ liệu nhị phân kiểu Big-Endian từ byte stream."""

    def __init__(self, data: Optional[Union[bytes, bytearray, List[int]]] = None):
        if data is None:
            self.buffer = bytearray()
        elif isinstance(data, (bytes, bytearray)):
            self.buffer = bytearray(data)
        elif isinstance(data, list):
            self.buffer = bytearray([(b & 0xFF) for b in data])
        else:
            self.buffer = bytearray(data)
        self.posRead: int = 0

    def readSByte(self) -> int:
        if self.posRead < len(self.buffer):
            b = self.buffer[self.posRead]
            self.posRead += 1
            return b if b < 128 else b - 256
        raise EOFError("loi doc sbyte eof")

    def readByte(self) -> int:
        return self.readSByte()

    def readUnsignedByte(self) -> int:
        val = self.readSByte()
        return val if val >= 0 else val + 256

    def readShort(self) -> int:
        if self.posRead + 2 <= len(self.buffer):
            val = struct.unpack(">h", self.buffer[self.posRead:self.posRead + 2])[0]
            self.posRead += 2
            return val
        raise EOFError("loi doc short eof")

    def readUnsignedShort(self) -> int:
        if self.posRead + 2 <= len(self.buffer):
            val = struct.unpack(">H", self.buffer[self.posRead:self.posRead + 2])[0]
            self.posRead += 2
            return val
        raise EOFError("loi doc ushort eof")

    def readInt(self) -> int:
        if self.posRead + 4 <= len(self.buffer):
            val = struct.unpack(">i", self.buffer[self.posRead:self.posRead + 4])[0]
            self.posRead += 4
            return val
        raise EOFError("loi doc int eof")

    def readInt3Byte(self) -> int:
        return self.readInt()

    def readLong(self) -> int:
        if self.posRead + 8 <= len(self.buffer):
            val = struct.unpack(">q", self.buffer[self.posRead:self.posRead + 8])[0]
            self.posRead += 8
            return val
        raise EOFError("loi doc long eof")

    def readBool(self) -> bool:
        return self.readSByte() > 0

    def readBoolean(self) -> bool:
        return self.readBool()

    def readUTF(self) -> str:
        length = self.readShort()
        if length < 0:
            return ""
        if self.posRead + length <= len(self.buffer):
            raw = self.buffer[self.posRead:self.posRead + length]
            self.posRead += length
            return raw.decode("utf-8", errors="replace")
        raise EOFError("loi doc string eof")

    def available(self) -> int:
        return len(self.buffer) - self.posRead

    def close(self) -> None:
        self.buffer = bytearray()
        self.posRead = 0


class myWriter:
    """Ghi dữ liệu nhị phân kiểu Big-Endian vào buffer động."""

    def __init__(self):
        self.buffer = bytearray()
        self.posWrite: int = 0

    def writeSByte(self, value: int) -> None:
        self.buffer.append(value & 0xFF)
        self.posWrite += 1

    def writeByte(self, value: int) -> None:
        self.writeSByte(value)

    def writeUnsignedByte(self, value: int) -> None:
        self.writeSByte(value)

    def writeShort(self, value: int) -> None:
        self.buffer.extend(struct.pack(">h", int(value)))
        self.posWrite += 2

    def writeUnsignedShort(self, value: int) -> None:
        self.buffer.extend(struct.pack(">H", int(value)))
        self.posWrite += 2

    def writeInt(self, value: int) -> None:
        self.buffer.extend(struct.pack(">i", int(value)))
        self.posWrite += 4

    def writeLong(self, value: int) -> None:
        self.buffer.extend(struct.pack(">q", int(value)))
        self.posWrite += 8

    def writeBoolean(self, value: bool) -> None:
        self.writeSByte(1 if value else 0)

    def writeUTF(self, value: str) -> None:
        utf8_bytes = value.encode("utf-8")
        self.writeShort(len(utf8_bytes))
        self.buffer.extend(utf8_bytes)
        self.posWrite += len(utf8_bytes)

    def getData(self) -> Optional[bytes]:
        if len(self.buffer) == 0:
            return None
        return bytes(self.buffer)

    def close(self) -> None:
        self.buffer = bytearray()
        self.posWrite = 0


class Message:
    """Gói tin giao thức DragonBoy: command + dữ liệu nhị phân."""

    def __init__(self, command: int = 0, data: Optional[bytes] = None):
        self.command: int = command if command < 128 else command - 256
        if data is not None:
            self.dis: myReader = myReader(data)
            self.dos: Optional[myWriter] = None
        else:
            self.dis: Optional[myReader] = None
            self.dos: myWriter = myWriter()

    def getData(self) -> Optional[bytes]:
        if self.dos is not None:
            return self.dos.getData()
        return None

    def reader(self) -> myReader:
        if self.dis is None:
            self.dis = myReader(self.getData() or b"")
        return self.dis

    def writer(self) -> myWriter:
        if self.dos is None:
            self.dos = myWriter()
        return self.dos

    def readInt3Byte(self) -> int:
        """Đọc int tương đương readInt3Byte trong C#."""
        return self.reader().readInt()

    def cleanup(self) -> None:
        if self.dis:
            self.dis.close()
        if self.dos:
            self.dos.close()

    def __repr__(self) -> str:
        return f"<Message cmd={self.command}>"


# ==============================================================================
# PHẦN 2: LỚP TRUYỀN DẪN MẠNG & BẮT TAY MÃ HOÁ (NETWORK SESSION & HANDSHAKE)
# ==============================================================================

class Sender:
    """Luồng gửi gói tin lên server với mã hoá XOR dynamic key."""

    def __init__(self, session: "Session_ME"):
        self.session: "Session_ME" = session
        self.sendingMessage: List[Message] = []
        self._lock = threading.Lock()

    def addMessage(self, message: Message) -> None:
        with self._lock:
            self.sendingMessage.append(message)

    def clearSendingMessage(self) -> None:
        with self._lock:
            self.sendingMessage.clear()

    def run(self) -> None:
        while self.session.connected:
            try:
                if self.session.getKeyComplete:
                    while True:
                        msg = None
                        with self._lock:
                            if len(self.sendingMessage) > 0:
                                msg = self.sendingMessage.pop(0)
                        if msg is None:
                            break
                        self.doSendMessage(msg)
                time.sleep(0.005)
            except Exception:
                pass

    def doSendMessage(self, m: Message) -> None:
        try:
            data = m.getData()
            raw_bytes = data if data is not None else b""
            size = len(raw_bytes)

            pkt = bytearray()
            if self.session.getKeyComplete:
                pkt.append(self.session.writeKey(m.command) & 0xFF)
                b1 = self.session.writeKey(size >> 8) & 0xFF
                b2 = self.session.writeKey(size & 0xFF) & 0xFF
                pkt.append(b1)
                pkt.append(b2)
                for byte_val in raw_bytes:
                    pkt.append(self.session.writeKey(byte_val) & 0xFF)
            else:
                pkt.append(m.command & 0xFF)
                pkt.append((size >> 8) & 0xFF)
                pkt.append(size & 0xFF)
                pkt.extend(raw_bytes)

            if self.session.sc is not None:
                self.session.sc.sendall(pkt)
                self.session.sendByteCount += len(pkt)
        except Exception as ex:
            if self.session.connected:
                print(f"[Sender] Lỗi gửi msg {m.command}: {ex}")


class MessageCollector:
    """Luồng nhận TCP stream, bóc tách gói tin và giải mã XOR key."""

    def __init__(self, session: "Session_ME"):
        self.session: "Session_ME" = session

    def _read_exact(self, num_bytes: int) -> bytes:
        data = bytearray()
        while len(data) < num_bytes:
            if not self.session.connected or self.session.sc is None:
                raise ConnectionError("Mất kết nối socket")
            packet = self.session.sc.recv(num_bytes - len(data))
            if not packet:
                raise ConnectionError("Đóng kết nối từ máy chủ")
            data.extend(packet)
        return bytes(data)

    def run(self) -> None:
        try:
            while self.session.connected:
                msg = self.readMessage()
                if msg is not None:
                    try:
                        if msg.command == -27:
                            self.getKey(msg)
                        else:
                            self.session.onRecieveMsg(msg)
                    except Exception as ex:
                        print(f"[MessageCollector] onRecieveMsg error: {ex}")
                else:
                    break
        except Exception:
            pass

        if self.session.connected:
            self.session.connected = False
            if self.session.messageHandler:
                self.session.messageHandler.onDisconnected()
        self.session.cleanNetwork()

    def getKey(self, message: Message) -> None:
        """Bắt tay trao đổi khóa XOR dynamic (cmd -27)."""
        try:
            b = message.reader().readSByte()
            key = [message.reader().readSByte() for _ in range(b)]
            for j in range(len(key) - 1):
                k_val = (key[j + 1] & 0xFF) ^ (key[j] & 0xFF)
                key[j + 1] = k_val if k_val < 128 else k_val - 256

            self.session.key = bytearray([(k & 0xFF) for k in key])
            self.session.curR = 0
            self.session.curW = 0
            self.session.getKeyComplete = True
            print(f"[Session_ME] Bắt tay XOR key thành công! Độ dài key: {len(self.session.key)}")
        except Exception as ex:
            print(f"[Session_ME] Lỗi giải mã XOR key: {ex}")

    def readMessage2(self, cmd: int) -> Message:
        """Đọc gói tin lớn 3 byte length."""
        b1 = self.session.readKey(self._read_exact(1)[0]) + 128
        b2 = self.session.readKey(self._read_exact(1)[0]) + 128
        b3 = self.session.readKey(self._read_exact(1)[0]) + 128
        size = ((b3 * 256) + b2) * 256 + b1

        raw = self._read_exact(size)
        self.session.recvByteCount += 5 + size
        decrypted = bytearray()
        if self.session.getKeyComplete:
            for byte_val in raw:
                decrypted.append(self.session.readKey(byte_val) & 0xFF)
        else:
            decrypted = bytearray(raw)
        return Message(cmd, bytes(decrypted))

    def readMessage(self) -> Optional[Message]:
        try:
            cmd_raw = self._read_exact(1)[0]
            cmd = cmd_raw if cmd_raw < 128 else cmd_raw - 256
            if self.session.getKeyComplete:
                cmd = self.session.readKey(cmd_raw)

            if cmd in (-32, -66, 11, -67, -74, -87, 66):
                return self.readMessage2(cmd)

            len_raw = self._read_exact(2)
            if self.session.getKeyComplete:
                b1 = self.session.readKey(len_raw[0]) & 0xFF
                b2 = self.session.readKey(len_raw[1]) & 0xFF
                size = (b1 << 8) | b2
            else:
                size = struct.unpack(">H", len_raw)[0]

            raw = self._read_exact(size)
            self.session.recvByteCount += 3 + size
            decrypted = bytearray()
            if self.session.getKeyComplete:
                for byte_val in raw:
                    decrypted.append(self.session.readKey(byte_val) & 0xFF)
            else:
                decrypted = bytearray(raw)
            return Message(cmd, bytes(decrypted))
        except Exception:
            return None


class Session_ME:
    """Quản lý kết nối socket TCP và điều phối luồng Sender / MessageCollector."""

    def __init__(self, proxy: Optional[str] = None):
        self.sc: Optional[socket.socket] = None
        self.messageHandler: Optional[Any] = None
        self.connected: bool = False
        self.connecting: bool = False
        self.proxy: Optional[str] = proxy

        self.host: str = ""
        self.port: int = 0

        self.getKeyComplete: bool = False
        self.key: Optional[bytearray] = None
        self.curR: int = 0
        self.curW: int = 0

        self.sendByteCount: int = 0
        self.recvByteCount: int = 0
        self.timeConnected: float = 0.0

        self.sender: Sender = Sender(self)
        self.collector: MessageCollector = MessageCollector(self)
        self.collectorThread: Optional[threading.Thread] = None
        self.sendThread: Optional[threading.Thread] = None
        self.initThread: Optional[threading.Thread] = None

    def isConnected(self) -> bool:
        return self.connected and self.sc is not None

    def setHandler(self, handler: Any) -> None:
        self.messageHandler = handler

    def connect(self, host: str, port: int) -> None:
        if not self.connected and not self.connecting:
            self.host = host
            self.port = port
            self.getKeyComplete = False
            self.close()
            self.initThread = threading.Thread(target=self.networkInit, daemon=True)
            self.initThread.start()

    def networkInit(self) -> None:
        self.connecting = True
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            sock.connect((self.host, self.port))
            sock.settimeout(None)

            self.sc = sock
            self.connected = True
            self.connecting = False
            self.timeConnected = time.time()

            self.sendThread = threading.Thread(target=self.sender.run, daemon=True)
            self.collectorThread = threading.Thread(target=self.collector.run, daemon=True)
            self.sendThread.start()
            self.collectorThread.start()

            # Gửi gói bắt tay lấy key -27 ngay khi kết nối
            self.sender.doSendMessage(Message(-27))

            if self.messageHandler:
                self.messageHandler.onConnectOK()
        except Exception as ex:
            self.connecting = False
            self.connected = False
            print(f"[Session_ME] Lỗi kết nối tới {self.host}:{self.port} -> {ex}")
            if self.messageHandler:
                self.messageHandler.onConnectionFail()

    def sendMessage(self, message: Message) -> None:
        self.sender.addMessage(message)

    def writeKey(self, b: int) -> int:
        if not self.getKeyComplete or self.key is None or len(self.key) == 0:
            return b
        k = self.key[self.curW]
        self.curW = (self.curW + 1) % len(self.key)
        res = (k ^ b) & 0xFF
        return res if res < 128 else res - 256

    def readKey(self, b: int) -> int:
        if not self.getKeyComplete or self.key is None or len(self.key) == 0:
            return b
        k = self.key[self.curR]
        self.curR = (self.curR + 1) % len(self.key)
        res = (k ^ b) & 0xFF
        return res if res < 128 else res - 256

    def onRecieveMsg(self, msg: Message) -> None:
        if self.messageHandler:
            self.messageHandler.onMessage(msg)

    def close(self) -> None:
        self.cleanNetwork()

    def cleanNetwork(self) -> None:
        self.key = None
        self.curR = 0
        self.curW = 0
        self.getKeyComplete = False
        self.connected = False
        self.connecting = False
        self.sender.clearSendingMessage()
        if self.sc is not None:
            try:
                self.sc.close()
            except Exception:
                pass
            self.sc = None


# ==============================================================================
# PHẦN 3: MÔ HÌNH DỮ LIỆU THẾ GIỚI GAME (GAME DATA MODELS)
# ==============================================================================

class ItemOption:
    def __init__(self, opt_id: int = -1, param: int = 0):
        self.id: int = opt_id
        self.param: int = param


class Item:
    def __init__(self, template_id: int = -1, quantity: int = 1):
        self.template_id: int = template_id
        self.quantity: int = quantity
        self.info: str = ""
        self.content: str = ""
        self.options: List[ItemOption] = []
        self.index_ui: int = -1

    def addOption(self, opt_id: int, param: int):
        self.options.append(ItemOption(opt_id, param))


class Mob:
    def __init__(
        self,
        mobId: int = 0,
        templateId: int = 0,
        hp: int = 0,
        maxHp: int = 0,
        x: int = 0,
        y: int = 0,
        status: int = 0,
        isBoss: bool = False,
    ):
        self.mobId: int = mobId
        self.templateId: int = templateId
        self.hp: int = hp
        self.maxHp: int = maxHp
        self.x: int = x
        self.y: int = y
        self.status: int = status
        self.isBoss: bool = isBoss

    @property
    def is_alive(self) -> bool:
        return self.hp > 0 and self.status != 0


class ItemMap:
    def __init__(self, itemMapID: int, itemTemplateID: int, x: int, y: int, playerId: int = -1):
        self.itemMapID: int = itemMapID
        self.itemTemplateID: int = itemTemplateID
        self.x: int = x
        self.y: int = y
        self.playerId: int = playerId


class Waypoint:
    def __init__(
        self,
        minX: int = 0,
        minY: int = 0,
        maxX: int = 0,
        maxY: int = 0,
        isEnter: bool = False,
        isOffline: bool = False,
        name: str = "",
    ):
        self.minX: int = minX
        self.minY: int = minY
        self.maxX: int = maxX
        self.maxY: int = maxY
        self.isEnter: bool = isEnter
        self.isOffline: bool = isOffline
        self.name: str = name


class ZoneInfo:
    def __init__(self, zoneId: int = 0, numPlayer: int = 0, maxPlayer: int = 15, pts: int = 0):
        self.zoneId: int = zoneId
        self.numPlayer: int = numPlayer
        self.maxPlayer: int = maxPlayer
        self.pts: int = pts


class MapInfo:
    def __init__(self):
        self.mapID: int = -1
        self.planetID: int = 0
        self.mapName: str = ""
        self.zoneID: int = -1
        self.typeMap: int = 0
        self.waypoints: List[Waypoint] = []
        self.mobs: Dict[int, Mob] = {}
        self.items: Dict[int, ItemMap] = {}
        self.chars: Dict[int, "Char"] = {}
        self.npcs: List[Dict[str, Any]] = []
        self.zones: List[ZoneInfo] = []


class Pet:
    def __init__(self):
        self.isHavePet: bool = False
        self.cName: str = ""
        self.cgender: int = 0
        self.cHP: int = 0
        self.cHPFull: int = 0
        self.cMP: int = 0
        self.cMPFull: int = 0
        self.cDamFull: int = 0
        self.cPower: int = 0
        self.cTiemNang: int = 0
        self.arrPetSkill: List[int] = []


class MagicTree:
    def __init__(self):
        self.id: int = 0
        self.name: str = ""
        self.x: int = 0
        self.y: int = 0
        self.level: int = 0
        self.currPeas: int = 0
        self.maxPeas: int = 0
        self.strInfo: str = ""
        self.seconds: int = 0


class PlayerData:
    def __init__(self, player_id: int, name: str, head: int, body: int, leg: int, ppoint: int):
        self.player_id: int = player_id
        self.name: str = name
        self.head: int = head
        self.body: int = body
        self.leg: int = leg
        self.ppoint: int = ppoint

    def __repr__(self) -> str:
        return f"<PlayerData ID={self.player_id}, Name='{self.name}', Power={self.ppoint:,}>"


class Char:
    """Thực thể nhân vật chính hoặc người chơi khác trong map."""

    def __init__(self):
        self.charID: int = 0
        self.cName: str = ""
        self.cx: int = 0
        self.cy: int = 0
        self.cdir: int = 1
        self.cgender: int = 0
        self.head: int = 0
        self.body: int = 0
        self.leg: int = 0

        self.cHP: int = 0
        self.cHPFull: int = 0
        self.cMP: int = 0
        self.cMPFull: int = 0
        self.cDamFull: int = 0
        self.cPower: int = 0
        self.cTiemNang: int = 0
        self.cspeed: int = 5

        self.xu: int = 0
        self.luong: int = 0
        self.luongKhoa: int = 0

        self.isDie: bool = False
        self.isPet: bool = False
        self.isMiniPet: bool = False

        self.skills: List[int] = []
        self.arrItemBody: List[Item] = []
        self.arrItemBag: List[Item] = []
        self.arrItemBox: List[Item] = []

        self.mapInfo: MapInfo = MapInfo()
        self.pet: Pet = Pet()
        self.magicTree: MagicTree = MagicTree()

    @property
    def is_dead(self) -> bool:
        return self.isDie or self.cHP <= 0


# ==============================================================================
# PHẦN 4: SERVICE (BỘ GỬI GÓI TIN LỆNH TỚI MÁY CHỦ)
# ==============================================================================

class ServiceAI:
    """Đóng gói và gửi các hành động của AI lên máy chủ DragonBoy."""

    def __init__(self, session: Session_ME, client: "ClientNROAI"):
        self.session: Session_ME = session
        self.client: "ClientNROAI" = client
        self.version: str = "2.1.4"

    def setClientType(self, typeClient: int = 4, zoomLevel: int = 2) -> None:
        """Khai báo thông số client (PC headless)."""
        m = Message(-29)
        m.writer().writeByte(2)
        m.writer().writeByte(typeClient)
        m.writer().writeByte(zoomLevel)
        m.writer().writeBoolean(False)
        m.writer().writeInt(1024)
        m.writer().writeInt(600)
        m.writer().writeBoolean(True)
        m.writer().writeBoolean(False)
        m.writer().writeUTF(f"Pc platform xxx|{self.version}")
        self.session.sendMessage(m)

    def clientOk(self) -> None:
        """Báo hoàn tất đồng bộ ban đầu (-28, sub 13)."""
        m = Message(-28)
        m.writer().writeByte(13)
        self.session.sendMessage(m)

    def getResource(self, action: int = 3) -> None:
        """Bỏ qua tải tài nguyên hình ảnh (-74)."""
        m = Message(-74)
        m.writer().writeByte(action)
        self.session.sendMessage(m)

    def login(self, username: str, password: str, version: Optional[str] = None) -> None:
        """Đăng nhập tài khoản."""
        ver = version or self.version
        m = Message(-29)
        m.writer().writeByte(0)
        m.writer().writeUTF(username)
        m.writer().writeUTF(password)
        m.writer().writeUTF(ver)
        m.writer().writeByte(0)
        self.session.sendMessage(m)

    def selectCharToPlay(self, charname: str) -> None:
        """Chọn nhân vật để vào map game."""
        m = Message(-28)
        m.writer().writeByte(1)
        m.writer().writeUTF(charname)
        self.session.sendMessage(m)

    def charMove(self, cx: int, cy: int, flying: bool = False) -> None:
        """Gửi toạ độ di chuyển."""
        m = Message(-7)
        m.writer().writeByte(1 if flying else 0)
        m.writer().writeShort(cx)
        m.writer().writeShort(cy)
        self.session.sendMessage(m)
        self.client.myChar.cx = cx
        self.client.myChar.cy = cy

    def finishLoadMap(self) -> None:
        """Báo tải xong map (cmd -39). Máy chủ sẽ gửi danh sách nhân vật/quái trong map."""
        self.session.sendMessage(Message(-39))

    def openUIZone(self) -> None:
        """Yêu cầu danh sách khu vực (cmd 29)."""
        self.session.sendMessage(Message(29))

    def requestChangeZone(self, zone_id: int) -> None:
        """Đổi sang khu vực khác (cmd 21)."""
        m = Message(21)
        m.writer().writeByte(zone_id)
        self.session.sendMessage(m)

    def sendPlayerAttack(self, mob_ids: Optional[List[int]] = None, char_ids: Optional[List[int]] = None) -> None:
        """Gửi lệnh tấn công quái hoặc người chơi."""
        mob_ids = mob_ids or []
        char_ids = char_ids or []
        if not mob_ids and not char_ids:
            return

        cdir = getattr(self.client.myChar, "cdir", 1)
        if mob_ids and char_ids:
            m = Message(-4)
            m.writer().writeByte(len(mob_ids))
            for m_id in mob_ids:
                m.writer().writeByte(m_id)
            for c_id in char_ids:
                m.writer().writeInt(c_id)
            m.writer().writeByte(cdir)
            self.session.sendMessage(m)
        elif mob_ids:
            m = Message(54)
            for m_id in mob_ids:
                m.writer().writeByte(m_id)
            m.writer().writeByte(cdir)
            self.session.sendMessage(m)
        elif char_ids:
            m = Message(-60)
            for c_id in char_ids:
                m.writer().writeInt(c_id)
            m.writer().writeByte(cdir)
            self.session.sendMessage(m)

    def pickItem(self, item_map_id: int) -> None:
        """Nhặt vật phẩm rơi trên đất (cmd -20)."""
        m = Message(-20)
        m.writer().writeShort(item_map_id)
        self.session.sendMessage(m)

    def useItem(self, item_type: int = 0, where: int = 1, index: int = -1, template: int = -1) -> None:
        """Dùng item trong hành trang (cmd -43)."""
        m = Message(-43)
        m.writer().writeByte(item_type)
        m.writer().writeByte(where)
        m.writer().writeByte(index)
        if index == -1:
            m.writer().writeShort(template)
        self.session.sendMessage(m)

    def selectSkill(self, skill_template_id: int) -> None:
        """Chọn skill xuất chiêu (cmd 34)."""
        m = Message(34)
        m.writer().writeShort(skill_template_id)
        self.session.sendMessage(m)

    def chat(self, text: str) -> None:
        """Gửi tin nhắn chat trong bản đồ (cmd 44)."""
        m = Message(44)
        m.writer().writeUTF(text)
        self.session.sendMessage(m)

    def chatGlobal(self, text: str) -> None:
        """Gửi tin nhắn kênh thế giới (cmd -71)."""
        m = Message(-71)
        m.writer().writeUTF(text)
        self.session.sendMessage(m)

    def openMenu(self, npc_id: int) -> None:
        """Mở menu tương tác NPC (cmd 33)."""
        m = Message(33)
        m.writer().writeShort(npc_id)
        self.session.sendMessage(m)

    def confirmMenu(self, npc_id: int, select_index: int) -> None:
        """Chọn dòng tuỳ chọn trong menu NPC (cmd 32)."""
        m = Message(32)
        m.writer().writeShort(npc_id)
        m.writer().writeByte(select_index)
        self.session.sendMessage(m)

    def returnTownFromDead(self) -> None:
        """Hồi sinh về nhà / làng (cmd -15)."""
        self.session.sendMessage(Message(-15))

    def wakeUpFromDead(self) -> None:
        """Hồi sinh tại chỗ bằng ngọc (cmd -16)."""
        self.session.sendMessage(Message(-16))

    def magicTree(self, action: int = 1) -> None:
        """Tương tác cây đậu thần (cmd -34: 1=xem, 2=thu hoạch)."""
        m = Message(-34)
        m.writer().writeByte(action)
        self.session.sendMessage(m)

    def sendCheckController(self) -> None:
        """Phản hồi ping controller (-120)."""
        self.session.sendMessage(Message(-120))

    def sendCheckMap(self) -> None:
        """Phản hồi ping map (-121)."""
        self.session.sendMessage(Message(-121))


# ==============================================================================
# PHẦN 5: CONTROLLER (BỘ TIẾP NHẬN & PHÂN TÁCH GÓI TIN MÁY CHỦ)
# ==============================================================================

class ControllerAI:
    """Tiếp nhận và bóc tách các gói tin từ máy chủ gửi về."""

    def __init__(self, client: "ClientNROAI"):
        self.client: "ClientNROAI" = client
        self.playerDataList: List[PlayerData] = []
        self.on_login_ok_callbacks: List[Callable[[List[PlayerData]], None]] = []
        self.on_map_info_callbacks: List[Callable[[MapInfo], None]] = []
        self.on_chat_callbacks: List[Callable[[int, str], None]] = []
        self.on_npc_menu_callbacks: List[Callable[[int, str, List[str]], None]] = []

    @property
    def myChar(self) -> Char:
        return self.client.myChar

    @property
    def service(self) -> ServiceAI:
        return self.client.service

    def onConnectOK(self) -> None:
        print("[ControllerAI] Kết nối socket TCP thành công! Gửi thiết lập client...")
        self.service.setClientType()

    def onConnectionFail(self) -> None:
        print("[ControllerAI] Kết nối tới máy chủ thất bại!")

    def onDisconnected(self) -> None:
        print("[ControllerAI] Đã ngắt kết nối với máy chủ!")

    def read_item(self, reader: myReader) -> Optional[Item]:
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

    def onMessage(self, msg: Message) -> None:
        cmd = msg.command
        try:
            # 1. Bỏ qua gói tin tải tài nguyên đồ họa (Headless)
            if cmd == -74:
                try:
                    if msg.reader().readByte() == 0:
                        self.service.getResource(3)
                except Exception:
                    pass
                return

            if cmd in (66, -87, -67, -66, -32, 11, -111, -114, -77, -78):
                return

            # 2. Ping / Heartbeat
            if cmd == -120:
                self.service.sendCheckController()
                return
            if cmd == -121:
                self.service.sendCheckMap()
                return

            # 3. Đăng nhập & danh sách nhân vật (cmd 0)
            if cmd == 0:
                count = msg.reader().readByte()
                self.playerDataList.clear()
                print(f"[ControllerAI] Đăng nhập thành công! Có {count} nhân vật:")
                for _ in range(count):
                    p_id = msg.reader().readInt()
                    name = msg.reader().readUTF()
                    head = msg.reader().readShort()
                    body = msg.reader().readShort()
                    leg = msg.reader().readShort()
                    power = msg.reader().readLong()
                    p = PlayerData(p_id, name, head, body, leg, power)
                    self.playerDataList.append(p)
                    print(f"  -> NV: {name} (Power: {power:,})")

                if self.on_login_ok_callbacks:
                    for cb in self.on_login_ok_callbacks:
                        cb(self.playerDataList)
                elif self.playerDataList:
                    # Mặc định tự động chọn nhân vật đầu tiên
                    self.service.selectCharToPlay(self.playerDataList[0].name)
                return

            # 4. Hàng đợi đăng nhập (cmd 122)
            if cmd == 122:
                time_wait = msg.reader().readShort()
                print(f"[ControllerAI] Server báo hàng đợi: vui lòng chờ {time_wait}s.")
                return

            # 5. Cấu hình NotMap (-28)
            if cmd == -28:
                sub = msg.reader().readByte()
                if sub == 4:
                    self.service.clientOk()
                return

            # 6. Thông tin nhân vật và hành trang (cmd -30)
            if cmd == -30:
                sub = msg.reader().readByte()
                if sub == 0:
                    char = self.myChar
                    char.charID = msg.reader().readInt()
                    msg.reader().readByte()  # ctaskId
                    char.cgender = msg.reader().readByte()
                    char.head = msg.reader().readShort()
                    char.cName = msg.reader().readUTF()
                    msg.reader().readByte()  # cPk
                    msg.reader().readByte()  # cTypePk
                    char.cPower = msg.reader().readLong()
                    msg.reader().readShort()
                    msg.reader().readShort()
                    msg.reader().readByte()  # nClass

                    # Danh sách kỹ năng
                    n_skills = msg.reader().readByte()
                    char.skills.clear()
                    for _ in range(n_skills):
                        char.skills.append(msg.reader().readShort())

                    # Tiền tệ
                    char.xu = msg.reader().readLong()
                    char.luongKhoa = msg.reader().readInt()
                    char.luong = msg.reader().readInt()

                    # Trang bị trên người
                    char.arrItemBody.clear()
                    n_body = msg.reader().readByte()
                    for _ in range(n_body):
                        it = self.read_item(msg.reader())
                        if it:
                            char.arrItemBody.append(it)

                    # Balo hành trang
                    char.arrItemBag.clear()
                    n_bag = msg.reader().readByte()
                    for l in range(n_bag):
                        it = self.read_item(msg.reader())
                        if it:
                            it.index_ui = l
                            char.arrItemBag.append(it)

                    # Rương đồ
                    char.arrItemBox.clear()
                    n_box = msg.reader().readByte()
                    for _ in range(n_box):
                        it = self.read_item(msg.reader())
                        if it:
                            char.arrItemBox.append(it)

                    print(f"[ControllerAI] Đã tải nhân vật: '{char.cName}', Sức mạnh: {char.cPower:,}, Vàng: {char.xu:,}")
                elif sub == 4:
                    self.myChar.xu = msg.reader().readLong()
                    self.myChar.luong = msg.reader().readInt()
                    self.myChar.cHP = msg.readInt3Byte()
                    self.myChar.cMP = msg.readInt3Byte()
                elif sub == 5:
                    self.myChar.cHP = msg.readInt3Byte()
                elif sub == 6:
                    self.myChar.cMP = msg.readInt3Byte()
                return

            # 7. Thông tin chi tiết chỉ số bản thân (cmd -42)
            if cmd == -42:
                char = self.myChar
                msg.readInt3Byte()  # cHPGoc
                msg.readInt3Byte()  # cMPGoc
                msg.reader().readInt()  # cDamGoc
                char.cHPFull = msg.readInt3Byte()
                char.cMPFull = msg.readInt3Byte()
                char.cHP = msg.readInt3Byte()
                char.cMP = msg.readInt3Byte()
                char.cspeed = msg.reader().readByte()
                msg.reader().readByte()
                msg.reader().readByte()
                msg.reader().readByte()
                char.cDamFull = msg.reader().readInt()
                return

            # 8. Tải thông tin bản đồ (cmd -24: loadInfoMap)
            if cmd == -24:
                char = self.myChar
                char.mapInfo.mapID = msg.reader().readUnsignedByte()
                char.mapInfo.planetID = msg.reader().readByte()
                msg.reader().readByte()
                msg.reader().readByte()
                char.mapInfo.typeMap = msg.reader().readByte()
                char.mapInfo.mapName = msg.reader().readUTF()
                char.mapInfo.zoneID = msg.reader().readByte()

                char.cx = msg.reader().readShort()
                char.cy = msg.reader().readShort()

                char.mapInfo.waypoints.clear()
                char.mapInfo.mobs.clear()
                char.mapInfo.items.clear()
                char.mapInfo.chars.clear()

                # Cổng chuyển map (Waypoints)
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

                # Quái vật trong map
                num_mobs = msg.reader().readByte()
                for b in range(num_mobs):
                    for _ in range(5):
                        msg.reader().readBoolean()
                    t_id = msg.reader().readByte()
                    msg.reader().readByte()  # sys
                    hp = msg.reader().readInt()
                    msg.reader().readByte()  # lvl
                    max_hp = msg.reader().readInt()
                    mx = msg.reader().readShort()
                    my = msg.reader().readShort()
                    status = msg.reader().readByte()
                    msg.reader().readByte()  # lvl_boss
                    is_boss = msg.reader().readBoolean()
                    mob = Mob(mobId=b, templateId=t_id, hp=hp, maxHp=max_hp, x=mx, y=my, status=status, isBoss=is_boss)
                    char.mapInfo.mobs[b] = mob

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
                    char.mapInfo.npcs.append({"status": st, "x": nx, "y": ny, "template_id": nt, "avatar": nav})

                # Vật phẩm dưới đất
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

                print(f"[ControllerAI] Vào map {char.mapInfo.mapID} ('{char.mapInfo.mapName}') - Khu {char.mapInfo.zoneID} | Vị trí: ({char.cx}, {char.cy}) | Quái: {len(char.mapInfo.mobs)} con")
                self.service.finishLoadMap()

                for cb in self.on_map_info_callbacks:
                    try:
                        cb(char.mapInfo)
                    except Exception:
                        pass
                return

            # 9. Danh sách khu vực (cmd 29)
            if cmd == 29:
                n_zones = msg.reader().readByte()
                self.myChar.mapInfo.zones.clear()
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
                    self.myChar.mapInfo.zones.append(ZoneInfo(zoneId=z_id, numPlayer=num_p, maxPlayer=max_p, pts=pts))
                return

            # 10. Người chơi khác vào map (cmd -5)
            if cmd == -5:
                charID = msg.reader().readInt()
                msg.reader().readInt()  # clanID
                c = Char()
                c.charID = charID
                msg.reader().readByte()
                msg.reader().readBoolean()
                msg.reader().readByte()
                msg.reader().readByte()
                c.cgender = msg.reader().readByte()
                c.head = msg.reader().readShort()
                c.cName = msg.reader().readUTF()
                c.cHP = msg.readInt3Byte()
                c.cHPFull = msg.readInt3Byte()
                c.body = msg.reader().readShort()
                c.leg = msg.reader().readShort()
                msg.reader().readUnsignedByte()
                msg.reader().readByte()
                c.cx = msg.reader().readShort()
                c.cy = msg.reader().readShort()
                self.myChar.mapInfo.chars[charID] = c
                return

            # 11. Người chơi khác rời map (cmd -6)
            if cmd == -6:
                c_id = msg.reader().readInt()
                self.myChar.mapInfo.chars.pop(c_id, None)
                return

            # 12. Người chơi khác di chuyển (cmd -7)
            if cmd == -7:
                c_id = msg.reader().readInt()
                cx = msg.reader().readShort()
                cy = msg.reader().readShort()
                if c_id in self.myChar.mapInfo.chars:
                    self.myChar.mapInfo.chars[c_id].cx = cx
                    self.myChar.mapInfo.chars[c_id].cy = cy
                return

            # 13. Vật phẩm rơi xuống đất (cmd 68)
            if cmd == 68:
                itemMapID = msg.reader().readShort()
                itemTemplateID = msg.reader().readShort()
                x = msg.reader().readShort()
                y = msg.reader().readShort()
                pId = msg.reader().readInt()
                if pId == -2:
                    msg.reader().readShort()
                self.myChar.mapInfo.items[itemMapID] = ItemMap(itemMapID, itemTemplateID, x, y, pId)
                return

            # 14. Vật phẩm bị nhặt hoặc biến mất (-21, -20, -19)
            if cmd in (-21, -20, -19):
                itemMapID = msg.reader().readShort()
                self.myChar.mapInfo.items.pop(itemMapID, None)
                return

            # 15. Quái bị trừ HP / Chết (-9, -12)
            if cmd == -9:
                mob_idx = msg.reader().readUnsignedByte()
                if mob_idx in self.myChar.mapInfo.mobs:
                    self.myChar.mapInfo.mobs[mob_idx].hp = msg.readInt3Byte()
                return

            if cmd == -12:
                mob_idx = msg.reader().readUnsignedByte()
                if mob_idx in self.myChar.mapInfo.mobs:
                    self.myChar.mapInfo.mobs[mob_idx].hp = 0
                    self.myChar.mapInfo.mobs[mob_idx].status = 0
                return

            # 16. Nhân vật tử vong (-17)
            if cmd == -17:
                self.myChar.isDie = True
                self.myChar.cHP = 0
                print("[ControllerAI] Nhân vật đã bị hạ gục (chết)!")
                return

            # 17. Hồi sinh (84, -16)
            if cmd in (84, -16):
                c_id = msg.reader().readInt()
                if c_id == self.myChar.charID:
                    self.myChar.isDie = False
                    self.myChar.cHP = self.myChar.cHPFull
                    self.myChar.cMP = self.myChar.cMPFull
                    print("[ControllerAI] Nhân vật đã hồi sinh thành công!")
                return

            # 18. Tin nhắn chat map (cmd 44)
            if cmd == 44:
                char_id = msg.reader().readInt()
                text = msg.reader().readUTF()
                for cb in self.on_chat_callbacks:
                    try:
                        cb(char_id, text)
                    except Exception:
                        pass
                return

            # 19. Menu NPC (cmd 32)
            if cmd == 32:
                npc_t_id = msg.reader().readShort()
                chat_text = msg.reader().readUTF()
                n_opts = msg.reader().readByte()
                options = [msg.reader().readUTF() for _ in range(n_opts)]
                for cb in self.on_npc_menu_callbacks:
                    try:
                        cb(npc_t_id, chat_text, options)
                    except Exception:
                        pass
                return

            # 20. Thông báo server (-26, -25, 94)
            if cmd in (-26, -25, 94):
                server_text = msg.reader().readUTF()
                print(f"[SERVER]: {server_text}")
                return

        except Exception as ex:
            pass


# ==============================================================================
# PHẦN 6: LỚP ĐIỀU KHIỂN CẤP CAO DÀNH CHO AI (ClientNROAI)
# ==============================================================================

class ClientNROAI:
    """
    ClientNROAI - Client Game DragonBoy Headless thuần phục vụ mô hình AI.
    Cung cấp hàm quan sát get_state() / get_observation() và hàm hành động nguyên bản.
    """

    def __init__(
        self,
        host: str = "51.79.163.109",
        port: int = 12457,
        version: str = "2.1.4",
        proxy: Optional[str] = None,
    ):
        self.host: str = host
        self.port: int = port
        self.version: str = version
        self.proxy: Optional[str] = proxy

        self.session: Session_ME = Session_ME(proxy=proxy)
        self.myChar: Char = Char()
        self.service: ServiceAI = ServiceAI(session=self.session, client=self)
        self.controller: ControllerAI = ControllerAI(client=self)

        # Đăng ký Controller tiếp nhận thông điệp mạng từ Session_ME
        self.session.setHandler(self.controller)

    # --------------------------------------------------------------------------
    # 1. KẾT NỐI & ĐĂNG NHẬP
    # --------------------------------------------------------------------------
    def connect(self, host: Optional[str] = None, port: Optional[int] = None) -> None:
        """Khởi tạo kết nối mạng socket TCP tới server game."""
        t_host = host or self.host
        t_port = port or self.port
        print(f"[ClientNROAI] Đang kết nối tới {t_host}:{t_port}...")
        self.session.connect(t_host, t_port)

    def is_connected(self) -> bool:
        """Kiểm tra socket và phiên mạng còn kết nối hay không."""
        return self.session.isConnected()

    def login(self, username: str, password: str, version: Optional[str] = None) -> None:
        """Gửi thông tin đăng nhập tài khoản."""
        self.service.login(username, password, version or self.version)

    def select_char(self, char_name: str) -> None:
        """Chọn nhân vật theo tên để vào bản đồ."""
        self.service.selectCharToPlay(char_name)

    def disconnect(self) -> None:
        """Ngắt kết nối mạng an toàn."""
        self.session.close()

    # --------------------------------------------------------------------------
    # 2. HÀM QUAN SÁT THẾ GIỚI GAME CHO MÔ HÌNH AI (ENVIRONMENT OBSERVATION)
    # --------------------------------------------------------------------------
    def get_state(self) -> Dict[str, Any]:
        """
        Trả về toàn bộ trạng thái thế giới game hiện tại dưới dạng dictionary
        đã được tính toán sẵn khoảng cách (distance, dx, dy) để mô hình AI dễ dàng
        xử lý vector quan sát (observation space).
        """
        c = self.myChar
        m = c.mapInfo

        # 1. Trạng thái bản thân nhân vật (Self State)
        player_state = {
            "id": c.charID,
            "name": c.cName,
            "x": c.cx,
            "y": c.cy,
            "hp": c.cHP,
            "max_hp": c.cHPFull,
            "hp_percent": round((c.cHP / max(1, c.cHPFull)) * 100, 2),
            "mp": c.cMP,
            "max_mp": c.cMPFull,
            "mp_percent": round((c.cMP / max(1, c.cMPFull)) * 100, 2),
            "power": c.cPower,
            "tiem_nang": c.cTiemNang,
            "damage": c.cDamFull,
            "speed": c.cspeed,
            "xu": c.xu,
            "luong": c.luong,
            "is_dead": c.is_dead,
            "skills": list(c.skills),
        }

        # 2. Thông tin Bản đồ & Khu vực (Map State)
        map_state = {
            "map_id": m.mapID,
            "map_name": m.mapName,
            "zone_id": m.zoneID,
            "waypoints": [
                {
                    "name": wp.name,
                    "x": (wp.minX + wp.maxX) // 2,
                    "y": (wp.minY + wp.maxY) // 2,
                    "dist": round(math.hypot(((wp.minX + wp.maxX) // 2) - c.cx, ((wp.minY + wp.maxY) // 2) - c.cy), 1),
                }
                for wp in m.waypoints
            ],
            "total_mobs": len(m.mobs),
            "total_items": len(m.items),
            "total_players": len(m.chars),
        }

        # 3. Quái vật lân cận (Mobs Observation kèm khoảng cách vector)
        mobs_obs = []
        for mob_id, mob in m.mobs.items():
            dx = mob.x - c.cx
            dy = mob.y - c.cy
            dist = round(math.hypot(dx, dy), 1)
            mobs_obs.append({
                "mob_id": mob_id,
                "template_id": mob.templateId,
                "x": mob.x,
                "y": mob.y,
                "dx": dx,
                "dy": dy,
                "dist": dist,
                "hp": mob.hp,
                "max_hp": mob.maxHp,
                "is_alive": mob.is_alive,
                "is_boss": mob.isBoss,
            })
        # Sắp xếp quái theo khoảng cách gần nhất
        mobs_obs.sort(key=lambda x: x["dist"])

        # 4. Vật phẩm rơi trên đất (Ground Items Observation)
        items_obs = []
        for it_id, it in m.items.items():
            dx = it.x - c.cx
            dy = it.y - c.cy
            dist = round(math.hypot(dx, dy), 1)
            items_obs.append({
                "item_map_id": it_id,
                "template_id": it.itemTemplateID,
                "x": it.x,
                "y": it.y,
                "dx": dx,
                "dy": dy,
                "dist": dist,
                "player_id": it.playerId,
            })
        items_obs.sort(key=lambda x: x["dist"])

        # 5. Người chơi xung quanh (Other Players)
        players_obs = []
        for p_id, other in m.chars.items():
            dx = other.cx - c.cx
            dy = other.cy - c.cy
            dist = round(math.hypot(dx, dy), 1)
            players_obs.append({
                "id": p_id,
                "name": other.cName,
                "x": other.cx,
                "y": other.cy,
                "dx": dx,
                "dy": dy,
                "dist": dist,
                "hp": other.cHP,
                "max_hp": other.cHPFull,
                "is_pet": other.isPet,
            })
        players_obs.sort(key=lambda x: x["dist"])

        # 6. Hành trang túi đồ (Bag Items)
        bag_obs = [
            {
                "index": it.index_ui,
                "template_id": it.template_id,
                "quantity": it.quantity,
                "info": it.info,
            }
            for it in c.arrItemBag
        ]

        return {
            "timestamp": time.time(),
            "player": player_state,
            "map": map_state,
            "mobs": mobs_obs,
            "ground_items": items_obs,
            "other_players": players_obs,
            "bag": bag_obs,
        }

    # --------------------------------------------------------------------------
    # 3. HÀM HÀNH ĐỘNG NGUYÊN BẢN (PRIMITIVE ACTIONS)
    # --------------------------------------------------------------------------
    def move_to(self, x: int, y: int, flying: bool = False) -> None:
        """Di chuyển nhân vật đến toạ độ (x, y)."""
        self.service.charMove(int(x), int(y), flying=flying)

    def attack_mob(self, mob_id: int) -> None:
        """Tấn công quái vật theo ID."""
        self.service.sendPlayerAttack(mob_ids=[mob_id])

    def attack_player(self, char_id: int) -> None:
        """Tấn công người chơi khác theo ID."""
        self.service.sendPlayerAttack(char_ids=[char_id])

    def pick_item(self, item_map_id: int) -> None:
        """Nhặt vật phẩm rơi trên mặt đất."""
        self.service.pickItem(item_map_id)

    def use_item(self, index: int = -1, template_id: int = -1) -> None:
        """Sử dụng vật phẩm trong hành trang theo vị trí slot hoặc template ID."""
        self.service.useItem(where=1, index=index, template=template_id)

    def change_zone(self, zone_id: int) -> None:
        """Đổi sang khu vực (zone) chỉ định trong map."""
        self.service.requestChangeZone(zone_id)

    def request_zones(self) -> None:
        """Yêu cầu danh sách các khu vực hiện có trong map."""
        self.service.openUIZone()

    def chat(self, text: str) -> None:
        """Gửi tin nhắn chat vào bản đồ."""
        self.service.chat(text)

    def chat_global(self, text: str) -> None:
        """Gửi tin nhắn chat kênh thế giới."""
        self.service.chatGlobal(text)

    def open_npc_menu(self, npc_id: int) -> None:
        """Mở menu tương tác NPC."""
        self.service.openMenu(npc_id)

    def select_npc_menu(self, npc_id: int, option_idx: int) -> None:
        """Chọn dòng tuỳ chọn trong menu NPC."""
        self.service.confirmMenu(npc_id, option_idx)

    def revive(self, at_place: bool = False) -> None:
        """
        Hồi sinh nhân vật:
        - at_place = False: Về làng miễn phí.
        - at_place = True: Hồi sinh tại chỗ bằng ngọc.
        """
        if at_place:
            self.service.wakeUpFromDead()
        else:
            self.service.returnTownFromDead()

    def harvest_magic_tree(self) -> None:
        """Thu hoạch đậu thần từ cây đậu."""
        self.service.magicTree(action=2)

    def select_skill(self, skill_template_id: int) -> None:
        """Chọn skill xuất chiêu."""
        self.service.selectSkill(skill_template_id)


# ==============================================================================
# PHẦN 7: KHỐI CHẠY THỬ NGHIỆM ĐỘC LẬP (TEST RUNNER)
# ==============================================================================

def test_ai_client(username: str = "poopooi02", password: str = "02082003", host: str = "51.79.163.109", port: int = 12457):
    """Hàm kiểm thử kết nối, bắt tay, đăng nhập và xuất trạng thái game cho AI."""
    print("=" * 70)
    print(f"[*] BẮT ĐẦU TEST CLIENT NRO AI: '{username}' tại {host}:{port}")
    print("=" * 70)

    client = ClientNROAI(host=host, port=port)
    client.connect()

    # Chờ kết nối và bắt tay XOR key (-27)
    time.sleep(1.0)
    if not client.is_connected():
        print("[!] Không thể kết nối tới server.")
        return

    # Gửi yêu cầu đăng nhập
    client.login(username, password)

    # Chờ phản hồi đăng nhập và vào map (tối đa 10s)
    start_wait = time.time()
    while time.time() - start_wait < 10.0:
        time.sleep(0.5)
        if client.myChar.mapInfo.mapID >= 0:
            break

    if client.myChar.mapInfo.mapID < 0:
        print("[!] Chưa vào được map trong thời gian chờ.")
    else:
        print("\n" + "=" * 70)
        print("[+] ĐÃ VÀO THẾ GIỚI GAME THÀNH CÔNG!")
        print("=" * 70)

        # Lấy trạng thái quan sát (Observation) cho AI
        state = client.get_state()
        print("\n--- BẢNG QUAN SÁT (OBSERVATION STATE) DÀNH CHO AI MODEL ---")
        print(f"1. Nhân vật: {state['player']['name']} | HP: {state['player']['hp']}/{state['player']['max_hp']} ({state['player']['hp_percent']}%) | Vị trí: ({state['player']['x']}, {state['player']['y']})")
        print(f"2. Sức mạnh: {state['player']['power']:,} | Vàng: {state['player']['xu']:,}")
        print(f"3. Bản đồ: ID {state['map']['map_id']} ('{state['map']['map_name']}'), Khu {state['map']['zone_id']}")
        print(f"4. Thực thể xung quanh: {len(state['mobs'])} quái vật, {len(state['ground_items'])} vật phẩm rơi, {len(state['other_players'])} người chơi")

        if state["mobs"]:
            closest_mob = state["mobs"][0]
            print(f"   -> Quái gần nhất: ID {closest_mob['mob_id']} (Template {closest_mob['template_id']}) - Khoảng cách: {closest_mob['dist']} px, Máu: {closest_mob['hp']}/{closest_mob['max_hp']}")

        if state["ground_items"]:
            closest_item = state["ground_items"][0]
            print(f"   -> Vật phẩm gần nhất: ID {closest_item['item_map_id']} (Template {closest_item['template_id']}) - Khoảng cách: {closest_item['dist']} px")

        print("=" * 70)
        print("[*] Thử nghiệm hoàn tất! Tiến hành ngắt kết nối an toàn.")

    client.disconnect()
    time.sleep(0.5)
    print("[*] Phiên kiểm thử kết thúc.")


if __name__ == "__main__":
    test_ai_client()
