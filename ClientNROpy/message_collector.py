# -*- coding: utf-8 -*-
"""
Luồng nhận và phân tách dữ liệu mạng (MessageCollector).
Mô phỏng chính xác class MessageCollector trong Session_ME.cs trong C#.
"""

import struct
from typing import Optional, TYPE_CHECKING
from .message import Message

if TYPE_CHECKING:
    from .session import Session_ME


class MessageCollector:
    """
    Luồng tiếp nhận TCP socket stream, giải mã XOR và phân tách thành Message.
    Đảm bảo 1 file chỉ chứa đúng 1 class.
    """

    def __init__(self, session: "Session_ME"):
        self.session: "Session_ME" = session

    def _read_exact(self, num_bytes: int) -> bytes:
        data = bytearray()
        while len(data) < num_bytes:
            if not self.session.connected or self.session.sc is None:
                raise ConnectionError("Mat ket noi socket")
            packet = self.session.sc.recv(num_bytes - len(data))
            if not packet:
                raise ConnectionError("Dong ket noi tu phia server")
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
                self.session.messageHandler.onDisconnected(self.session.isMainSession)
        self.session.cleanNetwork()

    def getKey(self, message: Message) -> None:
        """Bắt tay trao đổi khóa - Giải mã chuỗi XOR dynamic."""
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
            print(f"[Session_ME] getKey complete! Key length: {len(self.session.key)}")

            try:
                message.reader().readUTF()
                message.reader().readInt()
                message.reader().readByte()
            except Exception:
                pass
        except Exception as ex:
            print(f"[Session_ME] getKey failed: {ex}")

    def readMessage2(self, cmd: int) -> Message:
        """Đọc gói tin kích thước lớn với 3 byte length."""
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
        """Tách gói tin TCP stream thành Message."""
        try:
            cmd_raw = self._read_exact(1)[0]
            cmd = cmd_raw if cmd_raw < 128 else cmd_raw - 256
            if self.session.getKeyComplete:
                cmd = self.session.readKey(cmd_raw)

            # Các lệnh đặc biệt kích thước lớn
            if cmd in (-32, -66, 11, -67, -74, -87, 66):
                return self.readMessage2(cmd)

            # Gói tin thông thường: 2 byte length
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
