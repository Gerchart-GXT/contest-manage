import os
import json
import socket
import hashlib
from logger import logger 

class Utility:
    def __init__(self):
        logger.info("Utility Init.")

    def calculate_md5(self, input_string):
        md5_hash = hashlib.md5()
        md5_hash.update(input_string.encode('utf-8'))
        return md5_hash.hexdigest()

    def get_local_ipv4(self):
        logger.info("Get local ipv4!")
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
        except Exception as e:
            logger.error("Can't get local ipv4!")
            return {
                "status": "erro",
                "mesg": "Can't get local ipv4!"
            }
        finally:
            s.close()

        logger.info(f"Get local ipv4 successfully: {ip_address}")
        return {
            "status": "success",
            "mesg": "Get local ipv4 successfully!",
            "res": ip_address
        }
        
    def get_active_progress(self):
        return []

    def save_json_file(self, path, data):
        logger.info(f"Save file to {path}")
        try:
            with open(path, "w", encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            logger.info(f"Save file successfully : {path}")
            return {
                "status": "success",
                "mesg": f"Save {path} successfully!"
            }
        except PermissionError:
            logger.error(f"ERROR! Has NO permission to read {path}!")
            return {
                "status": "erro",
                "mesg": f"ERROR! Has NO permission to read {path}!"
            }
        except Exception as e:
            logger.error(f"File saving ERROR! Unkown {e}")
            return {
                "status": "erro",
                "mesg": f"ERROR! Unkown {e}"
            }
    
    def read_json_file(self, path):
        logger.info(f"Read file from {path}")
        try:
            with open(path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            logger.info(f"Read file successfully : {path}")
            return {
                "status": "success",
                "mesg": f"Read {path} successfully!",
                "res": data
            }
        except FileNotFoundError:
            logger.error(f"ERROR! File {path} not exsist!")
            return {
                "status": "erro",
                "mesg": f"ERROR! File {path} not exsist!"
            }
        except json.JSONDecodeError:
            logger.error(f"ERROR! File {path} is not Valid JSON format!")
            return {
                "status": "erro",
                "mesg": f"ERROR! File {path} is not Valid JSON format!"
            }
        except PermissionError:
            logger.error(f"ERROR! Has NO permission to read {path}!")
            return {
                "status": "erro",
                "mesg": f"ERROR! Has NO permission to read {path}!"
            }
        except Exception as e:
            logger.error(f"File reading ERROR! Unkown {e}")
            return {
                "status": "erro",
                "mesg": f"ERROR! Unkown {e}"
            }


    
    
    
