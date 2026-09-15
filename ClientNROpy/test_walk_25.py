import sys
import time
from client import ClientNRO

def main():
    client = ClientNRO()
    # Connect
    client.connect("51.79.163.109", 12446)
    
    # Login
    print("Bắt đầu login...")
    client.service.login("poopooi01", "poopooi01", version="2.1.4")
    
    # Đợi load map
    for _ in range(50):
        if client.myChar and client.myChar.mapInfo and client.myChar.mapInfo.mapID != -1:
            break
        time.sleep(0.1)
        
    print(f"Đã login, đang ở map {client.myChar.mapInfo.mapID}")
    
    # Bắt đầu xmap tới 0
    client.xmap_controller.start_xmap(0)
    
    while client.xmap_controller.is_running:
        time.sleep(1)
        
    print("Xmap hoàn thành!")

if __name__ == "__main__":
    main()
