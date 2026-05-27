import html
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit

# Initialize Flask app and configure a secret key
app = Flask(__name__)
app.config['SECRET_KEY'] = 'gunicorn_chat_secret_987'

# Initialize SocketIO with eventlet async mode for Gunicorn production support
socketio = SocketIO(app, cors_allowed_origins="*")

# Simple server-side list to keep track of the message history
message_store = []

# --- Integrated HTML/CSS/JS Interface ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Real-Time Broadcast Hub</title>
    <script src="https://cloudflare.com"></script>
    <style>
        :root {
            --bg-dark: #0f172a;
            --panel-bg: #1e293b;
            --text-main: #f8fafc;
            --accent-blue: #3b82f6;
        }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-main);
            margin: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .chat-container {
            width: 100%;
            max-width: 600px;
            background: var(--panel-bg);
            border-radius: 12px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            display: flex;
            flex-direction: column;
            height: 80vh;
            overflow: hidden;
        }
        .header {
            background: rgba(0,0,0,0.2);
            padding: 15px 20px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            font-weight: 600;
        }
        .user-tag {
            color: #38bdf8;
            font-size: 0.9em;
        }
        .message-pane {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .msg-bubble {
            background: rgba(255,255,255,0.05);
            padding: 10px 14px;
            border-radius: 8px;
            max-width: 85%;
            word-wrap: break-word;
            animation: popIn 0.2s ease-out;
        }
        .msg-user {
            font-size: 0.8em;
            color: #94a3b8;
            margin-bottom: 4px;
            font-weight: bold;
        }
        .input-area {
            padding: 15px 20px;
            background: rgba(0,0,0,0.1);
            border-top: 1px solid rgba(255,255,255,0.1);
            display: flex;
            gap: 10px;
        }
        input[type="text"] {
            flex: 1;
            background: #0f172a;
            border: 1px solid rgba(255,255,255,0.2);
            padding: 12px;
            border-radius: 6px;
            color: white;
            font-size: 14px;
        }
        input:focus {
            outline: none;
            border-color: var(--accent-blue);
        }
        button {
            background: var(--accent-blue);
            color: white;
            border: none;
            padding: 0 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            transition: background 0.2s;
        }
        button:hover { background: #2563eb; }
        @keyframes popIn {
            from { opacity: 0; transform: translateY(5px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body>

    <div class="chat-container">
        <div class="header">
            Broadcast Hub &mdash; Assigning ID...</span>
        </div>
        
        <div class="message-pane" id="message-pane">
            <!-- Messages from all users populate here instantly -->
        </div>

        <div class="input-area">
            <input type="text" id="msg-input" placeholder="Type a broadcast message..." onkeydown="if(event.key==='Enter') sendMessage()">
            <button onclick="sendMessage()">Send</button>
        </div>
    </div>

    <script>
        const socket = io();
        let myId = "";

        socket.on('connect', () => {
            myId = "User_" + socket.id.substring(0, 5);
            document.getElementById('identity').innerText = myId;
        });

        // Receives the existing history when first loading the page
        socket.on('load_history', (history) => {
            const pane = document.getElementById('message-pane');
            pane.innerHTML = '';
            history.forEach(appendMessage);
            scrollToBottom();
        });

        // Receives instant messages broadcast from the server
        socket.on('new_broadcast', (data) => {
            appendMessage(data);
            scrollToBottom();
        });

        function sendMessage() {
            const input = document.getElementById('msg-input');
            const text = input.value.trim();
            if (!text) return;

            socket.emit('submit_msg', { message: text });
            input.value = '';
        }

        function appendMessage(data) {
            const pane = document.getElementById('message-pane');
            const container = document.createElement('div');
            container.className = 'msg-bubble';

            // Mark your own messages uniquely
            if(data.user === myId) {
                container.style.borderLeft = "3px solid var(--accent-blue)";
            }

            container.innerHTML = `<div class="msg-user">${data.user}</div><div>${data.message}</div>`;
            pane.appendChild(container);
        }

        function scrollToBottom() {
            const pane = document.getElementById('message-pane');
            pane.scrollTop = pane.scrollHeight;
        }
    </script>
</body>
</html>
"""

# --- Routes and WebSockets ---

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('connect')
def handle_user_connect():
    # Provide the newly connected client with the historical logs
    emit('load_history', message_store)

@socketio.on('submit_msg')
def handle_new_msg(data):
    # Extract structural components safely
    user_id = f"User_{request.sid[:5]}"
    raw_text = data.get('message', '').strip()
    
    if raw_text:
        # Sanitize text to prevent simple script injection attacks
        clean_text = html.escape(raw_text)
        
        payload = {'user': user_id, 'message': clean_text}
        message_store.append(payload)
        
        # Restrict back-history memory buffer to the last 50 entries
        if len(message_store) > 50:
            message_store.pop(0)
            
        # BROADCAST to all connected web clients instantly
        socketio.emit('new_broadcast', payload)

if __name__ == '__main__':
    # Local fallback execution without gunicorn configuration
    socketio.run(app, debug=True)
