import socket
import json
import os
import time
import threading
from datetime import datetime
import atexit

# Get the IP address of the device
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip


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
while username.strip() == "" or len(username) >= 32:
    print("Invalid username")
    username = input("Enter your name: ")
    
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((get_ip(), 40000))
server.listen()

def close_server():
    server.close()
atexit.register(close_server)    

my_ip = get_ip()
ip_subnet = get_ip_subnet(my_ip)
discoverJson = json.dumps({"type": "DISCOVER_REQ", "sender_ip": my_ip, "sender_name": username})

online_users = [] 
renderState = 1
active_user = -1
thread_lock = threading.Lock()
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
                if (message_type == "DISCOVER_REQ"):
                    with thread_lock:
                        online_users.append({"ip": client_ip, "name": message["sender_name"], "unread_messages": 0, "messages": []})
                        send_json(client_ip, {"type": "DISCOVER_RESP", "responder_ip": my_ip, "responder_name": username})
                        if renderState == 0:
                            renderState = 1
                elif (message_type == "MESSAGE"):
                    payload = message["payload"]
                    sender_name = message["sender_name"]

                    with thread_lock:
                        for user in online_users:
                            if user["ip"] == client_ip:
                                user["messages"].append({"sender": sender_name, "message": payload, "timestamp": message["timestamp"]})
                                if renderState != 2 and renderState != 3:
                                    user["unread_messages"] += 1
                                    renderState = 1
                                else:    
                                    renderState = 3 
                                break         
                elif (message_type == "DISCOVER_RESP"):
                    sender_name = message["responder_name"]
                    with thread_lock:
                        online_users.append({"ip": client_ip, "name": sender_name, "unread_messages": 0, "messages": []})
                        if renderState == 0:
                            renderState = 1
            except:
                pass
serverThread = threading.Thread(target=serverThread)
serverThread.daemon = True
serverThread.start()

print("Discovering users in the network, this might take a while...")
def discover_users(ip_start, ip_end):
    for i in range(ip_start, ip_end):
        try:
            current_discover = ip_subnet + "." + str(i)
            if current_discover == my_ip:
                continue
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect((current_discover, 40000))
                s.send(discoverJson.encode())
                s.close()
        except:
            pass     

#Discover users in parallel
threads = []
for i in range(1, 255, 10):
    if i + 10 > 255:
        if i < 255:
            thread = threading.Thread(target=discover_users, args=(i, 255))
            thread.start()
            threads.append(thread)
            break
        else:
            break
    thread = threading.Thread(target=discover_users, args=(i, i + 10))
    thread.start()
    threads.append(thread)

for thread in threads:
    thread.join()



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
                    print("Enter user index to view chat: ")
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




inputThread = threading.Thread(target=inputThread)
inputThread.daemon = True
inputThread.start()

time.sleep(1)
os.system('cls' if os.name == 'nt' else 'clear')

renderThread = threading.Thread(target=renderThread)
renderThread.daemon = True
renderThread.start()

inputThread.join()
