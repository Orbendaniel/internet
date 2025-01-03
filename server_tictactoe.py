import socket
import threading

# GLOBAL VARIABLES 
HOST = '127.0.0.1'  # Standard loopback IP address (localhost)
PORT = 5000  # Port to listen on (non-privileged ports are > 1023)
FORMAT = 'utf-8'  # Define the encoding format of messages from client-server
ADDR = (HOST, PORT)  # Creating a tuple of IP+PORT
PLAYER_MARKERS = ["X", "O", "Δ", "☆", "♠", "♣", "♥", "♦", "♪", "♫"] # Define player markers 
CLIENT_MARKERS = {}  # Maps client connections to their assigned markers

def start_server():
    # Step 1: Bind and start listening
    server_socket.bind(ADDR)
    print(f"[LISTENING] Server is listening on {HOST}:{PORT}")
    server_socket.listen()

    active_connections = 0  # Counter for active connections
    clients = []  # List to store connected clients
    
    # Step 2: Accept clients dynamically
    while True:
        connection, address = server_socket.accept()
        print(f"[NEW CONNECTION] {address} connected.")
        
        # Add client to active list
        clients.append(connection)
        active_connections += 1
        print(f"[ACTIVE CONNECTIONS] {active_connections}")
        
        # Step 3: Handle client in a new thread
        thread = threading.Thread(target=handle_client, args=(connection, address,active_connections,clients))
        thread.start()

def handle_client(connection, addr, active_connections,clients):
    print(f"[HANDLING CLIENT] {addr}")
    connected = True
    game_state = None  # Initialize game_state as None until 'start' is received

    # Assign a marker to the new client
    if connection not in CLIENT_MARKERS:
        available_markers = [marker for marker in PLAYER_MARKERS if marker not in CLIENT_MARKERS.values()]
        if available_markers:
            marker = available_markers[0]
            CLIENT_MARKERS[connection] = marker  # Assign marker

        else:
            print(f"[ERROR] No markers available for client {addr}")
            connection.send("[SERVER] No markers available, disconnecting.".encode(FORMAT))
            connection.close()
            return  # Close connection if no markers are available
    else:
            marker = CLIENT_MARKERS[connection]  # Retrieve existing marker

    # Send the assigned marker
    connection.send(marker.encode(FORMAT))  # Send the assigned marker
    print(f"[ASSIGN] Assigned marker '{CLIENT_MARKERS[connection]}' to client {addr}")

    try:
        while connected:
            # Step 1: Receive a move or command from the client
            msg = connection.recv(1024).decode(FORMAT)

            if not msg:
                print(f"[DISCONNECT] Empty message received. Closing connection to {addr}")
                break
            
            # Handle other messages (e.g., chat messages)
            print(f"[CHAT] {addr} says: {msg}")
            connection.send(f"[SERVER RESPONSE] Message received: {msg}".encode(FORMAT))

            # Step 2: Process the client's command
            if msg.lower() == 'quit':
                print(f"[DISCONNECT] {addr} disconnected.")
                connected = False
                active_connections -=1
                CLIENT_MARKERS.pop(connection, None)  # Remove the client's marker
                break

            if msg.lower() == 'start':
                print(f"[START] Client {addr} is starting the game...")

                num_players = len(clients)  # Use the length of the clients list
                board_size = 3 if num_players <= 2 else (num_players + 1) ** 2
                game_state = [["" for _ in range(board_size)] for _ in range(board_size)]
                # Send "game started" notification to all clients
                for client in clients:
                    try:
                        client.send("game started".encode(FORMAT))
                        print(f"[BROADCAST] Sent 'game started' message to client: {client}")
                    except Exception as e:
                        print(f"[ERROR] Failed to send 'game started' message to client: {e}")
                
                # Prepare the players list
                players = list(CLIENT_MARKERS.values())

                # Call update_game_data to set the initial state
                game_data = update_game_data(game_state, move=None, current_player=players[0], players=players)
                
                # Broadcast the initial game state
                broadcast_update(clients, game_data["board"], game_data["next_turn"], "ongoing", winner=None)
                continue  # Continue to the next iteration to wait for moves
            
            # Handle move commands (e.g., "1,2")
            elif ',' in msg:
                try:
                    move = tuple(map(int, msg.split(',')))  # Parse move as (row, col)
                    current_player = CLIENT_MARKERS[connection]

                    # Validate the move
                    is_valid, validation_msg = validate_move(game_state, move)
                    if not is_valid:
                        connection.send(f"[ERROR] Invalid move: {validation_msg}".encode(FORMAT))
                        continue

                    # Update the game state
                    players = list(CLIENT_MARKERS.values())
                    game_data = update_game_data(game_state, move, current_player, players)

                    # Broadcast the updated game state
                    broadcast_update(clients, game_data["board"], game_data["next_turn"], game_data["status"], game_data["winner"])

                    # Check for game end conditions
                    if game_data["status"] == "win":
                        print(f"[GAME END] Player '{game_data['winner']}' has won!")
                        break
                    elif game_data["status"] == "draw":
                        print("[GAME END] The game is a draw!")
                        break

                except ValueError:
                    connection.send("[ERROR] Invalid move format. Use 'row,col'.".encode(FORMAT))
                    continue



    except ConnectionResetError:
        print(f"[ERROR] Connection with {addr} reset unexpectedly.")
    finally:
        # Step 3: Clean up the connection
        connection.close()
        print(f"[CONNECTION CLOSED] {addr}")


def broadcast_update(clients, game_state, next_turn, status, winner=None):
    """
    Sends the updated game state to all players in the game.

    Args:
        clients (list): List of connected client sockets.
        game_state (list of list): The current game board.
        next_turn (str): The marker ("X", "O", etc.) of the next player.
        status (str): The current status of the game ("ongoing", "win", "draw").
        winner (str or None): The winning player, if any.
    """
    formatted_board = [[" " if cell == "" else cell for cell in row] for row in game_state]
    # Prepare the game data dictionary
    game_data = {
        "board": formatted_board,
        "next_turn": next_turn,
        "status": status,
        "winner": winner,
    }

    # Convert the game data to a string for transmission
    update_message = str(game_data)
    print(f"[DEBUG] Sending game data: {update_message}")  # Debugging


    # Send the game data to all connected clients
    for client in clients:
        try:
            client.send(update_message.encode(FORMAT))
            print(f"[BROADCAST] Sent game update to client: {client}")
        except Exception as e:
            print(f"[ERROR] Failed to send game update to client: {e}")

def update_game_data(game_state, move, current_player, players):
    """
    Updates the game state based on the player's move.

    Args:
        game_state (list of list): The current game board.
        move (tuple): The player's move as (row, col).
        current_player (str): The marker for the current player ("X", "O", etc.).
        players (list): List of player markers (e.g., ["X", "O", "Δ"]).

    Returns:
        dict: Updated game data including the board, next turn, status, and winner.
    """
    if move is None:
        next_turn = players[0]  # First player's turn at game start

    else:
        # Process the move
        row, col = move
        game_state[row][col] = current_player

        # Determine the next turn
        next_turn_index = (players.index(current_player) + 1) % len(players)
        next_turn = players[next_turn_index]
    
    # Prepare the game data
    game_data = {
        "board": game_state,
        "next_turn": next_turn, 
        #"status": status, 
        #"winner": winner,  
    }

    return game_data

def validate_move(game_state, move):
    """
    Validates a move sent by a client.

    Args:
        game_state (list of list): The current game board.
        move (tuple): The player's move as (row, col).

    Returns:
        bool: True if the move is valid, False otherwise.
        str: An error message if the move is invalid.
    """
    row, col = move
    board_size = len(game_state)

    # Check if the move is within bounds
    if not (0 <= row < board_size and 0 <= col < board_size):
        return False, "Move is out of bounds."

    # Check if the cell is empty
    if game_state[row][col] != "":
        return False, "Cell is already occupied."

    return True, "Move is valid."

def check_winner(game_state, players):
    """
    Checks the game board to determine if there's a winner or if the game is a draw.

    Args:
        game_state (list of list): The current game board.
        players (list): List of player markers (e.g., ["X", "O", "Δ"]).

    Returns:
        str: The status of the game ("win", "draw", "ongoing").
        str or None: The winning player, if any.
    """
    board_size = len(game_state)

    # Check rows and columns for a winner
    for i in range(board_size):
        # Check row
        if all(cell == game_state[i][0] and cell != "" for cell in game_state[i]):
            return "win", game_state[i][0]
        # Check column
        if all(row[i] == game_state[0][i] and row[i] != "" for row in game_state):
            return "win", game_state[0][i]

    # Check diagonals for a winner
    if all(game_state[i][i] == game_state[0][0] and game_state[i][i] != "" for i in range(board_size)):
        return "win", game_state[0][0]
    if all(game_state[i][board_size - i - 1] == game_state[0][board_size - 1] and game_state[i][board_size - i - 1] != "" for i in range(board_size)):
        return "win", game_state[0][board_size - 1]

    # Check for a draw (no empty cells)
    if all(cell != "" for row in game_state for cell in row):
        return "draw", None

    return "ongoing", None


# Main
if __name__ == '__main__':
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # Opening Server socket
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow address reuse
    print("[STARTING] server is starting...")
    start_server()