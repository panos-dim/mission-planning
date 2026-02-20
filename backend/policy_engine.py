"""
Batch Planning Policy Engine (PS2.5)

Manages planning policies for order batching and scoring.
Policies control how orders are selected, weighted, and planned.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

# Default config path
DEFAULT_POLICY_CONFIG = Path(__file__).parent.parent / "config" / "batch_policies.yaml"


# =============================================================================
# Policy Data Classes
# =============================================================================


@dataclass
class PolicyWeights:
    """Weights for order scoring."""

    priority_weight: float = 1.0
    deadline_weight: float = 0.8
    age_weight: float = 0.3
    quality_weight: float = 0.5

    def to_dict(self) -> Dict[str, float]:
        return {
            "priority_weight": self.priority_weight,
            "deadline_weight": self.deadline_weight,
            "age_weight": self.age_weight,
            "quality_weight": self.quality_weight,
        }


@dataclass
class SelectionRules:
    """Rules for order selection in batches."""

    max_orders_per_batch: int = 50
    horizon_hours: int = 24
    min_priority: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_orders_per_batch": self.max_orders_per_batch,
            "horizon_hours": self.horizon_hours,
            "min_priority": self.min_priority,
        }


@dataclass
class BatchPolicy:
    """Complete batch planning policy."""

    id: str
    name: str
    description: str
    weights: PolicyWeights
    selection_rules: SelectionRules
    repair_preset: str = "Balanced"  # Conservative | Balanced | Aggressive
    planning_mode: str = "incremental"  # incremental | repair

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "weights": self.weights.to_dict(),
            "selection_rules": self.selection_rules.to_dict(),
            "repair_preset": self.repair_preset,
            "planning_mode": self.planning_mode,
        }


# =============================================================================
# Pydantic Models for API
# =============================================================================


class PolicyWeightsModel(BaseModel):
    """API model for policy weights."""

    priority_weight: float = Field(1.0, ge=0, le=5)
    deadline_weight: float = Field(0.8, ge=0, le=5)
    age_weight: float = Field(0.3, ge=0, le=5)
    quality_weight: float = Field(0.5, ge=0, le=5)


class SelectionRulesModel(BaseModel):
    """API model for selection rules."""

    max_orders_per_batch: int = Field(50, ge=1, le=500)
    horizon_hours: int = Field(24, ge=1, le=168)  # Max 1 week
    min_priority: int = Field(1, ge=1, le=5)


class BatchPolicyModel(BaseModel):
    """API model for batch policy."""

    id: str
    name: str
    description: str = ""
    weights: PolicyWeightsModel
    selection_rules: SelectionRulesModel
    repair_preset: str = Field(
        "Balanced", pattern="^(Conservative|Balanced|Aggressive)$"
    )
    planning_mode: str = Field("incremental", pattern="^(incremental|repair)$")


class PolicyListResponse(BaseModel):
    """API response for policy list."""

    policies: List[BatchPolicyModel]
    default_policy: str


# =============================================================================
# Order Scoring
# =============================================================================


@dataclass
class OrderScore:
    """Calculated score for an order."""

    order_id: str
    total_score: float
    priority_score: float
    deadline_score: float
    age_score: float
    quality_score: float
    breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "total_score": round(self.total_score, 3),
            "priority_score": round(self.priority_score, 3),
            "deadline_score": round(self.deadline_score, 3),
            "age_score": round(self.age_score, 3),
            "quality_score": round(self.quality_score, 3),
            "breakdown": {k: round(v, 3) for k, v in self.breakdown.items()},
        }


def calculate_order_score(
    order: Dict[str, Any],
    policy: BatchPolicy,
    reference_time: Optional[datetime] = None,
) -> OrderScore:
    """Calculate score for an order based on policy weights.

    Args:
        order: Order dict with id, priority, due_time, created_at, etc.
        policy: Policy to use for scoring
        reference_time: Reference time for calculations (default: now)

    Returns:
        OrderScore with calculated scores
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    weights = policy.weights
    order_id = order.get("id", "unknown")

    # Priority score (1=best→1.0, 5=lowest→0.0)
    priority = order.get("priority", 5)
    priority_score = (5 - priority) / 4  # Normalize to 0-1

    # Deadline score (urgency based on time to deadline)
    deadline_score = 0.0
    due_time_str = order.get("due_time")
    if due_time_str:
        try:
            due_time = datetime.fromisoformat(due_time_str.replace("Z", "+00:00"))
            if due_time.tzinfo:
                due_time = due_time.replace(tzinfo=None)
            hours_until_due = (due_time - reference_time).total_seconds() / 3600
            if hours_until_due <= 0:
                deadline_score = 1.0  # Overdue
            elif hours_until_due <= 24:
                deadline_score = 1.0 - (hours_until_due / 24)
            elif hours_until_due <= 168:  # 1 week
                deadline_score = 0.5 * (1.0 - (hours_until_due - 24) / 144)
            else:
                deadline_score = 0.0
        except (ValueError, TypeError):
            deadline_score = 0.0

    # Age score (older orders get higher score)
    age_score = 0.0
    created_at_str = order.get("created_at")
    if created_at_str:
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            if created_at.tzinfo:
                created_at = created_at.replace(tzinfo=None)
            hours_old = (reference_time - created_at).total_seconds() / 3600
            # Normalize: orders older than 7 days get max score
            age_score = min(1.0, hours_old / 168)
        except (ValueError, TypeError):
            age_score = 0.0

    # Quality score (from order constraints or default)
    quality_score = 0.5  # Default middle score
    constraints = order.get("constraints", {})
    if constraints:
        # If order has quality constraints, use them
        if "min_quality" in constraints:
            quality_score = constraints["min_quality"]
        elif "quality_preference" in constraints:
            quality_score = constraints["quality_preference"]

    # Calculate weighted total
    total_score = (
        weights.priority_weight * priority_score
        + weights.deadline_weight * deadline_score
        + weights.age_weight * age_score
        + weights.quality_weight * quality_score
    )

    # Normalize total score
    max_possible = (
        weights.priority_weight
        + weights.deadline_weight
        + weights.age_weight
        + weights.quality_weight
    )
    if max_possible > 0:
        total_score = total_score / max_possible

    return OrderScore(
        order_id=order_id,
        total_score=total_score,
        priority_score=priority_score * weights.priority_weight,
        deadline_score=deadline_score * weights.deadline_weight,
        age_score=age_score * weights.age_weight,
        quality_score=quality_score * weights.quality_weight,
        breakdown={
            "priority_raw": priority_score,
            "deadline_raw": deadline_score,
            "age_raw": age_score,
            "quality_raw": quality_score,
        },
    )


def rank_orders(
    orders: List[Dict[str, Any]],
    policy: BatchPolicy,
    reference_time: Optional[datetime] = None,
) -> List[OrderScore]:
    """Rank orders by score based on policy.

    Args:
        orders: List of order dicts
        policy: Policy to use for scoring
        reference_time: Reference time for calculations

    Returns:
        List of OrderScore sorted by total_score descending
    """
    scores = [calculate_order_score(order, policy, reference_time) for order in orders]
    scores.sort(key=lambda s: s.total_score, reverse=True)
    return scores


# =============================================================================
# Policy Manager
# =============================================================================


class PolicyManager:
    """Manages batch planning policies from YAML config."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize policy manager.

        Args:
            config_path: Path to policies YAML file
        """
        self.config_path = config_path or DEFAULT_POLICY_CONFIG
        self._policies: Dict[str, BatchPolicy] = {}
        self._default_policy: str = "default"
        self._load_policies()

    def _load_policies(self) -> None:
        """Load policies from YAML config file."""
        if not self.config_path.exists():
            logger.warning(f"Policy config not found: {self.config_path}")
            self._create_default_policy()
            return

        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f)

            self._default_policy = config.get("default_policy", "default")

            for policy_id, policy_data in config.get("policies", {}).items():
                weights_data = policy_data.get("weights", {})
                selection_data = policy_data.get("selection_rules", {})

                weights = PolicyWeights(
                    priority_weight=weights_data.get("priority_weight", 1.0),
                    deadline_weight=weights_data.get("deadline_weight", 0.8),
                    age_weight=weights_data.get("age_weight", 0.3),
                    quality_weight=weights_data.get("quality_weight", 0.5),
                )

                selection_rules = SelectionRules(
                    max_orders_per_batch=selection_data.get("max_orders_per_batch", 50),
                    horizon_hours=selection_data.get("horizon_hours", 24),
                    min_priority=selection_data.get("min_priority", 1),
                )

                policy = BatchPolicy(
                    id=policy_id,
                    name=policy_data.get("name", policy_id),
                    description=policy_data.get("description", ""),
                    weights=weights,
                    selection_rules=selection_rules,
                    repair_preset=policy_data.get("repair_preset", "Balanced"),
                    planning_mode=policy_data.get("planning_mode", "incremental"),
                )

                self._policies[policy_id] = policy

            logger.info(
                f"Loaded {len(self._policies)} policies from {self.config_path}"
            )

        except Exception as e:
            logger.error(f"Failed to load policies: {e}")
            self._create_default_policy()

    def _create_default_policy(self) -> None:
        """Create a default policy if config is missing."""
        self._policies["default"] = BatchPolicy(
            id="default",
            name="Default Balanced",
            description="Default balanced policy",
            weights=PolicyWeights(),
            selection_rules=SelectionRules(),
        )
        self._default_policy = "default"

    def get_policy(self, policy_id: str) -> Optional[BatchPolicy]:
        """Get a policy by ID.

        Args:
            policy_id: Policy ID

        Returns:
            BatchPolicy or None if not found
        """
        return self._policies.get(policy_id)

    def get_default_policy(self) -> BatchPolicy:
        """Get the default policy.

        Returns:
            Default BatchPolicy
        """
        return self._policies.get(self._default_policy) or self._policies["default"]

    def list_policies(self) -> List[BatchPolicy]:
        """List all available policies.

        Returns:
            List of BatchPolicy objects
        """
        return list(self._policies.values())

    def get_default_policy_id(self) -> str:
        """Get the default policy ID.

        Returns:
            Default policy ID string
        """
        return self._default_policy

    def reload_policies(self) -> None:
        """Reload policies from config file."""
        self._policies.clear()
        self._load_policies()

    def validate_policy_id(self, policy_id: str) -> bool:
        """Check if a policy ID is valid.

        Args:
            policy_id: Policy ID to validate

        Returns:
            True if valid
        """
        return policy_id in self._policies


# =============================================================================
# Global Instance
# =============================================================================

_policy_manager: Optional[PolicyManager] = None


def get_policy_manager() -> PolicyManager:
    """Get the global policy manager instance."""
    global _policy_manager
    if _policy_manager is None:
        _policy_manager = PolicyManager()
    return _policy_manager


def reset_policy_manager(config_path: Optional[Path] = None) -> PolicyManager:
    """Reset the global policy manager instance."""
    global _policy_manager
    _policy_manager = PolicyManager(config_path)
    return _policy_manager
