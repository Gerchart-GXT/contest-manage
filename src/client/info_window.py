import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt
from logger import logger  # 假设有一个日志记录器

class InfoWindow:
    def __init__(self, title, content, front_size):
        self.content = content
        self.title = title
        self.front_size = front_size
        self.window = None
        self._create_window()

    def _create_window(self):
        try:
            # 创建 Qt 主窗口
            self.window = CustomMainWindow(self)  # 使用自定义的 QMainWindow
            self.window.setWindowTitle(self.title)
            self.window.setGeometry(100, 100, 800, 600)
            self.window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
            self.window.activateWindow()
            self.window.raise_()
            # 使用 QWebEngineView 渲染 HTML
            self.browser = QWebEngineView()
            # 在 HTML 中添加 CSS 样式，动态调整字体大小
            styled_content = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{
                        font-size: {self.front_size}px; /* 默认字体大小 */
                        font-family: Arial, sans-serif;
                    }}
                </style>
            </head>
            <body>
                {self.content}
            </body>
            </html>
            """
            self.browser.setHtml(styled_content)
            self.window.setCentralWidget(self.browser)
            # 默认最大化窗口
            self.window.showMaximized()
            logger.info(f"Window '{self.title}' created successfully.")
        except Exception as e:
            logger.error(f"Failed to create window '{self.title}': {str(e)}")
            self.window = None  # 确保窗口对象为 None，避免后续操作出错

    def show(self):
        try:
            if self.window is not None:
                self.window.show()
                logger.info(f"Window '{self.title}' shown successfully.")
            else:
                logger.warning(f"Window '{self.title}' is not initialized and cannot be shown.")
        except Exception as e:
            logger.error(f"Failed to show window '{self.title}': {str(e)}")

    def close(self):
        try:
            if self.window is not None:
                self.window.request_close = True  # 标记为请求关闭
                self.window.close()
                self.window = None
                logger.info(f"Window '{self.title}' closed via request.")
            else:
                logger.warning(f"Window '{self.title}' is not initialized and cannot be closed.")
        except Exception as e:
            logger.error(f"Failed to close window '{self.title}': {str(e)}")

    def is_open(self):
        try:
            return self.window is not None
        except Exception as e:
            logger.error(f"Failed to check if window '{self.title}' is open: {str(e)}")
            return False

class CustomMainWindow(QMainWindow):
    def __init__(self, info_window):
        super().__init__()
        self.info_window = info_window
        self.request_close = False  # 标志位，用于区分请求关闭和手动关闭

    def closeEvent(self, event):
        if self.request_close:
            # 如果是请求关闭
            logger.info(f"Window '{self.info_window.title}' closed via request.")
        else:
            # 如果是手动关闭
            logger.info(f"Window '{self.info_window.title}' closed manually by user.")
        # 清理 info_window 中的 window 对象
        self.info_window.window = None
        event.accept()