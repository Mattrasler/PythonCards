from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
# Allow all origins for the initial setup
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('message')
def handle_message(data):
    print(f"Received: {data}")
    # Broadcast the message to all connected clients
    emit('response', {'data': data}, broadcast=True)