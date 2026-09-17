#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  ClientNRO Web Server - Real-time Log Streaming & Remote Web Dashboard
================================================================================
Cung cấp giao diện Web xem log thời gian thực qua Server-Sent Events (SSE)
và bảng điều khiển nhân vật, chiến đấu, săn boss, Xmap và gửi lệnh từ xa.
Sử dụng 100% Python Standard Library (không phụ thuộc bất kỳ thư viện ngoài nào).
================================================================================
"""

import sys
import io
import os
import json
import time
import socket
import select
import queue
import threading
import webbrowser
from collections import deque
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
import urllib.parse


class LogBroadcaster:
    """Quản lý bộ đệm log và phát sóng (broadcast) tới các client SSE."""

    def __init__(self, max_history: int = 3000):
        self.max_history = max_history
        self.history = deque(maxlen=max_history)
        self.listeners = set()
        self.lock = threading.Lock()
        self._counter = 0

    def add_listener(self) -> queue.Queue:
        q = queue.Queue(maxsize=1000)
        with self.lock:
            self.listeners.add(q)
        return q

    def remove_listener(self, q: queue.Queue):
        with self.lock:
            self.listeners.discard(q)

    def broadcast(self, text: str):
        if not text:
            return
        timestamp = time.strftime("%H:%M:%S")
        with self.lock:
            self._counter += 1
            entry = {
                "id": self._counter,
                "time": timestamp,
                "text": text,
                "category": self._detect_category(text)
            }
            self.history.append(entry)
            dead = []
            for q in list(self.listeners):
                try:
                    q.put_nowait(entry)
                except queue.Full:
                    try:
                        q.get_nowait()
                        q.put_nowait(entry)
                    except Exception:
                        pass
                except Exception:
                    dead.append(q)
            for d in dead:
                self.listeners.discard(d)

    def _detect_category(self, text: str) -> str:
        t = text.lower()
        if "boss" in t or "tiêu diệt" in t or "xuất hiện tại" in t:
            return "boss"
        elif "chat" in t or "thế giới" in t:
            return "chat"
        elif "ak" in t or "tàn sát" in t or "tansat" in t or "đánh quái" in t or "nhặt" in t or "đậu" in t or "combat" in t:
            return "combat"
        elif "xmap" in t or "chuyển map" in t or "shuttle" in t or "lộ trình" in t or "capsule" in t:
            return "xmap"
        elif "lỗi" in t or "error" in t or "fail" in t or "[!]" in t or "traceback" in t or "cảnh báo" in t:
            return "error"
        return "system"

    def get_history(self) -> list:
        with self.lock:
            return list(self.history)

    def clear(self):
        with self.lock:
            self.history.clear()


class WebLogCapture(io.TextIOBase):
    """
    Bộ đệm chặn sys.stdout & sys.stderr, chuyển mọi output từ print()
    vào LogBroadcaster để truyền trực tiếp tới giao diện Web.
    """

    def __init__(self, original_stream, broadcaster: LogBroadcaster, also_console: bool = False):
        super().__init__()
        self.original_stream = original_stream
        self.broadcaster = broadcaster
        self.also_console = also_console
        self.lock = threading.Lock()
        self.buffer = ""

    def write(self, s: str):
        if not s:
            return 0
        if self.also_console and self.original_stream:
            try:
                self.original_stream.write(s)
                self.original_stream.flush()
            except Exception:
                pass
        with self.lock:
            self.buffer += s
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                clean_line = line.rstrip("\r")
                if clean_line:
                    self.broadcaster.broadcast(clean_line)
        return len(s)

    def flush(self):
        if self.also_console and self.original_stream:
            try:
                self.original_stream.flush()
            except Exception:
                pass
        with self.lock:
            if self.buffer:
                clean_line = self.buffer.rstrip("\r\n")
                if clean_line:
                    self.broadcaster.broadcast(clean_line)
                self.buffer = ""

    @property
    def encoding(self):
        return getattr(self.original_stream, "encoding", "utf-8") or "utf-8"

    def fileno(self):
        if hasattr(self.original_stream, "fileno"):
            try:
                return self.original_stream.fileno()
            except Exception:
                pass
        raise io.UnsupportedOperation("fileno")

    def isatty(self):
        if hasattr(self.original_stream, "isatty"):
            try:
                return self.original_stream.isatty()
            except Exception:
                pass
        return False


# HTML Dashboard Template (Độc lập 100%, phong cách Dark Gaming hiện đại, Responsive)
WEB_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ClientNRO Web Dashboard - Real-time Log & Remote Control</title>
  <style>
    :root {
      --bg-main: #0a0d14;
      --bg-card: #111726;
      --bg-card-hover: #161f33;
      --bg-terminal: #07090e;
      --border-color: #1e293b;
      --border-accent: #334155;
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --primary: #06b6d4;
      --primary-hover: #0891b2;
      --primary-glow: rgba(6, 182, 212, 0.25);
      --accent-green: #10b981;
      --accent-red: #ef4444;
      --accent-amber: #f59e0b;
      --accent-purple: #a855f7;
      --accent-blue: #3b82f6;
      --font-ui: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      --font-mono: "Consolas", "Courier New", "Fira Code", monospace;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      background-color: var(--bg-main);
      color: var(--text-main);
      font-family: var(--font-ui);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
      font-size: 14px;
    }

    /* Top Navigation / Status Header */
    header {
      background: linear-gradient(180deg, #131b2e 0%, var(--bg-card) 100%);
      border-bottom: 1px solid var(--border-color);
      padding: 10px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 12px;
      z-index: 10;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .brand-icon {
      width: 32px;
      height: 32px;
      background: linear-gradient(135deg, #06b6d4, #3b82f6);
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 16px;
      color: #fff;
      box-shadow: 0 0 15px var(--primary-glow);
    }

    .brand-title {
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0.5px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .brand-subtitle {
      font-size: 11px;
      color: var(--text-muted);
      font-weight: 400;
    }

    .status-badges {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-color);
    }

    .badge.online {
      background: rgba(16, 185, 129, 0.15);
      border-color: rgba(16, 185, 129, 0.4);
      color: var(--accent-green);
    }

    .badge.offline {
      background: rgba(239, 68, 68, 0.15);
      border-color: rgba(239, 68, 68, 0.4);
      color: var(--accent-red);
    }

    .badge-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background-color: currentColor;
      box-shadow: 0 0 8px currentColor;
    }

    /* Player Overview Bar */
    .overview-bar {
      background: var(--bg-card);
      border-bottom: 1px solid var(--border-color);
      padding: 8px 18px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      align-items: center;
    }

    .stat-card {
      display: flex;
      flex-direction: column;
      gap: 3px;
    }

    .stat-label {
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .stat-value {
      font-size: 13px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .stat-bar-wrap {
      width: 100%;
      height: 6px;
      background: rgba(255, 255, 255, 0.08);
      border-radius: 3px;
      overflow: hidden;
      margin-top: 3px;
    }

    .stat-bar-fill {
      height: 100%;
      border-radius: 3px;
      transition: width 0.3s ease;
    }

    .stat-bar-fill.hp {
      background: linear-gradient(90deg, #f43f5e, #fb7185);
    }

    .stat-bar-fill.mp {
      background: linear-gradient(90deg, #0284c7, #38bdf8);
    }

    /* Main Container */
    main {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      padding: 12px 18px;
      gap: 10px;
    }

    /* Action & Filter Toolbar */
    .toolbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      flex-wrap: wrap;
    }

    .filter-group {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }

    .filter-btn {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      padding: 5px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 500;
      transition: all 0.2s;
    }

    .filter-btn:hover {
      background: var(--bg-card-hover);
      color: var(--text-main);
      border-color: var(--border-accent);
    }

    .filter-btn.active {
      background: var(--primary);
      color: #fff;
      border-color: var(--primary);
      box-shadow: 0 0 10px var(--primary-glow);
    }

    .search-box {
      position: relative;
      min-width: 220px;
    }

    .search-box input {
      width: 100%;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 6px 12px 6px 30px;
      border-radius: 6px;
      font-size: 12px;
      outline: none;
      transition: border-color 0.2s;
    }

    .search-box input:focus {
      border-color: var(--primary);
      box-shadow: 0 0 8px var(--primary-glow);
    }

    .search-box svg {
      position: absolute;
      left: 9px;
      top: 50%;
      transform: translateY(-50%);
      width: 14px;
      height: 14px;
      fill: var(--text-dim);
    }

    .tool-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .action-btn {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      padding: 5px 10px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.2s;
    }

    .action-btn:hover {
      background: var(--bg-card-hover);
      color: var(--text-main);
      border-color: var(--border-accent);
    }

    .action-btn.active-toggle {
      color: var(--primary);
      border-color: var(--primary);
    }

    /* Terminal Window */
    .terminal-container {
      flex: 1;
      background: var(--bg-terminal);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      position: relative;
      box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.5);
    }

    .terminal-header {
      background: #0f1420;
      padding: 6px 12px;
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 11px;
      color: var(--text-dim);
    }

    .terminal-dots {
      display: flex;
      gap: 6px;
    }

    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }

    .dot.red { background: #ef4444; }
    .dot.yellow { background: #f59e0b; }
    .dot.green { background: #10b981; }

    .terminal-body {
      flex: 1;
      padding: 10px 14px;
      overflow-y: auto;
      font-family: var(--font-mono);
      font-size: 12.5px;
      line-height: 1.55;
      white-space: pre-wrap;
      word-break: break-all;
    }

    .terminal-body::-webkit-scrollbar {
      width: 8px;
    }

    .terminal-body::-webkit-scrollbar-track {
      background: #090c12;
    }

    .terminal-body::-webkit-scrollbar-thumb {
      background: #1e293b;
      border-radius: 4px;
    }

    .terminal-body::-webkit-scrollbar-thumb:hover {
      background: #334155;
    }

    /* Log Line Styles */
    .log-line {
      display: flex;
      gap: 10px;
      padding: 1px 0;
      transition: background 0.15s;
    }

    .log-line:hover {
      background: rgba(255, 255, 255, 0.02);
    }

    .log-time {
      color: var(--text-dim);
      user-select: none;
      font-size: 11px;
      min-width: 62px;
    }

    .log-text {
      flex: 1;
      color: #cbd5e1;
    }

    /* Dynamic Category Highlights */
    .log-line.category-boss .log-text {
      color: #fde047;
      font-weight: 600;
    }
    .log-line.category-chat .log-text {
      color: #67e8f9;
    }
    .log-line.category-combat .log-text {
      color: #a7f3d0;
    }
    .log-line.category-xmap .log-text {
      color: #d8b4fe;
    }
    .log-line.category-error .log-text {
      color: #fca5a5;
      font-weight: 600;
    }

    .scroll-bottom-badge {
      position: absolute;
      bottom: 20px;
      right: 25px;
      background: var(--primary);
      color: #fff;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: none;
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
      border: 1px solid rgba(255, 255, 255, 0.2);
      z-index: 5;
      animation: bounce 1.5s infinite;
    }

    @keyframes bounce {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-4px); }
    }

    /* Quick Action Commands */
    .quick-bar {
      display: flex;
      align-items: center;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 2px;
    }

    .quick-btn {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      padding: 5px 11px;
      border-radius: 6px;
      font-size: 12px;
      cursor: pointer;
      white-space: nowrap;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.2s;
    }

    .quick-btn:hover {
      background: var(--bg-card-hover);
      border-color: var(--primary);
      color: var(--primary);
    }

    /* Interactive Command Input */
    .command-bar {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 6px 12px;
      display: flex;
      align-items: center;
      gap: 8px;
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
    }

    .command-prompt {
      font-family: var(--font-mono);
      font-weight: 700;
      color: var(--primary);
      font-size: 13px;
      user-select: none;
    }

    .command-input {
      flex: 1;
      background: transparent;
      border: none;
      outline: none;
      color: var(--text-main);
      font-family: var(--font-mono);
      font-size: 13px;
    }

    .command-send-btn {
      background: linear-gradient(135deg, var(--primary), #3b82f6);
      color: #fff;
      border: none;
      padding: 6px 16px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 12px;
      cursor: pointer;
      transition: opacity 0.2s, transform 0.1s;
    }

    .command-send-btn:hover {
      opacity: 0.9;
    }

    .command-send-btn:active {
      transform: scale(0.97);
    }

    /* Footer */
    footer {
      background: var(--bg-card);
      border-top: 1px solid var(--border-color);
      padding: 6px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 11px;
      color: var(--text-dim);
    }

    @media (max-width: 768px) {
      .overview-bar {
        grid-template-columns: 1fr 1fr;
      }
      .search-box {
        width: 100%;
      }
      .toolbar {
        flex-direction: column;
        align-items: stretch;
      }
    }
  </style>
</head>
<body>

  <!-- Header -->
  <header>
    <div class="brand">
      <div class="brand-icon">NRO</div>
      <div>
        <div class="brand-title">Client NRO Dashboard</div>
        <div class="brand-subtitle">Real-time Game Simulator & Log Streamer</div>
      </div>
    </div>
    <div class="status-badges">
      <div id="conn-badge" class="badge offline">
        <span class="badge-dot"></span>
        <span id="conn-text">Đang kết nối...</span>
      </div>
      <div class="badge">
        <span id="server-info">Host: --:--</span>
      </div>
    </div>
  </header>

  <!-- Player Status Bar -->
  <div class="overview-bar">
    <div class="stat-card">
      <div class="stat-label">Nhân vật</div>
      <div class="stat-value">
        <span id="char-name" style="color: var(--primary);">--</span>
        <span id="char-planet" style="color: var(--text-dim); font-size: 11px;">(--)</span>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Bản đồ & Khu</div>
      <div class="stat-value" id="map-zone-text">-- (Khu --)</div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Máu (HP) - <span id="hp-percent">0%</span></div>
      <div class="stat-value" id="hp-text">0 / 0</div>
      <div class="stat-bar-wrap">
        <div id="hp-bar" class="stat-bar-fill hp" style="width: 0%;"></div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Thể lực (MP) - <span id="mp-percent">0%</span></div>
      <div class="stat-value" id="mp-text">0 / 0</div>
      <div class="stat-bar-wrap">
        <div id="mp-bar" class="stat-bar-fill mp" style="width: 0%;"></div>
      </div>
    </div>

    <div class="stat-card">
      <div class="stat-label">Tài sản</div>
      <div class="stat-value" style="font-size: 12px;">
        <span style="color: #fbbf24;">💰 <span id="char-gold">0</span></span>
        <span style="color: #38bdf8; margin-left: 8px;">💎 <span id="char-gem">0</span></span>
      </div>
    </div>
  </div>

  <!-- Main View -->
  <main>
    <!-- Toolbar -->
    <div class="toolbar">
      <div class="filter-group">
        <button class="filter-btn active" data-cat="all">Tất cả</button>
        <button class="filter-btn" data-cat="boss">👹 Boss</button>
        <button class="filter-btn" data-cat="chat">💬 Chat</button>
        <button class="filter-btn" data-cat="combat">⚔️ Chiến đấu</button>
        <button class="filter-btn" data-cat="xmap">🗺️ Xmap</button>
        <button class="filter-btn" data-cat="error">⚠️ Lỗi</button>
      </div>

      <div class="search-box">
        <svg viewBox="0 0 24 24"><path d="M21.71 20.29l-5.01-5.01C17.54 13.9 18 12.01 18 10c0-4.41-3.59-8-8-8S2 5.59 2 10s3.59 8 8 8c2.01 0 3.9-.46 5.28-1.3l5.01 5.01c.39.39 1.02.39 1.41 0 .39-.39.39-1.02.01-1.42zM4 10c0-3.31 2.69-6 6-6s6 2.69 6 6-2.69 6-6 6-6-2.69-6-6z"/></svg>
        <input type="text" id="search-input" placeholder="Lọc từ khóa log..." autocomplete="off">
      </div>

      <div class="tool-actions">
        <button id="autoscroll-btn" class="action-btn active-toggle">⏬ Cuộn tự động: BẬT</button>
        <button id="pause-btn" class="action-btn">⏸️ Tạm dừng</button>
        <button id="copy-btn" class="action-btn">📋 Sao chép</button>
        <button id="clear-btn" class="action-btn">🧹 Xóa màn hình</button>
      </div>
    </div>

    <!-- Terminal Window -->
    <div class="terminal-container">
      <div class="terminal-header">
        <div class="terminal-dots">
          <div class="dot red"></div>
          <div class="dot yellow"></div>
          <div class="dot green"></div>
        </div>
        <div>REALTIME LOG STREAM (SSE)</div>
        <div id="log-count">0 dòng</div>
      </div>
      <div id="terminal-body" class="terminal-body"></div>
      <div id="scroll-bottom-badge" class="scroll-bottom-badge">⬇️ Có log mới - Bấm để cuộn xuống</div>
    </div>

    <!-- Quick Actions -->
    <div class="quick-bar">
      <span style="font-size: 11px; color: var(--text-dim); margin-right: 4px;">Phím tắt:</span>
      <button class="quick-btn" onclick="sendCommand('info')">ℹ️ Thông tin (info)</button>
      <button class="quick-btn" onclick="sendCommand('boss')">👹 Danh sách Boss</button>
      <button class="quick-btn" onclick="sendCommand('map')">🗺️ Bản đồ (map)</button>
      <button class="quick-btn" onclick="sendCommand('zone')">📍 Xem khu (zone)</button>
      <button class="quick-btn" onclick="sendCommand('ts on')">⚔️ Tàn sát BẬT</button>
      <button class="quick-btn" onclick="sendCommand('ts off')">🛑 Tàn sát TẮT</button>
      <button class="quick-btn" onclick="sendCommand('anhat')">💎 Tự nhặt đồ</button>
      <button class="quick-btn" onclick="sendCommand('abf')">🌿 Tự dùng đậu</button>
      <button class="quick-btn" onclick="sendCommand('hs')">✨ Hồi sinh ngay</button>
      <button class="quick-btn" onclick="sendCommand('autohs')">🔄 Auto Hồi sinh</button>
    </div>

    <!-- Interactive Command Bar -->
    <div class="command-bar">
      <div class="command-prompt">nro&gt;</div>
      <input type="text" id="cmd-input" class="command-input" placeholder="Nhập lệnh điều khiển (VD: boss, info, xmap Đông Karin, ts on, chat Hello)..." autocomplete="off">
      <button id="cmd-send-btn" class="command-send-btn">GỬI LỆNH</button>
    </div>
  </main>

  <!-- Footer -->
  <footer>
    <div>ClientNROpy &bull; Local Web Dashboard Server &bull; Port: <span id="current-port">--</span></div>
    <div>Sử dụng phím mũi tên Lên/Xuống để duyệt lịch sử lệnh &bull; Mặc định Terminal</div>
  </footer>

  <script>
    // State management
    let logs = [];
    let activeFilter = 'all';
    let searchQuery = '';
    let autoScroll = true;
    let isPaused = false;
    let cmdHistory = [];
    let historyIndex = -1;

    const terminalBody = document.getElementById('terminal-body');
    const scrollBadge = document.getElementById('scroll-bottom-badge');
    const logCountEl = document.getElementById('log-count');
    const autoscrollBtn = document.getElementById('autoscroll-btn');
    const pauseBtn = document.getElementById('pause-btn');
    const searchInput = document.getElementById('search-input');
    const cmdInput = document.getElementById('cmd-input');
    const cmdSendBtn = document.getElementById('cmd-send-btn');

    document.getElementById('current-port').textContent = window.location.port || '80';

    // SSE EventSource for live logs
    let eventSource = null;

    function initSSE() {
      if (eventSource) {
        eventSource.close();
      }
      eventSource = new EventSource('/api/logs/stream');

      eventSource.onmessage = function(event) {
        if (isPaused) return;
        try {
          const entry = JSON.parse(event.data);
          appendLog(entry);
        } catch (e) {
          console.error("SSE parse error", e);
        }
      };

      eventSource.onerror = function() {
        console.warn("SSE stream disconnected. Reconnecting in 3s...");
        eventSource.close();
        setTimeout(initSSE, 3000);
      };
    }

    function appendLog(entry) {
      logs.push(entry);
      if (logs.length > 3000) {
        logs.shift();
      }
      logCountEl.textContent = logs.length.toLocaleString() + " dòng";

      // Check if entry matches filter & search
      if (isMatch(entry)) {
        renderLogEntry(entry);
        if (autoScroll) {
          terminalBody.scrollTop = terminalBody.scrollHeight;
        } else {
          scrollBadge.style.display = 'block';
        }
      }
    }

    function isMatch(entry) {
      if (activeFilter !== 'all' && entry.category !== activeFilter) {
        return false;
      }
      if (searchQuery && !entry.text.toLowerCase().includes(searchQuery)) {
        return false;
      }
      return true;
    }

    function renderLogEntry(entry) {
      const line = document.createElement('div');
      line.className = 'log-line category-' + (entry.category || 'system');
      
      const timeSpan = document.createElement('span');
      timeSpan.className = 'log-time';
      timeSpan.textContent = '[' + entry.time + ']';

      const textSpan = document.createElement('span');
      textSpan.className = 'log-text';
      textSpan.textContent = entry.text;

      line.appendChild(timeSpan);
      line.appendChild(textSpan);
      terminalBody.appendChild(line);
    }

    function reRenderAllLogs() {
      terminalBody.innerHTML = '';
      const filtered = logs.filter(isMatch);
      filtered.forEach(renderLogEntry);
      if (autoScroll) {
        terminalBody.scrollTop = terminalBody.scrollHeight;
      }
    }

    // Filter Buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeFilter = btn.dataset.cat;
        reRenderAllLogs();
      });
    });

    // Search Box
    searchInput.addEventListener('input', (e) => {
      searchQuery = e.target.value.toLowerCase().trim();
      reRenderAllLogs();
    });

    // Auto-scroll toggle & detection
    autoscrollBtn.addEventListener('click', () => {
      autoScroll = !autoScroll;
      updateAutoScrollUI();
    });

    function updateAutoScrollUI() {
      if (autoScroll) {
        autoscrollBtn.classList.add('active-toggle');
        autoscrollBtn.textContent = '⏬ Cuộn tự động: BẬT';
        terminalBody.scrollTop = terminalBody.scrollHeight;
        scrollBadge.style.display = 'none';
      } else {
        autoscrollBtn.classList.remove('active-toggle');
        autoscrollBtn.textContent = '⏬ Cuộn tự động: TẮT';
      }
    }

    terminalBody.addEventListener('scroll', () => {
      const isAtBottom = terminalBody.scrollHeight - terminalBody.scrollTop - terminalBody.clientHeight < 30;
      if (isAtBottom) {
        scrollBadge.style.display = 'none';
        if (!autoScroll) {
          autoScroll = true;
          updateAutoScrollUI();
        }
      } else {
        if (autoScroll) {
          autoScroll = false;
          updateAutoScrollUI();
        }
      }
    });

    scrollBadge.addEventListener('click', () => {
      autoScroll = true;
      updateAutoScrollUI();
    });

    // Pause button
    pauseBtn.addEventListener('click', () => {
      isPaused = !isPaused;
      if (isPaused) {
        pauseBtn.classList.add('active-toggle');
        pauseBtn.textContent = '▶️ Tiếp tục stream';
      } else {
        pauseBtn.classList.remove('active-toggle');
        pauseBtn.textContent = '⏸️ Tạm dừng';
      }
    });

    // Clear logs
    document.getElementById('clear-btn').addEventListener('click', () => {
      logs = [];
      terminalBody.innerHTML = '';
      logCountEl.textContent = "0 dòng";
      fetch('/api/clear', { method: 'POST' }).catch(() => {});
    });

    // Copy logs
    document.getElementById('copy-btn').addEventListener('click', () => {
      const text = logs.map(l => `[${l.time}] ${l.text}`).join('\n');
      navigator.clipboard.writeText(text).then(() => {
        alert("Đã sao chép " + logs.length + " dòng log vào bộ nhớ tạm!");
      }).catch(() => {
        alert("Không thể tự động sao chép. Vui lòng thử lại.");
      });
    });

    // Send command function
    function sendCommand(cmd) {
      if (!cmd) return;
      cmdHistory.push(cmd);
      historyIndex = cmdHistory.length;

      fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd })
      })
      .then(res => res.json())
      .then(data => {
        console.log("Command executed:", data);
      })
      .catch(err => {
        console.error("Command error:", err);
      });
    }

    // Input handlers
    cmdSendBtn.addEventListener('click', () => {
      const val = cmdInput.value.trim();
      if (val) {
        sendCommand(val);
        cmdInput.value = '';
      }
    });

    cmdInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const val = cmdInput.value.trim();
        if (val) {
          sendCommand(val);
          cmdInput.value = '';
        }
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (cmdHistory.length > 0 && historyIndex > 0) {
          historyIndex--;
          cmdInput.value = cmdHistory[historyIndex];
        }
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (historyIndex < cmdHistory.length - 1) {
          historyIndex++;
          cmdInput.value = cmdHistory[historyIndex];
        } else {
          historyIndex = cmdHistory.length;
          cmdInput.value = '';
        }
      }
    });

    // Periodic Player Status Polling
    function updateStatus() {
      fetch('/api/status')
        .then(r => r.json())
        .then(data => {
          const connBadge = document.getElementById('conn-badge');
          const connText = document.getElementById('conn-text');
          if (data.connected) {
            connBadge.className = 'badge online';
            connText.textContent = 'ONLINE (Đã kết nối)';
          } else {
            connBadge.className = 'badge offline';
            connText.textContent = 'OFFLINE (Chưa kết nối)';
          }

          document.getElementById('server-info').textContent = (data.server_host || '--') + ':' + (data.server_port || '--');
          document.getElementById('char-name').textContent = data.char_name || '(Chưa đăng nhập)';
          document.getElementById('char-planet').textContent = '(' + (data.gender_name || '--') + ')';
          document.getElementById('map-zone-text').textContent = (data.map_name || 'Map --') + ' [ID: ' + data.map_id + '] - Khu ' + (data.zone_id >= 0 ? data.zone_id : '--');

          // HP Bar
          const hpCur = data.hp || 0;
          const hpMax = Math.max(data.hp_max || 1, 1);
          const hpPct = Math.min(Math.round((hpCur / hpMax) * 100), 100);
          document.getElementById('hp-text').textContent = hpCur.toLocaleString() + ' / ' + hpMax.toLocaleString();
          document.getElementById('hp-percent').textContent = hpPct + '%';
          document.getElementById('hp-bar').style.width = hpPct + '%';

          // MP Bar
          const mpCur = data.mp || 0;
          const mpMax = Math.max(data.mp_max || 1, 1);
          const mpPct = Math.min(Math.round((mpCur / mpMax) * 100), 100);
          document.getElementById('mp-text').textContent = mpCur.toLocaleString() + ' / ' + mpMax.toLocaleString();
          document.getElementById('mp-percent').textContent = mpPct + '%';
          document.getElementById('mp-bar').style.width = mpPct + '%';

          // Gold / Gem
          document.getElementById('char-gold').textContent = (data.gold || 0).toLocaleString();
          document.getElementById('char-gem').textContent = (data.gem || 0).toLocaleString();
        })
        .catch(() => {});
    }

    // Startup
    initSSE();
    updateStatus();
    setInterval(updateStatus, 1500);
  </script>
</body>
</html>
"""


class NroWebHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler phục vụ API và Single Page Application."""

    # Tắt in log HTTP mặc định ra console để tránh làm bẩn terminal
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(WEB_DASHBOARD_HTML.encode("utf-8"))

        elif path == "/api/logs/stream":
            self.handle_sse_stream()

        elif path == "/api/logs":
            broadcaster = self.server.broadcaster
            history = broadcaster.get_history()
            data = json.dumps(history, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        elif path == "/api/status":
            self.handle_status_api()

        elif path == "/api/bosses":
            self.handle_bosses_api()

        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/command":
            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8", errors="replace")
            try:
                data = json.loads(body)
                cmd_line = data.get("command", "").strip()
            except Exception:
                cmd_line = body.strip()

            if cmd_line and self.server.execute_cmd_func and self.server.client:
                # Thực thi lệnh trên thread riêng để không block HTTP server
                threading.Thread(
                    target=self.server.execute_cmd_func,
                    args=(self.server.client, cmd_line),
                    daemon=True
                ).start()

            res = json.dumps({"status": "ok", "command": cmd_line}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(res)

        elif path == "/api/clear":
            self.server.broadcaster.clear()
            res = json.dumps({"status": "cleared"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(res)

        else:
            self.send_error(404, "Not Found")

    def handle_sse_stream(self):
        """Phát sóng log qua Server-Sent Events (SSE)."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        broadcaster = self.server.broadcaster
        client_q = broadcaster.add_listener()

        try:
            # Gửi trước một lượng log gần nhất (last 150 lines) cho client mới vào
            history = broadcaster.get_history()
            initial_burst = history[-150:] if len(history) > 150 else history
            for entry in initial_burst:
                payload = json.dumps(entry, ensure_ascii=False)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
            self.wfile.flush()

            # Tiếp tục stream liên tục
            while not getattr(self.server, "stopped", False):
                try:
                    entry = client_q.get(timeout=1.5)
                    payload = json.dumps(entry, ensure_ascii=False)
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    # Gửi heartbeat keep-alive
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception:
            pass
        finally:
            broadcaster.remove_listener(client_q)

    def handle_status_api(self):
        client = self.server.client
        is_conn = client.isConnected() if client else False
        char = getattr(client, "myChar", None) if client else None
        map_info = getattr(char, "mapInfo", None) if char else None

        # Resolve gender name
        gender_map = {0: "Trái Đất", 1: "Namếc", 2: "Xayda"}
        gender_name = gender_map.get(getattr(char, "cgender", -1), "Chưa rõ")

        from ClientNROpy.xmap import get_map_name
        map_id = getattr(map_info, "mapID", -1) if map_info else -1
        map_name = get_map_name(map_id) if map_id >= 0 else "Chưa vào Map"

        status_data = {
            "connected": is_conn,
            "server_host": getattr(client, "host", "--") if client else "--",
            "server_port": getattr(client, "port", "--") if client else "--",
            "char_name": getattr(char, "cName", "") if char else "",
            "gender_name": gender_name,
            "map_id": map_id,
            "map_name": map_name,
            "zone_id": getattr(map_info, "zoneID", -1) if map_info else -1,
            "hp": getattr(char, "cHP", 0) if char else 0,
            "hp_max": getattr(char, "cHPFull", 1) if char else 1,
            "mp": getattr(char, "cMP", 0) if char else 0,
            "mp_max": getattr(char, "cMPFull", 1) if char else 1,
            "gold": getattr(char, "xu", 0) if char else 0,
            "gem": getattr(char, "luong", 0) if char else 0,
            "ruby": getattr(char, "luongKhoa", 0) if char else 0,
            "cx": getattr(char, "cx", 0) if char else 0,
            "cy": getattr(char, "cy", 0) if char else 0,
        }

        data = json.dumps(status_data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def handle_bosses_api(self):
        client = self.server.client
        bosses = client.get_bosses() if client else []
        boss_list = []
        for b in bosses:
            boss_list.append({
                "name": getattr(b, "name", "Boss"),
                "map_name": getattr(b, "map_name", "N/A"),
                "zone_id": getattr(b, "zone_id", -1),
                "is_died": getattr(b, "is_died", False),
                "killer": getattr(b, "killer", ""),
                "appear_time": getattr(b, "appear_time", ""),
            })
        data = json.dumps(boss_list, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)


class WebLogServer:
    """Quản lý vòng đời Web Server và chuyển hướng luồng log."""

    def __init__(self, client=None, execute_cmd_func=None, host="0.0.0.0", port=8080, also_console=False):
        self.client = client
        self.execute_cmd_func = execute_cmd_func
        self.host = host
        self.initial_port = port
        self.actual_port = port
        self.also_console = also_console

        self.broadcaster = LogBroadcaster(max_history=3000)
        self.httpd = None
        self.server_thread = None
        self.stopped = False

        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.capture_stdout = None
        self.capture_stderr = None

    def start(self, open_browser: bool = True) -> str:
        """Khởi động web server trên port trống và chuyển hướng log."""
        # Tìm cổng khả dụng từ initial_port
        curr_port = self.initial_port
        for p in range(curr_port, curr_port + 20):
            try:
                server_address = (self.host, p)
                self.httpd = ThreadingHTTPServer(server_address, NroWebHandler)
                self.actual_port = p
                break
            except OSError:
                continue

        if not self.httpd:
            raise RuntimeError(f"Không thể mở Web Server trên bất kỳ cổng nào từ {self.initial_port} đến {curr_port + 20}!")

        self.httpd.broadcaster = self.broadcaster
        self.httpd.client = self.client
        self.httpd.execute_cmd_func = self.execute_cmd_func
        self.httpd.stopped = False

        # Bật luồng bắt stdout / stderr
        self.capture_stdout = WebLogCapture(self.original_stdout, self.broadcaster, also_console=self.also_console)
        self.capture_stderr = WebLogCapture(self.original_stderr, self.broadcaster, also_console=self.also_console)
        sys.stdout = self.capture_stdout
        sys.stderr = self.capture_stderr

        # Chạy server trên background daemon thread
        self.server_thread = threading.Thread(target=self._serve, daemon=True)
        self.server_thread.start()

        url = f"http://localhost:{self.actual_port}"
        if open_browser:
            def _open():
                time.sleep(0.5)
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
            threading.Thread(target=_open, daemon=True).start()

        return url

    def _serve(self):
        try:
            self.httpd.serve_forever()
        except Exception:
            pass

    def stop(self):
        """Dừng server và khôi phục stdout/stderr."""
        self.stopped = True
        if self.httpd:
            self.httpd.stopped = True
            try:
                self.httpd.shutdown()
            except Exception:
                pass
        if self.capture_stdout:
            self.capture_stdout.flush()
        if self.capture_stderr:
            self.capture_stderr.flush()
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

    def set_console_echo(self, enabled: bool):
        """Bật/tắt in log đồng thời ra console."""
        self.also_console = enabled
        if self.capture_stdout:
            self.capture_stdout.also_console = enabled
        if self.capture_stderr:
            self.capture_stderr.also_console = enabled


_global_web_server = None


def start_web_server(client, execute_cmd_func, host="0.0.0.0", port=8080, also_console=False, open_browser=True) -> tuple:
    """Hàm tiện ích khởi động Web Log Server toàn cục."""
    global _global_web_server
    server = WebLogServer(
        client=client,
        execute_cmd_func=execute_cmd_func,
        host=host,
        port=port,
        also_console=also_console
    )
    url = server.start(open_browser=open_browser)
    _global_web_server = server
    return server, url


def stop_web_server():
    """Dừng Web Log Server toàn cục nếu đang chạy."""
    global _global_web_server
    if _global_web_server:
        _global_web_server.stop()
        _global_web_server = None
