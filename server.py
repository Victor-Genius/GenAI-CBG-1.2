import asyncio
import websockets
import pyperclip
from openai import AsyncOpenAI
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QLabel, QListWidget, QWidget
)
from PyQt5.QtCore import QThread, pyqtSignal
import traceback
import os

os.environ["QT_LOGGING_RULES"] = "qt.qpa.fonts.warning=false"

api_key = "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"
chat_history = []
MAX_EXCHANGES = 5
client = AsyncOpenAI(api_key=api_key)
SERVER_IP_ADDRESS = "10.96.45.62"
SERVER_PORT = 8765

with open("profile.txt", "r" , encoding="utf-8", errors='replace') as file:
    profile = file.read()

connected_clients = set()


async def process_clipboard_text(text):
    global chat_history

    await asyncio.sleep(0.1)
    predefined_instruction = {
        "role": "user",
        "content": (
            """Hi, You are a senior full-stack developer and now you have to attend the interview.
            The captioning script is offered so your task is to optimize the script and extract the last main question within it and provide a concise answer.
            The answer shouldn't be over 7 sentences and must be written in easy spoken English.
            If the question is about your experience, the answer has to follow this principle - STAR (Situation, Task, Action, Result).
            Ideally, the answer should be between 950 and 1000 characters.
            Here is your Additional Information. You are the best candidate to this job requirements. So you are really skillful in what an interviewer will ask.
            Additional Information(This is just additional):
                {}
            """.format(profile)
        )
    }
    chat_history = chat_history + [{"role": "user", "content": "Give me only answer. \ninterviewer's question:\""+text+"\""}]
    chat_history_with_instruction = [predefined_instruction] + chat_history

    if len(chat_history_with_instruction) > 2 * MAX_EXCHANGES + 2:
        chat_history_with_instruction = [predefined_instruction] + chat_history_with_instruction[-(2 * MAX_EXCHANGES):]

    stream = await client.chat.completions.create(
        model="gpt-4",
        messages=chat_history_with_instruction,
        max_tokens=200,
        temperature=0.7,
        stream=True,
    )

    chunks = []
    async for chunk in stream:
        content = chunk.choices[0].delta.content or ""
        if content:
            yield content
        chunks.append(chunk)

    assistant_reply = "".join(
        chunk.choices[0].delta.content or "" for chunk in chunks
    ).strip()
    chat_history.append({"role": "assistant", "content": assistant_reply})
    print(chat_history)


class ServerThread(QThread):
    connection_signal = pyqtSignal(str)
    disconnection_signal = pyqtSignal(str)
    log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.loop = asyncio.new_event_loop()
        self.stop_server_event = asyncio.Event()  # Fixed here

    async def handle_client(self, websocket):
        client_ip = websocket.remote_address[0]
        self.connection_signal.emit(client_ip)
        connected_clients.add(client_ip)

        try:
            recent_text = ""
            pyperclip.copy("")
            while not self.stop_server_event.is_set():
                clipboard_text = pyperclip.paste()
                if clipboard_text != recent_text:
                    recent_text = clipboard_text
                    try:
                        await websocket.send('((*))space((*))')
                        async for chunk in process_clipboard_text(clipboard_text):
                            await websocket.send(chunk)
                    except Exception as e:
                        self.log_signal.emit(f"Error processing clipboard text: {str(e)}")
                await asyncio.sleep(0.5)
        except websockets.exceptions.ConnectionClosed:
            self.disconnection_signal.emit(client_ip)
        except Exception as e:
            self.log_signal.emit(f"Unexpected error: {traceback.format_exc()}")
        finally:
            connected_clients.discard(client_ip)
            self.disconnection_signal.emit(client_ip)

    async def start_server(self):
        server = await websockets.serve(
            self.handle_client,
            SERVER_IP_ADDRESS,
            SERVER_PORT,
            ping_interval=20,  # Sends a ping every 20 seconds
            ping_timeout=20    # Disconnects if no pong is received within 20 seconds
        )
        await self.stop_server_event.wait()
        server.close()
        await server.wait_closed()

    def run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.start_server())
        finally:
            self.loop.close()

    def stop(self):
        self.stop_server_event.set()



class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WebSocket Server GUI")
        self.resize(600, 400)

        self.layout = QVBoxLayout()
        self.status_label = QLabel("Server starting...")
        self.layout.addWidget(self.status_label)

        self.action_log = QListWidget()
        self.layout.addWidget(self.action_log)

        self.connected_ips = QListWidget()
        self.layout.addWidget(self.connected_ips)

        container = QWidget()
        container.setLayout(self.layout)
        self.setCentralWidget(container)

        self.server_thread = ServerThread()
        self.server_thread.connection_signal.connect(self.on_client_connected)
        self.server_thread.disconnection_signal.connect(self.on_client_disconnected)
        self.server_thread.log_signal.connect(self.log_action)

        self.server_thread.start()
        self.status_label.setText(
            f"Server running on ws://{SERVER_IP_ADDRESS}:{SERVER_PORT}"
        )

    def on_client_connected(self, client_ip):
        self.log_action(f"{client_ip} connected")
        self.connected_ips.addItem(client_ip)

    def on_client_disconnected(self, client_ip):
        self.log_action(f"{client_ip} disconnected")
        for index in range(self.connected_ips.count()):
            if self.connected_ips.item(index).text() == client_ip:
                self.connected_ips.takeItem(index)
                break

    def log_action(self, message):
        self.action_log.addItem(message)

    def closeEvent(self, event):
        self.server_thread.stop()
        self.server_thread.wait()
        event.accept()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())
