import socket
import threading
import json
import sys
import os

# Add project root to path before importing setup_path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from Database import GameDatabase

class RPSServer:
    def __init__(self, host: str = 'localhost', port: int = 5555):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = []
        self.player_names = {}
        self.player_ids = {}
        self.choices = {}
        self.db = GameDatabase()
        self.game_in_progress = False
        self.lock = threading.Lock()
        self.game_ready_notified = False
        
    def start(self):
        """Start the server and listen for connections"""
        try:
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(2)
            print(f"Server started on {self.host}:{self.port}")
            print("Waiting for 2 players to connect...")
            
            while True:
                try:
                    # Check for empty slots
                    active_clients = sum(1 for c in self.clients if c is not None)
                    
                    if active_clients < 2:
                        client_socket, address = self.server_socket.accept()
                        print(f"Client connected from {address}")
                        
                        # Find an empty slot or add new one
                        slot_found = False
                        for i in range(len(self.clients)):
                            if self.clients[i] is None:
                                self.clients[i] = client_socket
                                player_num = i
                                slot_found = True
                                break
                        
                        if not slot_found:
                            self.clients.append(client_socket)
                            player_num = len(self.clients) - 1
                        
                        # Start a thread to handle this client
                        client_thread = threading.Thread(
                            target=self.handle_client, 
                            args=(client_socket, player_num)
                        )
                        client_thread.daemon = True
                        client_thread.start()
                        
                        active_clients = sum(1 for c in self.clients if c is not None)
                        if active_clients == 2:
                            print("Both players connected! Game can begin.")
                    else:
                        # Both slots filled, wait a bit before checking again
                        import time
                        time.sleep(0.1)
                        
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
    
    def handle_client(self, client_socket: socket.socket, player_num: int):
        """Handle communication with a single client"""
        try:
            # First, receive the player's name
            data = client_socket.recv(1024).decode('utf-8')
            if not data:
                return
                
            message = json.loads(data)
            
            if message['type'] == 'register':
                player_name = message['name']
                self.player_names[player_num] = player_name
                
                # Add user to database
                user_id = self.db.add_user(player_name)
                self.player_ids[player_num] = user_id
                
                print(f"Player {player_num + 1} registered as: {player_name}")
                
                # Send confirmation
                response = {
                    'type': 'registered',
                    'player_num': player_num + 1,
                    'message': f'Welcome {player_name}! You are Player {player_num + 1}'
                }
                client_socket.send(json.dumps(response).encode('utf-8'))
                
                # Wait for both players to be ready
                while len(self.player_names) < 2:
                    # Check if client disconnected while waiting
                    if player_num >= len(self.clients) or self.clients[player_num] is None:
                        return
                    import time
                    time.sleep(0.1)
                
                # When both players are registered, notify BOTH players
                if len(self.player_names) == 2:
                    self.notify_both_players_ready()
            
            # Main game loop
            while True:
                data = client_socket.recv(1024).decode('utf-8')
                if not data:
                    # Client disconnected
                    break
                
                message = json.loads(data)
                
                if message['type'] == 'choice':
                    self.handle_choice(player_num, message['choice'])
                    
        except (ConnectionError, OSError, json.JSONDecodeError) as e:
            print(f"Client {player_num} disconnected: {e}")
        except Exception as e:
            print(f"Error handling client {player_num}: {e}")
        finally:
            # Handle client disconnection
            self.handle_client_disconnect(player_num)
            try:
                client_socket.close()
            except:
                pass
    
    def notify_both_players_ready(self):
        """Notify both players that the game is ready"""
        with self.lock:
            # Only notify once when both players are ready
            if len(self.player_names) != 2 or self.game_ready_notified:
                return
            
            self.game_ready_notified = True
            
            # Get initial scores from database
            if 0 in self.player_ids and 1 in self.player_ids:
                p1_wins, p2_wins, draws = self.db.get_score(
                    self.player_ids[0],
                    self.player_ids[1]
                )
            else:
                p1_wins, p2_wins, draws = 0, 0, 0
            
            # Send game_ready to both players with initial scores
            for player_num in [0, 1]:
                if (player_num < len(self.clients) and 
                    self.clients[player_num] is not None and 
                    player_num in self.player_names):
                    other_player = 1 - player_num
                    if other_player in self.player_names:
                        opponent_name = self.player_names[other_player]
                        # Calculate scores from this player's perspective
                        your_score = p1_wins if player_num == 0 else p2_wins
                        opponent_score = p2_wins if player_num == 0 else p1_wins
                        
                        ready_msg = {
                            'type': 'game_ready',
                            'opponent': opponent_name,
                            'your_score': your_score,
                            'opponent_score': opponent_score,
                            'draws': draws
                        }
                        try:
                            self.clients[player_num].send(json.dumps(ready_msg).encode('utf-8'))
                            print(f"Sent game_ready to Player {player_num + 1} ({self.player_names[player_num]})")
                            print(f"  Initial scores - {self.player_names[player_num]}: {your_score}, {opponent_name}: {opponent_score}, Draws: {draws}")
                        except Exception as e:
                            print(f"Error sending game_ready to player {player_num}: {e}")
    
    def handle_client_disconnect(self, player_num: int):
        """Handle when a client disconnects"""
        with self.lock:
            # Check if client was registered
            if player_num not in self.player_names:
                # Still mark the slot as available
                if player_num < len(self.clients):
                    self.clients[player_num] = None
                return
            
            player_name = self.player_names.get(player_num, 'Unknown')
            print(f"Player {player_num + 1} ({player_name}) disconnected")
            
            # Notify the other client if it exists and is connected
            other_player_num = 1 - player_num
            if (other_player_num < len(self.clients) and 
                self.clients[other_player_num] is not None and 
                other_player_num in self.player_names):
                try:
                    disconnect_msg = {
                        'type': 'opponent_disconnected',
                        'message': 'Your opponent has left. Waiting for another player...'
                    }
                    self.clients[other_player_num].send(json.dumps(disconnect_msg).encode('utf-8'))
                except Exception as e:
                    print(f"Error notifying remaining client: {e}")
            
            # Remove disconnected client from lists
            if player_num < len(self.clients):
                try:
                    if self.clients[player_num] is not None:
                        self.clients[player_num].close()
                except:
                    pass
                self.clients[player_num] = None
            
            # Remove player data
            if player_num in self.player_names:
                del self.player_names[player_num]
            if player_num in self.player_ids:
                del self.player_ids[player_num]
            if player_num in self.choices:
                del self.choices[player_num]
            
            # Reset game state
            self.choices.clear()
            self.game_ready_notified = False  # Allow re-notification when new player connects
            
            print(f"Waiting for a new player to replace Player {player_num + 1}...")
    
    def handle_choice(self, player_num: int, choice: str):
        """Handle a player's choice and determine winner if both have chosen"""
        with self.lock:
            # Check if both clients are still connected
            if player_num >= len(self.clients) or self.clients[player_num] is None:
                return
            if 1 - player_num >= len(self.clients) or self.clients[1 - player_num] is None:
                return
            
            self.choices[player_num] = choice
            print(f"Player {player_num + 1} chose: {choice}")
            
            # Notify this player that their choice was received
            try:
                response = {
                    'type': 'choice_received',
                    'message': 'Waiting for opponent...'
                }
                self.clients[player_num].send(json.dumps(response).encode('utf-8'))
            except Exception as e:
                print(f"Error sending choice confirmation: {e}")
                return
            
            # Check if both players have made their choices
            if len(self.choices) == 2:
                self.determine_winner()
    
    def determine_winner(self):
        """Determine the winner and send results to both players"""
        choice1 = self.choices[0]
        choice2 = self.choices[1]
        
        # Determine winner
        if choice1 == choice2:
            result = 'draw'
            winner_text = "It's a draw!"
        elif (choice1 == 'rock' and choice2 == 'scissors') or \
             (choice1 == 'scissors' and choice2 == 'paper') or \
             (choice1 == 'paper' and choice2 == 'rock'):
            result = 'player1_win'
            winner_text = f"{self.player_names[0]} wins!"
        else:
            result = 'player2_win'
            winner_text = f"{self.player_names[1]} wins!"
        
        # Record game in database
        self.db.record_game(
            self.player_ids[0],
            self.player_ids[1],
            choice1,
            choice2,
            result
        )
        
        # Get updated scores
        p1_wins, p2_wins, draws = self.db.get_score(
            self.player_ids[0],
            self.player_ids[1]
        )
        
        # Send results to both players
        for i in range(2):
            if i >= len(self.clients) or self.clients[i] is None:
                continue
            opponent_num = 1 - i
            result_msg = {
                'type': 'result',
                'your_choice': self.choices[i],
                'opponent_choice': self.choices[opponent_num],
                'winner': winner_text,
                'your_name': self.player_names[i],
                'opponent_name': self.player_names[opponent_num],
                'your_score': p1_wins if i == 0 else p2_wins,
                'opponent_score': p2_wins if i == 0 else p1_wins,
                'draws': draws
            }
            try:
                self.clients[i].send(json.dumps(result_msg).encode('utf-8'))
            except Exception as e:
                print(f"Error sending result to player {i}: {e}")
        
        # Clear choices for next round
        self.choices.clear()
        print(f"Game result: {winner_text}")
        print(f"Score - {self.player_names[0]}: {p1_wins}, {self.player_names[1]}: {p2_wins}, Draws: {draws}")
    
    def shutdown(self):
        """Clean up resources and close all connections"""
        print("Closing client connections...")
        for client in self.clients:
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