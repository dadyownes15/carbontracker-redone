from typing import Optional, Literal
from pydantic import BaseModel
from src.core.config import BudgetPolicy
from src.core.prediction import PredictionResult

class GuardVerdict(BaseModel):
    action: Literal["pass", "warn", "stop", "checkpoint_and_stop"]
    reason: Optional[str] = None
    violated_field: Optional[str] = None  # "max_emissions_g", "max_energy_kwh", etc.

class BudgetGuard:
    """Checks predictions against budget policies."""
    
    def __init__(self, policy: BudgetPolicy):
        self.policy = policy
        self._consecutive_violations = 0
    ## TODO (dadyownes15): Extend extend gaurd and policy to include maximum current carbon_intensity  
    def check(self, prediction: PredictionResult) -> GuardVerdict:
        
        energy_kwh = prediction.projected_total_energy_kwh
        emissions_g = prediction.projected_total_emissions_g

        violated_field = None
        reason = None
        
        if self.policy.max_energy_kwh is not None and energy_kwh > self.policy.max_energy_kwh:
            violated_field = "max_energy_kwh"
            reason = f"Predicted energy ({energy_kwh:.2f} kWh) exceeds budget ({self.policy.max_energy_kwh} kWh)"
        elif self.policy.max_emissions_g is not None and emissions_g > self.policy.max_emissions_g:
            violated_field = "max_emissions_g"
            reason = f"Predicted emissions ({emissions_g:.2f} g) exceeds budget ({self.policy.max_emissions_g} g)"
            
        if violated_field:
            self._consecutive_violations += 1
            if self._consecutive_violations >= self.policy.patience:
                return GuardVerdict(action=self.policy.action, reason=reason, violated_field=violated_field)
            else:
                return GuardVerdict(action="pass", reason=f"Violation ({self._consecutive_violations}/{self.policy.patience}): {reason}", violated_field=violated_field)
        
        self._consecutive_violations = 0
        return GuardVerdict(action="pass")
