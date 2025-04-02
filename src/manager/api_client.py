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

    def set_user(self, user_data):
        url = f"{self.base_url}/client/user"
        payload = {
            "action": "USERSET",
            "user_data": user_data
        }
        logger.info(f"Set user {self.base_url}/client/user, {user_data}")
        response = requests.post(url, headers=self.headers, data=json.dumps(payload))
        return response.json()

    def get_status(self):
        url = f"{self.base_url}/client/status"
        payload = {
            "action": "GET"
        }
        logger.info(f"Get status {self.base_url}/client/status")
        response = requests.post(url, headers=self.headers, data=json.dumps(payload))
        return response.json()

    def get_log(self):
        url = f"{self.base_url}/client/log"
        payload = {
            "action": "get"
        }
        logger.info(f"Get log {self.base_url}/client/log")
        response = requests.post(url, headers=self.headers, data=json.dumps(payload))
        return response.json()

    def handle_info(self, action, title = None, content = None, window_id = None):
        url = f"{self.base_url}/client/info"
        payload = {
            "action": action,
            "title": title,
            "content": content,
            "window_id": window_id
        }
        logger.info(f"Window {window_id} {action}, {self.base_url}/client/info")
        response = requests.post(url, headers=self.headers, data=json.dumps(payload))
        return response.json()

    def execute_command(self, command):
        url = f"{self.base_url}/client/command"
        payload = {
            "action": "run",
            "content": command
        }
        logger.info(f"Run command {self.base_url}/client/command")
        response = requests.post(url, headers=self.headers, data=json.dumps(payload))
        return response.json()
