import copy
import json
import os
import platform
import re
import subprocess
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime

import pandas as pd

from api_client import APIClient
from logger import logger
from runtime import get_runtime_root
from utility import Utility


class ManagerService:
    def __init__(self):
        self.base_dir = get_runtime_root()
        self.utility = Utility()
        self.state_lock = threading.Lock()
        self.config_path = os.path.join(self.base_dir, "config.json")
        self.filter_path = os.path.join(self.base_dir, "filter.json")
        self.command_template_dir = os.path.join(self.base_dir, "command-template")
        self.window_template_dir = os.path.join(self.base_dir, "window_template")
        self.client_status_dir = os.path.join(self.base_dir, "client-status")
        self.client_log_dir = os.path.join(self.base_dir, "client-log")
        self.runtime_state_path = os.path.join(self.base_dir, "task-history", "manager-state.json")
        self.audit_logs = []
        self.tasks = {}
        self.task_order = []
        self.task_limit = 120
        self.persist_event = threading.Event()
        self.last_ping_scan = []
        self.last_ping_by_ip = {}
        self.last_connect_by_client = {}
        self.last_client_status = []
        self.last_client_log = []
        self.config = self._load_config()
        self.filter_data = self._load_filter()
        self.clients = []
        self._load_runtime_state()
        threading.Thread(target=self._persist_runtime_state_loop, daemon=True).start()
        try:
            self._load_clients()
        except Exception as exc:
            logger.error(f"Initial load clients failed: {exc}")

    def _normalize_task(self, task_id, task_data):
        progress = task_data.get("progress") if isinstance(task_data.get("progress"), dict) else {}
        logs = task_data.get("logs") if isinstance(task_data.get("logs"), list) else []
        meta = task_data.get("meta") if isinstance(task_data.get("meta"), dict) else {}
        normalized_logs = []
        for entry in logs[-500:]:
            if not isinstance(entry, dict):
                continue
            normalized_logs.append({
                "timestamp": entry.get("timestamp"),
                "level": entry.get("level", "info"),
                "message": str(entry.get("message", ""))
            })
        return {
            "task_id": str(task_data.get("task_id") or task_id),
            "action": str(task_data.get("action") or ""),
            "title": str(task_data.get("title") or task_data.get("action") or task_id),
            "status": str(task_data.get("status") or "queued"),
            "progress": {
                "completed": max(int(progress.get("completed", 0) or 0), 0),
                "total": max(int(progress.get("total", 0) or 0), 0)
            },
            "created_at": task_data.get("created_at"),
            "started_at": task_data.get("started_at"),
            "ended_at": task_data.get("ended_at"),
            "logs": normalized_logs,
            "meta": copy.deepcopy(meta),
            "result": task_data.get("result"),
            "error": task_data.get("error")
        }

    def _load_runtime_state(self):
        payload = self._read_json(self.runtime_state_path, {})
        tasks_payload = payload.get("tasks", {}) if isinstance(payload, dict) else {}
        task_order = payload.get("task_order", []) if isinstance(payload, dict) else []
        audit_logs = payload.get("audit_logs", []) if isinstance(payload, dict) else []

        normalized_tasks = {}
        for task_id, task_data in tasks_payload.items():
            if not isinstance(task_data, dict):
                continue
            normalized_task = self._normalize_task(task_id, task_data)
            normalized_tasks[normalized_task["task_id"]] = normalized_task

        ordered_ids = []
        for task_id in task_order:
            task_id_text = str(task_id)
            if task_id_text in normalized_tasks and task_id_text not in ordered_ids:
                ordered_ids.append(task_id_text)
        for task_id in normalized_tasks:
            if task_id not in ordered_ids:
                ordered_ids.append(task_id)

        self.tasks = {task_id: normalized_tasks[task_id] for task_id in ordered_ids[:self.task_limit]}
        self.task_order = ordered_ids[:self.task_limit]
        self.audit_logs = [entry for entry in audit_logs[-200:] if isinstance(entry, dict)]

    def _runtime_state_payload(self):
        with self.state_lock:
            return {
                "tasks": copy.deepcopy(self.tasks),
                "task_order": copy.deepcopy(self.task_order),
                "audit_logs": copy.deepcopy(self.audit_logs)
            }

    def _persist_runtime_state_now(self):
        payload = self._runtime_state_payload()
        result = self.utility.save_json_file(self.runtime_state_path, payload)
        if result["status"] != "success":
            logger.error(f"Persist runtime state failed: {result['mesg']}")

    def _mark_runtime_state_dirty(self):
        self.persist_event.set()

    def _persist_runtime_state_loop(self):
        while True:
            self.persist_event.wait()
            time.sleep(0.2)
            self.persist_event.clear()
            try:
                self._persist_runtime_state_now()
            except Exception as exc:
                logger.error(f"Persist runtime state loop failed: {exc}")

    def _create_task(self, action, title, meta=None):
        task_id = uuid.uuid4().hex[:12]
        task = {
            "task_id": task_id,
            "action": action,
            "title": title,
            "status": "queued",
            "progress": {
                "completed": 0,
                "total": 0
            },
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "ended_at": None,
            "logs": [],
            "meta": copy.deepcopy(meta or {}),
            "result": None,
            "error": None
        }
        with self.state_lock:
            self.tasks[task_id] = task
            self.task_order.insert(0, task_id)
            while len(self.task_order) > self.task_limit:
                expired_task_id = self.task_order.pop()
                self.tasks.pop(expired_task_id, None)
        self._mark_runtime_state_dirty()
        return task_id

    def _append_task_log(self, task_id, message, level="info"):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": str(message)
        }
        with self.state_lock:
            task = self.tasks.get(task_id)
            if not task:
                return
            task["logs"].append(entry)
            task["logs"] = task["logs"][-500:]
        self._mark_runtime_state_dirty()

    def _set_task_progress_total(self, task_id, total):
        with self.state_lock:
            task = self.tasks.get(task_id)
            if not task:
                return
            task["progress"]["total"] = max(int(total), 0)
        self._mark_runtime_state_dirty()

    def _advance_task_progress(self, task_id, step=1):
        with self.state_lock:
            task = self.tasks.get(task_id)
            if not task:
                return
            task["progress"]["completed"] = min(
                task["progress"]["completed"] + int(step),
                task["progress"]["total"] if task["progress"]["total"] else task["progress"]["completed"] + int(step)
            )
        self._mark_runtime_state_dirty()

    def _finalize_task(self, task_id, status, result=None, error_message=None):
        with self.state_lock:
            task = self.tasks.get(task_id)
            if not task:
                return
            task["status"] = status
            task["ended_at"] = datetime.now().isoformat()
            task["result"] = result
            task["error"] = error_message
            if task["progress"]["total"] and status == "completed":
                task["progress"]["completed"] = task["progress"]["total"]
        self._mark_runtime_state_dirty()

    def _run_task(self, task_id, runner):
        with self.state_lock:
            task = self.tasks.get(task_id)
            if not task:
                return
            task["status"] = "running"
            task["started_at"] = datetime.now().isoformat()
        self._append_task_log(task_id, "任务开始执行")
        try:
            result = runner(task_id)
            self._append_task_log(task_id, "任务执行完成")
            self._finalize_task(task_id, "completed", result=result)
        except Exception as exc:
            error_message = str(exc)
            self._append_task_log(task_id, f"任务执行失败: {error_message}", level="error")
            self._append_task_log(task_id, traceback.format_exc(), level="error")
            self._finalize_task(task_id, "error", error_message=error_message)

    def submit_task(self, action, title, runner, meta=None):
        task_id = self._create_task(action, title, meta=meta)
        threading.Thread(target=self._run_task, args=(task_id, runner), daemon=True).start()
        return self.get_task_summary(task_id)

    def get_task_summary(self, task_id):
        with self.state_lock:
            task = copy.deepcopy(self.tasks.get(task_id))
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        result_summary = None
        if isinstance(task.get("result"), dict):
            result_summary = task["result"].get("summary")
        task["result_summary"] = result_summary
        return {
            key: value for key, value in task.items()
            if key not in ["logs", "result", "error"]
        } | {
            "result_summary": result_summary,
            "error": task.get("error")
        }

    def get_task_detail(self, task_id):
        with self.state_lock:
            task = copy.deepcopy(self.tasks.get(task_id))
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        return task

    def get_task_summaries(self):
        with self.state_lock:
            task_ids = list(self.task_order)
        return [self.get_task_summary(task_id) for task_id in task_ids if task_id in self.tasks]

    def clear_task_history(self):
        with self.state_lock:
            removable_ids = [
                task_id for task_id in self.task_order
                if self.tasks.get(task_id, {}).get("status") in ["completed", "error"]
            ]
            for task_id in removable_ids:
                self.tasks.pop(task_id, None)
            self.task_order = [task_id for task_id in self.task_order if task_id not in removable_ids]
            remaining_count = len(self.task_order)
        self._mark_runtime_state_dirty()
        self._log_action("clear-task-history", {
            "cleared_count": len(removable_ids),
            "remaining_count": remaining_count
        })
        return {
            "cleared_count": len(removable_ids),
            "remaining_count": remaining_count
        }

    def _find_local_readme(self):
        candidate_dirs = []
        current_dir = self.base_dir
        for _ in range(4):
            if current_dir not in candidate_dirs:
                candidate_dirs.append(current_dir)
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:
                break
            current_dir = parent_dir

        cwd = os.getcwd()
        if cwd not in candidate_dirs:
            candidate_dirs.append(cwd)

        for directory in candidate_dirs:
            candidate = os.path.join(directory, "readme.md")
            if os.path.exists(candidate):
                return candidate
            candidate = os.path.join(directory, "README.md")
            if os.path.exists(candidate):
                return candidate
        raise FileNotFoundError("未找到本地 readme.md")

    def get_usage_readme(self):
        readme_path = self._find_local_readme()
        with open(readme_path, "r", encoding="utf-8") as file:
            content = file.read()
        self._log_action("open-readme", {"path": readme_path})
        return {
            "path": readme_path,
            "content": content
        }

    def _log_action(self, action, detail):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "detail": detail
        }
        with self.state_lock:
            self.audit_logs.append(entry)
            self.audit_logs = self.audit_logs[-200:]
        self._mark_runtime_state_dirty()
        return entry

    def _read_json(self, path, default_value):
        result = self.utility.read_json_file(path)
        if result["status"] == "success":
            return result["res"]
        return copy.deepcopy(default_value)

    def _save_json(self, path, data):
        result = self.utility.save_json_file(path, data)
        if result["status"] != "success":
            raise ValueError(result["mesg"])

    def _default_config(self):
        return {
            "ROOM_ID": "test",
            "IP_RANGE": "10.0.0.1-10",
            "LOCAL_IP": "",
            "CLIENT_EXCEL_PATH": "./client.xlsx",
            "CLIENT_EXCEL_TITLE": {
                "user_id": "准考证号",
                "user_name": "学生姓名",
                "user_room": "考生考场",
                "user_no": "考生机位号",
                "user_ip": "考生机器IP",
                "group_id": "参赛科目"
            }
        }

    def _default_filter(self):
        return {
            "active": False,
            "ip": {"reg": ""},
            "user_name": {"reg": ""},
            "user_id": {"reg": ""},
            "group_id": {"reg": ""}
        }

    def _normalize_config(self, config_data):
        config = copy.deepcopy(self._default_config())
        config.update(config_data or {})
        config["CLIENT_EXCEL_TITLE"].update((config_data or {}).get("CLIENT_EXCEL_TITLE", {}))
        return config

    def _normalize_filter(self, filter_data):
        filter_result = copy.deepcopy(self._default_filter())
        filter_result.update(filter_data or {})
        for key in ["ip", "user_name", "user_id", "group_id"]:
            filter_result[key].update((filter_data or {}).get(key, {}))
            filter_result[key]["reg"] = str(filter_result[key].get("reg", "") or "")
        filter_result["active"] = bool(filter_result.get("active", False))
        return filter_result

    def _load_config(self):
        return self._normalize_config(self._read_json(self.config_path, self._default_config()))

    def _load_filter(self):
        filter_data = self._normalize_filter(self._read_json(self.filter_path, self._default_filter()))
        for field_name, item in filter_data.items():
            if not isinstance(item, dict):
                continue
            try:
                self._validate_regex(item.get("reg", ""), field_name)
            except ValueError as exc:
                logger.error(str(exc))
                item["reg"] = ""
        return filter_data

    def _resolve_manager_path(self, path):
        if os.path.isabs(path):
            return path
        return os.path.join(self.base_dir, path)

    def _active_title_mapping(self):
        mapping = {}
        for key, alias in self.config["CLIENT_EXCEL_TITLE"].items():
            alias_text = str(alias or "").strip()
            if alias_text:
                mapping[key] = alias_text
        return mapping

    def _sanitize_cell(self, value):
        if pd.isna(value):
            return None
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                return value
        return value

    def _load_clients(self):
        excel_path = self._resolve_manager_path(self.config["CLIENT_EXCEL_PATH"])
        clients = []
        if not os.path.exists(excel_path):
            with self.state_lock:
                self.clients = []
            return []

        mapping = self._active_title_mapping()
        df = pd.read_excel(excel_path)
        required_columns = list(mapping.values())
        missing_columns = [column for column in required_columns if column not in df.columns]
        if missing_columns:
            raise ValueError(f"Excel 文件缺少以下必需字段: {missing_columns}")

        for index, row in df.iterrows():
            client = {"_client_id": str(index)}
            for key, alias in mapping.items():
                client[key] = self._sanitize_cell(row[alias]) if alias in df.columns else None
            clients.append(client)

        with self.state_lock:
            self.clients = clients
        logger.info(f"Read client Excel {excel_path} successfully!")
        return copy.deepcopy(clients)

    def _write_clients(self):
        mapping = self._active_title_mapping()
        rows = []
        with self.state_lock:
            for client in self.clients:
                row = {}
                for key in mapping:
                    row[key] = client.get(key)
                rows.append(row)

        df = pd.DataFrame(rows)
        df.rename(columns=mapping, inplace=True)
        excel_path = self._resolve_manager_path(self.config["CLIENT_EXCEL_PATH"])
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)
        df.to_excel(excel_path, index=False)
        logger.info(f"Save client Excel {excel_path} successfully!")

    def _validate_regex(self, pattern, field_name):
        if not pattern:
            return
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"{field_name} 正则无效: {exc}")

    def update_settings(self, payload):
        config = self._normalize_config(payload.get("config", self.config))
        filter_data = self._normalize_filter(payload.get("filter", self.filter_data))
        for field_name, item in filter_data.items():
            if isinstance(item, dict):
                self._validate_regex(item.get("reg", ""), field_name)

        self._save_json(self.config_path, config)
        self._save_json(self.filter_path, filter_data)
        with self.state_lock:
            self.config = config
            self.filter_data = filter_data
        clients = self._load_clients()
        self._log_action("update-settings", {
            "client_count": len(clients),
            "ip_range": config["IP_RANGE"]
        })
        return self.get_state()

    def save_uploaded_excel(self, uploaded_file):
        if not uploaded_file or not uploaded_file.filename:
            raise ValueError("未选择 Excel 文件")
        excel_path = self._resolve_manager_path(self.config["CLIENT_EXCEL_PATH"])
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)
        uploaded_file.save(excel_path)
        clients = self._load_clients()
        self._log_action("upload-xlsx", {
            "filename": uploaded_file.filename,
            "saved_to": excel_path,
            "client_count": len(clients)
        })
        return self.get_state()

    def reload_clients(self):
        clients = self._load_clients()
        self._log_action("reload-clients", {"client_count": len(clients)})
        return self.get_state()

    def _filter_regex(self, field_name):
        return self.filter_data.get(field_name, {}).get("reg", "")

    def _match_regex(self, pattern, value):
        if not pattern:
            return True
        return re.match(pattern, str(value if value is not None else "")) is not None

    def _match_client_filter(self, client, candidate_ip=None):
        if not self.filter_data.get("active", False):
            return True
        checks = [
            ("user_name", client.get("user_name")),
            ("user_id", client.get("user_id")),
            ("group_id", client.get("group_id")),
            ("ip", candidate_ip if candidate_ip is not None else client.get("user_ip"))
        ]
        for field_name, value in checks:
            if not self._match_regex(self._filter_regex(field_name), value):
                return False
        return True

    def _is_valid_ipv4(self, ip):
        pattern = r"^((25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])$"
        return re.match(pattern, str(ip if ip is not None else "")) is not None

    def _parse_ip_range(self):
        ip_range = self.config["IP_RANGE"]
        match = re.match(r"(\d+\.\d+\.\d+\.)(\d+)-(\d+)", ip_range)
        if not match:
            raise ValueError("IP range ERROR: it should be like '192.168.0.1-100'")
        base_ip, start, end = match.groups()
        start_int = int(start)
        end_int = int(end)
        if start_int > end_int:
            raise ValueError("IP range ERROR: start ip should not larger than end ip")
        return [f"{base_ip}{item}" for item in range(start_int, end_int + 1)]

    def _generate_api_key(self, ip):
        return self.utility.calculate_md5(str(ip) + str(date.today()))

    def _selected_clients(self, selected_ids=None):
        with self.state_lock:
            clients = copy.deepcopy(self.clients)
        if not selected_ids:
            return clients
        selected_set = {str(item) for item in selected_ids}
        return [client for client in clients if client["_client_id"] in selected_set]

    def _client_brief(self, client):
        return {
            "client_id": client["_client_id"],
            "user_id": client.get("user_id"),
            "user_name": client.get("user_name"),
            "user_room": client.get("user_room"),
            "user_no": client.get("user_no"),
            "user_ip": client.get("user_ip"),
            "group_id": client.get("group_id"),
            "exam_id": client.get("exam_id")
        }

    def _update_clients(self, updated_clients):
        updated_map = {client["_client_id"]: client for client in updated_clients}
        with self.state_lock:
            self.clients = [updated_map.get(client["_client_id"], client) for client in self.clients]

    def _ping_ip(self, ip):
        try:
            if platform.system().lower() == "windows":
                command = ["ping", "-n", "1", "-w", "1000", ip]
            else:
                command = ["ping", "-c", "1", "-W", "1", ip]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.returncode == 0
        except Exception as exc:
            logger.error(f"Ping {ip} error: {exc}")
            return False

    def run_ping(self, max_workers=50):
        return self._run_ping_internal(max_workers=max_workers, task_id=None)

    def _run_ping_internal(self, max_workers=50, task_id=None):
        ip_list = self._parse_ip_range()
        if self.filter_data.get("active", False):
            ip_list = [ip for ip in ip_list if self._match_regex(self._filter_regex("ip"), ip)]
        if task_id:
            self._set_task_progress_total(task_id, len(ip_list))
            self._append_task_log(task_id, f"开始 Ping，共 {len(ip_list)} 台")

        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(self._ping_ip, ip): ip for ip in ip_list}
            for future in as_completed(future_map):
                ip = future_map[future]
                ok = future.result()
                results.append({"ip": ip, "status": "success" if ok else "error"})
                if task_id:
                    self._advance_task_progress(task_id)
                    self._append_task_log(task_id, f"Ping {ip}: {'success' if ok else 'error'}")

        results.sort(key=lambda item: tuple(map(int, item["ip"].split("."))))
        ping_by_ip = {item["ip"]: item for item in results}
        with self.state_lock:
            self.last_ping_scan = results
            self.last_ping_by_ip = ping_by_ip

        summary = {
            "available": sum(1 for item in results if item["status"] == "success"),
            "loss": sum(1 for item in results if item["status"] != "success"),
            "total": len(results)
        }
        self._log_action("ping", summary)
        return {
            "summary": summary,
            "results": results,
            "clients": self.get_clients_view()
        }

    def _connect_ip(self, ip):
        try:
            api_client = APIClient(f"http://{ip}:8088", self._generate_api_key(ip))
            response = api_client.connect_check()
            return response.get("status") == "success"
        except Exception as exc:
            logger.error(f"Connect check {ip} error: {exc}")
            return False

    def run_connect_scan(self, max_workers=50):
        return self._run_connect_scan_internal(max_workers=max_workers, task_id=None)

    def _run_connect_scan_internal(self, max_workers=50, task_id=None):
        ip_list = self._parse_ip_range()
        if self.filter_data.get("active", False):
            ip_list = [ip for ip in ip_list if self._match_regex(self._filter_regex("ip"), ip)]
        if task_id:
            self._set_task_progress_total(task_id, len(ip_list))
            self._append_task_log(task_id, f"开始 Connect Scan，共 {len(ip_list)} 台")

        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(self._connect_ip, ip): ip for ip in ip_list}
            for future in as_completed(future_map):
                ip = future_map[future]
                ok = future.result()
                results.append({"ip": ip, "status": "success" if ok else "error"})
                if task_id:
                    self._advance_task_progress(task_id)
                    self._append_task_log(task_id, f"Connect {ip}: {'success' if ok else 'error'}")

        results.sort(key=lambda item: tuple(map(int, item["ip"].split("."))))
        summary = {
            "available": sum(1 for item in results if item["status"] == "success"),
            "loss": sum(1 for item in results if item["status"] != "success"),
            "total": len(results)
        }
        self._log_action("connect-scan", summary)
        return {
            "summary": summary,
            "results": results
        }

    def update_client_list(self):
        return self._update_client_list_internal(task_id=None)

    def _update_client_list_internal(self, task_id=None):
        connect_result = self._run_connect_scan_internal(task_id=task_id)
        available_ips = [item["ip"] for item in connect_result["results"] if item["status"] == "success"]
        with self.state_lock:
            clients = copy.deepcopy(self.clients)

        available_index = 0
        updated_clients = []
        mapped_count = 0
        for client in clients:
            updated_client = copy.deepcopy(client)
            if not self._match_client_filter(updated_client):
                updated_clients.append(updated_client)
                continue
            updated_client["user_room"] = self.config["ROOM_ID"]
            if available_index < len(available_ips):
                updated_client["user_ip"] = available_ips[available_index]
                available_index += 1
            else:
                updated_client["user_ip"] = None
            updated_clients.append(updated_client)
            mapped_count += 1

        self._update_clients(updated_clients)
        self._write_clients()
        self._log_action("update-client-list", {
            "mapped_count": mapped_count,
            "available_ip_count": len(available_ips),
            "bind_by": "connect-check"
        })
        if task_id:
            self._append_task_log(task_id, f"绑定完成，可用客户端 {len(available_ips)} 台，已映射 {mapped_count} 名")
        return {
            "summary": {
                "mapped_count": mapped_count,
                "available_ip_count": len(available_ips),
                "bind_by": "connect-check"
            },
            "clients": self.get_clients_view()
        }

    def _run_parallel_clients(self, action_name, selected_ids, worker, max_workers=50, task_id=None):
        selected_clients = self._selected_clients(selected_ids)
        if task_id:
            self._set_task_progress_total(task_id, len(selected_clients))
            self._append_task_log(task_id, f"{action_name} 开始，共 {len(selected_clients)} 台")
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {executor.submit(worker, client): client for client in selected_clients}
            for future in as_completed(future_map):
                result = future.result()
                results.append(result)
                if task_id:
                    self._advance_task_progress(task_id)
                    client = result["client"]
                    result_status = result["result"].get("status", "unknown")
                    result_message = result["result"].get("mesg", "")
                    self._append_task_log(
                        task_id,
                        f"{client.get('user_name') or client.get('user_id') or client.get('client_id')} ({client.get('user_ip')}): {result_status} {result_message}"
                    )

        success = sum(1 for item in results if item["result"]["status"] == "success")
        fail = len(results) - success
        summary = {
            "action": action_name,
            "success": success,
            "fail": fail,
            "total": len(results)
        }
        self._log_action(action_name, summary)
        return {
            "summary": summary,
            "results": results,
            "clients": self.get_clients_view()
        }

    def _client_request_guard(self, client):
        if not self._match_client_filter(client):
            return {
                "status": "error",
                "mesg": "Regular expr not match!"
            }
        if not self._is_valid_ipv4(client.get("user_ip")):
            return {
                "status": "error",
                "mesg": "IP format ERROR"
            }
        return None

    def connect_check(self, selected_ids=None, max_workers=50):
        return self._connect_check_internal(selected_ids=selected_ids, max_workers=max_workers, task_id=None)

    def _connect_check_internal(self, selected_ids=None, max_workers=50, task_id=None):
        def worker(client):
            guard = self._client_request_guard(client)
            if guard:
                response = guard
            else:
                api_client = APIClient(f"http://{client['user_ip']}:8088", self._generate_api_key(client["user_ip"]))
                response = api_client.connect_check()
            with self.state_lock:
                self.last_connect_by_client[client["_client_id"]] = response
            return {
                "client": self._client_brief(client),
                "result": response
            }

        return self._run_parallel_clients("connect-check", selected_ids, worker, max_workers=max_workers, task_id=task_id)

    def set_client_info(self, selected_ids=None, max_workers=50):
        return self._set_client_info_internal(selected_ids=selected_ids, max_workers=max_workers, task_id=None)

    def _set_client_info_internal(self, selected_ids=None, max_workers=50, task_id=None):
        def worker(client):
            guard = self._client_request_guard(client)
            if guard:
                response = guard
            else:
                api_client = APIClient(f"http://{client['user_ip']}:8088", self._generate_api_key(client["user_ip"]))
                response = api_client.set_user({key: value for key, value in client.items() if not key.startswith("_")})
            return {
                "client": self._client_brief(client),
                "result": response
            }

        return self._run_parallel_clients("set-client-info", selected_ids, worker, max_workers=max_workers, task_id=task_id)

    def get_client_status(self, selected_ids=None, max_workers=50):
        return self._get_client_status_internal(selected_ids=selected_ids, max_workers=max_workers, task_id=None)

    def _get_client_status_internal(self, selected_ids=None, max_workers=50, task_id=None):
        def worker(client):
            guard = self._client_request_guard(client)
            if guard:
                response = guard
            else:
                api_client = APIClient(f"http://{client['user_ip']}:8088", self._generate_api_key(client["user_ip"]))
                response = api_client.get_status()
            return {
                "client": self._client_brief(client),
                "result": response
            }

        response = self._run_parallel_clients("get-client-status", selected_ids, worker, max_workers=max_workers, task_id=task_id)
        os.makedirs(self.client_status_dir, exist_ok=True)
        save_path = os.path.join(self.client_status_dir, f"{datetime.now().strftime('%y-%m-%d-%H-%M-%S')}.json")
        self._save_json(save_path, response["results"])
        with self.state_lock:
            self.last_client_status = response["results"]
        response["saved_path"] = save_path
        if task_id:
            self._append_task_log(task_id, f"状态结果已保存到 {save_path}")
        return response

    def get_client_log(self, selected_ids=None, max_workers=50):
        return self._get_client_log_internal(selected_ids=selected_ids, max_workers=max_workers, task_id=None)

    def _get_client_log_internal(self, selected_ids=None, max_workers=50, task_id=None):
        def worker(client):
            guard = self._client_request_guard(client)
            if guard:
                response = guard
            else:
                api_client = APIClient(f"http://{client['user_ip']}:8088", self._generate_api_key(client["user_ip"]))
                response = api_client.get_log()
            return {
                "client": self._client_brief(client),
                "result": response
            }

        response = self._run_parallel_clients("get-client-log", selected_ids, worker, max_workers=max_workers, task_id=task_id)
        os.makedirs(self.client_log_dir, exist_ok=True)
        save_path = os.path.join(self.client_log_dir, f"{datetime.now().strftime('%y-%m-%d-%H-%M-%S')}.json")
        self._save_json(save_path, response["results"])
        with self.state_lock:
            self.last_client_log = response["results"]
        response["saved_path"] = save_path
        if task_id:
            self._append_task_log(task_id, f"日志结果已保存到 {save_path}")
        return response

    def _render_template(self, template_text, client):
        env = {
            "LOCAL_IP": self.config["LOCAL_IP"],
            "client": client
        }
        template_source = str(template_text or "")
        stripped = template_source.strip()
        if stripped.startswith("f'") or stripped.startswith('f"'):
            return eval(template_source, {}, env)
        return template_source

    def run_command(self, selected_ids=None, command_id="default", command_template="", max_workers=50):
        return self._run_command_internal(selected_ids=selected_ids, command_id=command_id, command_template=command_template, max_workers=max_workers, task_id=None)

    def _run_command_internal(self, selected_ids=None, command_id="default", command_template="", max_workers=50, task_id=None):
        def worker(client):
            guard = self._client_request_guard(client)
            if guard:
                response = guard
            else:
                api_client = APIClient(f"http://{client['user_ip']}:8088", self._generate_api_key(client["user_ip"]))
                command = self._render_template(command_template, client)
                response = api_client.execute_command(str(command_id), command)
            return {
                "client": self._client_brief(client),
                "result": response
            }

        return self._run_parallel_clients("run-command", selected_ids, worker, max_workers=max_workers, task_id=task_id)

    def kill_command(self, selected_ids=None, command_id="default", max_workers=50):
        return self._kill_command_internal(selected_ids=selected_ids, command_id=command_id, max_workers=max_workers, task_id=None)

    def _kill_command_internal(self, selected_ids=None, command_id="default", max_workers=50, task_id=None):
        def worker(client):
            guard = self._client_request_guard(client)
            if guard:
                response = guard
            else:
                api_client = APIClient(f"http://{client['user_ip']}:8088", self._generate_api_key(client["user_ip"]))
                response = api_client.kill_command(str(command_id))
            return {
                "client": self._client_brief(client),
                "result": response
            }

        return self._run_parallel_clients("kill-command", selected_ids, worker, max_workers=max_workers, task_id=task_id)

    def open_info_window(self, selected_ids=None, window_id=1, title="", content="", front_size=16, max_workers=50):
        return self._open_info_window_internal(selected_ids=selected_ids, window_id=window_id, title=title, content=content, front_size=front_size, max_workers=max_workers, task_id=None)

    def _open_info_window_internal(self, selected_ids=None, window_id=1, title="", content="", front_size=16, max_workers=50, task_id=None):
        def worker(client):
            guard = self._client_request_guard(client)
            if guard:
                response = guard
            else:
                api_client = APIClient(f"http://{client['user_ip']}:8088", self._generate_api_key(client["user_ip"]))
                response = api_client.handle_info("on", title=title, content=self._render_template(content, client), window_id=int(window_id), front_size=int(front_size))
            return {
                "client": self._client_brief(client),
                "result": response
            }

        return self._run_parallel_clients("open-info-window", selected_ids, worker, max_workers=max_workers, task_id=task_id)

    def close_info_window(self, selected_ids=None, window_id=1, max_workers=50):
        return self._close_info_window_internal(selected_ids=selected_ids, window_id=window_id, max_workers=max_workers, task_id=None)

    def _close_info_window_internal(self, selected_ids=None, window_id=1, max_workers=50, task_id=None):
        def worker(client):
            guard = self._client_request_guard(client)
            if guard:
                response = guard
            else:
                api_client = APIClient(f"http://{client['user_ip']}:8088", self._generate_api_key(client["user_ip"]))
                response = api_client.handle_info("off", title="", content="", window_id=int(window_id), front_size=16)
            return {
                "client": self._client_brief(client),
                "result": response
            }

        return self._run_parallel_clients("close-info-window", selected_ids, worker, max_workers=max_workers, task_id=task_id)

    def _template_candidates(self, primary_dir, alias_dirs=None, fallback_files=None):
        candidates = []
        for directory in [primary_dir] + list(alias_dirs or []):
            if os.path.isdir(directory) and directory not in candidates:
                candidates.append(directory)
        for file_path in fallback_files or []:
            if os.path.isfile(file_path) and file_path not in candidates:
                candidates.append(file_path)
        return candidates

    def _read_template_file(self, path):
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    def _template_payloads(self, template_type):
        templates = []
        seen_names = set()
        if template_type == "command":
            candidates = self._template_candidates(
                self.command_template_dir,
                alias_dirs=[
                    os.path.join(self.base_dir, "command_template"),
                    os.path.join(self.base_dir, "commands")
                ],
                fallback_files=[os.path.join(self.base_dir, "command.json")]
            )
        else:
            candidates = self._template_candidates(
                self.window_template_dir,
                alias_dirs=[
                    os.path.join(self.base_dir, "window-template"),
                    os.path.join(self.base_dir, "windows")
                ],
                fallback_files=[os.path.join(self.base_dir, "window.json")]
            )

        for candidate in candidates:
            if os.path.isdir(candidate):
                for filename in sorted(os.listdir(candidate)):
                    path = os.path.join(candidate, filename)
                    if not os.path.isfile(path):
                        continue
                    try:
                        content = self._read_template_file(path)
                        template_name = filename
                        if template_name in seen_names:
                            continue
                        content["template_name"] = template_name
                        templates.append(content)
                        seen_names.add(template_name)
                    except Exception as exc:
                        logger.error(f"Read template {path} failed: {exc}")
            else:
                try:
                    content = self._read_template_file(candidate)
                    template_name = os.path.basename(candidate)
                    if template_name in seen_names:
                        continue
                    content["template_name"] = template_name
                    templates.append(content)
                    seen_names.add(template_name)
                except Exception as exc:
                    logger.error(f"Read template {candidate} failed: {exc}")
        return templates

    def get_clients_view(self):
        with self.state_lock:
            clients = copy.deepcopy(self.clients)
            ping_by_ip = copy.deepcopy(self.last_ping_by_ip)
            connect_by_client = copy.deepcopy(self.last_connect_by_client)

        result = []
        for client in clients:
            ping_state = None
            if client.get("user_ip") in ping_by_ip:
                ping_state = ping_by_ip[client["user_ip"]]["status"]
            connect_state = connect_by_client.get(client["_client_id"])
            result.append({
                **client,
                "ping_status": ping_state,
                "connect_status": connect_state.get("status") if connect_state else None,
                "connect_message": connect_state.get("mesg") if connect_state else None
            })
        return result

    def get_state(self):
        with self.state_lock:
            config = copy.deepcopy(self.config)
            filter_data = copy.deepcopy(self.filter_data)
            audit_logs = copy.deepcopy(self.audit_logs)
            ping_scan = copy.deepcopy(self.last_ping_scan)
        return {
            "config": config,
            "filter": filter_data,
            "clients": self.get_clients_view(),
            "ping_scan": ping_scan,
            "audit_logs": audit_logs,
            "tasks": self.get_task_summaries(),
            "templates": {
                "command": self._template_payloads("command"),
                "window": self._template_payloads("window")
            }
        }
