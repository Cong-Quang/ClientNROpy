# -*- coding: utf-8 -*-
"""
Gói tin thông điệp (Message).
Mô phỏng chính xác Message.cs trong C#.
"""

from typing import Optional
from .reader import myReader
from .writer import myWriter


class Message:
    """
    Message mô phỏng Message.cs trong C#.
    Chứa command và luồng đọc (dis: myReader) hoặc luồng ghi (dos: myWriter).
    """

    def __init__(self, command: int = 0, data: Optional[bytes] = None):
        self.command: int = command if command < 128 else command - 256
        if data is not None:
            self.dis: myReader = myReader(data)
            self.dos: Optional[myWriter] = None
        else:
            self.dis: Optional[myReader] = None
            self.dos: myWriter = myWriter()

    def getData(self) -> Optional[bytes]:
        """Lấy dữ liệu từ luồng ghi dos."""
        if self.dos is not None:
            return self.dos.getData()
        return None

    def reader(self) -> myReader:
        """Lấy luồng đọc dis."""
        if self.dis is None:
            self.dis = myReader(self.getData() or b"")
        return self.dis

    def writer(self) -> myWriter:
        """Lấy luồng ghi dos."""
        if self.dos is None:
            self.dos = myWriter()
        return self.dos

    def readInt3Byte(self) -> int:
        """Đọc int (mô phỏng readInt3Byte trong Message.cs)."""
        return self.reader().readInt()

    def cleanup(self) -> None:
        """Dọn dẹp buffer."""
        if self.dis is not None:
            self.dis.close()
        if self.dos is not None:
            self.dos.close()

    def __repr__(self) -> str:
        return f"<Message cmd={self.command}>"
