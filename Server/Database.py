import sqlite3
from typing import Optional, Tuple

class GameDatabase:
    def __init__(self, db_name: str = "rps_game.db"):
        self.db_name = db_name
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)
        
        # Create games table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player1_id INTEGER NOT NULL,
                player2_id INTEGER NOT NULL,
                player1_choice TEXT NOT NULL,
                player2_choice TEXT NOT NULL,
                game_status TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player1_id) REFERENCES users(id),
                FOREIGN KEY (player2_id) REFERENCES users(id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_user(self, name: str) -> Optional[int]:
        """Add a new user or get existing user ID"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        try:
            cursor.execute("INSERT INTO users (name) VALUES (?)", (name,))
            conn.commit()
            user_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            # User already exists, get their ID
            cursor.execute("SELECT id FROM users WHERE name = ?", (name,))
            user_id = cursor.fetchone()[0]
        
        conn.close()
        return user_id
    
    def record_game(self, player1_id: int, player2_id: int, 
                    player1_choice: str, player2_choice: str, 
                    game_status: str):
        """Record a game result"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO games (player1_id, player2_id, player1_choice, 
                             player2_choice, game_status)
            VALUES (?, ?, ?, ?, ?)
        """, (player1_id, player2_id, player1_choice, player2_choice, game_status))
        
        conn.commit()
        conn.close()
    
    def get_score(self, player1_id: int, player2_id: int) -> Tuple[int, int, int]:
        """Get win/loss/draw counts between two players"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Count player1 wins
        cursor.execute("""
            SELECT COUNT(*) FROM games 
            WHERE ((player1_id = ? AND player2_id = ?) OR 
                   (player1_id = ? AND player2_id = ?))
            AND game_status = 'player1_win'
        """, (player1_id, player2_id, player2_id, player1_id))
        player1_wins = cursor.fetchone()[0]
        
        # Count player2 wins
        cursor.execute("""
            SELECT COUNT(*) FROM games 
            WHERE ((player1_id = ? AND player2_id = ?) OR 
                   (player1_id = ? AND player2_id = ?))
            AND game_status = 'player2_win'
        """, (player1_id, player2_id, player2_id, player1_id))
        player2_wins = cursor.fetchone()[0]
        
        # Count draws
        cursor.execute("""
            SELECT COUNT(*) FROM games 
            WHERE ((player1_id = ? AND player2_id = ?) OR 
                   (player1_id = ? AND player2_id = ?))
            AND game_status = 'draw'
        """, (player1_id, player2_id, player2_id, player1_id))
        draws = cursor.fetchone()[0]
        
        conn.close()
        return (player1_wins, player2_wins, draws)
    
    def get_user_name(self, user_id: int) -> Optional[str]:
        """Get username by ID"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        
        conn.close()
        return result[0] if result else None