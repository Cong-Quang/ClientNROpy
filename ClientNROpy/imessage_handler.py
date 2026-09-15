# -*- coding: utf-8 -*-
"""
Interface IMessageHandler mô phỏng IMessageHandler.cs trong C#.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .message import Message


class IMessageHandler(ABC):
    """Giao diện tiếp nhận và phân phối sự kiện mạng từ máy chủ."""

    @abstractmethod
    def onConnectOK(self, isMain: bool) -> None:
        pass

    @abstractmethod
    def onConnectionFail(self, isMain: bool) -> None:
        pass

    @abstractmethod
    def onDisconnected(self, isMain: bool) -> None:
        pass

    @abstractmethod
    def onMessage(self, message: "Message") -> None:
        pass
