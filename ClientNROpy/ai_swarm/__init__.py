"""
AI Swarm - Multi-Agent Graph Neural Network (GATv2) Pipeline for 2D Game Bots.
Optimized for NVIDIA RTX 3050 (4GB VRAM) / CPU Fallback.
"""

from .data_logger import DataLogger, Entity, EntityType, SwarmGraphBuilder
from .model import SwarmGATPolicy
from .train_bc import BehaviorCloningTrainer
from .inference_bridge import SwarmInferenceBridge

__all__ = [
    "DataLogger",
    "Entity",
    "EntityType",
    "SwarmGraphBuilder",
    "SwarmGATPolicy",
    "BehaviorCloningTrainer",
    "SwarmInferenceBridge",
]
