from flask import Flask, render_template_string
from flask_socketio import SocketIO

app = Flask(__name__)
# cors_allowed_origins="*" allows testing locally across different ports
socketio = SocketIO(app, cors_allowed_origins="*")

# Simple HTML page with embedded JavaScript to handle the WebSocket connection
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Flask-SocketIO Chat</title>
    <script src="https://socket.io"></script>
</head>
<body>
    <h2>Broadcast Message Board</h2>
    <input id="message_input" type="text" placeholder="Type a message...">
    <button onclick="sendMessage()">Send to All</button>
    <ul id="messages"></ul>

    <script>
        // Connect to the Flask-SocketIO server
        const socket = io();

        // Listen for the 'broadcast_message' event from the server
        socket.on('broadcast_message', function(data) {
            const li = document.createElement('li');
            li.textContent = data.msg;
            document.getElementById('messages').appendChild(li);
        });

        // Send a message to the server
        function sendMessage() {
            const input = document.getElementById('message_input');
            socket.emit('send_message', { msg: input.value });
            input.value = '';
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

# Triggered when a client emits 'send_message'
@socketio.on('send_message')
def handle_message(data):
    # broadcast=True sends the data to every connected user
    socketio.emit('broadcast_message', {'msg: ': data['msg']}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app)
