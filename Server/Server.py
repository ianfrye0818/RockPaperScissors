import socket
import threading
import json
import sys
import os
import uuid

# Add project root to path before importing setup_path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from Database import GameDatabase

class Room:
    def __init__(self, room_id: str):
        self.room_id = room_id
        self.clients = [None, None]
        self.player_names = {}
        self.player_ids = {}
        self.choices = {}
        self.lock = threading.Lock()
        self.game_ready = False

    def is_full(self):
        """Check if room has 2 players"""
        return self.clients[0] is not None and self.clients[1] is not None

    def is_empty(self):
        """Check if room has no players"""
        return self.clients[0] is None and self.clients[1] is None

    def get_available_slot(self):
        """Get the next available slot index, or None if full"""
        if self.clients[0] is None:
            return 0
        elif self.clients[1] is None:
            return 1
        return None

    def add_client(self, client_socket):
        """Add a client to the room, return player_num or None if full"""
        slot = self.get_available_slot()
        if slot is not None:
            self.clients[slot] = client_socket
            return slot
        return None

    def remove_client(self, player_num: int):
        """Remove a client from the room"""
        if 0 <= player_num < len(self.clients):
            self.clients[player_num] = None
            if player_num in self.player_names:
                del self.player_names[player_num]
            if player_num in self.player_ids:
                del self.player_ids[player_num]
            if player_num in self.choices:
                del self.choices[player_num]

class RPSServer:
    def __init__(self, host: str = 'localhost', port: int = 5555):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.rooms = {}
        self.client_to_room = {}
        self.db = GameDatabase()
        self.lock = threading.Lock()
        
    def start(self):
        """Start the server and listen for connections"""
        try:
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen()
            print(f"Server started on {self.host}:{self.port}")
            print("Waiting for players to connect...")

            while True:
                try:
                    client_socket, address = self.server_socket.accept()
                    print(f"Client connected from {address}")

                    # Find or create a room for this client
                    room_id, player_num = self.assign_client_to_room(client_socket)

                    print(f"Client assigned to room {room_id} as Player {player_num + 1}")

                    # Start a thread to handle this client
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, room_id, player_num)
                    )
                    client_thread.daemon = True
                    client_thread.start()

                except Exception as e:
                    # Re-raise KeyboardInterrupt to be handled by outer try-except
                    if isinstance(e, KeyboardInterrupt):
                        raise
                    print(f"Error accepting connection: {e}")
                    break
        except KeyboardInterrupt:
            print("\nServer shutdown requested...")
            self.shutdown()
            raise

    def assign_client_to_room(self, client_socket):
        """Assign a client to an available room or create a new one"""
        with self.lock:
            # Find an existing room with space
            for room_id, room in self.rooms.items():
                if not room.is_full():
                    player_num = room.add_client(client_socket)
                    if player_num is not None:
                        self.client_to_room[client_socket] = room_id
                        if room.is_full():
                            print(f"Room {room_id} is now full. Game can begin!")
                        return room_id, player_num

            # No available room, create a new one
            room_id = str(uuid.uuid4())[:8]
            new_room = Room(room_id)
            player_num = new_room.add_client(client_socket)
            self.rooms[room_id] = new_room
            self.client_to_room[client_socket] = room_id
            print(f"Created new room {room_id}")
            return room_id, player_num

    def handle_client(self, client_socket: socket.socket, room_id: str, player_num: int):
        """Handle communication with a single client"""
        room = self.rooms.get(room_id)
        if not room:
            return

        try:
            # First, receive the player's name
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                return

            message = json.loads(data)

            if message['type'] == 'register':
                player_name = message['name']
                room.player_names[player_num] = player_name

                # Add user to database
                user_id = self.db.add_user(player_name)
                room.player_ids[player_num] = user_id

                print(f"Room {room_id}: Player {player_num + 1} registered as: {player_name}")

                # Send confirmation with room_id
                response = {
                    'type': 'registered',
                    'player_num': player_num + 1,
                    'room_id': room_id,
                    'message': f'Welcome {player_name}! You are Player {player_num + 1} in Room {room_id}'
                }
                client_socket.send(json.dumps(response).encode('utf-8'))

                # Wait for both players to be ready
                while len(room.player_names) < 2:
                    # Check if client disconnected while waiting
                    if room.clients[player_num] is None:
                        return
                    import time
                    time.sleep(0.1)

                # When both players are registered, notify BOTH players
                if len(room.player_names) == 2 and not room.game_ready:
                    self.notify_both_players_ready(room_id)

            # Main game loop
            while True:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    # Client disconnected
                    break

                message = json.loads(data)

                if message['type'] == 'choice':
                    self.handle_choice(room_id, player_num, message['choice'])

        except (ConnectionError, OSError, json.JSONDecodeError) as e:
            print(f"Room {room_id}: Client {player_num} disconnected: {e}")
        except Exception as e:
            print(f"Room {room_id}: Error handling client {player_num}: {e}")
        finally:
            # Handle client disconnection
            self.handle_client_disconnect(room_id, player_num)
            try:
                client_socket.close()
            except:
                pass
    
    def notify_both_players_ready(self, room_id: str):
        """Notify both players in a room that the game is ready"""
        room = self.rooms.get(room_id)
        if not room:
            return

        with room.lock:
            # Only notify once when both players are ready
            if len(room.player_names) != 2 or room.game_ready:
                return

            room.game_ready = True

            # Get initial scores from database
            if 0 in room.player_ids and 1 in room.player_ids:
                p1_wins, p2_wins, draws = self.db.get_score(
                    room.player_ids[0],
                    room.player_ids[1]
                )
            else:
                p1_wins, p2_wins, draws = 0, 0, 0

            # Send game_ready to both players with initial scores
            for player_num in [0, 1]:
                if (room.clients[player_num] is not None and
                    player_num in room.player_names):
                    other_player = 1 - player_num
                    if other_player in room.player_names:
                        opponent_name = room.player_names[other_player]
                        # Calculate scores from this player's perspective
                        your_score = p1_wins if player_num == 0 else p2_wins
                        opponent_score = p2_wins if player_num == 0 else p1_wins

                        ready_msg = {
                            'type': 'game_ready',
                            'opponent': opponent_name,
                            'room_id': room_id,
                            'your_score': your_score,
                            'opponent_score': opponent_score,
                            'draws': draws
                        }
                        try:
                            room.clients[player_num].send(json.dumps(ready_msg).encode('utf-8'))
                            print(f"Room {room_id}: Sent game_ready to Player {player_num + 1} ({room.player_names[player_num]})")
                            print(f"  Initial scores - {room.player_names[player_num]}: {your_score}, {opponent_name}: {opponent_score}, Draws: {draws}")
                        except Exception as e:
                            print(f"Room {room_id}: Error sending game_ready to player {player_num}: {e}")
    
    def handle_client_disconnect(self, room_id: str, player_num: int):
        """Handle when a client disconnects"""
        room = self.rooms.get(room_id)
        if not room:
            return

        with room.lock:
            # Check if client was registered
            if player_num not in room.player_names:
                # Still mark the slot as available
                room.remove_client(player_num)
                return

            player_name = room.player_names.get(player_num, 'Unknown')
            print(f"Room {room_id}: Player {player_num + 1} ({player_name}) disconnected")

            # Notify the other client if it exists and is connected
            other_player_num = 1 - player_num
            if (room.clients[other_player_num] is not None and
                other_player_num in room.player_names):
                try:
                    disconnect_msg = {
                        'type': 'opponent_disconnected',
                        'message': 'Your opponent has left. Waiting for another player...'
                    }
                    room.clients[other_player_num].send(json.dumps(disconnect_msg).encode('utf-8'))
                except Exception as e:
                    print(f"Room {room_id}: Error notifying remaining client: {e}")

            # Remove disconnected client from room
            client_socket = room.clients[player_num]
            if client_socket:
                try:
                    client_socket.close()
                except:
                    pass
                if client_socket in self.client_to_room:
                    del self.client_to_room[client_socket]

            room.remove_client(player_num)

            # Reset game state
            room.choices.clear()
            room.game_ready = False

            # Clean up empty rooms
            if room.is_empty():
                print(f"Room {room_id} is now empty, removing it")
                del self.rooms[room_id]
            else:
                print(f"Room {room_id}: Waiting for a new player to replace Player {player_num + 1}...")
    
    def handle_choice(self, room_id: str, player_num: int, choice: str):
        """Handle a player's choice and determine winner if both have chosen"""
        room = self.rooms.get(room_id)
        if not room:
            return

        with room.lock:
            # Check if both clients are still connected
            if room.clients[player_num] is None:
                return
            if room.clients[1 - player_num] is None:
                return

            room.choices[player_num] = choice
            print(f"Room {room_id}: Player {player_num + 1} chose: {choice}")

            # Notify this player that their choice was received
            try:
                response = {
                    'type': 'choice_received',
                    'message': 'Waiting for opponent...'
                }
                room.clients[player_num].send(json.dumps(response).encode('utf-8'))
            except Exception as e:
                print(f"Room {room_id}: Error sending choice confirmation: {e}")
                return

            # Check if both players have made their choices
            if len(room.choices) == 2:
                self.determine_winner(room_id)
    
    def determine_winner(self, room_id: str):
        """Determine the winner and send results to both players"""
        room = self.rooms.get(room_id)
        if not room:
            return

        choice1 = room.choices[0]
        choice2 = room.choices[1]

        # Determine winner
        if choice1 == choice2:
            result = 'draw'
            winner_text = "It's a draw!"
        elif (choice1 == 'rock' and choice2 == 'scissors') or \
             (choice1 == 'scissors' and choice2 == 'paper') or \
             (choice1 == 'paper' and choice2 == 'rock'):
            result = 'player1_win'
            winner_text = f"{room.player_names[0]} wins!"
        else:
            result = 'player2_win'
            winner_text = f"{room.player_names[1]} wins!"

        # Record game in database
        self.db.record_game(
            room.player_ids[0],
            room.player_ids[1],
            choice1,
            choice2,
            result
        )

        # Get updated scores
        p1_wins, p2_wins, draws = self.db.get_score(
            room.player_ids[0],
            room.player_ids[1]
        )

        # Send results to both players
        for i in range(2):
            if room.clients[i] is None:
                continue
            opponent_num = 1 - i
            result_msg = {
                'type': 'result',
                'your_choice': room.choices[i],
                'opponent_choice': room.choices[opponent_num],
                'winner': winner_text,
                'your_name': room.player_names[i],
                'opponent_name': room.player_names[opponent_num],
                'your_score': p1_wins if i == 0 else p2_wins,
                'opponent_score': p2_wins if i == 0 else p1_wins,
                'draws': draws
            }
            try:
                room.clients[i].send(json.dumps(result_msg).encode('utf-8'))
            except Exception as e:
                print(f"Room {room_id}: Error sending result to player {i}: {e}")

        # Clear choices for next round
        room.choices.clear()
        print(f"Room {room_id}: Game result: {winner_text}")
        print(f"Room {room_id}: Score - {room.player_names[0]}: {p1_wins}, {room.player_names[1]}: {p2_wins}, Draws: {draws}")
    
    def shutdown(self):
        """Clean up resources and close all connections"""
        print("Closing client connections...")
        for room in self.rooms.values():
            for client in room.clients:
                if client:
                    try:
                        client.close()
                    except Exception as e:
                        print(f"Error closing client: {e}")

        print("Closing server socket...")
        try:
            self.server_socket.close()
        except Exception as e:
            print(f"Error closing server socket: {e}")

        print("Server shutdown complete.")

if __name__ == "__main__":
    server = RPSServer()
    try:
        server.start()
        
        # Keep server running
        try:
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nServer shutdown requested...")
            server.shutdown()
    except KeyboardInterrupt:
        # Already handled in start() or here as fallback
        print("\nServer shutdown requested...")
        server.shutdown()
    except OSError as e:
        if e.errno == 48:  # Address already in use
            print(f"\nERROR: Port {server.port} is already in use!")
            print("Please kill the existing process or use a different port.")
            print("You can find and kill the process with: lsof -ti:5555 | xargs kill -9")
        else:
            print(f"\nServer error: {e}")
        server.shutdown()
        sys.exit(1)
    except Exception as e:
        print(f"\nServer error: {e}")
        server.shutdown()
        sys.exit(1)