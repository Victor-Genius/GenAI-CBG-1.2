# Real-Time WebSocket Viewer

A Python-based real-time WebSocket viewer with a sleek, modern UI. The application allows users to view real-time WebSocket messages, send input through a prompt dialog, and includes features like network status indicators, global hotkeys, and a movable, rounded window.

---

## Features

1. **Real-Time WebSocket Viewer**  
   - Displays real-time messages received from a WebSocket server.
   - Automatically reconnects to the server if the connection drops.

2. **Input Dialog**  
   - Allows users to send prompts to the WebSocket server through a modal dialog.

3. **Hotkeys**  
   - `Ctrl+Alt+X`: Open the input dialog.  
   - `Ctrl+Shift+Q`: Quit the application.

4. **Network Status Indicator**  
   - **Green Text**: Indicates successful connection to the WebSocket server.  
   - **Red Text**: Indicates a network connection error.

5. **Custom UI**  
   - Frameless window with rounded corners.  
   - Dark-themed "Sublime Text" style for better readability.

6. **Movable Window**  
   - The window can be dragged and repositioned by holding the left mouse button.

---

## Prerequisites

- Python 3.8 or later
- Dependencies listed in `requirements.txt`

---