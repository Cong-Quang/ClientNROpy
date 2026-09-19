# -*- coding: utf-8 -*-
"""
Package network cho ClientNROpy.
Quản lý I/O luồng nhị phân, cấu trúc gói tin (Message),
quản lý Session TCP, Sender/Collector và phân bổ kết nối qua Proxy.
"""

from .reader import myReader
from .writer import myWriter
from .message import Message
from .isession import ISession
from .imessage_handler import IMessageHandler
from .sender import Sender
from .message_collector import MessageCollector
from .session import Session_ME
from .proxy_manager import ProxyConfig, ProxyPool, create_proxy_socket, parse_proxy

__all__ = [
    "myReader",
    "myWriter",
    "Message",
    "ISession",
    "IMessageHandler",
    "Sender",
    "MessageCollector",
    "Session_ME",
    "ProxyConfig",
    "ProxyPool",
    "create_proxy_socket",
    "parse_proxy",
]
