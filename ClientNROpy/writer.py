# -*- coding: utf-8 -*-
"""
Bộ ghi dữ liệu nhị phân Big-Endian (myWriter).
Mô phỏng chính xác myWriter.cs trong C#.
"""

import struct
from typing import Optional, List


class myWriter:
    """
    myWriter mô phỏng class myWriter trong C#.
    Ghi dữ liệu nhị phân Big-Endian vào buffer và tự động co dãn.
    """

    def __init__(self, length: int = 2048):
        self.buffer = bytearray()
        self.posWrite: int = 0
        self.lenght: int = length

    def writeSByte(self, value: int) -> None:
        """Ghi 1 byte có dấu (-128 .. 127)."""
        self.buffer.append(value & 0xFF)
        self.posWrite += 1

    def writeByte(self, value: int) -> None:
        self.writeSByte(value)

    def writeUnsignedByte(self, value: int) -> None:
        self.writeSByte(value)

    def writeChar(self, value: str) -> None:
        self.writeSByte(0)
        self.writeSByte(ord(value[0]) if value else 0)

    def writeShort(self, value: int) -> None:
        """Ghi 2 byte short Big-Endian."""
        data = struct.pack(">h", int(value))
        self.buffer.extend(data)
        self.posWrite += 2

    def writeUnsignedShort(self, value: int) -> None:
        data = struct.pack(">H", int(value))
        self.buffer.extend(data)
        self.posWrite += 2

    def writeInt(self, value: int) -> None:
        """Ghi 4 byte int Big-Endian."""
        data = struct.pack(">i", int(value))
        self.buffer.extend(data)
        self.posWrite += 4

    def writeLong(self, value: int) -> None:
        """Ghi 8 byte long Big-Endian."""
        data = struct.pack(">q", int(value))
        self.buffer.extend(data)
        self.posWrite += 8

    def writeBoolean(self, value: bool) -> None:
        """Ghi 1 byte boolean (1 nếu True, 0 nếu False)."""
        self.writeSByte(1 if value else 0)

    def writeBool(self, value: bool) -> None:
        self.writeBoolean(value)

    def writeString(self, value: str) -> None:
        """Ghi chuỗi UTF-8: độ dài 2 byte short + nội dung bytes."""
        utf8_bytes = value.encode("utf-8")
        self.writeShort(len(utf8_bytes))
        self.buffer.extend(utf8_bytes)
        self.posWrite += len(utf8_bytes)

    def writeUTF(self, value: str) -> None:
        self.writeString(value)

    def write(self, data: bytes | bytearray | List[int]) -> None:
        if isinstance(data, list):
            data = bytes([(b & 0xFF) for b in data])
        self.buffer.extend(data)
        self.posWrite += len(data)

    def getData(self) -> Optional[bytes]:
        """Lấy mảng bytes đã ghi."""
        if len(self.buffer) == 0:
            return None
        return bytes(self.buffer)

    def close(self) -> None:
        self.buffer = bytearray()
        self.posWrite = 0

    def Close(self) -> None:
        self.close()
