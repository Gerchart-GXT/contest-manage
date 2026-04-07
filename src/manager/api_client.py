import requests
import json
from logger import logger

class APIClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }

    def _make_request(self, url, payload):
        try:
            response = requests.post(url, headers=self.headers, data=json.dumps(payload), timeout=30)
            try:
                response_json = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON response: {e}")
                return {
                    "status": "error",
                    "mesg": f"Failed to decode JSON response: {e}"
                }

            if response.ok:
                return response_json

            logger.error(f"Request {url} failed: {response.status_code} {response_json}")
            return response_json
        except requests.exceptions.RequestException as e:
            logger.error(f"Request {url} failed: {e}")
            return {
                "status": "error",
                "mesg": f"Request failed: {e}"
            }
        
    def connect_check(self):
        url = f"{self.base_url}/client/connect"
        payload = {
            "action": "CHECK"
        }
        logger.info(f"Connect to {self.base_url}/client/connect")
        return self._make_request(url, payload)

    def set_user(self, user_data):
        url = f"{self.base_url}/client/user"
        payload = {
            "action": "USERSET",
            "user_data": user_data
        }
        logger.info(f"Set user {self.base_url}/client/user, {user_data}")
        return self._make_request(url, payload)

    def get_status(self):
        url = f"{self.base_url}/client/status"
        payload = {
            "action": "GET"
        }
        logger.info(f"Get status {self.base_url}/client/status")
        return self._make_request(url, payload)

    def get_log(self):
        url = f"{self.base_url}/client/log"
        payload = {
            "action": "get"
        }
        logger.info(f"Get log {self.base_url}/client/log")
        return self._make_request(url, payload)

    def handle_info(self, action, title=None, content=None, window_id=None, front_size=16):
        url = f"{self.base_url}/client/info"
        payload = {
            "action": action,
            "title": title,
            "content": content,
            "window_id": window_id,
            "front_size": front_size
        }
        logger.info(f"Window {window_id} {action}, {self.base_url}/client/info")
        return self._make_request(url, payload)

    def execute_command(self, command_id, command):
        url = f"{self.base_url}/client/command"
        payload = {
            "action": "run",
            "command_id": command_id,
            "content": command
        }
        logger.info(f"Run command {self.base_url}/client/command")
        return self._make_request(url, payload)

    def kill_command(self, command_id):
        url = f"{self.base_url}/client/command"
        payload = {
            "action": "kill",
            "command_id": command_id
        }
        logger.info(f"Kill command {self.base_url}/client/command")
        return self._make_request(url, payload)
