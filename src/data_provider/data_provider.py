
from abc import abstractmethod
from typing import Generic
from typing_extensions import TypeVar

T = TypeVar('T')
class DataProvider(Generic[T]):
    @abstractmethod
    def fetch(self) -> T:
        pass
        
    @abstractmethod
    def shutdown(self):
        pass