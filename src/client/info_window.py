import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import Qt

class InfoWindow:
    def __init__(self, title, content, front_size):
        self.content = content
        self.title = title
        self.front_size = front_size
        self.window = None
        self._create_window()

    def _create_window(self):
        # 创建 Qt 主窗口
        self.window = QMainWindow()
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

    def show(self):
        if self.window is not None:
            self.window.show()

    def close(self):
        if self.window is not None:
            self.window.close()
            self.window = None

    def is_open(self):
        return self.window is not None