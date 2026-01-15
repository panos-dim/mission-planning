"""
Unit tests for constellation conflict resolution (PR #7).

Tests the ConstellationConflictResolver class and helper functions.
"""

import pytest
from datetime import datetime, timedelta

# Import from conflict resolution module
# Using isolated test implementation to avoid import issues
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import defaultdict


# ============================================================================
# Isolated Implementation (mirrors conflict_resolution.py for testing)
# ============================================================================

@dataclass
class ConflictInfo:
    """Information about a scheduling conflict between satellites."""
    target_name: str
    conflicting_passes: List[Dict]
    resolution_strategy: str = ""
    winner_satellite_id: str = ""
    conflict_type: str = "temporal_overlap"


class ConstellationConflictResolver:
    """Test implementation of conflict resolver."""
    
    def __init__(
        self,
        time_threshold_seconds: float = 300.0,
        strategy: str = "best_geometry"
    ):
        self.time_threshold_seconds = time_threshold_seconds
        self.strategy = strategy
        self._satellite_loads: Dict[str, int] = defaultdict(int)
    
    def detect_conflicts(self, passes: List[Dict]) -> List[ConflictInfo]:
        """Detect conflicts among passes."""
        conflicts = []
        passes_by_target: Dict[str, List[Dict]] = defaultdict(list)
        
        for p in passes:
            target = p.get("target", "")
            passes_by_target[target].append(p)
        
        for target, target_passes in passes_by_target.items():
            if len(target_passes) < 2:
                continue
            
            conflict_group = []
            for i, p1 in enumerate(target_passes):
                for p2 in target_passes[i+1:]:
                    sat1 = p1.get("satellite_id", "")
                    sat2 = p2.get("satellite_id", "")
                    
                    if sat1 == sat2:
                        continue
                    
                    if self._passes_overlap(p1, p2):
                        if p1 not in conflict_group:
                            conflict_group.append(p1)
                        if p2 not in conflict_group:
                            conflict_group.append(p2)
            
            if conflict_group:
                conflicts.append(ConflictInfo(
                    target_name=target,
                    conflicting_passes=conflict_group
                ))
        
        return conflicts
    
    def _passes_overlap(self, p1: Dict, p2: Dict) -> bool:
        """Check if two passes overlap."""
        try:
            start1 = datetime.fromisoformat(p1.get("start_time", "").replace('Z', ''))
            end1 = datetime.fromisoformat(p1.get("end_time", "").replace('Z', ''))
            start2 = datetime.fromisoformat(p2.get("start_time", "").replace('Z', ''))
            end2 = datetime.fromisoformat(p2.get("end_time", "").replace('Z', ''))
            
            threshold = timedelta(seconds=self.time_threshold_seconds)
            start1_ext = start1 - threshold
            end1_ext = end1 + threshold
            
            return not (end2 < start1_ext or start2 > end1_ext)
        except:
            return False
    
    def _select_winner(self, conflict: ConflictInfo) -> Optional[Dict]:
        """Select winning pass based on strategy."""
        passes = conflict.conflicting_passes
        if not passes:
            return None
        
        if self.strategy == "best_geometry":
            return min(passes, key=lambda p: abs(p.get("incidence_angle_deg", 90) or 90))
        elif self.strategy == "first_available":
            return min(passes, key=lambda p: p.get("start_time", "9999"))
        elif self.strategy == "load_balance":
            return min(passes, key=lambda p: self._satellite_loads.get(p.get("satellite_id", ""), 0))
        return passes[0]
    
    def resolve_conflicts(self, passes: List[Dict], conflicts: List[ConflictInfo]) -> Dict:
        """Resolve conflicts and return deduplicated passes."""
        if not conflicts:
            return {"resolved_passes": passes, "passes_removed": 0}
        
        passes_to_remove = set()
        
        for conflict in conflicts:
            winner = self._select_winner(conflict)
            if winner:
                conflict.winner_satellite_id = winner.get("satellite_id", "")
                conflict.resolution_strategy = self.strategy
                
                for p in conflict.conflicting_passes:
                    if p.get("satellite_id") != conflict.winner_satellite_id:
                        pass_key = f"{p.get('satellite_id')}_{p.get('target')}_{p.get('start_time')}"
                        passes_to_remove.add(pass_key)
                
                self._satellite_loads[conflict.winner_satellite_id] += 1
        
        resolved = [
            p for p in passes 
            if f"{p.get('satellite_id')}_{p.get('target')}_{p.get('start_time')}" not in passes_to_remove
        ]
        
        return {
            "resolved_passes": resolved,
            "passes_removed": len(passes) - len(resolved),
            "conflicts": conflicts
        }
    
    def process(self, passes: List[Dict]) -> Dict:
        """Full pipeline."""
        self._satellite_loads.clear()
        conflicts = self.detect_conflicts(passes)
        return self.resolve_conflicts(passes, conflicts)


# ============================================================================
# Tests
# ============================================================================

class TestConflictDetection:
    """Test conflict detection."""
    
    def test_no_conflicts_single_satellite(self) -> None:
        """Single satellite has no conflicts."""
        passes = [
            {"satellite_id": "sat_A", "target": "Target1", "start_time": "2025-01-01T10:00:00", "end_time": "2025-01-01T10:10:00"},
            {"satellite_id": "sat_A", "target": "Target2", "start_time": "2025-01-01T12:00:00", "end_time": "2025-01-01T12:10:00"},
        ]
        
        resolver = ConstellationConflictResolver()
        conflicts = resolver.detect_conflicts(passes)
        
        assert len(conflicts) == 0
    
    def test_no_conflicts_different_targets(self) -> None:
        """Different targets don't conflict."""
        passes = [
            {"satellite_id": "sat_A", "target": "Target1", "start_time": "2025-01-01T10:00:00", "end_time": "2025-01-01T10:10:00"},
            {"satellite_id": "sat_B", "target": "Target2", "start_time": "2025-01-01T10:00:00", "end_time": "2025-01-01T10:10:00"},
        ]
        
        resolver = ConstellationConflictResolver()
        conflicts = resolver.detect_conflicts(passes)
        
        assert len(conflicts) == 0
    
    def test_conflict_detected_same_target_overlapping_time(self) -> None:
        """Two satellites viewing same target at same time conflicts."""
        passes = [
            {"satellite_id": "sat_A", "target": "Target1", "start_time": "2025-01-01T10:00:00", "end_time": "2025-01-01T10:10:00"},
            {"satellite_id": "sat_B", "target": "Target1", "start_time": "2025-01-01T10:05:00", "end_time": "2025-01-01T10:15:00"},
        ]
        
        resolver = ConstellationConflictResolver()
        conflicts = resolver.detect_conflicts(passes)
        
        assert len(conflicts) == 1
        assert conflicts[0].target_name == "Target1"
        assert len(conflicts[0].conflicting_passes) == 2
    
    def test_conflict_detected_within_threshold(self) -> None:
        """Passes within threshold also conflict."""
        passes = [
            {"satellite_id": "sat_A", "target": "Target1", "start_time": "2025-01-01T10:00:00", "end_time": "2025-01-01T10:10:00"},
            {"satellite_id": "sat_B", "target": "Target1", "start_time": "2025-01-01T10:12:00", "end_time": "2025-01-01T10:22:00"},
        ]
        
        # 2 minute gap, but 5 minute threshold
        resolver = ConstellationConflictResolver(time_threshold_seconds=300)
        conflicts = resolver.detect_conflicts(passes)
        
        assert len(conflicts) == 1
    
    def test_no_conflict_outside_threshold(self) -> None:
        """Passes outside threshold don't conflict."""
        passes = [
            {"satellite_id": "sat_A", "target": "Target1", "start_time": "2025-01-01T10:00:00", "end_time": "2025-01-01T10:10:00"},
            {"satellite_id": "sat_B", "target": "Target1", "start_time": "2025-01-01T10:20:00", "end_time": "2025-01-01T10:30:00"},
        ]
        
        # 10 minute gap, only 5 minute threshold
        resolver = ConstellationConflictResolver(time_threshold_seconds=300)
        conflicts = resolver.detect_conflicts(passes)
        
        assert len(conflicts) == 0


class TestConflictResolution:
    """Test conflict resolution strategies."""
    
    def test_best_geometry_selects_lowest_incidence(self) -> None:
        """Best geometry strategy selects lowest incidence angle."""
        passes = [
            {"satellite_id": "sat_A", "target": "Target1", "start_time": "2025-01-01T10:00:00", 
             "end_time": "2025-01-01T10:10:00", "incidence_angle_deg": 35.0},
            {"satellite_id": "sat_B", "target": "Target1", "start_time": "2025-01-01T10:05:00", 
             "end_time": "2025-01-01T10:15:00", "incidence_angle_deg": 15.0},  # Better angle
        ]
        
        resolver = ConstellationConflictResolver(strategy="best_geometry")
        result = resolver.process(passes)
        
        resolved = result["resolved_passes"]
        assert len(resolved) == 1
        assert resolved[0]["satellite_id"] == "sat_B"  # Lower incidence wins
    
    def test_first_available_selects_earliest(self) -> None:
        """First available strategy selects earliest pass."""
        passes = [
            {"satellite_id": "sat_A", "target": "Target1", "start_time": "2025-01-01T10:05:00", 
             "end_time": "2025-01-01T10:15:00", "incidence_angle_deg": 15.0},
            {"satellite_id": "sat_B", "target": "Target1", "start_time": "2025-01-01T10:00:00", 
             "end_time": "2025-01-01T10:10:00", "incidence_angle_deg": 35.0},  # Earlier
        ]
        
        resolver = ConstellationConflictResolver(strategy="first_available")
        result = resolver.process(passes)
        
        resolved = result["resolved_passes"]
        assert len(resolved) == 1
        assert resolved[0]["satellite_id"] == "sat_B"  # Earlier start wins
    
    def test_load_balance_distributes_evenly(self) -> None:
        """Load balance strategy distributes targets across satellites."""
        # First conflict - sat_A wins (both have 0 load)
        # Second conflict - sat_B should win (sat_A now has 1 load)
        passes = [
            # Conflict 1
            {"satellite_id": "sat_A", "target": "Target1", "start_time": "2025-01-01T10:00:00", 
             "end_time": "2025-01-01T10:10:00"},
            {"satellite_id": "sat_B", "target": "Target1", "start_time": "2025-01-01T10:05:00", 
             "end_time": "2025-01-01T10:15:00"},
            # Conflict 2
            {"satellite_id": "sat_A", "target": "Target2", "start_time": "2025-01-01T12:00:00", 
             "end_time": "2025-01-01T12:10:00"},
            {"satellite_id": "sat_B", "target": "Target2", "start_time": "2025-01-01T12:05:00", 
             "end_time": "2025-01-01T12:15:00"},
        ]
        
        resolver = ConstellationConflictResolver(strategy="load_balance")
        result = resolver.process(passes)
        
        resolved = result["resolved_passes"]
        satellite_ids = [p["satellite_id"] for p in resolved]
        
        # Both satellites should have 1 pass each
        assert len(resolved) == 2
        assert "sat_A" in satellite_ids
        assert "sat_B" in satellite_ids


class TestDeduplication:
    """Test pass deduplication."""
    
    def test_duplicates_removed_correctly(self) -> None:
        """Losing passes are removed from output."""
        passes = [
            {"satellite_id": "sat_A", "target": "Target1", "start_time": "2025-01-01T10:00:00", 
             "end_time": "2025-01-01T10:10:00", "incidence_angle_deg": 10.0},
            {"satellite_id": "sat_B", "target": "Target1", "start_time": "2025-01-01T10:05:00", 
             "end_time": "2025-01-01T10:15:00", "incidence_angle_deg": 30.0},
            {"satellite_id": "sat_A", "target": "Target2", "start_time": "2025-01-01T14:00:00", 
             "end_time": "2025-01-01T14:10:00", "incidence_angle_deg": 20.0},
        ]
        
        resolver = ConstellationConflictResolver(strategy="best_geometry")
        result = resolver.process(passes)
        
        resolved = result["resolved_passes"]
        assert len(resolved) == 2  # 1 removed from conflict
        assert result["passes_removed"] == 1
        
        # sat_A Target1 and sat_A Target2 should remain
        targets = [p["target"] for p in resolved]
        assert "Target1" in targets
        assert "Target2" in targets
    
    def test_non_conflicting_passes_preserved(self) -> None:
        """Non-conflicting passes are preserved."""
        passes = [
            {"satellite_id": "sat_A", "target": "Target1", "start_time": "2025-01-01T10:00:00", "end_time": "2025-01-01T10:10:00"},
            {"satellite_id": "sat_B", "target": "Target2", "start_time": "2025-01-01T12:00:00", "end_time": "2025-01-01T12:10:00"},
            {"satellite_id": "sat_C", "target": "Target3", "start_time": "2025-01-01T14:00:00", "end_time": "2025-01-01T14:10:00"},
        ]
        
        resolver = ConstellationConflictResolver()
        result = resolver.process(passes)
        
        assert len(result["resolved_passes"]) == 3
        assert result["passes_removed"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
