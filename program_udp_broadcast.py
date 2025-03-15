import socket
import threading
import atexit
import json
import time
import os
from datetime import datetime

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        s.close()
        return "192.168.1.1"


def get_ip_subnet(ip):
    return ".".join(ip.split(".")[:-1])

def render_online_users(online_users):
    print("Online Users:")
    for i, user in enumerate(online_users):
        if (user["unread_messages"] == 0):
            print(f"{i + 1}. {user['name']}")
        else:    
            print(f"{i + 1}. {user['name']} ({user['unread_messages']} unread messages)")


def send_json(ip, message):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            s.connect((ip, 40000))
            s.send(json.dumps(message).encode())
            s.close()
            return True
    except:
        return False    

username = input("Enter your name: ")
while username.strip() == "" or len(username) >= 128:
    print("Invalid username")
    username = input("Enter your name: ")

my_ip = get_ip()
broadcast_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
broadcast_server.bind(("0.0.0.0", 40000))

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((my_ip, 40000))
server.listen()

online_users = [] 
renderState = 1
active_user = -1
thread_lock = threading.Lock()


def close_servers():
    broadcast_server.close()
    server.close()
atexit.register(close_servers)


def serverThread():
    global renderState
    global active_user
    while True:
        client, address = server.accept()
        output = client.recv(1024).decode()
        client.close()
        if output:
            try:
                client_ip = address[0]
                message = output.strip()
                message = json.loads(message)
                message_type = message["type"]
                if (message_type == "MESSAGE"):
                    payload = message["payload"]
                    sender_name = message["sender_name"]

                    with thread_lock:
                        for user in online_users:
                            if user["ip"] == client_ip:
                                user["messages"].append({"sender": sender_name, "message": payload, "timestamp": message["timestamp"]})
                                if renderState != 2 and renderState != 3:
                                    user["unread_messages"] += 1
                                    renderState = 1
                                elif active_user != -1 and online_users[active_user]["ip"] == client_ip:
                                    renderState = 3    
                                else:    
                                    user["unread_messages"] += 1    
                                break         
                elif (message_type == "DISCOVER_RESP"):
                    sender_name = message["responder_name"]
                    with thread_lock:
                        online_users.append({"ip": client_ip, "name": sender_name, "unread_messages": 0, "messages": []})
                        if renderState == 0:
                            renderState = 1
            except:
                pass

recieved_timestamps = set()

def broadcast_server_thread():
    global renderState
    while True:
        data, addr = broadcast_server.recvfrom(1024)
        try:
            client_ip = addr[0]
            if client_ip == my_ip:
                continue
            message = json.loads(data.decode().strip())
            if message["sequence_number"] in recieved_timestamps:
                continue
    
            recieved_timestamps.add(message["sequence_number"])
            with thread_lock:
                online_users.append({"ip": client_ip, "name": message["sender_name"], "unread_messages": 0, "messages": []})
                send_json(client_ip, {"type": "DISCOVER_RESP", "responder_ip": my_ip, "responder_name": username})
                if renderState == 0:
                    renderState = 1
        except:
            pass
        


ip_subnet = get_ip_subnet(my_ip)
broadcast_ip = ip_subnet + ".255"

broadcastThread = threading.Thread(target=broadcast_server_thread, daemon=True)
broadcastThread.start()

server_Thread = threading.Thread(target=serverThread, daemon=True)
server_Thread.start()

print("Searching for users...")
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    discoverJson = json.dumps({"type": "DISCOVER_REQ", "sender_ip": my_ip, "sender_name": username, "sequence_number": (int)(time.time())}).encode()   
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.sendto(discoverJson, (broadcast_ip, 40000))
    s.sendto(discoverJson, (broadcast_ip, 40000))
    s.sendto(discoverJson, (broadcast_ip, 40000))
    s.close()



def renderThread():
    global renderState
    global active_user
    while True:
        with thread_lock:
            if renderState == 1:
                os.system('cls' if os.name == 'nt' else 'clear')
                render_online_users(online_users)
                print()
                if (len(online_users) != 0):
                    print("Enter user index to view chat or enter Q to exit the program: ")
                renderState = 0
            elif renderState == 3:
                os.system('cls' if os.name == 'nt' else 'clear')
                print(f"Chat with {online_users[active_user]['name']}:")
                for message in online_users[active_user]["messages"]:
                    print(f"{message['sender']}: {message['message']} ({datetime.fromtimestamp(int(message['timestamp'])).strftime('%d.%m.%Y %H:%M:%S')})")
                print()    
                print("Enter message or enter Q to go back to previous menu: ")    
                renderState = 2            
        time.sleep(0.3)




def inputThread():
    global renderState
    global active_user
    while True:
        userInput = input()
        with thread_lock:
            if renderState == 0 or renderState == 1:
                if userInput == "Q":
                    os._exit(0)
                if len(online_users) <= 0:
                    continue
                if (not userInput.isdigit()) or (int(userInput) < 1 or int(userInput) > len(online_users)):
                    print("Invalid user index")
                    continue
                active_user = int(userInput) - 1
                online_users[active_user]["unread_messages"] = 0
                renderState = 3
            else:
                message = userInput
                if len(message) >= 128:
                    print("Message is too long")
                    continue
                if message == "Q":
                    renderState = 1
                else:
                    res = send_json(online_users[active_user]["ip"], {"type": "MESSAGE", "sender_name": username, "payload": message, "timestamp": int(time.time())})
                    if res:
                        online_users[active_user]["messages"].append({"sender": username, "message": message, "timestamp": int(time.time())})
                        renderState = 3
                    else:
                        print("Failed to send message")    
        time.sleep(0.5)        




input_Thread = threading.Thread(target=inputThread)
input_Thread.daemon = True
input_Thread.start()

time.sleep(1)
os.system('cls' if os.name == 'nt' else 'clear')

render_Thread = threading.Thread(target=renderThread)
render_Thread.daemon = True
render_Thread.start()

input_Thread.join()

