    
# src/frontend/decorator.py

import functools
from typing import Optional, List, Callable, Literal
from src.core.config import SessionConfig, SessionMode, BudgetPolicy
from src.core.engine import CarbonTrackerEngine  # The renamed internal backend

def track(
    project_name: str = "default_run",
    components: List[str] = ["cpu", "gpu", "ram"],
    budget: Optional[BudgetPolicy] = None,
    log_dir: str = "./logs",
    max_intensity: Optional[float] = None,
    max_energy_kwh: Optional[float] = None,
    max_emissions_g: Optional[float] = None,
    max_duration_s: Optional[int] = None,
    callback_on_trigger: Optional[Callable] = None,
    action: Literal["log", "stop", "callback"] = "log",
    patience: int = 2,
    evalaute_on_forecast: bool = False,
    # Any other top-level UX arguments...
):
    """Decorator to track the carbon footprint of a function."""
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            
            config = SessionConfig.from_frontend_args(
                mode=SessionMode.PYTHON_DECORATOR,
                project_name=project_name,
                components=components,
                budget_policy=budget,
                log_dir=log_dir,
            )
            
            engine = CarbonTrackerEngine(config)
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                final_stats = engine.finish()
                
        return wrapper
    return decorator
