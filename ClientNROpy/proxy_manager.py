# -*- coding: utf-8 -*-
# Wrapper tương thích ngược chuyển tiếp sang network/proxy_manager.py
from .network.proxy_manager import ProxyConfig, ProxyPool, create_proxy_socket, parse_proxy

__all__ = ["ProxyConfig", "ProxyPool", "create_proxy_socket", "parse_proxy"]
