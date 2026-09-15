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

    # Lộ trình test
    route = [0, 47, 2, 9, 68, 64, 74, 102, 109]
    
    # Bật lại capsule
    if client.xmap_controller:
        client.xmap_controller.use_capsule = True
        
    for target in route:
        print(f"\n======================================")
        print(f"[TEST] Bắt đầu Xmap tới map {target}")
        print(f"======================================")
        
        client.xmap(target)
        
        while True:
            if client.xmap_controller and client.xmap_controller.is_acting:
                time.sleep(1.0)
            else:
                break
                
        my_char = client.get_my_char()
        if my_char and my_char.mapInfo.mapID == target:
            print(f"[TEST] [THÀNH CÔNG] Đã đến map {target}!")
        else:
            print(f"[TEST] [THẤT BẠI] Không thể đến map {target}!")
            
        time.sleep(3.0)

    print("\n[TEST] HOÀN TẤT!")
    
if __name__ == "__main__":
    run_test()
