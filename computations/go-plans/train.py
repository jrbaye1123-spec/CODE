"""
Go Training Pipeline — generate training data from self-play and train the neural net.

Features:
  - Self-play game generation using MCTS engine
  - Board-to-tensor feature extraction
  - Supervised training from engine evaluations
  - Curriculum learning (9x9 -> 13x13)
  - Checkpoint saving and evaluation
  - Integration with Shin Jinseo knowledge as training priors
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import random
import time
import os
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from collections import deque

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from board import Board, Color, Point
from engine import MCTSEngine, create_engine
from go_network import GoNetwork


# ─── Feature Extraction ─────────────────────────────────────

def board_to_tensor(board: Board, color: Color) -> np.ndarray:
    """
    Convert board state to a 17-plane input tensor.
    Plane order matches GoNetwork documentation.
    """
    size = board.size
    planes = np.zeros((17, size, size), dtype=np.float32)
    
    my_color = color
    opp_color = color.opponent
    
    for r in range(size):
        for c in range(size):
            p = Point(r, c)
            stone = board.grid[r][c]
            
            # Plane 0-2: stone presence
            if stone == my_color:
                planes[0, r, c] = 1.0
            elif stone == opp_color:
                planes[1, r, c] = 1.0
            else:
                planes[2, r, c] = 1.0
            
            # Plane 3-8: liberties
            if stone is not None and p in board.groups:
                group = board.groups[p]
                libs = group.num_liberties
                base = 3 if stone == my_color else 5
                if libs == 1:
                    planes[base, r, c] = 1.0
                elif libs == 2:
                    planes[base + 1, r, c] = 1.0
                elif libs >= 3:
                    planes[base + 2, r, c] = 1.0
    
    # Plane 9-10: ladder capture (simplified — atari groups)
    for r in range(size):
        for c in range(size):
            p = Point(r, c)
            if board.grid[r][c] is not None and p in board.groups:
                group = board.groups[p]
                if group.num_liberties == 1:
                    base = 9 if group.color == my_color else 10
                    for s in group.stones:
                        planes[base, s.row, s.col] = 1.0
    
    # Plane 11: ko (approximate — if last move was a capture)
    # Simplified: mark points adjacent to recent captures
    # (Skipping full ko detection for now)
    
    # Plane 12: move number
    planes[12, :, :] = board.move_number / (size * size)
    
    # Plane 13: color to play (all 1 for my_color)
    planes[13, :, :] = 1.0 if my_color == Color.BLACK else 0.0
    
    # Plane 14-15: captures
    planes[14, :, :] = board.captures[my_color] / max(1, size * size)
    planes[15, :, :] = board.captures[opp_color] / max(1, size * size)
    
    # Plane 16: pass indicator (always 0 for now)
    
    return planes


def move_to_index(move: Optional[Point], board_size: int) -> int:
    """Convert a move to a flat index. Pass = board_size * board_size."""
    if move is None or move.row < 0:
        return board_size * board_size
    return move.row * board_size + move.col


def index_to_move(index: int, board_size: int) -> Optional[Point]:
    """Convert a flat index back to a Point. Last index = pass."""
    if index == board_size * board_size:
        return None
    row = index // board_size
    col = index % board_size
    return Point(row, col)


# ─── Training Data Generation ───────────────────────────────

@dataclass
class TrainingExample:
    """A single training example."""
    planes: np.ndarray  # [17, size, size]
    policy_target: np.ndarray  # [size*size + 1] — visit distribution
    value_target: float  # -1 to 1, from current player's perspective
    board_size: int


class GoDataset(Dataset):
    """PyTorch dataset for Go training examples."""
    
    def __init__(self, examples: List[TrainingExample]):
        self.planes = torch.FloatTensor(np.stack([e.planes for e in examples]))
        self.policy_targets = torch.FloatTensor(np.stack([e.policy_target for e in examples]))
        self.value_targets = torch.FloatTensor(
            np.array([e.value_target for e in examples]).reshape(-1, 1)
        )
    
    def __len__(self):
        return len(self.planes)
    
    def __getitem__(self, idx):
        return self.planes[idx], self.policy_targets[idx], self.value_targets[idx]


def generate_self_play_game(
    engine: MCTSEngine,
    board_size: int,
    komi: float = 6.5,
    temperature: float = 1.0,
    max_moves: int = 400,
) -> List[TrainingExample]:
    """
    Generate one self-play game and return training examples.
    Each position becomes a training example with MCTS visit distribution
    as the policy target and game outcome as the value target.
    """
    board = Board(size=board_size, komi=komi)
    examples = []
    
    while not board.finished and board.move_number < max_moves:
        # Run MCTS to get visit distribution
        root = engine.search(board, time_limit=0.5 if board_size <= 9 else 1.0)
        
        if not root.children:
            break
        
        # Build policy target from visit distribution
        total_visits = sum(c.visits for c in root.children)
        policy_target = np.zeros(board_size * board_size + 1, dtype=np.float32)
        
        for child in root.children:
            if child.point is None or child.point.row < 0:
                idx = board_size * board_size  # pass
            else:
                idx = child.point.row * board_size + child.point.col
            policy_target[idx] = child.visits / max(1, total_visits)
        
        # Extract features before the move
        planes = board_to_tensor(board, board.current_player)
        
        # Select and play the move (temperature-based)
        children = sorted(root.children, key=lambda c: -c.visits)
        if temperature > 0:
            visits = np.array([c.visits ** (1.0 / temperature) for c in children])
            visits = visits / visits.sum()
            chosen = np.random.choice(len(children), p=visits)
        else:
            chosen = 0
        move = children[chosen].point
        
        # Play the move
        success = board.play(move)
        if not success:
            # Try the best legal move instead
            legal = board.get_legal_moves()
            if legal:
                move = random.choice(legal)
                board.play(move)
            else:
                board.play(None)
        
        # Store example (value target will be filled after game ends)
        examples.append(TrainingExample(
            planes=planes,
            policy_target=policy_target,
            value_target=0.0,  # placeholder
            board_size=board_size,
        ))
    
    # Game over — compute value targets
    black_score, white_score = board.score()
    
    # Winner from Black's perspective (1 = Black win, -1 = White win)
    outcome = 1.0 if black_score > white_score else (-1.0 if white_score > black_score else 0.0)
    
    # Fill in value targets: from the perspective of the player who made the move
    for i, ex in enumerate(examples):
        # Determine which color played the move
        # Even indices = Black's moves, odd = White's moves
        move_color = Color.BLACK if i % 2 == 0 else Color.WHITE
        if move_color == Color.BLACK:
            ex.value_target = outcome
        else:
            ex.value_target = -outcome
    
    return examples


def generate_training_data(
    board_size: int = 9,
    num_games: int = 50,
    engine_strength: str = "medium",
    output_dir: str = "training_data",
) -> List[TrainingExample]:
    """
    Generate self-play training data.
    """
    os.makedirs(output_dir, exist_ok=True)
    engine = create_engine(board_size, engine_strength)
    
    all_examples = []
    print(f"Generating {num_games} self-play games on {board_size}x{board_size}...")
    
    for game_idx in range(num_games):
        start = time.time()
        examples = generate_self_play_game(engine, board_size)
        all_examples.extend(examples)
        
        elapsed = time.time() - start
        print(f"  Game {game_idx + 1}/{num_games}: {len(examples)} positions, "
              f"{elapsed:.1f}s, total: {len(all_examples)}")
        
        # Save checkpoint every 10 games
        if (game_idx + 1) % 10 == 0:
            save_path = os.path.join(output_dir, f"data_{board_size}x{board_size}_{game_idx + 1}.pt")
            planes = np.stack([e.planes for e in all_examples])
            policies = np.stack([e.policy_target for e in all_examples])
            values = np.array([e.value_target for e in all_examples])
            torch.save({
                'planes': torch.FloatTensor(planes),
                'policies': torch.FloatTensor(policies),
                'values': torch.FloatTensor(values.reshape(-1, 1)),
                'board_size': board_size,
                'num_examples': len(all_examples),
            }, save_path)
            print(f"  Saved checkpoint: {save_path}")
    
    return all_examples


# ─── Training Loop ──────────────────────────────────────────

class GoTrainer:
    """Train the Go neural network."""
    
    def __init__(
        self,
        model: GoNetwork,
        device: torch.device = torch.device('cpu'),
        learning_rate: float = 0.001,
        weight_decay: float = 1e-4,
        policy_weight: float = 1.0,
        value_weight: float = 1.0,
    ):
        self.model = model.to(device)
        self.device = device
        self.policy_weight = policy_weight
        self.value_weight = value_weight
        
        self.optimizer = optim.Adam(
            model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay,
        )
        
        self.policy_loss_fn = nn.KLDivLoss(reduction='batchmean')
        self.value_loss_fn = nn.MSELoss()
        
        self.train_losses = []
        self.val_losses = []
    
    def train_step(self, batch) -> Dict[str, float]:
        """Single training step."""
        planes, policy_target, value_target = batch
        planes = planes.to(self.device)
        policy_target = policy_target.to(self.device)
        value_target = value_target.to(self.device)
        
        self.optimizer.zero_grad()
        
        policy_logits, value_pred = self.model(planes)
        
        # Policy loss: KL divergence between predicted log-probs and target distribution
        policy_loss = self.policy_loss_fn(policy_logits, policy_target)
        
        # Value loss: MSE
        value_loss = self.value_loss_fn(value_pred, value_target)
        
        # Combined loss
        total_loss = self.policy_weight * policy_loss + self.value_weight * value_loss
        
        total_loss.backward()
        
        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
        
        self.optimizer.step()
        
        return {
            'total': total_loss.item(),
            'policy': policy_loss.item(),
            'value': value_loss.item(),
        }
    
    @torch.no_grad()
    def validate(self, dataloader: DataLoader) -> Dict[str, float]:
        """Validation step."""
        self.model.eval()
        total_policy = 0.0
        total_value = 0.0
        count = 0
        
        for planes, policy_target, value_target in dataloader:
            planes = planes.to(self.device)
            policy_target = policy_target.to(self.device)
            value_target = value_target.to(self.device)
            
            policy_logits, value_pred = self.model(planes)
            
            policy_loss = self.policy_loss_fn(policy_logits, policy_target)
            value_loss = self.value_loss_fn(value_pred, value_target)
            
            total_policy += policy_loss.item() * planes.shape[0]
            total_value += value_loss.item() * planes.shape[0]
            count += planes.shape[0]
        
        self.model.train()
        
        return {
            'policy': total_policy / max(1, count),
            'value': total_value / max(1, count),
        }
    
    def train(
        self,
        train_loader: DataLoader,
        val_loader: Optional[DataLoader] = None,
        epochs: int = 10,
        save_path: str = "go_model.pt",
        log_interval: int = 10,
    ):
        """Full training loop."""
        print(f"Training {self.model.count_parameters():,} parameters on {self.device}")
        print(f"Training batches: {len(train_loader)}, epochs: {epochs}")
        
        for epoch in range(epochs):
            epoch_start = time.time()
            epoch_losses = []
            
            for batch_idx, batch in enumerate(train_loader):
                losses = self.train_step(batch)
                epoch_losses.append(losses)
                
                if (batch_idx + 1) % log_interval == 0:
                    avg_loss = np.mean([l['total'] for l in epoch_losses[-log_interval:]])
                    avg_pol = np.mean([l['policy'] for l in epoch_losses[-log_interval:]])
                    avg_val = np.mean([l['value'] for l in epoch_losses[-log_interval:]])
                    print(f"  Epoch {epoch+1}/{epochs} | Batch {batch_idx+1}/{len(train_loader)} | "
                          f"Loss: {avg_loss:.4f} (P:{avg_pol:.4f} V:{avg_val:.4f})")
            
            # Epoch summary
            avg_total = np.mean([l['total'] for l in epoch_losses])
            avg_policy = np.mean([l['policy'] for l in epoch_losses])
            avg_value = np.mean([l['value'] for l in epoch_losses])
            
            summary = f"Epoch {epoch+1}/{epochs} | Train Loss: {avg_total:.4f} (P:{avg_policy:.4f} V:{avg_value:.4f})"
            
            if val_loader:
                val_losses = self.validate(val_loader)
                summary += f" | Val Loss: P:{val_losses['policy']:.4f} V:{val_losses['value']:.4f}"
            
            summary += f" | Time: {time.time() - epoch_start:.1f}s"
            print(summary)
            
            self.train_losses.append(avg_total)
            
            # Save checkpoint
            torch.save({
                'epoch': epoch + 1,
                'model_state_dict': self.model.state_dict(),
                'optimizer_state_dict': self.optimizer.state_dict(),
                'train_loss': avg_total,
                'val_loss': val_losses if val_loader else None,
                'board_size': self.model.board_size,
            }, save_path)
        
        print(f"Model saved to {save_path}")


def load_training_data(data_dir: str, board_size: int) -> Tuple[GoDataset, GoDataset]:
    """Load all training data files and split into train/val."""
    all_data = []
    
    for fname in sorted(os.listdir(data_dir)):
        if fname.startswith(f"data_{board_size}x{board_size}") and fname.endswith(".pt"):
            path = os.path.join(data_dir, fname)
            data = torch.load(path, weights_only=True)
            
            planes = data['planes'].numpy()
            policies = data['policies'].numpy()
            values = data['values'].numpy()
            
            for i in range(len(planes)):
                all_data.append(TrainingExample(
                    planes=planes[i],
                    policy_target=policies[i],
                    value_target=float(values[i][0]),
                    board_size=board_size,
                ))
    
    print(f"Loaded {len(all_data)} examples from {data_dir}")
    
    # 80/20 train/val split
    split = int(len(all_data) * 0.8)
    train_examples = all_data[:split]
    val_examples = all_data[split:]
    
    return GoDataset(train_examples), GoDataset(val_examples)


def main_train(board_size: int = 9, num_games: int = 20, epochs: int = 10):
    """Main training entry point."""
    # Generate data
    data_dir = f"training_data_{board_size}"
    examples = generate_training_data(
        board_size=board_size,
        num_games=num_games,
        engine_strength="medium",
        output_dir=data_dir,
    )
    
    # Create datasets
    train_set, val_set = load_training_data(data_dir, board_size)
    
    # Create dataloaders
    train_loader = DataLoader(train_set, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=64)
    
    # Create model
    model = GoNetwork(board_size=board_size, num_filters=32, num_res_blocks=4)
    print(f"Model parameters: {model.count_parameters():,}")
    
    # Train
    trainer = GoTrainer(
        model,
        learning_rate=0.001,
        policy_weight=1.0,
        value_weight=0.5,
    )
    
    trainer.train(
        train_loader,
        val_loader,
        epochs=epochs,
        save_path=f"go_model_{board_size}x{board_size}.pt",
    )
    
    return model, trainer


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=9, choices=[9, 13, 19])
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--epochs", type=int, default=10)
    args = parser.parse_args()
    
    model, trainer = main_train(args.size, args.games, args.epochs)
