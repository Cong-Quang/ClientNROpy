# -*- coding: utf-8 -*-
"""
Module quản lý kết nối mạng qua Proxy cho ClientNROpy.
Hỗ trợ cả SOCKS5 (RFC 1928, RFC 1929) và HTTP CONNECT Tunnel.
Thuần Python 100% sử dụng thư viện socket chuẩn - KHÔNG phụ thuộc PySocks hay bất kỳ thư viện ngoài nào.
Đảm bảo an toàn tuyệt đối khi đóng gói EXE (Nuitka / PyInstaller).
"""

import socket
import base64
from typing import Optional, List, Union


class ProxyConfig:
    """Cấu hình chi tiết của 1 proxy."""

    def __init__(
        self,
        protocol: str = "socks5",
        host: str = "",
        port: int = 1080,
        username: Optional[str] = None,
        password: Optional[str] = None,
        raw_str: str = "",
    ):
        self.protocol: str = protocol.lower()  # 'socks5' hoặc 'http'
        self.host: str = host
        self.port: int = port
        self.username: Optional[str] = username
        self.password: Optional[str] = password
        self.raw_str: str = raw_str or f"{self.protocol}://{self.host}:{self.port}"
        self.active_accounts_count: int = 0

    @property
    def display_str(self) -> str:
        """Chuỗi hiển thị an toàn (che mật khẩu)."""
        auth_str = f"{self.username}:***@" if self.username else ""
        return f"{self.protocol}://{auth_str}{self.host}:{self.port}"

    def __repr__(self) -> str:
        return f"<ProxyConfig {self.display_str} (used_by={self.active_accounts_count})>"


def parse_proxy(proxy_str: Union[str, ProxyConfig, None]) -> Optional[ProxyConfig]:
    """
    Phân tích chuỗi proxy thành ProxyConfig object.
    Hỗ trợ toàn diện các định dạng phổ biến:
      1. socks5://user:pass@host:port (hoặc kèm dấu gạch chéo '/')
      2. http://user:pass@host:port (Webshare, BrightData, Oxylabs, ...)
      3. host:port:user:pass (Định dạng phổ biến khi mua proxy tại VN)
      4. user:pass:host:port
      5. host port user pass (Copy trực tiếp từ bảng Webshare / dấu cách / tab / dòng mới)
      6. user:pass@host:port
      7. host:port (Mặc định hiểu là socks5)
    """
    if not proxy_str:
        return None
    if isinstance(proxy_str, ProxyConfig):
        return proxy_str

    s = str(proxy_str).strip()
    if not s:
        return None

    protocol = "socks5"
    if s.startswith("http://"):
        protocol = "http"
        s = s[7:]
    elif s.startswith("https://"):
        protocol = "http"
        s = s[8:]
    elif s.startswith("socks5://"):
        protocol = "socks5"
        s = s[9:]
    elif s.startswith("socks4://"):
        protocol = "socks5"
        s = s[9:]

    # Loại bỏ dấu gạch chéo cuối nếu có từ copy-paste URL (vd: http://u:p@host:port/)
    s = s.rstrip("/")

    username = None
    password = None
    host = ""
    port = 1080

    # Dạng copy bảng (khoảng trắng / tab / xuống dòng): host port user pass
    tokens = s.split()
    if len(tokens) >= 4 and tokens[1].isdigit():
        host = tokens[0]
        port = int(tokens[1])
        username = tokens[2]
        password = tokens[3]
    elif len(tokens) == 2 and tokens[1].isdigit():
        host = tokens[0]
        port = int(tokens[1])
    # Dạng URL: user:pass@host:port
    elif "@" in s:
        auth_part, host_part = s.split("@", 1)
        host_part = host_part.rstrip("/")
        if ":" in auth_part:
            username, password = auth_part.split(":", 1)
        else:
            username = auth_part
        if ":" in host_part:
            h_parts = host_part.split(":", 1)
            host = h_parts[0]
            try:
                port = int(h_parts[1].rstrip("/"))
            except ValueError:
                port = 1080
        else:
            host = host_part
    # Dạng phân tách bởi dấu hai chấm: host:port:user:pass hoặc user:pass:host:port
    else:
        parts = s.split(":")
        if len(parts) == 4:
            if parts[1].isdigit():
                # host:port:user:pass
                host = parts[0]
                port = int(parts[1])
                username = parts[2]
                password = parts[3]
            elif parts[3].isdigit():
                # user:pass:host:port
                username = parts[0]
                password = parts[1]
                host = parts[2]
                port = int(parts[3])
            else:
                host = parts[0]
                port = int(parts[1]) if parts[1].isdigit() else 1080
                username = parts[2]
                password = parts[3]
        elif len(parts) == 2:
            host = parts[0]
            try:
                port = int(parts[1].rstrip("/"))
            except ValueError:
                port = 1080
        elif len(parts) == 1:
            host = parts[0]
            port = 1080
        else:
            host = parts[0]
            try:
                port = int(parts[1].rstrip("/"))
            except ValueError:
                port = 1080

    return ProxyConfig(
        protocol=protocol,
        host=host,
        port=port,
        username=username,
        password=password,
        raw_str=str(proxy_str),
    )


def _recv_exact(sock: socket.socket, length: int) -> bytearray:
    """Đọc chính xác `length` byte từ socket."""
    buf = bytearray()
    while len(buf) < length:
        chunk = sock.recv(length - len(buf))
        if not chunk:
            raise ConnectionError("Kết nối tới Proxy bị đóng đột ngột trong khi nhận dữ liệu.")
        buf.extend(chunk)
    return buf


def _socks5_handshake(
    sock: socket.socket,
    proxy: ProxyConfig,
    dest_host: str,
    dest_port: int,
) -> None:
    """
    Thực hiện bắt tay SOCKS5 theo chuẩn RFC 1928 và RFC 1929.
    """
    # 1. Gửi bản tin chào ban đầu (Client Greeting)
    if proxy.username and proxy.password:
        # Hỗ trợ cả method 0x00 (No Auth) và 0x02 (User/Pass Auth)
        sock.sendall(bytes([0x05, 0x02, 0x00, 0x02]))
    else:
        # Chỉ No Auth
        sock.sendall(bytes([0x05, 0x01, 0x00]))

    # Nhận phản hồi từ Proxy: VER (1 byte) + METHOD (1 byte)
    resp = _recv_exact(sock, 2)
    if resp[0] != 0x05:
        raise ConnectionError(f"Proxy không hỗ trợ giao thức SOCKS5 (trả về phiên bản {resp[0]}).")

    method = resp[1]
    if method == 0xFF:
        raise ConnectionError("Proxy từ chối phương thức xác thực (No acceptable methods).")

    # 2. Xác thực tài khoản nếu Proxy yêu cầu (RFC 1929)
    if method == 0x02:
        if not proxy.username or not proxy.password:
            raise ConnectionError("Proxy yêu cầu xác thực Username/Password nhưng chưa được cấu hình.")
        u_bytes = proxy.username.encode("utf-8")
        p_bytes = proxy.password.encode("utf-8")
        auth_req = bytearray([0x01, len(u_bytes)]) + u_bytes + bytearray([len(p_bytes)]) + p_bytes
        sock.sendall(auth_req)

        # Nhận phản hồi xác thực: VER (1 byte) + STATUS (1 byte)
        auth_resp = _recv_exact(sock, 2)
        if auth_resp[1] != 0x00:
            raise ConnectionError(f"Xác thực SOCKS5 thất bại với Proxy {proxy.display_str} (Mã lỗi {auth_resp[1]}).")

    # 3. Gửi lệnh kết nối tới Game Server: CMD = 0x01 (CONNECT)
    req = bytearray([0x05, 0x01, 0x00])

    # Kiểm tra xem dest_host là IPv4 hay Domain
    try:
        ip_bytes = socket.inet_aton(dest_host)
        req.append(0x01)  # ATYP = IPv4
        req.extend(ip_bytes)
    except OSError:
        d_bytes = dest_host.encode("ascii")
        req.append(0x03)  # ATYP = Domain name
        req.append(len(d_bytes))
        req.extend(d_bytes)

    # Port (2 byte Big-endian)
    req.extend(dest_port.to_bytes(2, "big"))
    sock.sendall(req)

    # 4. Nhận phản hồi kết nối từ Proxy:
    # VER (1) + REP (1) + RSV (1) + ATYP (1) + BND.ADDR + BND.PORT (2)
    conn_resp = _recv_exact(sock, 4)
    if conn_resp[0] != 0x05:
        raise ConnectionError("Phản hồi SOCKS5 không hợp lệ.")

    rep = conn_resp[1]
    if rep != 0x00:
        rep_errors = {
            1: "Lỗi chung từ proxy (General SOCKS server failure)",
            2: "Quy tắc kết nối không cho phép (Connection not allowed by ruleset)",
            3: "Không thể định tuyến tới mạng (Network unreachable)",
            4: "Không thể định tuyến tới máy chủ (Host unreachable)",
            5: "Máy chủ game từ chối kết nối (Connection refused)",
            6: "Hết thời gian chờ kết nối TTL (TTL expired)",
            7: "Lệnh không được hỗ trợ (Command not supported)",
            8: "Kiểu địa chỉ không được hỗ trợ (Address type not supported)",
        }
        err_msg = rep_errors.get(rep, f"Mã lỗi SOCKS5 #{rep}")
        raise ConnectionError(f"SOCKS5 Connect thất bại tới {dest_host}:{dest_port} -> {err_msg}")

    # Đọc nốt thông tin địa chỉ BND mà proxy gửi kèm
    atyp = conn_resp[3]
    if atyp == 0x01:  # IPv4 (4 byte) + Port (2 byte)
        _recv_exact(sock, 6)
    elif atyp == 0x03:  # Domain (1 byte len + domain) + Port (2 byte)
        domain_len = _recv_exact(sock, 1)[0]
        _recv_exact(sock, domain_len + 2)
    elif atyp == 0x04:  # IPv6 (16 byte) + Port (2 byte)
        _recv_exact(sock, 18)


def _http_connect_handshake(
    sock: socket.socket,
    proxy: ProxyConfig,
    dest_host: str,
    dest_port: int,
) -> None:
    """
    Thực hiện tạo HTTP CONNECT Tunnel để truyền dữ liệu TCP thô.
    """
    connect_headers = [
        f"CONNECT {dest_host}:{dest_port} HTTP/1.1",
        f"Host: {dest_host}:{dest_port}",
        "Proxy-Connection: Keep-Alive",
    ]
    if proxy.username and proxy.password:
        raw_cred = f"{proxy.username}:{proxy.password}".encode("utf-8")
        b64_cred = base64.b64encode(raw_cred).decode("ascii")
        connect_headers.append(f"Proxy-Authorization: Basic {b64_cred}")

    req_str = "\r\n".join(connect_headers) + "\r\n\r\n"
    sock.sendall(req_str.encode("ascii"))

    # Đọc phản hồi từ HTTP Proxy tới khi gặp \r\n\r\n
    resp_bytes = bytearray()
    while b"\r\n\r\n" not in resp_bytes:
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionError("HTTP Proxy đóng kết nối sớm trong quá trình bắt tay CONNECT.")
        resp_bytes.extend(chunk)

    first_line = resp_bytes.split(b"\r\n")[0].decode("ascii", errors="replace")
    parts = first_line.split(" ")
    if len(parts) < 2:
        raise ConnectionError(f"Phản hồi HTTP CONNECT không hợp lệ: {first_line}")

    status_code = parts[1]
    if status_code != "200":
        raise ConnectionError(f"HTTP CONNECT Tunnel bị từ chối: {first_line}")


def create_proxy_socket(
    proxy: Union[str, ProxyConfig],
    dest_host: str,
    dest_port: int,
    timeout: float = 12.0,
) -> socket.socket:
    """
    Tạo và thiết lập đường truyền socket TCP kết nối tới máy chủ thông qua Proxy.
    Hỗ trợ cả SOCKS5 và HTTP Tunnel.
    Trả về socket TCP đã sẵn sàng truyền nhận dữ liệu game.
    """
    cfg = parse_proxy(proxy)
    if not cfg:
        # Nếu không có cấu hình proxy, tạo socket trực tiếp
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((dest_host, dest_port))
        sock.settimeout(None)
        return sock

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        # 1. Kết nối vật lý tới Proxy Server
        sock.connect((cfg.host, cfg.port))

        # 2. Bắt tay tạo đường truyền tới máy chủ Game
        if cfg.protocol == "socks5":
            _socks5_handshake(sock, cfg, dest_host, dest_port)
        elif cfg.protocol in ("http", "https"):
            _http_connect_handshake(sock, cfg, dest_host, dest_port)
        else:
            # Mặc định thử socks5
            _socks5_handshake(sock, cfg, dest_host, dest_port)

        sock.settimeout(None)
        return sock
    except Exception as ex:
        try:
            sock.close()
        except Exception:
            pass
        raise ConnectionError(f"[Proxy {cfg.display_str}] Không thể kết nối tới {dest_host}:{dest_port}: {ex}") from ex


class ProxyPool:
    """
    Quản lý danh sách Proxy và thuật toán phân bổ tài khoản vào Proxy.
    Mặc định:
      - use_proxy: False (không dùng proxy)
      - accounts_per_proxy: 4 (nếu bật proxy, mỗi proxy chịu tối đa 4 acc)
    """

    def __init__(self, use_proxy: bool = False, accounts_per_proxy: int = 4):
        self.use_proxy: bool = use_proxy
        self.accounts_per_proxy: int = max(1, accounts_per_proxy)
        self.proxies: List[ProxyConfig] = []

    def set_use_proxy(self, enable: bool) -> None:
        self.use_proxy = enable

    def set_accounts_per_proxy(self, count: int) -> None:
        self.accounts_per_proxy = max(1, count)

    def add_proxy(self, proxy_str: Union[str, ProxyConfig]) -> Optional[ProxyConfig]:
        cfg = parse_proxy(proxy_str)
        if cfg:
            self.proxies.append(cfg)
            return cfg
        return None

    def clear(self) -> None:
        self.proxies.clear()

    def get_proxy_for_account(
        self,
        account_index: int,
        custom_proxy: Optional[Union[str, ProxyConfig]] = None,
    ) -> Optional[ProxyConfig]:
        """
        Lấy Proxy được phân bổ cho một tài khoản.
        Quy tắc:
        1. Nếu use_proxy = False và không có custom_proxy: Trả về None (chạy trực tiếp).
        2. Nếu tài khoản có custom_proxy riêng: Sử dụng custom_proxy đó.
        3. Nếu bật use_proxy và có proxy trong pool:
           Phân bổ theo quy tắc mặc định N acc / 1 proxy (mặc định 4 acc/proxy).
           Acc 0..3 -> Proxy 0
           Acc 4..7 -> Proxy 1
           ...
        """
        if custom_proxy:
            cfg = parse_proxy(custom_proxy)
            if cfg:
                cfg.active_accounts_count += 1
                return cfg

        if not self.use_proxy or not self.proxies:
            return None

        proxy_idx = (account_index // self.accounts_per_proxy) % len(self.proxies)
        selected = self.proxies[proxy_idx]
        selected.active_accounts_count += 1
        return selected

    def remove_proxy(self, identifier: Union[int, str]) -> bool:
        """Xoá một proxy khỏi danh sách theo số thứ tự (1, 2, ...) hoặc chuỗi raw."""
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.strip().isdigit()):
            idx = int(identifier) - 1
            if 0 <= idx < len(self.proxies):
                self.proxies.pop(idx)
                return True
            return False

        ident_str = str(identifier).strip().lower()
        for i, p in enumerate(self.proxies):
            if p.raw_str.lower() == ident_str or p.display_str.lower() == ident_str or ident_str in p.raw_str.lower():
                self.proxies.pop(i)
                return True
        return False

    def get_raw_proxies_list(self) -> List[str]:
        """Lấy danh sách chuỗi proxy thô để lưu cấu hình."""
        return [p.raw_str for p in self.proxies]

    def __len__(self) -> int:
        return len(self.proxies)
