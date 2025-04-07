from api_client import APIClient
from datetime import datetime, date
from utility import Utility
from logger import logger
import pandas as pd
import subprocess
import copy
import sys
import platform
import re
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOM_ID = "101"
IP_RANGE = "10.0.0.23-23"
CLIENT_EXCEL_PATH = "client.xlsx"
CLIENT_EXCEL_TITLE = {
    "user_id": "考生准考证号", 
    "user_name": "考生姓名",
    "user_room": "考生考场",
    "user_ip": "考生机器IP",
    "group_id": "组别",
    "exam_id": "考试编号"
}
CLIENT_DATA = []

UTILITY = Utility()
def generate_api_key(ip):
    global UTILITY
    return UTILITY.calculate_md5(ip + date.today().__str__())

def read_client_excel():
    global CLIENT_DATA
    global CLIENT_EXCEL_PATH
    global CLIENT_EXCEL_TITLE
    try:
        df = pd.read_excel(CLIENT_EXCEL_PATH)
        required_columns = list(CLIENT_EXCEL_TITLE.values())
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Excel 文件缺少以下必需字段: {missing_columns}")
        for _, row in df.iterrows():
            client_info = {
                key: row[alias] for key, alias in CLIENT_EXCEL_TITLE.items()
            }
            CLIENT_DATA.append(client_info)
        logger.info(f"Read client Excel {CLIENT_EXCEL_PATH} successfully!")
    except FileNotFoundError:
        logger.error(f"File {CLIENT_EXCEL_PATH} not exist!")
    except PermissionError:
        logger.error(f"Have no permission to read {CLIENT_EXCEL_PATH}！")
    except Exception as e:
        logger.error(f"Reading {CLIENT_EXCEL_PATH} ERROR: {e}")

def write_client_excel():
    global CLIENT_EXCEL_PATH
    global CLIENT_DATA
    global CLIENT_EXCEL_TITLE

    # 将考生数据转换为 DataFrame
    df = pd.DataFrame(CLIENT_DATA)

    # 重命名列，使用别名作为表头
    df.rename(columns=CLIENT_EXCEL_TITLE, inplace=True)

    # 将 DataFrame 写入 Excel 文件
    df.to_excel(CLIENT_EXCEL_PATH, index=False)
    logger.info(f"Save client Excel {CLIENT_EXCEL_PATH} successfully!")

def parse_ip_range(ip_range):
    try:
        match = re.match(r"(\d+\.\d+\.\d+\.)(\d+)-(\d+)", ip_range)
        if not match:
            raise ValueError("IP range ERROR: it should be like '192.168.0.1-100' ")
        base_ip, start, end = match.groups()
        start = int(start)
        end = int(end)
        return [f"{base_ip}{i}" for i in range(start, end + 1)]
    except ValueError as e:
        logger.error(f"IP Parsing failed : {e}")
        return []

def ping_test(max_workers=50):
    """
    对指定 IP 范围内的机器进行 Ping 测试，返回可用的 IP 地址列表。
    :param max_workers: 最大线程数
    :return: 可用的 IP 地址列表
    """
    global IP_RANGE

    def ping_ip(ip):
        """
        对指定 IP 地址进行 Ping 测试。
        :param ip: 需要测试的 IP 地址
        :return: 如果 IP 可用，返回 IP；否则返回 None
        """
        try:
            # 根据操作系统调整 ping 命令参数
            if platform.system().lower() == "windows":
                command = ["ping", "-n", "1", "-w", "1000", ip]  # Windows 使用 -n 和 -w
            else:
                command = ["ping", "-c", "1", "-W", "1", ip]  # Linux/Mac 使用 -c 和 -W

            # 执行 ping 命令
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # 通过返回值判断是否成功
            if result.returncode == 0:
                return ip
            else:
                return None
        except Exception as e:
            logger.error(f"Ping {ip} error: {e}")
            return None

    # 解析 IP 范围
    ip_list = parse_ip_range(IP_RANGE)
    logger.info(f"Ping test for {IP_RANGE}")
    # 使用多线程并发 Ping
    available_ips = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(ping_ip, ip): ip for ip in ip_list}
        for future in as_completed(futures):
            result = future.result()
            if result:
                available_ips.append(result)
    logger.info(f"Available ip count: {len(available_ips)}")

    return sorted(available_ips, key=lambda ip: tuple(map(int, ip.split('.'))))

def map_client_to_ip(available_ips):
    """
    将可用的 IP 地址分配给考生，并为每个考生新增 user_room 和 user_ip 字段。
    :param client_data: 考生数据列表，每个考生是一个字典
    :param available_ips: 可用的 IP 地址列表
    :return: 处理后的考生数据列表
    """
    global ROOM_ID
    global CLIENT_DATA
    # 遍历考生数据，分配 IP 地址
    logger.info(f"Client count {len(CLIENT_DATA)}")
    for i, client in enumerate(CLIENT_DATA):
        # 添加 user_room 字段
        client["user_room"] = ROOM_ID
        # 添加 user_ip 字段
        if i < len(available_ips):
            client["user_ip"] = available_ips[i]
        else:
            client["user_ip"] = None  # 如果 IP 地址不足，设置为 None
        logger.info(f"Mapping {client["user_name"]}({client["user_id"]}) to {client["user_ip"]}")
    return CLIENT_DATA
    
def connect_to_client():
    global CLIENT_DATA
    client_response = []
    for client in CLIENT_DATA:
        api_key = generate_api_key(client["user_ip"])
        client_connect = APIClient(f"http://{client["user_ip"]}:8088", api_key)
        response = client_connect.connect_check()
        if(response["status"] == "success"):
            logger.info(f"Connect to {client["user_ip"]} {client["user_name"]} successfully!")
            client_response.append((client, response))
        else:
            logger.error(f"Fail to connect{client["user_ip"]} {client["user_name"]}!")
            client_response.append((client, response))
    return client_response
 
def set_client_info():
    global CLIENT_DATA
    client_response = []
    for client in CLIENT_DATA:
        api_key = generate_api_key(client["user_ip"])
        client_connect = APIClient(f"http://{client["user_ip"]}:8088", api_key)
        response = client_connect.set_user(client)
        if(response["status"] == "success"):
            logger.info(f"Set client info {client["user_ip"]} to {client["user_name"]} successfully!")
            client_response.append((client, response))
        else:
            logger.error(f"Set client info {client["user_ip"]} to {client["user_name"]} Failed!")
            client_response.append((client, response))
    return client_response

def get_client_status():
    global CLIENT_DATA
    client_status = []
    for client in CLIENT_DATA:
        api_key = generate_api_key(client["user_ip"])
        client_connect = APIClient(f"http://{client["user_ip"]}:8088", api_key)
        response = client_connect.get_status()
        client_status.append((client, response))
        if(response["status"] == "success"):
            logger.info(f"Get client status {client["user_ip"]}  {client["user_name"]} successfully!")
        else:
            logger.error(f"Get client status {client["user_ip"]} {client["user_name"]} Failed!")
    return client_status

def get_client_log():
    global CLIENT_DATA
    client_log = []
    for client in CLIENT_DATA:
        api_key = generate_api_key(client["user_ip"])
        client_connect = APIClient(f"http://{client["user_ip"]}:8088", api_key)
        response = client_connect.get_log()
        client_log.append((client, response))
        if(response["status"] == "success"):
            logger.info(f"Get client logs {client["user_ip"]}  {client["user_name"]} successfully!")
        else:
            logger.error(f"Get client logs {client["user_ip"]} {client["user_name"]} Failed!")
    return client_log

def open_info_window(title, content, window_id, front_size):
    global CLIENT_DATA
    window_status = []
    for client in CLIENT_DATA:
        api_key = generate_api_key(client["user_ip"])
        client_connect = APIClient(f"http://{client["user_ip"]}:8088", api_key)
        response = client_connect.handle_info("on", title, eval(content), window_id, front_size)
        window_status.append((client, response))
        if(response["status"] == "success"):
            logger.info(f"Open info window {client["user_ip"]}  {client["user_name"]} successfully!")
        else:
            logger.error(f"Open info window {client["user_ip"]} {client["user_name"]} Failed!")
    return window_status

def close_info_window(window_id):
    global CLIENT_DATA
    window_status = []
    for client in CLIENT_DATA:
        api_key = generate_api_key(client["user_ip"])
        client_connect = APIClient(f"http://{client["user_ip"]}:8088", api_key)
        response = client_connect.handle_info("off", window_id=window_id)
        window_status.append((client, response))
        if(response["status"] == "success"):
            logger.info(f"Close info window {client["user_ip"]}  {client["user_name"]} successfully!")
        else:
            logger.error(f"Close info window {client["user_ip"]} {client["user_name"]} Failed!")
    return window_status

def run_command(command):
    global CLIENT_DATA
    command_return = []
    for client in CLIENT_DATA:
        api_key = generate_api_key(client["user_ip"])
        client_connect = APIClient(f"http://{client["user_ip"]}:8088", api_key)
        response = client_connect.execute_command(command)
        command_return.append((client, response))
        if(response["status"] == "success"):
            logger.info(f"Run command {client["user_ip"]}  {client["user_name"]} successfully!")
        else:
            logger.error(f"Run command {client["user_ip"]} {client["user_name"]} Failed!")
    return command_return

def main():
    read_client_excel()
    args = sys.argv[1:]
    if args[0] == "update-client-list":
        map_client_to_ip(ping_test())
        write_client_excel()
    elif args[0] == "ping":
        total_ips = parse_ip_range(IP_RANGE)
        available_ips = ping_test()
        a_ips_p = 0
        connect = 0
        disconnect = 0
        if len(available_ips) > 0:
            for ip in total_ips:
                if available_ips[a_ips_p] == ip:
                    connect += 1
                    a_ips_p += 1
                else :
                    disconnect += 1
                    logger.warning(f"{ip} is lost")
        logger.info(f"Ping: Available {connect}, loss {disconnect}, total {connect + disconnect}")
    elif args[0] == "connect-check":
        response= connect_to_client()
        success = 0
        fail = 0
        for client, res in response:
            if res["status"] == "success":
                success += 1
            else:
                fail += 1
                logger.warning(f"{client["user_name"]}-{client["user_ip"]} connect failed!")
        logger.info(f"Connect client info: Success {success}, Fail {fail}, total {success + fail}")
    elif args[0] == "set-client-info":
        response= set_client_info()
        success = 0
        fail = 0
        for client, res in response:
            if res["status"] == "success":
                success += 1
            else:
                fail += 1
                logger.warning(f"{client["user_name"]}-{client["user_ip"]} set client info failed!")
        logger.info(f"Set client info: Success {success}, Fail {fail}, total {success + fail}")
    elif args[0] == "get-client-status":
        response= get_client_status()
        success = 0
        fail = 0
        for client, res in response:
            if res["status"] == "success":
                success += 1
            else:
                fail += 1
                logger.warning(f"{client["user_name"]}-{client["user_ip"]} set client info failed!")
        if not os.path.exists("client-status"):
            os.makedirs("client-status")
        UTILITY.save_json_file(f"client-status/{datetime.now().__str__()}.json", response)
        logger.info(f"Get client status: Success {success}, Fail {fail}, total {success + fail}")
    elif args[0] == "get-client-log":
        response= get_client_log()
        success = 0
        fail = 0
        for client, res in response:
            if res["status"] == "success":
                success += 1
            else:
                fail += 1
                logger.warning(f"{client["user_name"]}-{client["user_ip"]} set client log failed!")
        if not os.path.exists("client-log"):
            os.makedirs("client-log")
        UTILITY.save_json_file(f"client-log/{datetime.now().__str__()}.json", response)
        logger.info(f"Get client log: Success {success}, Fail {fail}, total {success + fail}")
    elif args[0] == "open-info-window":
        window_id = int(args[1])
        window_info = UTILITY.read_json_file("window.json")["res"]
        response = open_info_window(window_info["title"], window_info["content"], window_id, window_info["front_size"])
        success = 0
        fail = 0
        for client, res in response:
            if res["status"] == "success":
                success += 1
            else:
                fail += 1
                logger.warning(f"{client["user_name"]}-{client["user_ip"]} open window failed!")
        logger.info(f"Open info window: Success {success}, Fail {fail}, total {success + fail}")
    elif args[0] == "close-info-window":
        window_id = int(args[1])
        response = close_info_window(window_id)
        success = 0
        fail = 0
        for client, res in response:
            if res["status"] == "success":
                success += 1
            else:
                fail += 1
                logger.warning(f"{client["user_name"]}-{client["user_ip"]} open window failed!")
        logger.info(f"Close info window: Success {success}, Fail {fail}, total {success + fail}")
    elif args[0] == "run-command":
        command_info = UTILITY.read_json_file("command.json")["res"]
        response= run_command(command_info["command"])
        success = 0
        fail = 0
        for client, res in response:
            if res["status"] == "success":
                success += 1
            else:
                fail += 1
                logger.warning(f"{client["user_name"]}-{client["user_ip"]} run command failed!")
        UTILITY.save_json_file(f"command-log.json", response)
        logger.info(f"Run command: Success {success}, Fail {fail}, total {success + fail}")
    else:
        logger.error(f"Command Error: {args}")
if __name__ == "__main__":
    main()


