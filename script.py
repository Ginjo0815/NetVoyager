import threading
import time
import sys
import netifaces
import requests
import subprocess

#-----------------------
interface = "eth0"
pingv4_targets = [
    ["8.8.8.8", "Google DNS"],
    ["8.8.4.4", "Google DNS Backup"],
    ["1.1.1.1", "Cloudflare DNS"],
    ["1.0.0.1", "Cloudflare DNS Backup"]
]
pingv4_option = "-c 1 -M do -s 1472 -W 1"
pingv6_targets = [
    ["2001:4860:4860::8888", "Google DNS IPv6"],
    ["2001:4860:4860::8844", "Google DNS Backup IPv6"],
    ["2606:4700:4700::1111", "Cloudflare DNS IPv6"],
    ["2606:4700:4700::1001", "Cloudflare DNS Backup IPv6"]
]
pingv6_option = "-c 1 -s 1452 -W 1"
http_check_targets = [
    ["http://www.google.com", "Google"],
    ["http://www.cloudflare.com", "Cloudflare"],
    ["http://www.example.com", "Example"]
]
#-----------------------

response_myipaddr = ""
response_ping_gateway_v4 = ""
response_ping_internet_v4 = []
response_ping_internet_v6 = []
response_http_checks = []
response_http_checks_lock = threading.Lock()

response_ping_internet_v4_lock = threading.Lock()
response_ping_internet_v6_lock = threading.Lock()

def myipaddr():
    global interface
    addrs = netifaces.ifaddresses(interface)
    if netifaces.AF_INET in addrs:
        ipv4_info = addrs[netifaces.AF_INET][0]
        gateways = netifaces.gateways()
        default_gateway = gateways['default'][netifaces.AF_INET][0]
        return ipv4_info.get('addr'), ipv4_info.get('netmask'), default_gateway
    return None

def ping_gateway_v4():
    global interface
    gateways = netifaces.gateways()
    default_gateway = gateways['default'][netifaces.AF_INET][0]
    cmd = ["ping", "-c", "1", "-M", "do", "-s", "1472", "-W", "1", default_gateway]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    if result.returncode == 0:
        response_ping_gateway_v4 = f"\033[92mOK\033[0m : {default_gateway}"
    else:
        response_ping_gateway_v4 = f"\033[91mNG\033[0m : {default_gateway}"
    return response_ping_gateway_v4

def ping_internet_v4(host, name):
    cmd = ["ping", "-c", "1", "-M", "do", "-s", "1472", "-W", "1", host]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    if result.returncode == 0:
        status = f"\033[92mOK\033[0m : {host} ({name})"
    else:
        status = f"\033[91mNG\033[0m : {host} ({name})"
    with response_ping_internet_v4_lock:
        response_ping_internet_v4.append(status)

def ping_internet_v6(host, name):
    cmd = ["ping6", "-c", "1", "-s", "1452", "-W", "1", host]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    if result.returncode == 0:
        status = f"\033[92mOK\033[0m : {host} ({name})"
    else:
        status = f"\033[91mNG\033[0m : {host} ({name})"
    with response_ping_internet_v6_lock:
        response_ping_internet_v6.append(status)

def theading_ping_internet_v4():
    threads = []
    for i in range(len(pingv4_targets)):
        thread = threading.Thread(target=ping_internet_v4, args=(pingv4_targets[i][0], pingv4_targets[i][1]))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()

def theading_ping_internet_v6():
    threads = []
    for i in range(len(pingv6_targets)):
        thread = threading.Thread(target=ping_internet_v6, args=(pingv6_targets[i][0], pingv6_targets[i][1]))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()

def check_http_response(url, name):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            status = f"\033[92mOK\033[0m : {url} ({name})"
        else:
            status = f"\033[91mNG\033[0m : {url} ({name}) - Status Code: {response.status_code}"
    except requests.exceptions.RequestException:
        status = f"\033[91mNG\033[0m : {url} ({name}) - Error"
    with response_http_checks_lock:
        response_http_checks.append(status)

def threading_http_checks():
    threads = []
    for target in http_check_targets:
        thread = threading.Thread(target=check_http_response, args=(target[0], target[1]))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()

def update_cli():
    global response_myipaddr
    global response_ping_gateway_v4
    global response_ping_internet_v4
    global response_ping_internet_v6

    response_myipaddr = myipaddr()
    response_ping_gateway_v4 = ping_gateway_v4()
    response_ping_internet_v4.clear()
    response_ping_internet_v6.clear()
    response_http_checks.clear()
    theading_ping_internet_v4()
    theading_ping_internet_v6()
    threading_http_checks()

    response_ping_internet_v4.sort()
    response_ping_internet_v6.sort()
    response_http_checks.sort()

    sys.stdout.write("\033[H\033[J")

    print("-------Setting-------")
    print(f"Interface: {interface}")
    print(f"IP Address: {response_myipaddr[0]}")
    print(f"Netmask: {response_myipaddr[1]}")
    print(f"Gateway: {response_myipaddr[2]}")
    print("\n-------IPv4 Ping Results-------")
    print(f"{response_ping_gateway_v4} (Gateway)")
    print("\n-------IPv4 Ping Results-------")
    for status in response_ping_internet_v4:
        print(status)
    print("\n-------IPv6 Ping Results-------")
    for status in response_ping_internet_v6:
        print(status)
    print("\n-------HTTP Check Results-------")
    for status in response_http_checks:
        print(status)

if __name__ == '__main__':       
    while True:
        update_cli()
        time.sleep(1) 

