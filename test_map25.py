import os
import sys
import time
import threading

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ClientNROpy.client import ClientNRO

def run_test():
    client = ClientNRO(host="51.79.163.109", port=12457, version="2.1.4")
    has_entered = threading.Event()

    def on_char_info(char):
        print(f"[TEST] Đã vào game. Tọa độ ban đầu: Map {char.mapInfo.mapID}")
        has_entered.set()

    client.on_char_info(on_char_info)
    client.connect()
    time.sleep(1.0)
    # Thay username/password bằng tài khoản test nếu cần
    client.login("poopooi01", "02082003", version="2.1.4")

    if not has_entered.wait(20.0):
        print("[TEST] Không vào được game!")
        return

    time.sleep(3.0) # Đợi đồng bộ các gói tin khác

    print(f"\n======================================")
    print(f"[TEST] Bắt đầu Xmap tới map 26")
    print(f"======================================")
    
    # Kích hoạt Xmap tới Trạm Tàu Vũ Trụ Xayda (26)
    client.xmap(26)
    
    while True:
        if client.xmap_controller and client.xmap_controller.is_acting:
            time.sleep(1.0)
        else:
            break
            
    time.sleep(5.0)

if __name__ == "__main__":
    run_test()
