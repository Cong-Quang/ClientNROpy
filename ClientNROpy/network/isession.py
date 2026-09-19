# -*- coding: utf-8 -*-
"""
Interface ISession mô phỏng ISession.cs trong C#.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .imessage_handler import IMessageHandler
    from .message import Message


class ISession(ABC):
    """Giao diện đại diện cho một phiên làm việc mạng kết nối socket."""

    @abstractmethod
    def isConnected(self) -> bool:
        pass

    @abstractmethod
    def setHandler(self, msgHandler: "IMessageHandler") -> None:
        pass

    @abstractmethod
    def connect(self, host: str, port: int) -> None:
        pass

    @abstractmethod
    def sendMessage(self, message: "Message") -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass
