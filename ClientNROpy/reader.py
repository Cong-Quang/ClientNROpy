# -*- coding: utf-8 -*-
"""
Bộ đọc dữ liệu nhị phân Big-Endian (myReader).
Mô phỏng chính xác myReader.cs trong C#.
"""

import struct
from typing import Optional, Any, List


class myReader:
    """
    myReader mô phỏng class myReader trong C#.
    Đọc dữ liệu nhị phân kiểu Big-Endian (sbyte, byte, short, int, long, UTF-8 string).
    """

    def __init__(self, data: Optional[bytes | bytearray | List[int]] = None):
        if data is None:
            self.buffer = bytearray()
        elif isinstance(data, (bytes, bytearray)):
            self.buffer = bytearray(data)
        elif isinstance(data, list):
            self.buffer = bytearray([(b & 0xFF) for b in data])
        else:
            self.buffer = bytearray(data)
        self.posRead: int = 0
        self.posMark: int = 0

    def readSByte(self) -> int:
        """Đọc 1 byte có dấu (-128 .. 127)."""
        if self.posRead < len(self.buffer):
            b = self.buffer[self.posRead]
            self.posRead += 1
            return b if b < 128 else b - 256
        self.posRead = len(self.buffer)
        raise EOFError("loi doc sbyte eof")

    def readsbyte(self) -> int:
        return self.readSByte()

    def readByte(self) -> int:
        return self.readSByte()

    def readUnsignedByte(self) -> int:
        """Đọc 1 byte không dấu (0 .. 255)."""
        val = self.readSByte()
        return val if val >= 0 else val + 256

    def readShort(self) -> int:
        """Đọc 2 byte số nguyên có dấu Big-Endian (-32768 .. 32767)."""
        if self.posRead + 2 <= len(self.buffer):
            val = struct.unpack(">h", self.buffer[self.posRead:self.posRead + 2])[0]
            self.posRead += 2
            return val
        raise EOFError("loi doc short eof")

    def readUnsignedShort(self) -> int:
        """Đọc 2 byte số nguyên không dấu Big-Endian (0 .. 65535)."""
        if self.posRead + 2 <= len(self.buffer):
            val = struct.unpack(">H", self.buffer[self.posRead:self.posRead + 2])[0]
            self.posRead += 2
            return val
        raise EOFError("loi doc ushort eof")

    def readInt(self) -> int:
        """Đọc 4 byte số nguyên có dấu Big-Endian."""
        if self.posRead + 4 <= len(self.buffer):
            val = struct.unpack(">i", self.buffer[self.posRead:self.posRead + 4])[0]
            self.posRead += 4
            return val
        raise EOFError("loi doc int eof")

    def readInt3Byte(self) -> int:
        """Đọc int tương tự hàm trong C# Message.cs."""
        return self.readInt()

    def readLong(self) -> int:
        """Đọc 8 byte số nguyên có dấu Big-Endian."""
        if self.posRead + 8 <= len(self.buffer):
            val = struct.unpack(">q", self.buffer[self.posRead:self.posRead + 8])[0]
            self.posRead += 8
            return val
        raise EOFError("loi doc long eof")

    def readBool(self) -> bool:
        """Đọc 1 byte boolean (True nếu > 0)."""
        return self.readSByte() > 0

    def readBoolean(self) -> bool:
        return self.readBool()

    def readString(self) -> str:
        """Đọc chuỗi UTF-8: độ dài 2 byte short + nội dung bytes."""
        length = self.readShort()
        if length < 0:
            return ""
        if self.posRead + length <= len(self.buffer):
            raw = self.buffer[self.posRead:self.posRead + length]
            self.posRead += length
            return raw.decode("utf-8", errors="replace")
        raise EOFError("loi doc string eof")

    def readStringUTF(self) -> str:
        return self.readString()

    def readUTF(self) -> str:
        return self.readString()

    def read(self, length: Optional[int] = None) -> Any:
        if length is None:
            if self.posRead < len(self.buffer):
                return self.readSByte()
            return -1
        if self.posRead + length <= len(self.buffer):
            res = self.buffer[self.posRead:self.posRead + length]
            self.posRead += length
            return res
        raise EOFError("loi doc read bytes eof")

    def readFully(self, length: int) -> bytearray:
        return self.read(length)

    def mark(self, readlimit: int = 0) -> None:
        self.posMark = self.posRead

    def reset(self) -> None:
        self.posRead = self.posMark

    def available(self) -> int:
        return len(self.buffer) - self.posRead

    def close(self) -> None:
        self.buffer = bytearray()
        self.posRead = 0

    def Close(self) -> None:
        self.close()
