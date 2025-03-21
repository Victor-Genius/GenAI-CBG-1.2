from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget, QDialog, QLineEdit,
    QPushButton, QHBoxLayout, QLabel
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPoint, QMetaObject
from PyQt5.QtGui import QGuiApplication, QPainter, QPainterPath, QBrush, QColor
import sys
import asyncio
import websockets
import threading
import keyboard  # For global hotkey
import os


os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts.warning=false"


class WebSocketClient(QThread):
    message_received = pyqtSignal(str)
    connection_ok = pyqtSignal()
    connection_error = pyqtSignal()

    def __init__(self, uri, parent=None):
        super().__init__(parent)
        self.uri = uri
        self.websocket = None
        self.keep_running = True

    async def receive_data(self):
        while self.keep_running:
            try:
                async with websockets.connect(self.uri) as websocket:
                    self.websocket = websocket
                    self.connection_ok.emit()  # Signal connection success
                    while self.keep_running:
                        message = await websocket.recv()
                        self.message_received.emit(message)
            except Exception as e:
                self.connection_error.emit()
                await asyncio.sleep(1)  # Wait before retrying

    async def send_message(self, message):
        try:
            if self.websocket:
                await self.websocket.send(message)
        except Exception as e:
            self.connection_error.emit()

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.receive_data())
        except asyncio.CancelledError:
            pass
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())  # Clean up async generators
            loop.close()


    # def stop(self):
    #     self.keep_running = False
    #     self.quit()  # Ensure the thread exits cleanly
    def stop(self):
        self.keep_running = False
        if self.websocket:
            asyncio.run_coroutine_threadsafe(self.websocket.close(), asyncio.get_event_loop())
        # Cancel all tasks in the event loop
        loop = asyncio.get_event_loop()
        tasks = asyncio.all_tasks(loop)
        for task in tasks:
            task.cancel()
        self.quit()  # Ensure the thread exits cleanly




class InputDialog(QDialog):
    def __init__(self, websocket_client, parent=None):
        super().__init__(parent)
        self.websocket_client = websocket_client
        self.setWindowTitle("Enter GPT Prompt")
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedSize(400, 150)

        # Input field
        self.input_field = QLineEdit(self)
        self.input_field.setPlaceholderText("Type your GPT prompt here...")

        # Buttons
        self.save_button = QPushButton("Save", self)
        self.save_button.clicked.connect(self.save)

        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.input_field)
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def save(self):
        # Send the entered text to the WebSocket server
        text = self.input_field.text()
        if text.strip():
            asyncio.run(self.websocket_client.send_message(text))
        self.accept()


class ServerIpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Server IP")
        self.setWindowModality(Qt.ApplicationModal)
        self.setFixedSize(500, 100)

        # Current server IP
        self.parent = parent

        # Input field
        self.input_field = QLineEdit(self)
        self.input_field.setText(self.parent.client.uri)
        self.input_field.setPlaceholderText("Enter new server IP...")

        # Buttons
        self.ok_button = QPushButton("OK", self)
        self.ok_button.clicked.connect(self.save_ip)

        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Server IP:", self))
        layout.addWidget(self.input_field)
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def save_ip(self):
        new_ip = self.input_field.text().strip()
        if new_ip:
            self.parent.client.uri = new_ip  # Update WebSocket server URI
            self.accept()  # Close the dialog immediately
            QTimer.singleShot(0, self.parent.reconnect_client)  # Trigger reconnection after dialog closes


class RealTimeViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Real-Time WebSocket Viewer")
        self.resize(500, 200)
        self.center_top()

        # Remove window decoration and add rounded corners
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Connection Status Label
        self.status_label = QLabel(self)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.hide()  # Initially hidden

        # Text widget for displaying messages
        self.text_widget = QTextEdit(self)
        self.text_widget.setReadOnly(True)
        self.text_widget.setLineWrapMode(QTextEdit.WidgetWidth)
        self.text_widget.setStyleSheet("""
            QTextEdit {
                background-color: #2E2E2E;
                color: #F8F8F2;
                font-family: Consolas, "Courier New", monospace;
                font-size: 11pt;
                border: none;
            }
        """)

        # Layout
        central_widget = QWidget(self)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.status_label)
        layout.addWidget(self.text_widget)
        self.setCentralWidget(central_widget)

        # WebSocket Client
        self.client = WebSocketClient("ws://10.96.45.62:8765")  # Default to localhost
        self.client.message_received.connect(self.display_response)
        self.client.connection_ok.connect(self.show_connection_ok)
        self.client.connection_error.connect(self.show_connection_error)
        self.client.start()

        # Variables for dragging the window
        self.drag_position = None

        # Start the global hotkey thread
        self.start_global_hotkey_listener()

    def paintEvent(self, event):
        # Add rounded corners
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 15, 15)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(45, 45, 45, 255)))  # Dark background
        painter.setPen(Qt.NoPen)
        painter.drawPath(path)

    def center_top(self):
        # Get the screen size
        screen = QGuiApplication.primaryScreen()
        screen_geometry = screen.geometry()

        # Calculate the x and y position
        x = (screen_geometry.width() - self.width()) // 2
        y = 0

        # Move the window to the calculated position
        self.move(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_position is not None and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None

    def display_response(self, message):
        self.status_label.hide()  # Hide connection error if message received
        if message == "((*))space((*))":
            self.text_widget.clear()
        else:
            current_text = self.text_widget.toPlainText()
            updated_text = current_text + message
            self.text_widget.setText(updated_text)

    def show_connection_error(self):
        self.status_label.setText("Network Connection Error")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.status_label.show()

    def show_connection_ok(self):
        self.status_label.setText("Network OK")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        self.status_label.show()
        QTimer.singleShot(3000, self.status_label.hide)  # Hide after 3 seconds

    def toggle_visibility(self):
        if self.isHidden():
            self.show()
        else:
            self.hide()
    def show_input_dialog(self):
        input_dialog = InputDialog(self.client, self)
        input_dialog.exec_()

    def show_ip_dialog(self):
        ip_dialog = ServerIpDialog(self)
        ip_dialog.exec_()

    def start_global_hotkey_listener(self):
        def hotkey_listener():
            keyboard.add_hotkey('ctrl+alt+x', lambda: QTimer.singleShot(0, self.show_input_dialog))
            keyboard.add_hotkey('ctrl+shift+q', QApplication.quit)
            keyboard.add_hotkey('ctrl+shift+x', self.toggle_visibility)
            keyboard.add_hotkey('ctrl+shift+i', lambda: QTimer.singleShot(0, self.show_ip_dialog))  # New hotkey for IP configuration

        thread = threading.Thread(target=hotkey_listener, daemon=True)
        thread.start()
    def reconnect_client(self):
        # Stop the current WebSocket client
        self.client.stop()
        self.client.wait()  # Ensure the thread stops completely

        # Restart the WebSocket client
        self.start_new_client()

    def start_new_client(self):
        # Start a new WebSocket client
        self.client = WebSocketClient(self.client.uri)
        self.client.message_received.connect(self.display_response)
        self.client.connection_ok.connect(self.show_connection_ok)
        self.client.connection_error.connect(self.show_connection_error)
        self.client.start()



if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = RealTimeViewer()
    viewer.show()
    sys.exit(app.exec_())
