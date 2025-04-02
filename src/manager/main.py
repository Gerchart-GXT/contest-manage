from api_client import APIClient
from datetime import date
from utility import Utility
import pandas as pd
import subprocess
import copy
import platform
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOM_ID = "101"
IP_RANGE = "10.0.0.25-25"
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
        # 读取 Excel 文件
        df = pd.read_excel(CLIENT_EXCEL_PATH)

        # 检查表头是否包含所有必需的字段
        required_columns = list(CLIENT_EXCEL_TITLE.values())
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Excel 文件缺少以下必需字段: {missing_columns}")

        # 将数据转换为 CLIENT_EXCEL_TITLE 的格式
        for _, row in df.iterrows():
            client_info = {
                key: row[alias] for key, alias in CLIENT_EXCEL_TITLE.items()
            }
            CLIENT_DATA.append(client_info)

        print("Excel 文件读取成功，数据已存入 CLIENT_DATA。")
    except Exception as e:
        print(f"读取 Excel 文件时出错: {e}")

def write_client_excel():
    """
    将处理后的考生数据写回 Excel 文件。
    :param client_data: 处理后的考生数据列表
    :param output_file: 输出的 Excel 文件路径
    """
    global CLIENT_EXCEL_PATH
    global CLIENT_DATA
    global CLIENT_EXCEL_TITLE

    # 将考生数据转换为 DataFrame
    df = pd.DataFrame(CLIENT_DATA)

    # 重命名列，使用别名作为表头
    df.rename(columns=CLIENT_EXCEL_TITLE, inplace=True)

    # 将 DataFrame 写入 Excel 文件
    df.to_excel(CLIENT_EXCEL_PATH, index=False)
    print(f"考生数据已成功写入 {CLIENT_EXCEL_PATH}")

def ping_test(max_workers=50):
    """
    对指定 IP 范围内的机器进行 Ping 测试，返回可用的 IP 地址列表。
    :param max_workers: 最大线程数
    :return: 可用的 IP 地址列表
    """
    global IP_RANGE
    def parse_ip_range(ip_range):
        """
        解析 IP 范围，生成所有需要测试的 IP 地址。
        """
        match = re.match(r"(\d+\.\d+\.\d+\.)(\d+)-(\d+)", ip_range)
        if not match:
            raise ValueError("IP 范围格式不正确，应为 '192.168.0.1-100' 格式")

        base_ip, start, end = match.groups()
        start = int(start)
        end = int(end)

        return [f"{base_ip}{i}" for i in range(start, end + 1)]

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

    # 使用多线程并发 Ping
    available_ips = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(ping_ip, ip): ip for ip in ip_list}
        for future in as_completed(futures):
            result = future.result()
            if result:
                available_ips.append(result)

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
    for i, client in enumerate(CLIENT_DATA):
        # 添加 user_room 字段
        client["user_room"] = ROOM_ID
        # 添加 user_ip 字段
        if i < len(available_ips):
            client["user_ip"] = available_ips[i]
        else:
            client["user_ip"] = None  # 如果 IP 地址不足，设置为 None
    return CLIENT_DATA
    
def set_client_config():
    global CLIENT_DATA
    successed_client = []
    unsuccessed_client = []
    for client in CLIENT_DATA:
        api_key = generate_api_key(client["user_ip"])
        client_connect = APIClient(f"http://{client["user_ip"]}:8088", api_key)
        response = client_connect.set_user(client)
        if(response["status"] == "success"):
            successed_client.append(client)
        else:
            unsuccessed_client.append(client)
    return successed_client

def get_client_status():
    global CLIENT_DATA
    client_status = []
    for client in CLIENT_DATA:
        api_key = generate_api_key(client["user_ip"])
        client_connect = APIClient(f"http://{client["user_ip"]}:8088", api_key)
        response = client_connect.get_status(client["user_id"])
        client_status.append((client, response))
    return client_status

def get_client_log():
    global CLIENT_DATA
    client_log = []
    for client in CLIENT_DATA:
        api_key = generate_api_key(client["user_ip"])
        client_connect = APIClient(f"http://{client["user_ip"]}:8088", api_key)
        response = client_connect.get_log()
        client_log.append((client, response))
    return client_log

def open_info_window(title, content, window_id):
    global CLIENT_DATA
    window_status = []
    for client in CLIENT_DATA:
        api_key = generate_api_key(client["user_ip"])
        client_connect = APIClient(f"http://{client["user_ip"]}:8088", api_key)
        response = client_connect.handle_info("on", title, content, window_id)
        window_status.append((client, response))
    return window_status

def close_info_window(window_id):
    global CLIENT_DATA
    window_status = []
    for client in CLIENT_DATA:
        api_key = generate_api_key(client["user_ip"])
        client_connect = APIClient(f"http://{client["user_ip"]}:8088", api_key)
        response = client_connect.handle_info("off", window_id=window_id)
        window_status.append((client, response))
    return window_status

def run_command(command):
    global CLIENT_DATA
    command_return = []
    for client in CLIENT_DATA:
        api_key = generate_api_key(client["user_ip"])
        client_connect = APIClient(f"http://{client["user_ip"]}:8088", api_key)
        response = client_connect.execute_command(command)
        command_return.append((client, response))
    return command_return


        
if __name__ == "__main__":
    read_client_excel()
    # map_client_to_ip(ping_test())
    # write_client_excel()


