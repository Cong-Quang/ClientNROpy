# -*- coding: utf-8 -*-
"""
Bộ điều khiển vòng đời và máy trạng thái Xmap,
mô phỏng XmapController.cs trong Dragonboy C#.
"""

import threading
import time
from typing import Callable, Dict, List, Optional, Union, TYPE_CHECKING
from .xmap_objects import MapNext
from .xmap_data import XmapData
from .xmap_algorithm import XmapAlgorithm
from .xmap_executor import XmapExecutor
from .map_data import get_map_name, resolve_map_id

if TYPE_CHECKING:
    from ..client import ClientNRO


class XmapController:
    """
    Quản lý luồng thực thi tìm đường và tự động chuyển map trong môi trường nền (Background Thread).
    """

    def __init__(self, client: "ClientNRO"):
        self.client: "ClientNRO" = client
        self.xmap_data: XmapData = XmapData()

        self.is_acting: bool = False
        self.map_end: Optional[int] = None
        self.way: Optional[List[MapNext]] = None
        self.index_way: int = 0
        self.is_next_map_failed: bool = False
        self.status_message: str = "Sẵn sàng"

        # Cấu hình sử dụng Capsule (mô phỏng Pk9rXmap trong Dragonboy C#)
        self.is_use_capsule_vip: bool = True         # Mặc định BẬT Capsule Đặc Biệt (ID 194)
        self.is_use_capsule_normal: bool = False      # Mặc định TẮT Capsule Thường (ID 193)

        self._thread: Optional[threading.Thread] = None
        self._lock: threading.Lock = threading.Lock()

        self.on_status_callbacks: List[Callable[[str], None]] = []
        self.on_finish_callbacks: List[Callable[[bool, str], None]] = []

    def has_item_capsule_vip(self) -> bool:
        """Kiểm tra nhân vật có Capsule Đặc Biệt (ID 194) trong Balo hay không."""
        return any(it is not None and it.template_id == 194 for it in self.client.myChar.arrItemBag)

    def has_item_capsule_normal(self) -> bool:
        """Kiểm tra nhân vật có Capsule Thường (ID 193) trong Balo hay không."""
        return any(it is not None and it.template_id == 193 for it in self.client.myChar.arrItemBag)

    def can_use_capsule_vip(self) -> bool:
        """Kiểm tra điều kiện được phép dùng Capsule Đặc Biệt."""
        return self.is_use_capsule_vip and self.has_item_capsule_vip()

    def can_use_capsule_normal(self) -> bool:
        """Kiểm tra điều kiện được phép dùng Capsule Thường."""
        return self.is_use_capsule_normal and self.has_item_capsule_normal()

    def toggle_use_capsule_vip(self) -> bool:
        """Bật/tắt sử dụng Capsule Đặc Biệt."""
        self.is_use_capsule_vip = not self.is_use_capsule_vip
        st = "BẬT" if self.is_use_capsule_vip else "TẮT"
        self._log(f"Sử dụng Capsule Đặc Biệt: {st}")
        return self.is_use_capsule_vip

    def toggle_use_capsule_normal(self) -> bool:
        """Bật/tắt sử dụng Capsule Thường."""
        self.is_use_capsule_normal = not self.is_use_capsule_normal
        st = "BẬT" if self.is_use_capsule_normal else "TẮT"
        self._log(f"Sử dụng Capsule Thường: {st}")
        return self.is_use_capsule_normal

    def _log(self, msg: str) -> None:
        self.status_message = msg
        print(f"[Xmap] {msg}")
        for cb in self.on_status_callbacks:
            try:
                cb(msg)
            except Exception:
                pass

    def get_status(self) -> Dict:
        """Lấy thông tin trạng thái hoạt động hiện tại của Xmap."""
        curr_map = self.client.myChar.mapInfo.mapID
        return {
            "is_acting": self.is_acting,
            "current_map_id": curr_map,
            "current_map_name": get_map_name(curr_map),
            "target_map_id": self.map_end,
            "target_map_name": get_map_name(self.map_end) if self.map_end is not None else None,
            "current_step": self.index_way + 1 if self.way else 0,
            "total_steps": len(self.way) if self.way else 0,
            "status_message": self.status_message,
            "capsule_vip": "BẬT" if self.is_use_capsule_vip else "TẮT",
            "has_capsule_vip": self.has_item_capsule_vip(),
            "capsule_normal": "BẬT" if self.is_use_capsule_normal else "TẮT",
            "has_capsule_normal": self.has_item_capsule_normal(),
        }

    def find_path(self, start_map: int, end_map: int, use_capsule: bool = True) -> Optional[List[MapNext]]:
        """Tra cứu đường đi giữa hai map mà không cần di chuyển."""
        cgender = self.client.myChar.cgender
        task_id = self.client.myChar.ctaskId
        self.xmap_data.load(cgender=cgender, task_id=task_id)

        if use_capsule:
            capsule_id = None
            if self.can_use_capsule_vip():
                capsule_id = 194
            elif self.can_use_capsule_normal():
                capsule_id = 193
            if capsule_id is not None:
                caps_names = getattr(self.client.controller, "capsule_map_names", None)
                self.xmap_data.load_link_map_capsule(
                    current_map=start_map,
                    cgender=cgender,
                    capsule_map_names=caps_names if caps_names else None,
                    capsule_item_id=capsule_id,
                )

        return XmapAlgorithm.find_way(self.xmap_data, start_map, end_map)

    def start(self, target: Union[int, str]) -> bool:
        """
        Bắt đầu Xmap di chuyển tới map chỉ định (ID hoặc tên map/alias).
        Trả về True nếu bắt đầu tiến trình thành công, False nếu target không hợp lệ.
        """
        cgender = self.client.myChar.cgender
        target_id = resolve_map_id(target, cgender=cgender)

        if target_id is None:
            self._log(f"Không nhận diện được map: '{target}'!")
            return False

        curr_map = self.client.myChar.mapInfo.mapID
        if curr_map == target_id:
            self._log(f"Bạn đã ở sẵn tại map '{get_map_name(target_id)}' (ID: {target_id}) rồi!")
            return True

        with self._lock:
            if self.is_acting:
                self.stop()
                time.sleep(0.2)

            self.map_end = target_id
            self.way = None
            self.index_way = 0
            self.is_next_map_failed = False
            self.is_acting = True

            self._log(f"Bắt đầu Xmap từ '{get_map_name(curr_map)}' (ID: {curr_map}) "
                      f"tới '{get_map_name(target_id)}' (ID: {target_id})...")

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            return True

    def stop(self) -> None:
        """Hủy tiến trình Xmap đang thực hiện."""
        with self._lock:
            if self.is_acting:
                self._log("Người chơi yêu cầu hủy Xmap.")
                self.is_acting = False
                self.way = None
                self.index_way = 0

    def _run_loop(self) -> None:
        """Vòng lặp máy trạng thái điều khiển di chuyển qua từng chặng map."""
        while self.is_acting:
            try:
                curr_map = self.client.myChar.mapInfo.mapID

                # 1. Đã tới map đích
                if curr_map == self.map_end:
                    dest_name = get_map_name(self.map_end)
                    self._log(f"Chúc mừng! Đã đến đích thành công: '{dest_name}' (ID: {self.map_end})!")
                    self.is_acting = False
                    self.way = None
                    for cb in self.on_finish_callbacks:
                        try:
                            cb(True, dest_name)
                        except Exception:
                            pass
                    break

                # 2. Chưa có lộ trình hoặc cần tính toán lại lộ trình
                if self.way is None:
                    cgender = self.client.myChar.cgender
                    task_id = self.client.myChar.ctaskId
                    self.xmap_data.load(cgender=cgender, task_id=task_id)

                    # Nạp liên kết bay nhanh từ Capsule nếu người chơi có Capsule trong Balo
                    capsule_id = None
                    if self.can_use_capsule_vip():
                        capsule_id = 194
                        self._log("Sử dụng Capsule Đặc Biệt trong Balo để bay nhanh!")
                    elif self.can_use_capsule_normal():
                        capsule_id = 193
                        self._log("Sử dụng Capsule Thường trong Balo để bay nhanh!")

                    if capsule_id is not None:
                        caps_names = getattr(self.client.controller, "capsule_map_names", None)
                        self.xmap_data.load_link_map_capsule(
                            current_map=curr_map,
                            cgender=cgender,
                            capsule_map_names=caps_names if caps_names else None,
                            capsule_item_id=capsule_id,
                        )

                    self.way = XmapAlgorithm.find_way(self.xmap_data, curr_map, self.map_end)
                    self.index_way = 0

                    if self.way is None or len(self.way) == 0:
                        self._log(f"Không tìm thấy đường đi từ ID {curr_map} tới ID {self.map_end}!")
                        self.is_acting = False
                        for cb in self.on_finish_callbacks:
                            try:
                                cb(False, "Không tìm thấy đường đi")
                            except Exception:
                                pass
                        break

                    path_str = " -> ".join([str(step.to) for step in self.way])
                    self._log(f"Đã lập lộ trình ({len(self.way)} chặng): {curr_map} -> {path_str}")

                # 3. Đang ở map bắt đầu của chặng hiện tại
                if curr_map == self.way[self.index_way].map_start:
                    # Kiểm tra nếu nhân vật bị chết thật sự
                    is_dead = (self.client.myChar.cHPFull > 0 and self.client.myChar.cHP <= 0) or self.client.myChar.statusMe == 14
                    if is_dead:
                        self._log("Nhân vật bị kiệt sức! Tự động hồi sinh về thành...")
                        self.client.service.returnTownFromDead()
                        self.way = None
                        time.sleep(2.0)
                        continue

                    # Thực thi bước chuyển map kế tiếp
                    step = self.way[self.index_way]
                    target_name = get_map_name(step.to)
                    self._log(f"[{self.index_way + 1}/{len(self.way)}] Chuyển map sang: {target_name} (ID: {step.to}) [{step.type.name}]...")

                    success = XmapExecutor.execute_next_map(self.client, step)
                    if not success:
                        self._log(f"Không thể thực hiện bước chuyển map sang ID {step.to}! Thử lại sau 1s...")
                        time.sleep(1.0)
                        continue

                    # Chờ máy chủ phản hồi gói tin chuyển map
                    for _ in range(30):
                        time.sleep(0.1)
                        if not self.is_acting:
                            break
                        if self.client.myChar.mapInfo.mapID != curr_map:
                            break

                    continue

                # 4. Đã sang map đích của chặng hiện tại thành công
                elif curr_map == self.way[self.index_way].to:
                    self.index_way += 1
                    time.sleep(0.3)
                    continue

                # 5. Lệch khỏi lộ trình (bị dịch chuyển, chết về nhà, rơi vào map khác)
                else:
                    self._log(f"Vị trí hiện tại ({curr_map}) lệch khỏi lộ trình! Tự động tính toán lại đường đi...")
                    self.way = None
                    self.index_way = 0
                    time.sleep(0.5)
                    continue

            except Exception as ex:
                self._log(f"Lỗi ngoại lệ trong vòng lặp Xmap: {ex}")
                time.sleep(1.0)
