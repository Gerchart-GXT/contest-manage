# logger.py
import logging
import os
from datetime import datetime

class Logger:
    def __init__(self, name, log_file='app.log', level=logging.INFO):
        # 创建日志目录
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # 设置日志文件路径
        log_file_path = os.path.join(log_dir, log_file)

        # 创建日志记录器
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # 创建文件处理器
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(level)

        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        # 创建日志格式
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # 添加处理器到日志记录器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def info(self, message):
        self.logger.info(message)

    def error(self, message):
        self.logger.error(message)

    def warning(self, message):
        self.logger.warning(message)

    def debug(self, message):
        self.logger.debug(message)

# 创建一个全局的日志实例
logger = Logger(__name__)