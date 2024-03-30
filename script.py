import threading
import time
import sys
import netifaces
import requests
import subprocess
import os


#-----------------------
interface = "eth0"
pingv4_targets = [
    ["8.8.8.8", "Google DNS"],
    ["8.8.4.4", "Google DNS Backup"],
    ["1.1.1.1", "Cloudflare DNS"],
    ["1.0.0.1", "Cloudflare DNS Backup"]
]
pingv4_large_option = ["-c", "1", "-M", "do", "-s", "1472", "-W", "1"]
pingv4_short_option = ["-c", "1", "-s", "64", "-W", "1"]
pingv6_targets = [
    ["2001:4860:4860::8888", "Google DNS IPv6"],
    ["2001:4860:4860::8844", "Google DNS Backup IPv6"],
    ["2606:4700:4700::1111", "Cloudflare DNS IPv6"],
    ["2606:4700:4700::1001", "Cloudflare DNS Backup IPv6"]
]
pingv6_large_option = ["-c", "1", "-s", "1452", "-W", "1"]
pingv6_short_option = ["-c", "1", "-s", "128", "-W", "1"]
http_check_targets = [
    ["http://ipv4.google.com", "Google-IPv4"],
    ["http://ipv6.google.com", "Google-IPv6"]
]
virus_check_targets = [
    ["http://example.com/malicious_file", "Malicious File 1"],
    ["http://example.org/bad_file", "Malicious File 2"]
]
mtr_v4_targets = [
    ["139.130.4.5", "Australia DNS"],
]
mtr_v6_targets = [
    ["2001:4860:4860::8844", "Google DNS IPv6 Secondary"],
]

#-----------------------

response_myipaddr = ""
response_ping_gateway_v4 = ""
response_ping_internet_v4 = []
response_ping_internet_v4_lock = threading.Lock()
response_ping_internet_v6 = []
response_ping_internet_v6_lock = threading.Lock()
response_http_checks = []
response_http_checks_lock = threading.Lock()
response_virus_checks = []
response_virus_checks_lock = threading.Lock()
response_mtr_checks = []
response_mtr_checks_lock = threading.Lock()



def myipaddr():
    global interface
    ipv6_addr = None
    ipv4_addr = None
    netmask = None
    gateway = None
    try:
        addrs = netifaces.ifaddresses(interface)
        # IPv4アドレスとネットマスクの取得
        if netifaces.AF_INET in addrs:
            ipv4_info = addrs[netifaces.AF_INET][0]
            ipv4_addr = ipv4_info.get('addr')
            netmask = ipv4_info.get('netmask')
        # デフォルトゲートウェイの取得
        gateways = netifaces.gateways()
        if netifaces.AF_INET in gateways['default']:
            gateway = gateways['default'][netifaces.AF_INET][0]
        # IPv6アドレスの取得（リンクローカルアドレスを除外）
        if netifaces.AF_INET6 in addrs:
            for addr_info in addrs[netifaces.AF_INET6]:
                if addr_info['addr'].startswith('fe80') is False:
                    ipv6_addr = addr_info['addr'].split('%')[0]  # ゾーンインデックスを除去
                    break
    except Exception as e:
        print(f"IPアドレス取得中にエラーが発生しました: {e}")

    return ipv4_addr, netmask, gateway, ipv6_addr

def ping_gateway_v4():
    global interface
    gateways = netifaces.gateways()
    default_gateway = gateways['default'][netifaces.AF_INET][0]
    
    # ショートパケットでの疎通確認
    short_packet_cmd = ["ping"] + pingv4_short_option + [default_gateway]
    short_packet_result = subprocess.run(short_packet_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    short_status = "OK" if short_packet_result.returncode == 0 else "NG"
    short_color = "\033[92m" if short_status == "OK" else "\033[91m"

    # ラージパケットでの疎通確認
    large_packet_cmd = ["ping"] + pingv4_large_option + [default_gateway]
    large_packet_result = subprocess.run(large_packet_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    large_status = "OK" if large_packet_result.returncode == 0 else "NG"
    large_color = "\033[92m" if large_status == "OK" else "\033[91m"
    
    # 全体のステータスの決定
    status = "OK" if short_status == "OK" and large_status == "OK" else "NG"
    status_color = "\033[92m" if status == "OK" else "\033[91m"

    # 結果の結合
    combined_status = f"{status_color}{status}\033[0m ({short_color}Short\033[0m / {large_color}Large\033[0m) : {default_gateway}"

    return combined_status

def ping_internet_v4(host, name):
    # ショートパケットでの疎通確認
    short_packet_cmd = ["ping"] + pingv4_short_option + [host]
    short_packet_result = subprocess.run(short_packet_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    short_status = "OK" if short_packet_result.returncode == 0 else "NG"
    short_color = "\033[92m" if short_status == "OK" else "\033[91m"

    # ラージパケットでの疎通確認
    large_packet_cmd = ["ping"] + pingv4_large_option + [host]
    large_packet_result = subprocess.run(large_packet_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    large_status = "OK" if large_packet_result.returncode == 0 else "NG"
    large_color = "\033[92m" if large_status == "OK" else "\033[91m"
    
    # 全体のステータスの決定
    status = "OK" if short_status == "OK" and large_status == "OK" else "NG"
    status_color = "\033[92m" if status == "OK" else "\033[91m"

    # 結果の結合
    combined_status = f"{status_color}{status}\033[0m ({short_color}Short\033[0m / {large_color}Large\033[0m) : {host} ({name})"
    
    with response_ping_internet_v4_lock:
        response_ping_internet_v4.append(combined_status)

def ping_internet_v6(host, name):
    # ショートパケットでの疎通確認
    short_packet_cmd = ["ping6"] + pingv6_short_option + [host]
    short_packet_result = subprocess.run(short_packet_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    short_status = "OK" if short_packet_result.returncode == 0 else "NG"
    short_color = "\033[92m" if short_status == "OK" else "\033[91m"

    # ラージパケットでの疎通確認
    large_packet_cmd = ["ping6"] + pingv6_large_option + [host]
    large_packet_result = subprocess.run(large_packet_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    large_status = "OK" if large_packet_result.returncode == 0 else "NG"
    large_color = "\033[92m" if large_status == "OK" else "\033[91m"
    
    # 全体のステータスの決定
    status = "OK" if short_status == "OK" and large_status == "OK" else "NG"
    status_color = "\033[92m" if status == "OK" else "\033[91m"

    # 結果の結合
    combined_status = f"{status_color}{status}\033[0m ({short_color}Short\033[0m / {large_color}Large\033[0m) : {host} ({name})"
    
    with response_ping_internet_v6_lock:
        response_ping_internet_v6.append(combined_status)


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
        status = f"\033[92mOK ({response.status_code})\033[0m : {url} ({name})" if response.status_code == 200 else f"\033[91mNG ({response.status_code})\033[0m : {url} ({name})"
    except requests.exceptions.RequestException as e:
        status = f"\033[91mNG (Error)\033[0m : {url} ({name}) - {e}"
    with response_http_checks_lock:
        response_http_checks.append(status)

# ウイルスチェックを行う関数
def check_virus_download(url, name):
    try:
        local_filename = url.split('/')[-1]
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            status = f"\033[92mOK\033[0m : {url} ({name}) - Downloaded as {local_filename}"
    except requests.exceptions.RequestException as e:
        status = f"\033[91mNG\033[0m : {url} ({name}) - {str(e)}"
    with response_virus_checks_lock:
        response_virus_checks.append(status)

# HTTPチェックを行うスレッド関数
def threading_http_checks():
    threads = []
    for target in http_check_targets:
        thread = threading.Thread(target=check_http_response, args=(target[0], target[1]))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()

# ウイルスチェックを行うスレッド関数
def threading_virus_checks():
    threads = []
    for target in virus_check_targets:
        thread = threading.Thread(target=check_virus_download, args=(target[0], target[1]))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()

def check_mtr(target, name, version='ipv4'):
    mtr_cmd = ['mtr', '--report', '--report-cycles', '1','--no-dns']
    if version == 'ipv6':
        mtr_cmd.append('-6')
    mtr_cmd.append(target)

    try:
        result = subprocess.run(mtr_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = f"{name} ({target}) - IPv{version[-1]}:\n{result.stdout}"
    except Exception as e:
        output = f"{name} ({target}) - IPv{version[-1]}: Error - {str(e)}"

    with response_mtr_checks_lock:
        response_mtr_checks.append(output)

def threading_mtr_checks():
    threads = []
    # IPv4のターゲットに対するMTRチェックのスレッドを作成
    for target in mtr_v4_targets:
        thread = threading.Thread(target=check_mtr, args=(target[0], target[1], 'ipv4'))
        threads.append(thread)
        thread.start()
    # IPv6のターゲットに対するMTRチェックのスレッドを作成
    for target in mtr_v6_targets:
        thread = threading.Thread(target=check_mtr, args=(target[0], target[1], 'ipv6'))
        threads.append(thread)
        thread.start()
    # すべてのスレッドが終了するまで待機
    for thread in threads:
        thread.join()

def threading_ping_v4():
    thread = threading.Thread(target=theading_ping_internet_v4)
    thread.start()
    return thread

def threading_ping_v6():
    thread = threading.Thread(target=theading_ping_internet_v6)
    thread.start()
    return thread

def update_cli():
    global response_myipaddr
    global response_ping_gateway_v4
    global response_ping_internet_v4
    global response_ping_internet_v6
    global response_mtr_checks

    response_myipaddr = myipaddr()
    response_ping_gateway_v4 = ping_gateway_v4()
    response_ping_internet_v4.clear()
    response_ping_internet_v6.clear()
    response_http_checks.clear()
    response_virus_checks.clear()
    response_mtr_checks.clear()

    v4_thread = threading_ping_v4()
    v6_thread = threading_ping_v6()
    threading_http_checks()
    threading_virus_checks()
    threading_mtr_checks()

    v4_thread.join()
    v6_thread.join()

    response_ping_internet_v4.sort()
    response_ping_internet_v6.sort()
    response_http_checks.sort()
    response_virus_checks.sort()
    response_mtr_checks.sort()

    sys.stdout.write("\033[H\033[J")

    ipv4_addr, netmask, gateway, ipv6_addr = myipaddr()

    print("-------Network Setting-------")
    print(f"Interface: {interface}")
    if ipv4_addr and netmask:
        print(f"IPv4 Address: {ipv4_addr}")
        print(f"Netmask: {netmask}")
    if gateway:
        print(f"Default Gateway: {gateway}")
    if ipv6_addr:
        print(f"IPv6 Address: {ipv6_addr}")
    print("\n-------IPv4 Ping Results-------")
    print(ping_gateway_v4())
    for status in response_ping_internet_v4:
        print(status)
    print("\n-------IPv6 Ping Results-------")
    for status in response_ping_internet_v6:
        print(status)
    print("\n-------HTTP Results-------")
    for status in response_http_checks:
        print(status)
    print("\n-------Virus Check Results-------")
    for status in response_virus_checks:
        print(status)
    print("\n-------MTR Results-------")
    for result in response_mtr_checks:
        print(result)
    
if __name__ == '__main__':       
    while True:
        update_cli()
        time.sleep(5) 
