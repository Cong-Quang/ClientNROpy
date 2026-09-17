# -*- coding: utf-8 -*-
"""
Phiên làm việc mạng (Session_ME).
Mô phỏng chính xác Session_ME.cs trong C#.
Đảm bảo 1 file chỉ chứa đúng 1 class.
"""

import socket
import threading
import time
from typing import Optional, List
from .isession import ISession
from .imessage_handler import IMessageHandler
from .message import Message
from .sender import Sender
from .message_collector import MessageCollector


class Session_ME(ISession):
    """
    Session_ME mô phỏng class Session_ME trong C#.
    Quản lý kết nối socket TCP, bắt tay dynamic XOR key,
    điều phối Sender và MessageCollector.
    """

    instance: Optional["Session_ME"] = None

    def __init__(self, proxy: Optional[str] = None):
        self.sc: Optional[socket.socket] = None
        self.messageHandler: Optional[IMessageHandler] = None
        self.isMainSession: bool = True
        self.connected: bool = False
        self.connecting: bool = False
        self.proxy: Optional[str] = proxy

        self.host: str = ""
        self.port: int = 0

        # Cơ chế mã hoá động XOR
        self.getKeyComplete: bool = False
        self.key: Optional[bytearray] = None
        self.curR: int = 0
        self.curW: int = 0

        self.sendByteCount: int = 0
        self.recvByteCount: int = 0
        self.timeConnected: float = 0.0

        # Luồng và hàng đợi
        self.sender: Sender = Sender(self)
        self.collector: MessageCollector = MessageCollector(self)
        self.collectorThread: Optional[threading.Thread] = None
        self.sendThread: Optional[threading.Thread] = None
        self.initThread: Optional[threading.Thread] = None

        self.recieveMsg: List[Message] = []
        self._lock = threading.Lock()

    @classmethod
    def gI(cls) -> "Session_ME":
        """Singleton getter tương đương Session_ME.gI() trong C#."""
        if cls.instance is None:
            cls.instance = Session_ME()
        return cls.instance

    def isConnected(self) -> bool:
        return self.connected and self.sc is not None

    def setHandler(self, msgHandler: IMessageHandler) -> None:
        self.messageHandler = msgHandler

    def connect(self, host: str, port: int) -> None:
        if not self.connected and not self.connecting:
            self.host = host
            self.port = port
            self.getKeyComplete = False
            self.close()
            self.initThread = threading.Thread(target=self.NetworkInit, daemon=True)
            self.initThread.start()

    def NetworkInit(self) -> None:
        self.connecting = True
        try:
            if self.proxy:
                from .proxy_manager import create_proxy_socket
                sock = create_proxy_socket(self.proxy, self.host, self.port, timeout=12.0)
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(10.0)
                sock.connect((self.host, self.port))
                sock.settimeout(None)
            self.sc = sock
            self.connected = True
            self.connecting = False
            self.timeConnected = time.time()

            # Khởi động luồng gửi và nhận
            self.sendThread = threading.Thread(target=self.sender.run, daemon=True)
            self.collectorThread = threading.Thread(target=self.collector.run, daemon=True)
            self.sendThread.start()
            self.collectorThread.start()

            # Gửi gói tin bắt tay lấy key -27 ngay khi kết nối (giống Session_ME.cs line 334)
            self.sender.doSendMessage(Message(-27))

            if self.messageHandler:
                self.messageHandler.onConnectOK(self.isMainSession)
        except Exception as ex:
            self.connecting = False
            self.connected = False
            from .logger import logger
            logger.error(f"Connect error to {self.host}:{self.port} (proxy={self.proxy}) -> {ex}")
            if self.messageHandler:
                self.messageHandler.onConnectionFail(self.isMainSession)

    def sendMessage(self, message: Message) -> None:
        self.sender.AddMessage(message)

    def writeKey(self, b: int) -> int:
        """Mã hoá 1 byte ghi lên mạng bằng XOR key xoay vòng."""
        if not self.getKeyComplete or self.key is None or len(self.key) == 0:
            return b
        k = self.key[self.curW]
        self.curW = (self.curW + 1) % len(self.key)
        res = (k ^ b) & 0xFF
        return res if res < 128 else res - 256

    def readKey(self, b: int) -> int:
        """Giải mã 1 byte đọc từ mạng bằng XOR key xoay vòng."""
        if not self.getKeyComplete or self.key is None or len(self.key) == 0:
            return b
        k = self.key[self.curR]
        self.curR = (self.curR + 1) % len(self.key)
        res = (k ^ b) & 0xFF
        return res if res < 128 else res - 256

    def onRecieveMsg(self, msg: Message) -> None:
        with self._lock:
            self.recieveMsg.append(msg)
        if self.messageHandler:
            self.messageHandler.onMessage(msg)

    def update(self) -> None:
        """Cập nhật hàng đợi tin nhắn."""
        while True:
            msg = None
            with self._lock:
                if len(self.recieveMsg) > 0:
                    msg = self.recieveMsg.pop(0)
            if msg is None:
                break
            if self.messageHandler:
                self.messageHandler.onMessage(msg)

    def clearSendingMessage(self) -> None:
        """Xóa sạch hàng đợi tin nhắn chưa gửi tương tự C#."""
        self.sender.clearSendingMessage()

    def close(self) -> None:
        self.cleanNetwork()

    def cleanNetwork(self) -> None:
        self.key = None
        self.curR = 0
        self.curW = 0
        self.getKeyComplete = False
        self.connected = False
        self.connecting = False
        self.clearSendingMessage()
        with self._lock:
            self.recieveMsg.clear()
        if self.sc is not None:
            try:
                self.sc.close()
            except Exception:
                pass
            self.sc = None
