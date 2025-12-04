"""
Test script to verify database functionality
Run this to make sure the database is working correctly
"""

import sys
import os

# Add project root to path before importing setup_path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from Server.Database import GameDatabase


def test_database():
    print("=" * 50)
    print("Testing Rock Paper Scissors Database")
    print("=" * 50)
    
    # Initialize database
    db = GameDatabase("test_rps.db")
    print("✓ Database initialized")
    
    # Add users
    alice_id = db.add_user("Alice")
    bob_id = db.add_user("Bob")
    print(f"✓ Added users - Alice (ID: {alice_id}), Bob (ID: {bob_id})")
    
    # Test adding same user again (should return existing ID)
    alice_id_2 = db.add_user("Alice")
    assert alice_id == alice_id_2, "User IDs should match for same user"
    print("✓ Duplicate user handling works")
    
    # Record some games
    db.record_game(alice_id, bob_id, "rock", "scissors", "player1_win")
    print("✓ Game 1 recorded: Alice (rock) vs Bob (scissors) - Alice wins")
    
    db.record_game(alice_id, bob_id, "paper", "rock", "player1_win")
    print("✓ Game 2 recorded: Alice (paper) vs Bob (rock) - Alice wins")
    
    db.record_game(alice_id, bob_id, "scissors", "scissors", "draw")
    print("✓ Game 3 recorded: Alice (scissors) vs Bob (scissors) - Draw")
    
    db.record_game(alice_id, bob_id, "rock", "paper", "player2_win")
    print("✓ Game 4 recorded: Alice (rock) vs Bob (paper) - Bob wins")
    
    # Get scores
    alice_wins, bob_wins, draws = db.get_score(alice_id, bob_id)
    print(f"\n✓ Score retrieved: Alice: {alice_wins}, Bob: {bob_wins}, Draws: {draws}")
    
    # Verify scores
    assert alice_wins == 2, f"Expected Alice to have 2 wins, got {alice_wins}"
    assert bob_wins == 1, f"Expected Bob to have 1 win, got {bob_wins}"
    assert draws == 1, f"Expected 1 draw, got {draws}"
    print("✓ Score calculation correct!")
    
    # Test get_user_name
    alice_name = db.get_user_name(alice_id)
    bob_name = db.get_user_name(bob_id)
    assert alice_name == "Alice", f"Expected 'Alice', got '{alice_name}'"
    assert bob_name == "Bob", f"Expected 'Bob', got '{bob_name}'"
    print(f"✓ User name retrieval works: {alice_name}, {bob_name}")
    
    print("\n" + "=" * 50)
    print("All tests passed! ✓")
    print("=" * 50)
    print("\nYou can safely delete 'test_rps.db' if you want.")

if __name__ == "__main__":
    test_database()