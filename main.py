import random
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit

# Initialize Flask app and SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret_card_key_123'
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Game Logic Constants ---
SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

class GameState:
    def __init__(self):
        self.deck = []
        self.history = []  # To store drawn cards and actions
        self.shuffle_decks()

    def shuffle_decks(self):
        # Combine 3 standard decks (52 * 3 = 156 cards)
        single_deck = [f"{r}{s}" for r in RANKS for s in SUITS]
        self.deck = single_deck * 3
        random.shuffle(self.deck)
        self.history = [{"type": "system", "msg": "Decks shuffled! 156 cards ready."}]

    def draw_card(self, player_id):
        if not self.deck:
            return None
        card = self.deck.pop(0)
        action = {"type": "draw", "player": player_id, "card": card, "remaining": len(self.deck)}
        self.history.insert(0, action)
        return action

# Global game instance
game = GameState()

# --- HTML Template (Embedded for Single-File Portability) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>3-Deck Real-Time Cards</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        :root {
            --bg-color: #1a472a; /* Classic card table green */
            --card-white: #ffffff;
            --text-light: #f0f0f0;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-light);
            margin: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
        }
        .container {
            width: 90%;
            max-width: 800px;
            text-align: center;
            padding: 20px;
        }
        .controls {
            margin: 20px 0;
            display: flex;
            gap: 10px;
            justify-content: center;
        }
        button {
            padding: 12px 24px;
            font-size: 16px;
            cursor: pointer;
            border: none;
            border-radius: 8px;
            transition: transform 0.1s, background 0.3s;
            font-weight: bold;
        }
        .btn-draw { background: #e67e22; color: white; }
        .btn-shuffle { background: #c0392b; color: white; }
        button:active { transform: scale(0.95); }
        button:hover { filter: brightness(1.1); }

        .status-bar {
            background: rgba(0,0,0,0.3);
            padding: 10px;
            border-radius: 20px;
            margin-bottom: 20px;
        }

        #action-log {
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 15px;
            height: 300px;
            overflow-y: auto;
            text-align: left;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .log-entry {
            padding: 8px;
            border-radius: 6px;
            background: rgba(0,0,0,0.2);
            animation: fadeIn 0.3s ease;
        }
        .card-val {
            font-weight: bold;
            color: #ffcc00;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Multiplayer 3-Deck Cards</h1>
        
        <div class="status-bar">
            Connected as: <span id="player-name">Connecting...</span> | 
            Cards Remaining: <span id="card-count">156</span>
        </div>

        <div class="controls">
            <button class="btn-draw" onclick="drawCard()">Draw Card</button>
            <button class="btn-shuffle" onclick="shuffleDecks()">Shuffle All</button>
        </div>

        <div id="action-log">
            <!-- Real-time actions will appear here -->
        </div>
    </div>

    <script>
        const socket = io();
        let myId = "";

        socket.on('connect', () => {
            myId = socket.id.substring(0, 5);
            document.getElementById('player-name').innerText = "Player_" + myId;
        });

        // Initialize state or catch up with history
        socket.on('init', (data) => {
            document.getElementById('card-count').innerText = data.remaining;
            updateLog(data.history);
        });

        // Listen for draw events
        socket.on('card_drawn', (data) => {
            document.getElementById('card-count').innerText = data.remaining;
            addSingleLog(data);
        });

        // Listen for shuffle events
        socket.on('decks_shuffled', (data) => {
            document.getElementById('card-count').innerText = "156";
            const log = document.getElementById('action-log');
            log.innerHTML = ''; // Clear for fresh start
            addSingleLog({type: 'system', msg: 'Decks were shuffled by a player!'});
        });

        function drawCard() {
            socket.emit('request_draw');
        }

        function shuffleDecks() {
            if(confirm("Shuffle all 3 decks? This clears the current board.")) {
                socket.emit('request_shuffle');
            }
        }

        function addSingleLog(action) {
            const log = document.getElementById('action-log');
            const div = document.createElement('div');
            div.className = 'log-entry';
            
            if (action.type === 'draw') {
                const isMe = action.player === myId ? "(You)" : `(Player_${action.player})`;
                div.innerHTML = `<span>${isMe} drew </span><span class="card-val">${action.card}</span>`;
            } else {
                div.innerHTML = `<i>${action.msg}</i>`;
            }
            
            log.prepend(div);
        }

        function updateLog(history) {
            const log = document.getElementById('action-log');
            log.innerHTML = '';
            history.forEach(item => {
                const div = document.createElement('div');
                div.className = 'log-entry';
                if (item.type === 'draw') {
                    div.innerHTML = `Player_${item.player} drew <span class="card-val">${item.card}</span>`;
                } else {
                    div.innerHTML = `<i>${item.msg}</i>`;
                }
                log.appendChild(div);
            });
        }
    </script>
</body>
</html>
"""

# --- SocketIO Event Handlers ---

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('connect')
def handle_connect():
    # Send current game state to the newly connected player
    emit('init', {
        'remaining': len(game.deck),
        'history': game.history
    })

@socketio.on('request_draw')
def handle_draw():
    # Use short version of session ID as player identifier
    player_id = random.choice(['Alpha', 'Beta', 'Gamma', 'Delta']) # Placeholder if ID isn't ready
    from flask import request
    player_id = request.sid[:5]
    
    action = game.draw_card(player_id)
    if action:
        # Broadcast the draw to EVERYONE
        socketio.emit('card_drawn', action)
    else:
        emit('error', {'msg': 'Deck is empty! Please shuffle.'})

@socketio.on('request_shuffle')
def handle_shuffle():
    game.shuffle_decks()
    # Broadcast shuffle to EVERYONE
    socketio.emit('decks_shuffled', {'remaining': 156})

if __name__ == '__main__':
    # Local development run
    socketio.run(app, debug=True)
