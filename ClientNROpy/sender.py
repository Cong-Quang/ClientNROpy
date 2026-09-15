# -*- coding: utf-8 -*-
"""
Luồng gửi dữ liệu mạng (Sender).
Mô phỏng chính xác class Sender trong Session_ME.cs trong C#.
"""

import threading
import time
from typing import List, TYPE_CHECKING
from .message import Message

if TYPE_CHECKING:
    from .session import Session_ME


class Sender:
    """
    Luồng hàng đợi gửi gói tin mạng lên máy chủ.
    Đảm bảo 1 file chỉ chứa đúng 1 class.
    """

    def __init__(self, session: "Session_ME"):
        self.session: "Session_ME" = session
        self.sendingMessage: List[Message] = []
        self._lock = threading.Lock()

    def AddMessage(self, message: Message) -> None:
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
            else:
                pkt.append(m.command & 0xFF)

            if self.session.getKeyComplete:
                b1 = self.session.writeKey(size >> 8) & 0xFF
                b2 = self.session.writeKey(size & 0xFF) & 0xFF
                pkt.append(b1)
                pkt.append(b2)
                for byte_val in raw_bytes:
                    pkt.append(self.session.writeKey(byte_val) & 0xFF)
            else:
                pkt.append((size >> 8) & 0xFF)
                pkt.append(size & 0xFF)
                pkt.extend(raw_bytes)

            if self.session.sc is not None:
                self.session.sc.sendall(pkt)
                self.session.sendByteCount += len(pkt)
        except Exception as ex:
            if self.session.connected:
                print(f"[Sender] Error sending message {m.command}: {ex}")
