from abc import ABC, abstractmethod
from typing import Optional


class ExecutionGuard(ABC):

    # Used for determining when to check. 
    @abstractmethod
    def check_condition(self) -> bool:
        pass
    
    # Check any gaurd conditions, and sends a TrackerEvent. 
    # Use for "None" when check passes
    @abstractmethod
    def check(self) -> Optional[TrackerEvent]:
        pass
