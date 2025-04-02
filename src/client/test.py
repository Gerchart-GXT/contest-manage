import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView

class HTMLViewer(QMainWindow):
    def __init__(self, html_content, title="HTML Viewer"):
        """
        构造函数，传入 HTML 字符串并创建窗口。
        :param html_content: HTML 字符串
        :param title: 窗口标题
        """
        super().__init__()
        self.setWindowTitle(title)
        self.setGeometry(100, 100, 800, 600)

        # 使用 QWebEngineView 渲染 HTML
        self.browser = QWebEngineView()
        self.browser.setHtml(html_content)
        self.setCentralWidget(self.browser)

# 示例使用
if __name__ == "__main__":
    app = QApplication(sys.argv)

    html_content = """
    <html>
        <head><title>Sample HTML</title></head>
        <body>
            <h1>Hello, World!</h1>
            <p>This is a sample HTML content.</p>
            <a href="https://www.example.com">Visit Example</a>
        </body>
    </html>
    """

    # 创建两个窗口
    a = HTMLViewer(html_content, title="a")
    b = HTMLViewer(html_content, title="b")

    # 显示窗口
    a.show()
    b.show()
    # 运行应用程序主循环
    # sys.exit(app.exec_())