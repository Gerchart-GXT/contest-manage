import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt
from logger import logger

class InfoWindow:
    def __init__(self, title, content):
        """
        构造函数，传入 HTML 字符串并创建窗口。
        :param content: HTML 字符串
        :param title: 窗口标题
        """
        self.content = content
        self.title = title
        self.window = None
        self._create_window()

    def _create_window(self):
        """
        创建窗口并展示 HTML 内容。
        """
        # 创建 Qt 主窗口
        logger.info(f"Create window {self.title}")
        self.window = QMainWindow()
        self.window.setWindowTitle(self.title)
        self.window.setGeometry(100, 100, 800, 600)
        self.window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.window.activateWindow()
        self.window.raise_()

        # 使用 QWebEngineView 渲染 HTML
        self.browser = QWebEngineView()
        self.browser.setHtml(self.content)
        self.window.setCentralWidget(self.browser)

        # 绑定窗口关闭事件
        self.window.closeEvent = self._on_window_close

    def _on_window_close(self, event):
        """
        窗口关闭时的回调函数。
        """
        logger.info(f"Window {self.title} closed manually!")
        self.window = None  # 标记窗口已关闭
        event.accept()

    def show(self):
        """
        显示窗口。
        """
        logger.info(f"Window {self.title} show!")
        if self.window is not None:
            self.window.show()

    def close(self):
        """
        关闭窗口。
        """
        logger.info(f"Window {self.title} closed!")
        if self.window is not None:
            self.window.close()
            self.window = None

    def is_open(self):
        """
        检查窗口是否仍然打开。
        :return: True 如果窗口仍然打开，否则 False
        """
        return self.window is not None