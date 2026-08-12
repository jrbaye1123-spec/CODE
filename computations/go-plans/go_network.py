"""
Go Neural Network — policy and value network for Go position evaluation.

A compact ResNet-style CNN designed for CPU training.
Architecture: Input (board_size x board_size x 17) -> ResBlocks -> Policy Head + Value Head

Input planes (17 channels):
  0:  Current player's stones
  1:  Opponent's stones  
  2:  Empty points
  3:  Current player's stones with 1 liberty (atari)
  4:  Opponent's stones with 1 liberty
  5:  Current player's stones with 2 liberties
  6:  Opponent's stones with 2 liberties
  7:  Current player's stones with 3+ liberties
  8:  Opponent's stones with 3+ liberties
  9:  Ladder capturable (current player)
  10: Ladder capturable (opponent)
  11: Ko point (1 if ko restricts this point)
  12: Move number / max_moves
  13: Current player color (all 1s or all 0s)
  14: Captures by current player (normalized)
  15: Captures by opponent (normalized)
  16: Pass move indicator

Designed to be small enough for CPU training (~500K params).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Optional


class ConvBlock(nn.Module):
    """Conv -> BatchNorm -> ReLU"""
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size,
                              padding=kernel_size // 2, bias=False)
        self.bn = nn.BatchNorm2d(out_channels)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.relu(self.bn(self.conv(x)))


class ResBlock(nn.Module):
    """Residual block with two conv layers."""
    def __init__(self, channels: int):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(channels)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out = F.relu(out + residual)
        return out


class GoNetwork(nn.Module):
    """
    Policy + Value network for Go.
    
    Args:
        board_size: 9, 13, or 19
        num_input_planes: Number of input feature planes
        num_filters: Base filter count
        num_res_blocks: Number of residual blocks
        policy_head_filters: Filters in policy head
    """
    
    def __init__(
        self,
        board_size: int = 9,
        num_input_planes: int = 17,
        num_filters: int = 64,
        num_res_blocks: int = 6,
        policy_head_filters: int = 32,
    ):
        super().__init__()
        self.board_size = board_size
        
        # Input convolution
        self.input_conv = ConvBlock(num_input_planes, num_filters, 3)
        
        # Residual tower
        self.res_blocks = nn.Sequential(*[
            ResBlock(num_filters) for _ in range(num_res_blocks)
        ])
        
        # Policy head
        self.policy_conv = ConvBlock(num_filters, policy_head_filters, 1)
        self.policy_fc = nn.Linear(
            policy_head_filters * board_size * board_size,
            board_size * board_size + 1  # +1 for pass
        )
        
        # Value head
        self.value_conv = ConvBlock(num_filters, 16, 1)
        self.value_fc1 = nn.Linear(16 * board_size * board_size, 128)
        self.value_fc2 = nn.Linear(128, 1)
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.constant_(m.bias, 0)
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: Input tensor [batch, planes, board_size, board_size]
        
        Returns:
            policy_logits: [batch, board_size*board_size + 1]
            value: [batch, 1] — tanh output in [-1, 1]
        """
        batch = x.shape[0]
        
        # Shared trunk
        out = self.input_conv(x)
        out = self.res_blocks(out)
        
        # Policy head
        policy = self.policy_conv(out)
        policy = policy.view(batch, -1)
        policy = self.policy_fc(policy)
        policy_logits = F.log_softmax(policy, dim=1)
        
        # Value head
        value = self.value_conv(out)
        value = value.view(batch, -1)
        value = F.relu(self.value_fc1(value))
        value = torch.tanh(self.value_fc2(value))
        
        return policy_logits, value
    
    def predict(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Inference mode prediction.
        Returns (policy_probs, value, best_move_index).
        """
        with torch.no_grad():
            log_probs, value = self.forward(x)
            probs = torch.exp(log_probs)
            best_move = torch.argmax(probs[:, :-1], dim=1)  # exclude pass index
        return probs, value, best_move
    
    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)
