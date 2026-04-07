from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import subprocess
import threading
import sys
import os
import signal
import platform
from datetime import date
from queue import Queue
from utility import Utility
from info_window import InfoWindow
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from logger import logger 

flask_app = Flask(__name__)
CORS(flask_app)

qt_app = QApplication(sys.argv)
qt_app.setQuitOnLastWindowClosed(False)

UTILITY = None
API_KEY = ""
USER_DATA = None
API_FILE_LOCK = threading.Lock()
USER_DATA_FILE_LOCK = threading.Lock()
COMMAND_LOCK = threading.Lock()
WINDOWS = {}
GUI_QUEUE = Queue()  # 用于在主线程中处理 GUI 操作
COMMAND_TASKS = {}

# API Key 校验中间件
@flask_app.before_request
def validate_api_key():
    global API_KEY
    if request.endpoint in ['handle_user', 'get_status', 'handle_info', 'execute_command']:
        api_key = request.headers.get('X-Api-Key')
        if not api_key:
            logger.error("Missing X-Api-Key header")
            return jsonify({"status": "error", "error": "Missing X-Api-Key header"}), 401
        
        if api_key != API_KEY:
            logger.error("Invalid API Key")
            return jsonify({"status": "error", "error": "Invalid API Key"}), 403

# 公共验证中间件
def validate_request(required_fields):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                data = request.get_json()
                if not data:
                    logger.error("Invalid JSON")
                    return jsonify({"status": "error", "mesg": "Invalid JSON"}), 400
                
                for field in required_fields:
                    if field not in data:
                        logger.error(f"Missing field: {field}")
                        return jsonify({"status": "error", "mesg": f"Missing field: {field}"}), 400
                
                return func(data, *args, **kwargs)
            except Exception as e:
                logger.error(f"Exception occurred: {str(e)}")
                return jsonify({"status": "error", "mesg": str(e)}), 500
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator


def get_command_tasks_snapshot(active_only=False):
    with COMMAND_LOCK:
        snapshot = {}
        for command_id, task in COMMAND_TASKS.items():
            if active_only and task["status"] not in ["running", "kill_requested"]:
                continue
            snapshot[command_id] = {
                "command": task["command"],
                "status": task["status"],
                "pid": task["pid"],
                "started_at": task["started_at"],
                "ended_at": task["ended_at"],
                "return_code": task["return_code"]
            }
    return snapshot


def build_popen_kwargs():
    popen_kwargs = {
        "shell": True,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True
    }
    if platform.system().lower() == "windows":
        creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        if creation_flags:
            popen_kwargs["creationflags"] = creation_flags
    else:
        popen_kwargs["start_new_session"] = True
    return popen_kwargs


def terminate_process_tree(process):
    if process.poll() is not None:
        return
    if platform.system().lower() == "windows":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/F", "/T"],
            capture_output=True,
            text=True,
            timeout=15
        )
    else:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)


def monitor_command_task(command_id, process):
    try:
        stdout, stderr = process.communicate()
        with COMMAND_LOCK:
            task = COMMAND_TASKS.get(command_id)
            if not task:
                return
            task["stdout"] = stdout
            task["stderr"] = stderr
            task["return_code"] = process.returncode
            task["ended_at"] = datetime.now().isoformat()
            if task["status"] == "kill_requested":
                task["status"] = "killed"
            elif process.returncode == 0:
                task["status"] = "success"
            else:
                task["status"] = "error"
        logger.info(f"Command {command_id} finished with code {process.returncode}")
    except Exception as e:
        with COMMAND_LOCK:
            task = COMMAND_TASKS.get(command_id)
            if task:
                task["status"] = "error"
                task["stderr"] = str(e)
                task["ended_at"] = datetime.now().isoformat()
        logger.error(f"Monitor command {command_id} failed: {str(e)}")

@flask_app.route('/client/connect', methods=['POST'])
@validate_request(['action'])
def handle_connect(data):
    global USER_DATA
    global API_KEY
    if data['action'] != 'CHECK':
        logger.error("Invalid action")
        return jsonify({"status": "error", "mesg": "Invalid action"}), 400
    
    return jsonify({
        "status": "success",
        "mesg": "Connect successfully",
        "user_data": USER_DATA,
        "api_key": API_KEY
    })


# 用户信息设置接口
@flask_app.route('/client/user', methods=['POST'])
@validate_request(['action', 'user_data'])
def handle_user(data):
    global USER_DATA
    if data['action'] != 'USERSET':
        logger.error("Invalid action")
        return jsonify({"status": "error", "mesg": "Invalid action"}), 400
    
    user = data['user_data']
    required_fields = ['user_id', 'user_name', 'user_ip']
    for field in required_fields:
        if field not in user:
            logger.error(f"Missing user field: {field}")
            return jsonify({"status": "error", "mesg": f"Missing user field: {field}"}), 400
    
    # 存储用户信息
    with USER_DATA_FILE_LOCK:
        _ = UTILITY.save_json_file("./user-info.json", user)
    if _["status"] == "success":
        logger.info(f"User info saved successfully: {user}")
        USER_DATA = user
        return jsonify( {
            "status": "success",
            "mesg": _["mesg"],
            "user_id": user['user_id'],
            "user_name": user['user_name'],
            "user_ip": user['user_ip']
        })
    else:
        logger.error(f"Failed to save user info: {_['mesg']}")
        return jsonify({
            "status": "error",
            "mesg": _["mesg"]
        })

# 状态获取接口
@flask_app.route('/client/status', methods=['POST'])
@validate_request(['action'])
def get_status(data):
    global USER_DATA
    global UTILITY
    if data['action'] != 'GET':
        logger.error("Invalid action")
        return jsonify({"status": "error", "mesg": "Invalid action"}), 400
    
    user = USER_DATA
    if not user:
        logger.error("User not found")
        return jsonify({"status": "error", "mesg": "User not found"}), 404
    
    logger.info(f"Status retrieved successfully for user: {user}")
    return jsonify({
        "status": "success",
        "mesg": "Get status successfully",
        "user_data": user,
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "active_progress": UTILITY.get_active_progress(),
            "active_commands": get_command_tasks_snapshot(active_only=True)
        }
    })

@flask_app.route('/client/log', methods=['POST'])
@validate_request(['action'])
def get_log(data):
    if data['action'] != 'get':
        logger.error("Invalid action for log retrieval")
        return jsonify({"status": "error", "mesg": "Invalid action"}), 400
    
    log_file_path = 'logs/app.log'  # 日志文件路径
    try:
        with open(log_file_path, 'r') as log_file:
            log_content = log_file.readlines()[-100:] 
        logger.info("Log file retrieved successfully")
        return jsonify({
            "status": "success",
            "mesg": "Log file retrieved successfully",
            "log_content": log_content
        })
    except FileNotFoundError:
        logger.error("Log file not found")
        return jsonify({"status": "error", "mesg": "Log file not found"}), 404
    except Exception as e:
        logger.error(f"Failed to read log file: {str(e)}")
        return jsonify({"status": "error", "mesg": str(e)}), 500
        
# 信息提示接口
@flask_app.route('/client/info', methods=['POST'])
@validate_request(['action', 'title', 'content', 'window_id'])
def handle_info(data):
    global WINDOWS
    action = data['action'].lower()
    if action not in ['on', 'off']:
        logger.error("Invalid action")
        return jsonify({"status": "error", "mesg": "Invalid action"}), 400
    window_id = data["window_id"]
    # 将 GUI 操作放入队列，由主线程处理
    GUI_QUEUE.put((action, window_id, data["title"], data["content"], data["front_size"]))
    logger.info(f"Request to {action} window {window_id} received.")
    return {
        "status": "success",
        "mesg": f"Request to {action} window {window_id} received."
    }

# 命令执行接口
@flask_app.route('/client/command', methods=['POST'])
@validate_request(['action', 'command_id'])
def execute_command(data):
    action = data['action'].lower()
    command_id = str(data['command_id'])

    if action not in ['run', 'kill']:
        logger.error("Invalid action")
        return jsonify({"status": "error", "mesg": "Invalid action"}), 400

    if action == 'run':
        command = data.get('content')
        if not command:
            logger.error("Empty command")
            return jsonify({"status": "error", "mesg": "Empty command"}), 400

        try:
            with COMMAND_LOCK:
                current_task = COMMAND_TASKS.get(command_id)
                if current_task and current_task["status"] in ["running", "kill_requested"]:
                    logger.warning(f"Command {command_id} is already running")
                    return jsonify({
                        "status": "error",
                        "mesg": f"Command {command_id} is already running"
                    }), 409

            process = subprocess.Popen(command, **build_popen_kwargs())
            with COMMAND_LOCK:
                COMMAND_TASKS[command_id] = {
                    "command": command,
                    "status": "running",
                    "pid": process.pid,
                    "started_at": datetime.now().isoformat(),
                    "ended_at": None,
                    "return_code": None,
                    "stdout": "",
                    "stderr": "",
                    "process": process
                }

            threading.Thread(
                target=monitor_command_task,
                args=(command_id, process),
                daemon=True
            ).start()
            logger.info(f"Command {command_id} started asynchronously, pid={process.pid}")
            return jsonify({
                "status": "success",
                "mesg": f"Command {command_id} started",
                "command_id": command_id,
                "pid": process.pid
            })
        except Exception as e:
            logger.error(f"Exception occurred: {str(e)}")
            return jsonify({"status": "error", "mesg": str(e)}), 500

    try:
        with COMMAND_LOCK:
            task = COMMAND_TASKS.get(command_id)
            if not task:
                logger.error(f"Command {command_id} not found")
                return jsonify({
                    "status": "error",
                    "mesg": f"Command {command_id} not found"
                }), 404
            if task["status"] not in ["running", "kill_requested"]:
                logger.warning(f"Command {command_id} is not running")
                return jsonify({
                    "status": "error",
                    "mesg": f"Command {command_id} is not running"
                }), 409
            task["status"] = "kill_requested"
            process = task["process"]

        terminate_process_tree(process)
        logger.info(f"Kill command {command_id} request sent")
        return jsonify({
            "status": "success",
            "mesg": f"Kill command {command_id} request sent",
            "command_id": command_id
        })
    except subprocess.TimeoutExpired:
        logger.error(f"Kill command {command_id} timeout")
        return jsonify({"status": "error", "mesg": "Kill command timeout"}), 408
    except ProcessLookupError:
        logger.warning(f"Command {command_id} already exited")
        return jsonify({
            "status": "error",
            "mesg": f"Command {command_id} already exited"
        }), 409
    except Exception as e:
        logger.error(f"Exception occurred: {str(e)}")
        return jsonify({"status": "error", "mesg": str(e)}), 500

class GuiHandler(QObject):
    def __init__(self):
        super().__init__()
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_gui_queue)
        self.timer.start(100)  # 每 100 毫秒检查一次队列

    def process_gui_queue(self):
        """
        在主线程中处理 GUI 操作。
        """
        while not GUI_QUEUE.empty():
            action, window_id, title, content, front_size = GUI_QUEUE.get()
            if action == "on":
                if (window_id in WINDOWS) and WINDOWS[window_id].is_open():
                    logger.warning(f"Window {window_id} is already open!")
                else:
                    now_window = InfoWindow(title, content, front_size)
                    now_window.show()
                    WINDOWS[window_id] = now_window
                    logger.info(f"Window {window_id} opened!")
            elif action == "off":
                if (window_id in WINDOWS) and WINDOWS[window_id].is_open():
                    WINDOWS[window_id].close()
                    logger.info(f"Window {window_id} closed!")
                else:
                    logger.warning(f"Window {window_id} does not exist or is already closed!")

if __name__ == '__main__':
    UTILITY = Utility()
    API_KEY = UTILITY.calculate_md5(UTILITY.get_local_ipv4()["res"] + date.today().__str__())

    logger.info(f"Generate API-KEY: {API_KEY}")
    with API_FILE_LOCK:
        UTILITY.save_json_file("./api-key.json", {
            "API_KEY": API_KEY
        })
    with USER_DATA_FILE_LOCK:
        _ = UTILITY.read_json_file("./user-info.json")
        if _["status"] == "success":
            USER_DATA = _["res"]
    
    # 启动 Flask 服务器
    flask_thread = threading.Thread(
        target=flask_app.run,
        kwargs={'host': '0.0.0.0', 'port': 8088, 'threaded': True, 'use_reloader': False},
        daemon=True
    )
    flask_thread.start()
    logger.info("Flask server start!")
    # 在主线程中启动 GUI 事件处理器
    gui_handler = GuiHandler()
    
    # 启动 Qt 事件循环
    sys.exit(qt_app.exec_())
