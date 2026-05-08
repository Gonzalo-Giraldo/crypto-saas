from dataclasses import dataclass

from apps.protection.protection_decision import ProtectionDecision


@dataclass(frozen=True)
class LifecycleDecisionTraceStep:
    evaluator_name: str
    decision: ProtectionDecision


@dataclass(frozen=True)
class LifecycleDecisionTrace:
    current_state: str
    evaluated_steps: tuple[LifecycleDecisionTraceStep, ...]
    final_decision: ProtectionDecision

    @property
    def rejected_steps(self) -> tuple[LifecycleDecisionTraceStep, ...]:
        return tuple(
            step
            for step in self.evaluated_steps
            if not step.decision.allowed
        )

    @property
    def accepted_steps(self) -> tuple[LifecycleDecisionTraceStep, ...]:
        return tuple(
            step
            for step in self.evaluated_steps
            if step.decision.allowed
        )
