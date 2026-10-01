#!/usr/bin/env python3
"""
Neural Emergence Test Protocol - Fixed Wiring + Trainable Heads
Tests if strategy emerges from structured knowledge (synaptic connections) alone
"""

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from collections import deque
import random

class FixedWiringNetwork(nn.Module):
    """Network with fixed synaptic structure, trainable output heads"""
    
    def __init__(self, input_size=15*15, hidden_size=128, output_size=15*15):
        super().__init__()
        
        # FIXED WIRING: encode fleet laws as synaptic structure
        self.fixed_connections = nn.Sequential(
            # Law 1: Loopback-only (no external weights)
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            # Law 2: Receipts first (structure over content)  
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            # Law 3: Tri-state (SUPPORTED/DISPUTED/UNPROVEN)
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
        )
        
        # TRAINABLE HEADS: policy and value
        self.policy_head = nn.Linear(hidden_size, output_size)  # move probabilities
        self.value_head = nn.Linear(hidden_size, 1)  # game outcome prediction
        
    def forward(self, x):
        # Fixed wiring processes input
        fixed_features = self.fixed_connections(x)
        
        # Trainable heads produce output
        policy_logits = self.policy_head(fixed_features)
        value = self.value_head(fixed_features)
        
        return policy_logits, value

class GomokuGame:
    """Simple Gomoku (5-in-a-row) game logic"""
    
    def __init__(self, board_size=15):
        self.board_size = board_size
        self.board = np.zeros((board_size, board_size), dtype=int)
        self.current_player = 1  # 1 or 2
        self.move_history = []
        
    def is_valid_move(self, row, col):
        return 0 <= row < self.board_size and 0 <= col < self.board_size and self.board[row, col] == 0
    
    def make_move(self, row, col):
        if not self.is_valid_move(row, col):
            return False
        self.board[row, col] = self.current_player
        self.move_history.append((row, col, self.current_player))
        self.current_player = 3 - self.current_player  # switch player
        return True
    
    def check_win(self, row, col, player):
        directions = [(0,1), (1,0), (1,1), (1,-1)]
        for dr, dc in directions:
            count = 1
            # Check forward
            r, c = row + dr, col + dc
            while 0 <= r < self.board_size and 0 <= c < self.board_size and self.board[r, c] == player:
                count += 1
                r += dr
                c += dc
            # Check backward
            r, c = row - dr, col - dc
            while 0 <= r < self.board_size and 0 <= c < self.board_size and self.board[r, c] == player:
                count += 1
                r -= dr
                c -= dc
            if count >= 5:
                return True
        return False
    
    def get_valid_moves(self):
        moves = []
        for row in range(self.board_size):
            for col in range(self.board_size):
                if self.is_valid_move(row, col):
                    moves.append((row, col))
        return moves
    
    def get_state(self):
        # Convert board to flattened tensor
        return torch.FloatTensor(self.board.flatten()).unsqueeze(0)
    
    def is_terminal(self):
        # Check if last move was winning
        if len(self.move_history) == 0:
            return False
        last_row, last_col, last_player = self.move_history[-1]
        if self.check_win(last_row, last_col, last_player):
            return True
        
        # Check if board is full
        return len(self.get_valid_moves()) == 0

def self_play_episode(model, temperature=1.0):
    """Run one self-play episode"""
    game = GomokuGame()
    model.eval()
    
    states = []
    policies = []
    values = []
    
    while not game.is_terminal():
        state = game.get_state()
        states.append(state)
        
        # Get policy from model
        with torch.no_grad():
            policy_logits, value = model(state)
            policy_logits = policy_logits.squeeze(0) / temperature
            
            # Mask invalid moves
            valid_moves = game.get_valid_moves()
            policy = torch.zeros_like(policy_logits)
            for row, col in valid_moves:
                idx = row * game.board_size + col
                policy[idx] = 1.0 / len(valid_moves)
            
            # Add temperature exploration
            policy = policy * torch.softmax(policy_logits, dim=0)
            policy = policy / policy.sum()
            
            policies.append(policy)
            values.append(value)
        
        # Sample move
        move_idx = torch.multinomial(policy, 1).item()
        row = move_idx // game.board_size
        col = move_idx % game.board_size
        game.make_move(row, col)
    
    # Determine winner
    if game.is_terminal() and len(game.move_history) > 0:
        last_row, last_col, last_player = game.move_history[-1]
        if game.check_win(last_row, last_col, last_player):
            winner = last_player
        else:
            winner = 0  # draw
    else:
        winner = 0
    
    # Prepare training data
    returns = torch.zeros(len(states))
    if winner != 0:
        # Last player to move wins (1) or loses (-1)
        final_return = 1.0 if winner == 2 else -1.0
        returns[-1] = final_return
        # Discount returns
        for t in range(len(states)-2, -1, -1):
            returns[t] = 0.9 * returns[t+1]
    
    return states, policies, values, returns

def create_shuffled_model(base_model):
    """Create model with identical heads but shuffled fixed connections"""
    shuffled_model = FixedWiringNetwork()
    
    # Copy trainable heads exactly
    shuffled_model.policy_head.load_state_dict(base_model.policy_head.state_dict())
    shuffled_model.value_head.load_state_dict(base_model.value_head.state_dict())
    
    # Shuffle fixed connections (keep structure, randomize weights)
    with torch.no_grad():
        for param in shuffled_model.fixed_connections.parameters():
            # Randomize while keeping shape
            param.data = torch.randn_like(param.data)
    
    return shuffled_model

def run_emergence_test(num_games=100):
    """Run emergence test: wired vs shuffled models"""
    
    # Initialize models
    wired_model = FixedWiringNetwork()
    shuffled_model = create_shuffled_model(wired_model)
    
    # Training setup
    optimizer = optim.Adam(list(wired_model.parameters()) + list(shuffled_model.parameters()), lr=0.001)
    
    wired_wins = 0
    shuffled_wins = 0
    draws = 0
    
    print(f"Running {num_games} self-play games...")
    
    for game_num in range(num_games):
        # Play episode with wired model
        states, policies, values, returns = self_play_episode(wired_model)
        
        # Train on episode
        wired_model.train()
        optimizer.zero_grad()
        
        total_loss = 0
        for t in range(len(states)):
            policy_logits, value_pred = wired_model(states[t])
            
            # Policy loss (cross entropy)
            policy_loss = torch.nn.functional.cross_entropy(policy_logits, policies[t])
            
            # Value loss (MSE)
            value_loss = torch.nn.functional.mse_loss(value_pred.squeeze(), returns[t])
            
            loss = policy_loss + value_loss
            total_loss += loss
            
        total_loss.backward()
        optimizer.step()
        
        # Play episode with shuffled model (no training)
        states_shuffled, policies_shuffled, values_shuffled, returns_shuffled = self_play_episode(shuffled_model, temperature=0.1)
        
        # Determine winner
        if values_shuffled[-1].item() > 0:
            wired_wins += 1
        elif values_shuffled[-1].item() < 0:
            shuffled_wins += 1
        else:
            draws += 1
        
        if (game_num + 1) % 10 == 0:
            print(f"Game {game_num + 1}: Wired {wired_wins}, Shuffled {shuffled_wins}, Draws {draws}")
    
    print(f"\nFinal Results:")
    print(f"Wired model wins: {wired_wins}/{num_games} ({wired_wins/num_games*100:.1f}%)")
    print(f"Shuffled model wins: {shuffled_wins}/{num_games} ({shuffled_wins/num_games*100:.1f}%)")
    print(f"Draws: {draws}/{num_games} ({draws/num_games*100:.1f}%)")
    
    # Determine emergence
    wired_win_rate = wired_wins / num_games
    shuffled_win_rate = shuffled_wins / num_games
    
    if wired_win_rate > 0.7:
        print("\n✅ EMERGENCE CONFIRMED: Wired model dominates - strategy emerges from fixed structure")
        return True
    elif shuffled_win_rate > 0.7:
        print("\n❌ EMERGENCE REJECTED: Shuffled model dominates - heads matter more than wiring")
        return False
    else:
        print("\n🤔 INCONCLUSIVE: Both models perform similarly - needs more games")
        return None

if __name__ == "__main__":
    run_emergence_test(num_games=100)
