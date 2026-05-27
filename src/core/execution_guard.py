from typing import Optional, Literal
from pydantic import BaseModel
from src.config.config import SessionConfig
from src.core.prediction import PredictionResult

class GuardVerdict(BaseModel):
    action: Literal["pass", "warn", "stop", "checkpoint_and_stop", "log", "callback"]
    reason: Optional[str] = None
    violated_field: Optional[str] = None  # "max_emissions_g", "max_energy_kwh", etc.

class BudgetGuard:
    """Checks predictions against budget policies."""
    
    def __init__(self, config: SessionConfig):
        self.config = config
        self._consecutive_violations = 0
        self.patience = 2 # hardcoded patience since it was removed from config

    def check(self, prediction: PredictionResult) -> GuardVerdict:
        
        energy_kwh = prediction.projected_total_energy_kwh
        emissions_g = prediction.projected_total_emissions_g

        violated_field = None
        reason = None
        
        if self.config.max_energy_kwh is not None and energy_kwh > self.config.max_energy_kwh:
            violated_field = "max_energy_kwh"
            reason = f"Predicted energy ({energy_kwh:.2f} kWh) exceeds budget ({self.config.max_energy_kwh} kWh)"
        elif self.config.max_emissions_g is not None and emissions_g > self.config.max_emissions_g:
            violated_field = "max_emissions_g"
            reason = f"Predicted emissions ({emissions_g:.2f} g) exceeds budget ({self.config.max_emissions_g} g)"
            
        if violated_field:
            self._consecutive_violations += 1
            if self._consecutive_violations >= self.patience:
                # Map breach action to Literal string expected by GuardVerdict
                action_str = self.config.action_on_breach.value if hasattr(self.config.action_on_breach, 'value') else self.config.action_on_breach
                return GuardVerdict(action=action_str, reason=reason, violated_field=violated_field)
            else:
                return GuardVerdict(action="pass", reason=f"Violation ({self._consecutive_violations}/{self.patience}): {reason}", violated_field=violated_field)
        
        self._consecutive_violations = 0
        return GuardVerdict(action="pass")
