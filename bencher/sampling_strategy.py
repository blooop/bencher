"""Sampling strategy definitions for unified benchmarking interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from enum import Enum, auto
from bencher.bench_cfg import BenchRunCfg


class SamplingMode(Enum):
    """Defines how sampling density should be increased over iterations."""
    
    SINGLE = auto()  # Single run with specified parameters
    REPEATS_FIRST = auto()  # Increase repeats to max before increasing level
    LEVEL_FIRST = auto()  # Increase level to max before increasing repeats
    ALTERNATING = auto()  # Alternate between increasing repeats and level
    
    # Function interleaving modes
    FUNCTIONS_PARALLEL = auto()  # Run all functions at same level/repeat, then advance together
    FUNCTIONS_SEQUENTIAL = auto()  # Complete one function fully before starting next
    FUNCTIONS_ROUND_ROBIN = auto()  # Alternate between functions at each level/repeat increment


class SamplingStrategy(ABC):
    """Abstract base class for sampling strategies."""
    
    def __init__(self, mode: SamplingMode):
        self.mode = mode
    
    @abstractmethod
    def generate_configs(self, base_cfg: BenchRunCfg) -> List[BenchRunCfg]:
        """Generate a list of configurations for progressive sampling."""


class SingleSamplingStrategy(SamplingStrategy):
    """Strategy for single benchmark run with fixed parameters."""
    
    def __init__(self, level: int = 2, repeats: int = 1, **kwargs):
        super().__init__(SamplingMode.SINGLE)
        self.level = level
        self.repeats = repeats
        self.kwargs = kwargs
    
    def generate_configs(self, base_cfg: BenchRunCfg) -> List[BenchRunCfg]:
        """Generate single configuration."""
        from copy import deepcopy
        cfg = deepcopy(base_cfg)
        cfg.level = self.level
        cfg.repeats = self.repeats
        
        # Apply any additional kwargs
        for key, value in self.kwargs.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        
        return [cfg]


class RepeatsFirstStrategy(SamplingStrategy):
    """Strategy that increases repeats to maximum before increasing level."""
    
    def __init__(self, level: int = 2, max_level: int = 6, 
                 repeats: int = 1, max_repeats: int = 5,
                 # Legacy parameters for backward compatibility
                 min_level: int = None, min_repeats: int = None):
        super().__init__(SamplingMode.REPEATS_FIRST)
        self.level = level if min_level is None else min_level
        self.max_level = max_level
        self.repeats = repeats if min_repeats is None else min_repeats
        self.max_repeats = max_repeats
    
    def generate_configs(self, base_cfg: BenchRunCfg) -> List[BenchRunCfg]:
        """Generate configurations that max out repeats before increasing level."""
        from copy import deepcopy
        configs = []
        
        for current_level in range(self.level, self.max_level + 1):
            for current_repeats in range(self.repeats, self.max_repeats + 1):
                cfg = deepcopy(base_cfg)
                cfg.level = current_level
                cfg.repeats = current_repeats
                configs.append(cfg)
        
        return configs


class LevelFirstStrategy(SamplingStrategy):
    """Strategy that increases level to maximum before increasing repeats."""
    
    def __init__(self, level: int = 2, max_level: int = 6,
                 repeats: int = 1, max_repeats: int = 5,
                 # Legacy parameters for backward compatibility
                 min_level: int = None, min_repeats: int = None):
        super().__init__(SamplingMode.LEVEL_FIRST)
        self.level = level if min_level is None else min_level
        self.max_level = max_level
        self.repeats = repeats if min_repeats is None else min_repeats
        self.max_repeats = max_repeats
    
    def generate_configs(self, base_cfg: BenchRunCfg) -> List[BenchRunCfg]:
        """Generate configurations that max out level before increasing repeats."""
        from copy import deepcopy
        configs = []
        
        for current_repeats in range(self.repeats, self.max_repeats + 1):
            for current_level in range(self.level, self.max_level + 1):
                cfg = deepcopy(base_cfg)
                cfg.level = current_level
                cfg.repeats = current_repeats
                configs.append(cfg)
        
        return configs


class AlternatingStrategy(SamplingStrategy):
    """Strategy that alternates between increasing repeats and level."""
    
    def __init__(self, level: int = 2, max_level: int = 6,
                 repeats: int = 1, max_repeats: int = 5,
                 # Legacy parameters for backward compatibility
                 min_level: int = None, min_repeats: int = None):
        super().__init__(SamplingMode.ALTERNATING)
        self.level = level if min_level is None else min_level
        self.max_level = max_level
        self.repeats = repeats if min_repeats is None else min_repeats
        self.max_repeats = max_repeats
    
    def generate_configs(self, base_cfg: BenchRunCfg) -> List[BenchRunCfg]:
        """Generate configurations alternating between level and repeat increases."""
        from copy import deepcopy
        configs = []
        
        current_level = self.level
        current_repeats = self.repeats
        increase_level_next = True
        
        # Start with initial configuration
        cfg = deepcopy(base_cfg)
        cfg.level = current_level
        cfg.repeats = current_repeats
        configs.append(cfg)
        
        while current_level < self.max_level or current_repeats < self.max_repeats:
            if increase_level_next and current_level < self.max_level:
                current_level += 1
            elif current_repeats < self.max_repeats:
                current_repeats += 1
            else:
                # If we can't increase repeats, increase level
                current_level += 1
            
            cfg = deepcopy(base_cfg)
            cfg.level = current_level
            cfg.repeats = current_repeats
            configs.append(cfg)
            
            increase_level_next = not increase_level_next
        
        return configs


class FunctionsParallelStrategy(SamplingStrategy):
    """Strategy that runs all functions at same level/repeat, then advances together."""
    
    def __init__(self, level: int = 2, max_level: int = 6,
                 repeats: int = 1, max_repeats: int = 5):
        super().__init__(SamplingMode.FUNCTIONS_PARALLEL)
        self.level = level
        self.max_level = max_level
        self.repeats = repeats
        self.max_repeats = max_repeats
    
    def generate_configs(self, base_cfg: BenchRunCfg) -> List[BenchRunCfg]:
        """Generate configs where all functions run at same level/repeat before advancing."""
        from copy import deepcopy
        configs = []
        
        for current_level in range(self.level, self.max_level + 1):
            for current_repeats in range(self.repeats, self.max_repeats + 1):
                cfg = deepcopy(base_cfg)
                cfg.level = current_level
                cfg.repeats = current_repeats
                cfg.interleaving_mode = "parallel"  # All functions at this level/repeat
                configs.append(cfg)
        
        return configs


class FunctionsSequentialStrategy(SamplingStrategy):
    """Strategy that completes one function fully before starting the next."""
    
    def __init__(self, level: int = 2, max_level: int = 6,
                 repeats: int = 1, max_repeats: int = 5):
        super().__init__(SamplingMode.FUNCTIONS_SEQUENTIAL)
        self.level = level
        self.max_level = max_level
        self.repeats = repeats
        self.max_repeats = max_repeats
    
    def generate_configs(self, base_cfg: BenchRunCfg) -> List[BenchRunCfg]:
        """Generate configs where each function completes fully before next starts."""
        from copy import deepcopy
        configs = []
        
        for current_level in range(self.level, self.max_level + 1):
            for current_repeats in range(self.repeats, self.max_repeats + 1):
                cfg = deepcopy(base_cfg)
                cfg.level = current_level
                cfg.repeats = current_repeats
                cfg.interleaving_mode = "sequential"  # One function at a time
                configs.append(cfg)
        
        return configs


class FunctionsRoundRobinStrategy(SamplingStrategy):
    """Strategy that alternates between functions at each level/repeat increment."""
    
    def __init__(self, level: int = 2, max_level: int = 6,
                 repeats: int = 1, max_repeats: int = 5):
        super().__init__(SamplingMode.FUNCTIONS_ROUND_ROBIN)
        self.level = level
        self.max_level = max_level
        self.repeats = repeats
        self.max_repeats = max_repeats
    
    def generate_configs(self, base_cfg: BenchRunCfg) -> List[BenchRunCfg]:
        """Generate configs alternating between functions at each increment."""
        from copy import deepcopy
        configs = []
        
        for current_level in range(self.level, self.max_level + 1):
            for current_repeats in range(self.repeats, self.max_repeats + 1):
                cfg = deepcopy(base_cfg)
                cfg.level = current_level
                cfg.repeats = current_repeats
                cfg.interleaving_mode = "round_robin"  # Alternate functions
                configs.append(cfg)
        
        return configs


# Convenience factory functions
def single_run(level: int = 2, repeats: int = 1, **kwargs) -> SingleSamplingStrategy:
    """Create a single run sampling strategy."""
    return SingleSamplingStrategy(level=level, repeats=repeats, **kwargs)


def repeats_first(level: int = 2, max_level: int = 6,
                  repeats: int = 1, max_repeats: int = 5) -> RepeatsFirstStrategy:
    """Create a strategy that increases repeats to max before increasing level."""
    return RepeatsFirstStrategy(level, max_level, repeats, max_repeats)


def level_first(level: int = 2, max_level: int = 6,
                repeats: int = 1, max_repeats: int = 5) -> LevelFirstStrategy:
    """Create a strategy that increases level to max before increasing repeats."""
    return LevelFirstStrategy(level, max_level, repeats, max_repeats)


def alternating(level: int = 2, max_level: int = 6,
                repeats: int = 1, max_repeats: int = 5) -> AlternatingStrategy:
    """Create a strategy that alternates between increasing repeats and level."""
    return AlternatingStrategy(level, max_level, repeats, max_repeats)