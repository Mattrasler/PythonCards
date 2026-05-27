import random
from flask import Flask, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = 'super_secret_websocket_key'
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

# 1. Added turn tracking structures
GAME_STATE = {
    'deck': [],
    'players': {},
    'player_order': [],      # Ordered list of player names (e.g., ["Player 1", "Player 2"])
    'current_player': None,   # Name of the player who must act
    'drawn_card': None, 
    'discard_pile': [],  
    'error': None
}

def create_triple_deck():
    suits = ['♠', '♥', '♦', '♣']
    ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
    single_deck = [f"{rank}{suit}" for suit in suits for rank in ranks]
    triple_deck = single_deck * 3
    random.shuffle(triple_deck)
    return triple_deck

def advance_turn():
    """Helper to move the turn ticker forward to the next player systematically"""
    if not GAME_STATE['player_order']:
        return
    try:
        current_idx = GAME_STATE['player_order'].index(GAME_STATE['current_player'])
        next_idx = (current_idx + 1) % len(GAME_STATE['player_order'])
        GAME_STATE['current_player'] = GAME_STATE['player_order'][next_idx]
    except ValueError:
        GAME_STATE['current_player'] = GAME_STATE['player_order'][0]

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    emit_state_update()

@socketio.on('shuffle_deck')
def handle_shuffle():
    GAME_STATE['deck'] = create_triple_deck()
    GAME_STATE['current_player'] = None
    GAME_STATE['drawn_card'] = None
    GAME_STATE['discard_pile'] = []
    GAME_STATE['error'] = None
    
    # Keep the existing players and order, but empty their card hands
    if GAME_STATE['player_order']:
        for name in GAME_STATE['player_order']:
            GAME_STATE['players'][name] = []
    else:
        GAME_STATE['players'] = {}
        GAME_STATE['player_order'] = []
        
    emit_state_update(broadcast=True)

@socketio.on('deal_cards')
def handle_deal(data):
    deck = GAME_STATE['deck']
    num_players = int(data.get('num_players', 1))
    GAME_STATE['error'] = None
    GAME_STATE['drawn_card'] = None  

    if not deck:
        GAME_STATE['error'] = "Shuffle the deck first!"
        emit_state_update(broadcast=True)
        return

    total_cards_needed = num_players * 9
    if len(deck) < total_cards_needed:
        GAME_STATE['error'] = f"Not enough cards left! Need {total_cards_needed}, have {len(deck)}."
        emit_state_update(broadcast=True)
        return

    player_hands = {}
    player_order = []
    for i in range(num_players):
        name = f"Player {i+1}"
        player_hands[name] = []
        player_order.append(name)
    
    for round_num in range(3):
        for name in player_order:
            # 1. Store cards as hidden objects instead of raw strings
            three_cards = [{'value': deck.pop(), 'visible': False} for _ in range(3)]
            player_hands[name].extend(three_cards)

    GAME_STATE['deck'] = deck
    GAME_STATE['players'] = player_hands
    GAME_STATE['player_order'] = player_order
    GAME_STATE['current_player'] = player_order[0] if player_order else None
    emit_state_update(broadcast=True)

@socketio.on('draw_card')
def handle_draw(data):
    """Expects data format: {'player_name': 'Player X'} from the client side"""
    player_name = data.get('player_name')
    deck = GAME_STATE['deck']
    GAME_STATE['error'] = None

    # Enforce global turn authority matching
    if player_name != GAME_STATE['current_player']:
        GAME_STATE['error'] = f"It is not your turn, {player_name}! Wait for {GAME_STATE['current_player']}."
        emit_state_update(broadcast=True)
        return

    if GAME_STATE['drawn_card']:
        GAME_STATE['error'] = "Resolve or Pass the current drawn card first!"
        emit_state_update(broadcast=True)
        return

    if not deck:
        GAME_STATE['error'] = "The deck is completely empty! Reshuffle."
        emit_state_update(broadcast=True)
        return

    GAME_STATE['drawn_card'] = deck.pop()
    emit_state_update(broadcast=True)

@socketio.on('pass_card')
def handle_pass(data):
    """Expects data format: {'player_name': 'Player X'}"""
    player_name = data.get('player_name')
    GAME_STATE['error'] = None
    card_to_discard = GAME_STATE['drawn_card']

    if player_name != GAME_STATE['current_player']:
        GAME_STATE['error'] = f"It is not your turn, {player_name}!"
        emit_state_update(broadcast=True)
        return

    if not card_to_discard:
        GAME_STATE['error'] = "There is no active drawn card to pass!"
        emit_state_update(broadcast=True)
        return

    GAME_STATE['discard_pile'].append(card_to_discard)
    GAME_STATE['drawn_card'] = None  
    advance_turn()  # Turn passes on a successful move
    emit_state_update(broadcast=True)

@socketio.on('swap_card')
def handle_swap(data):
    GAME_STATE['error'] = None
    player_name = data.get('player_name')
    card_index = data.get('card_index')
    active_draw = GAME_STATE['drawn_card']

    if player_name != GAME_STATE['current_player']:
        GAME_STATE['error'] = f"It is not your turn, {player_name}!"
        emit_state_update(broadcast=True)
        return

    try:
        card_index = int(card_index)
        player_hand = GAME_STATE['players'][player_name]
        old_hand_card_obj = player_hand[card_index]
        
        # Extract the raw card string value for the discard pile
        card_to_discard = old_hand_card_obj['value']

        # SCENARIO A: A card was drawn from the main deck
        if active_draw:
            # 2. Replaced card goes to hand face up (visible=True)
            player_hand[card_index] = {'value': active_draw, 'visible': True}
            GAME_STATE['discard_pile'].append(card_to_discard)
            GAME_STATE['drawn_card'] = None 
            advance_turn()
            emit_state_update(broadcast=True)
            return

        # SCENARIO B: Swap with the top of the discard pile
        if not GAME_STATE['discard_pile']:
            GAME_STATE['error'] = "The discard pile is empty! You must draw from the deck."
            emit_state_update(broadcast=True)
            return

        top_discard_card = GAME_STATE['discard_pile'].pop()
        
        # 3. New card from discard pile is placed face up
        player_hand[card_index] = {'value': top_discard_card, 'visible': True}
        GAME_STATE['discard_pile'].append(card_to_discard)
        
        advance_turn()
        emit_state_update(broadcast=True)

    except (TypeError, ValueError, IndexError):
        GAME_STATE['error'] = "Invalid card selection attempt."
        emit_state_update(broadcast=True)
        
@socketio.on('change_player_name')
def handle_change_name(data):
    GAME_STATE['error'] = None
    old_name = data.get('old_name')
    new_name = str(data.get('new_name', '')).strip()

    # 1. Validation checks
    if not new_name:
        GAME_STATE['error'] = "Name cannot be left blank!"
        emit_state_update(broadcast=True)
        return

    if old_name not in GAME_STATE['players']:
        GAME_STATE['error'] = f"Could not find historical name record: {old_name}"
        emit_state_update(broadcast=True)
        return

    if new_name in GAME_STATE['players'] and old_name != new_name:
        GAME_STATE['error'] = f"The name '{new_name}' is already taken by another player!"
        emit_state_update(broadcast=True)
        return

    # 2. Perform dictionary key migration to preserve cards hand array
    player_hand_cards = GAME_STATE['players'].pop(old_name)
    GAME_STATE['players'][new_name] = player_hand_cards

    # 3. Update the global ordered array index tracker
    if old_name in GAME_STATE['player_order']:
        idx = GAME_STATE['player_order'].index(old_name)
        GAME_STATE['player_order'][idx] = new_name

    # 4. Correct active turn pointer references if it was that player's turn
    if GAME_STATE['current_player'] == old_name:
        GAME_STATE['current_player'] = new_name

    # 5. Broadcast changes out live to everyone
    emit_state_update(broadcast=True)
    
@socketio.on('reveal_card')
def handle_reveal(data):
    GAME_STATE['error'] = None
    acting_player = data.get('player_name')  # Who is clicking the button
    target_player = data.get('target_player')  # Whose hand is being targeted
    card_index = data.get('card_index')

    # Security check: You can only reveal cards in your own hand
    if acting_player != target_player:
        GAME_STATE['error'] = f"Security Violation: {acting_player}, you cannot reveal {target_player}'s cards!"
        emit_state_update(broadcast=True)
        return

    if acting_player not in GAME_STATE['players']:
        GAME_STATE['error'] = f"Invalid player profile: {acting_player}"
        emit_state_update(broadcast=True)
        return

    try:
        card_index = int(card_index)
        player_hand = GAME_STATE['players'][acting_player]
        card_obj = player_hand[card_index]

        # Flip the visibility status flag if it's currently face-down
        if not card_obj['visible']:
            card_obj['visible'] = True
            emit_state_update(broadcast=True)
        else:
            GAME_STATE['error'] = "That card is already revealed face-up!"
            emit_state_update(broadcast=True)

    except (TypeError, ValueError, IndexError):
        GAME_STATE['error'] = "Invalid card selection target."
        emit_state_update(broadcast=True)

def emit_state_update(broadcast=True):
    # Pass out current_player status to the board metrics channel
    emit('state_updated', {
        'deck_count': len(GAME_STATE['deck']),
        'players': GAME_STATE['players'],
        'drawn_card': GAME_STATE['drawn_card'],
        'discard_pile': GAME_STATE['discard_pile'],
        'current_player': GAME_STATE['current_player'],
        'error': GAME_STATE['error']
    }, broadcast=broadcast)

if __name__ == '__main__':
    socketio.run(app)
