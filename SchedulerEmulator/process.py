from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ProcessState(Enum):
    """Состояния процесса"""
    READY = "Готов"
    RUNNING = "Выполняется"
    WAITING = "Ожидание"
    TERMINATED = "Завершен"


@dataclass
class Process:
    """Класс для представления процесса"""
    pid: int
    name: str
    arrival_time: float
    burst_time: float
    priority: int = 1
    remaining_time: float = field(init=False)
    state: ProcessState = ProcessState.READY
    start_time: Optional[float] = None
    completion_time: Optional[float] = None
    dynamic_priority: int = field(init=False)

    def __post_init__(self):
        self.remaining_time = self.burst_time
        self.dynamic_priority = self.priority

    def __str__(self):
        return (f"PID: {self.pid:3} | Имя: {self.name:10} | "
                f"Состояние: {self.state.value:12} | "
                f"Приоритет: {self.priority:2} (динамический: {self.dynamic_priority:2}) | "
                f"Осталось: {self.remaining_time:.1f}/{self.burst_time:.1f}")