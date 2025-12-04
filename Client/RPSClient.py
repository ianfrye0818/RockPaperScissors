import socket
import threading
import json
import tkinter as tk
from tkinter import messagebox, simpledialog

class RPSClient:
    def __init__(self, host: str = 'localhost', port: int = 5555):
        self.host = host
        self.port = port
        self.client_socket = None
        self.player_name = ""
        self.opponent_name = ""
        self.game_ready = False
        
        # Create GUI
        self.root = tk.Tk()
        self.root.title("Rock Paper Scissors")
        self.root.geometry("500x600")
        self.root.resizable(False, False)
        
        self.setup_gui()
        
    def setup_gui(self):
        """Set up the GUI elements"""
        # Title
        title_label = tk.Label(
            self.root, 
            text="Rock Paper Scissors", 
            font=("Arial", 24, "bold"),
            pady=20
        )
        title_label.pack()
        
        # Player info frame
        info_frame = tk.Frame(self.root)
        info_frame.pack(pady=10)
        
        self.player_label = tk.Label(
            info_frame,
            text="Not connected",
            font=("Arial", 12)
        )
        self.player_label.pack()
        
        self.opponent_label = tk.Label(
            info_frame,
            text="Waiting for opponent...",
            font=("Arial", 12),
            fg="gray"
        )
        self.opponent_label.pack()
        
        # Status label
        self.status_label = tk.Label(
            self.root,
            text="Click Connect to start",
            font=("Arial", 14),
            pady=20,
            fg="blue"
        )
        self.status_label.pack()
        
        # Choice buttons frame
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=20)
        
        self.rock_btn = tk.Button(
            button_frame,
            text="🪨\nRock",
            font=("Arial", 16),
            width=10,
            height=4,
            command=lambda: self.make_choice('rock'),
            state=tk.DISABLED
        )
        self.rock_btn.grid(row=0, column=0, padx=10)
        
        self.paper_btn = tk.Button(
            button_frame,
            text="📄\nPaper",
            font=("Arial", 16),
            width=10,
            height=4,
            command=lambda: self.make_choice('paper'),
            state=tk.DISABLED
        )
        self.paper_btn.grid(row=0, column=1, padx=10)
        
        self.scissors_btn = tk.Button(
            button_frame,
            text="✂️\nScissors",
            font=("Arial", 16),
            width=10,
            height=4,
            command=lambda: self.make_choice('scissors'),
            state=tk.DISABLED
        )
        self.scissors_btn.grid(row=0, column=2, padx=10)
        
        # Result display
        result_frame = tk.Frame(self.root, relief=tk.SUNKEN, borderwidth=2)
        result_frame.pack(pady=20, padx=20, fill=tk.BOTH, expand=True)
        
        tk.Label(
            result_frame,
            text="Last Round",
            font=("Arial", 14, "bold")
        ).pack(pady=5)
        
        self.result_text = tk.Text(
            result_frame,
            height=8,
            width=50,
            font=("Arial", 11),
            state=tk.DISABLED
        )
        self.result_text.pack(padx=10, pady=5)
        
        # Score display
        score_frame = tk.Frame(self.root)
        score_frame.pack(pady=10)
        
        self.score_label = tk.Label(
            score_frame,
            text="Score: 0 - 0 (Draws: 0)",
            font=("Arial", 12, "bold")
        )
        self.score_label.pack()
        
        # Connect button
        self.connect_btn = tk.Button(
            self.root,
            text="Connect to Server",
            font=("Arial", 12),
            command=self.connect_to_server,
            bg="green",
            fg="white",
            padx=20,
            pady=10
        )
        self.connect_btn.pack(pady=10)
        
    def connect_to_server(self):
        """Connect to the game server"""
        # Ask for player name
        self.player_name = simpledialog.askstring(
            "Player Name",
            "Enter your name:",
            parent=self.root
        )
        
        if not self.player_name:
            messagebox.showerror("Error", "Name is required!")
            return
        
        try:
            # Connect to server
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))
            
            # Send registration
            register_msg = {
                'type': 'register',
                'name': self.player_name
            }
            self.client_socket.send(json.dumps(register_msg).encode('utf-8'))
            
            # Disable connect button
            self.connect_btn.config(state=tk.DISABLED)
            self.status_label.config(text="Connected! Waiting for opponent...")
            
            # Start listening thread
            listen_thread = threading.Thread(target=self.listen_to_server)
            listen_thread.daemon = True
            listen_thread.start()
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to server:\n{e}")
            self.connect_btn.config(state=tk.NORMAL)
    
    def listen_to_server(self):
        """Listen for messages from the server"""
        try:
            while True:
                data = self.client_socket.recv(4096).decode('utf-8')
                if not data:
                    break
                
                message = json.loads(data)
                self.handle_server_message(message)
                
        except Exception as e:
            print(f"Error listening to server: {e}")
            self.root.after(0, self.connection_lost)
    
    def handle_server_message(self, message: dict):
        """Handle different types of messages from server"""
        msg_type = message['type']
        
        if msg_type == 'registered':
            self.root.after(0, self.update_player_info, message)
            
        elif msg_type == 'game_ready':
            self.opponent_name = message['opponent']
            self.game_ready = True
            # Extract initial scores if provided
            initial_scores = {
                'your_score': message.get('your_score', 0),
                'opponent_score': message.get('opponent_score', 0),
                'draws': message.get('draws', 0)
            }
            self.root.after(0, self.enable_game, initial_scores)
            
        elif msg_type == 'opponent_disconnected':
            self.game_ready = False
            self.root.after(0, self.handle_opponent_disconnected, message['message'])
            
        elif msg_type == 'choice_received':
            self.root.after(0, self.update_status, message['message'])
            
        elif msg_type == 'result':
            self.root.after(0, self.display_result, message)
    
    def update_player_info(self, message: dict):
        """Update player info labels"""
        self.player_label.config(text=f"You: {self.player_name} (Player {message['player_num']})")
        self.status_label.config(text=message['message'])
    
    def enable_game(self, initial_scores=None):
        """Enable the game buttons when both players are ready"""
        self.opponent_label.config(
            text=f"Opponent: {self.opponent_name}",
            fg="black"
        )
        self.status_label.config(text="Make your choice!")
        
        # Update score display with initial scores if provided
        if initial_scores:
            your_score = initial_scores.get('your_score', 0)
            opponent_score = initial_scores.get('opponent_score', 0)
            draws = initial_scores.get('draws', 0)
            self.score_label.config(
                text=f"Score: {your_score} - {opponent_score} (Draws: {draws})"
            )
        
        self.rock_btn.config(state=tk.NORMAL)
        self.paper_btn.config(state=tk.NORMAL)
        self.scissors_btn.config(state=tk.NORMAL)
    
    def handle_opponent_disconnected(self, message: str):
        """Handle when opponent disconnects"""
        self.game_ready = False
        self.opponent_name = ""
        self.opponent_label.config(
            text="Waiting for opponent...",
            fg="gray"
        )
        self.status_label.config(text=message, fg="orange")
        # Disable game buttons
        self.rock_btn.config(state=tk.DISABLED)
        self.paper_btn.config(state=tk.DISABLED)
        self.scissors_btn.config(state=tk.DISABLED)
    
    def make_choice(self, choice: str):
        """Send player's choice to server"""
        if not self.game_ready:
            return
        
        # Disable buttons
        self.rock_btn.config(state=tk.DISABLED)
        self.paper_btn.config(state=tk.DISABLED)
        self.scissors_btn.config(state=tk.DISABLED)
        
        # Send choice to server
        choice_msg = {
            'type': 'choice',
            'choice': choice
        }
        self.client_socket.send(json.dumps(choice_msg).encode('utf-8'))
        
        self.status_label.config(text=f"You chose {choice}. Waiting for opponent...")
    
    def update_status(self, status: str):
        """Update status label"""
        self.status_label.config(text=status)
    
    def display_result(self, result: dict):
        """Display the game result"""
        # Update result text
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        
        result_display = f"""
{result['your_name']} chose: {result['your_choice'].upper()}
{result['opponent_name']} chose: {result['opponent_choice'].upper()}

{result['winner']}
        """
        
        self.result_text.insert(1.0, result_display)
        self.result_text.config(state=tk.DISABLED)
        
        # Update score
        self.score_label.config(
            text=f"Score: {result['your_score']} - {result['opponent_score']} (Draws: {result['draws']})"
        )
        
        # Update status
        self.status_label.config(text="Make your choice for next round!")
        
        # Re-enable buttons
        self.rock_btn.config(state=tk.NORMAL)
        self.paper_btn.config(state=tk.NORMAL)
        self.scissors_btn.config(state=tk.NORMAL)
    
    def connection_lost(self):
        """Handle lost connection"""
        messagebox.showerror("Connection Lost", "Connection to server was lost!")
        self.root.quit()
    
    def run(self):
        """Run the GUI"""
        self.root.mainloop()
        
        # Clean up
        if self.client_socket:
            self.client_socket.close()

if __name__ == "__main__":
    import sys
    
    # Allow passing port as argument for testing multiple clients
    port = 5555
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    
    client = RPSClient(port=port)
    client.run()