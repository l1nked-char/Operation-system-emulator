import sys
from queue import Queue
from collections import deque
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import time


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
    burst_time: float
    arrival_time: float = 0.0
    priority: int = 1
    absolute_priority: bool = False  # Флаг абсолютного приоритета
    remaining_time: float = field(init=False)
    state: ProcessState = ProcessState.READY
    start_time: Optional[float] = None
    completion_time: Optional[float] = None
    current_queue: int = 0  # Очередь, в которой находится процесс
    quantum_used: float = 0.0  # Сколько времени использовано в текущем кванте

    def __post_init__(self):
        self.remaining_time = self.burst_time

    def __str__(self):
        return (f"PID: {self.pid:3} | Имя: {self.name:10} | "
                f"Состояние: {self.state.value:12} | Очередь: {self.current_queue} | "
                f"Абсолютный: {'Да' if self.absolute_priority else 'Нет'} | "
                f"Осталось: {self.remaining_time:.1f}/{self.burst_time:.1f}")


class ProcessQueue:
    """Класс-обертка для очереди процессов с дополнительной функциональностью"""

    def __init__(self, queue_id: int, quantum: float = float('inf')):
        self.queue = Queue()
        self.queue_id = queue_id
        self.quantum = quantum
        self.process_list = []  # Для отображения содержимого без удаления

    def put(self, process: Process):
        """Добавление процесса в очередь"""
        process.current_queue = self.queue_id
        process.state = ProcessState.READY
        self.queue.put(process)
        self.process_list.append(process)

    def get(self) -> Optional[Process]:
        """Получение процесса из очереди"""
        if not self.queue.empty():
            process = self.queue.get()
            # Удаляем из списка для отображения
            self.process_list = [p for p in self.process_list if p.pid != process.pid]
            return process
        return None

    def get_nowait(self) -> Optional[Process]:
        """Получение процесса без ожидания"""
        try:
            process = self.queue.get_nowait()
            self.process_list = [p for p in self.process_list if p.pid != process.pid]
            return process
        except:
            return None

    def empty(self) -> bool:
        """Проверка на пустоту"""
        return self.queue.empty()

    def qsize(self) -> int:
        """Размер очереди"""
        return self.queue.qsize()

    def __bool__(self):
        """Преобразование в bool"""
        return not self.empty()

    def __len__(self):
        """Длина очереди"""
        return self.qsize()


class MultilevelFeedbackQueueScheduler:
    """Многоуровневый планировщик с обратной связью"""

    def __init__(self, quantum_times: List[float] = None):
        # Очереди: 0 - высший приоритет, 1 - средний, 2 - низший
        self.queues = [
            ProcessQueue(0, quantum_times[0] if quantum_times else 2.0),
            ProcessQueue(1, quantum_times[1] if quantum_times else 4.0),
            ProcessQueue(2, quantum_times[2] if quantum_times and len(quantum_times) > 2 else float('inf'))
        ]

        # Отдельная очередь для абсолютных приоритетов
        self.absolute_queue = deque()

        # Все процессы для отслеживания
        self.all_processes = []

        # Время квантов для каждой очереди
        self.quantum_times = quantum_times or [2.0, 4.0, float('inf')]

        # Текущие параметры
        self.current_time = 0.0
        self.current_process: Optional[Process] = None
        self.pid_counter = 1
        self.running = False

        # Статистика
        self.total_context_switches = 0

    def add_process(self, name: str, burst_time: float,
                    arrival_time: float = 0.0, priority: int = 1,
                    absolute_priority: bool = False):
        """Добавление нового процесса"""
        if arrival_time < self.current_time:
            arrival_time = self.current_time

        process = Process(
            pid=self.pid_counter,
            name=name,
            arrival_time=arrival_time,
            burst_time=burst_time,
            priority=priority,
            absolute_priority=absolute_priority
        )

        self.pid_counter += 1

        # Добавляем в соответствующую очередь
        if absolute_priority:
            self.absolute_queue.append(process)
            print(f"\n[!] Добавлен процесс с АБСОЛЮТНЫМ приоритетом: {process.name}")
        else:
            self.queues[0].put(process)
            print(f"\n[+] Добавлен процесс: {process.name}")

        self.all_processes.append(process)
        return process

    def get_next_process(self) -> Optional[Process]:
        """Получение следующего процесса для выполнения"""
        # 1. Проверяем очередь абсолютных приоритетов
        if self.absolute_queue:
            process = self.absolute_queue[0]
            return process

        # 2. Ищем процесс в очередях по приоритету
        for i in range(3):
            if not self.queues[i].empty():
                # Получаем процесс из очереди
                process = self.queues[i].get_nowait()
                if process:
                    return process

        return None

    def preempt_current_process(self, new_process: Process):
        """Вытеснение текущего процесса"""
        if not self.current_process:
            return

        print(f"\n[!] Вытеснение процесса {self.current_process.name} "
              f"процессом {new_process.name}")

        # Сохраняем состояние вытесненного процесса
        self.current_process.state = ProcessState.READY

        # Сбрасываем счетчик кванта для вытесненного процесса
        self.current_process.quantum_used = 0.0

        # Возвращаем в соответствующую очередь
        if self.current_process.absolute_priority:
            self.absolute_queue.append(self.current_process)
        else:
            queue_idx = self.current_process.current_queue
            # Если процесс был вытеснен во время выполнения кванта,
            # возвращаем его в ту же очередь
            self.queues[queue_idx].put(self.current_process)

        # Увеличиваем счетчик переключений
        self.total_context_switches += 1

    def execute_time_slice(self, time_slice: float = 1.0):
        """Выполнение одного кванта времени"""
        # Проверяем, нужно ли переключить процесс из-за абсолютного приоритета
        if self.absolute_queue and self.current_process:
            next_absolute = self.absolute_queue[0]
            if next_absolute != self.current_process and not self.current_process.absolute_priority:
                # Вытесняем текущий процесс
                self.preempt_current_process(next_absolute)
                # Удаляем абсолютный процесс из очереди
                self.absolute_queue.popleft()
                # Начинаем выполнение абсолютного процесса
                self.current_process = next_absolute
                self.current_process.state = ProcessState.RUNNING
                if self.current_process.start_time is None:
                    self.current_process.start_time = self.current_time
                print(f"\n[→] Начинает выполняться АБСОЛЮТНЫЙ процесс: {self.current_process.name}")
                self.total_context_switches += 1

        # Если нет текущего процесса, получаем следующий
        if not self.current_process:
            next_process = self.get_next_process()
            if next_process:
                self.current_process = next_process
                self.current_process.state = ProcessState.RUNNING
                if self.current_process.start_time is None:
                    self.current_process.start_time = self.current_time
                print(f"\n[→] Начинает выполняться: {self.current_process.name} "
                      f"(очередь: {self.current_process.current_queue})")
                self.total_context_switches += 1

        # Выполняем текущий процесс
        if self.current_process:
            # Определяем доступное время выполнения
            if self.current_process.absolute_priority:
                # Для абсолютных приоритетов используем бесконечный квант
                quantum = float('inf')
                queue_idx = 2  # Для отображения в статистике
            else:
                queue_idx = self.current_process.current_queue
                quantum = self.quantum_times[queue_idx] if queue_idx < 2 else float('inf')

            # Сколько времени осталось в текущем кванте
            time_left_in_quantum = quantum - self.current_process.quantum_used

            # Выполняем минимальное из: кванта, оставшегося времени и общего среза
            exec_time = min(time_slice, time_left_in_quantum,
                            self.current_process.remaining_time)

            # Имитация выполнения
            time.sleep(0.3)
            self.current_time += exec_time
            self.current_process.remaining_time -= exec_time
            self.current_process.quantum_used += exec_time

            print(f"[+] Выполнено {exec_time:.1f} для {self.current_process.name}")
            print(f"    Осталось времени: {self.current_process.remaining_time:.1f}, "
                  f"использовано кванта: {self.current_process.quantum_used:.1f}/{quantum if quantum != float('inf') else '∞'}")

            # Проверяем завершение процесса
            if self.current_process.remaining_time <= 0:
                self.current_process.state = ProcessState.TERMINATED
                self.current_process.completion_time = self.current_time
                print(f"\n[✓] Процесс {self.current_process.name} завершен!")
                self.current_process = None
                return

            # Проверяем исчерпание кванта (только для RR очередей 0 и 1)
            if not self.current_process.absolute_priority:
                queue_idx = self.current_process.current_queue
                if queue_idx < 2 and self.current_process.quantum_used >= self.quantum_times[queue_idx]:
                    # Перемещаем процесс в следующую очередь
                    self.move_to_next_queue()
                    return

    def move_to_next_queue(self):
        """Перемещение процесса в следующую очередь"""
        if not self.current_process or self.current_process.absolute_priority:
            return

        current_queue = self.current_process.current_queue

        if current_queue < 2:  # Если это не последняя очередь
            next_queue = current_queue + 1
            self.current_process.current_queue = next_queue
            self.current_process.quantum_used = 0.0
            self.current_process.state = ProcessState.READY

            print(f"\n[↓] Процесс {self.current_process.name} перемещен "
                  f"из очереди {current_queue} в очередь {next_queue}")

            # Возвращаем процесс в конец новой очереди
            self.queues[next_queue].put(self.current_process)
            self.current_process = None

            self.total_context_switches += 1

    def display_status(self):
        """Отображение статуса всех процессов"""
        print("\n" + "=" * 90)
        print(f"Текущее время: {self.current_time:.1f}")
        print(f"Текущий процесс: {self.current_process.name if self.current_process else 'Нет'}")
        if self.current_process:
            if self.current_process.absolute_priority:
                print(f"  Тип: АБСОЛЮТНЫЙ приоритет, Квант: ∞")
            else:
                queue_idx = self.current_process.current_queue
                quantum = self.quantum_times[queue_idx] if queue_idx < 2 else "∞"
                print(f"  Очередь: {queue_idx}, Квант: {quantum}")
        print(f"Переключений контекста: {self.total_context_switches}")
        print("=" * 90)

        # Группируем по состояниям
        by_state = {}
        for state in ProcessState:
            by_state[state] = [p for p in self.all_processes if p.state == state]

        for state, procs in by_state.items():
            if procs:
                print(f"\n{state.value}:")
                for process in procs:
                    print(f"  {process}")

        # Отображаем содержимое очередей
        print("\n" + "-" * 90)
        print("ОЧЕРЕДИ:")

        # Абсолютная очередь
        print(f"\nАбсолютная очередь (приоритет ∞, квант: ∞):")
        if self.absolute_queue:
            for i, process in enumerate(self.absolute_queue):
                print(f"  {i + 1}. {process.name} (PID: {process.pid}) - "
                      f"осталось: {process.remaining_time:.1f}")
        else:
            print("  Пусто")

        # Обычные очереди
        for i, queue in enumerate(self.queues):
            quantum = self.quantum_times[i] if i < 2 else "FCFS"
            print(f"\nОчередь {i} (приоритет {i}, квант: {quantum}):")
            if queue.process_list:
                for j, process in enumerate(queue.process_list):
                    queue_type = "RR" if i < 2 else "FCFS"
                    print(f"  {j + 1}. {process.name} (PID: {process.pid}) - "
                          f"осталось: {process.remaining_time:.1f}, "
                          f"исп. кванта: {process.quantum_used:.1f}")
            else:
                print("  Пусто")

        print("=" * 90)

    def run_simulation(self, steps: int = 30):
        """Запуск симуляции"""
        self.running = True

        print("\n" + "=" * 90)
        print("ЗАПУСК СИМУЛЯЦИИ МНОГОУРОВНЕВОГО ПЛАНИРОВЩИКА")
        print("=" * 90)
        print("Алгоритм:")
        print("  1. Процессы начинают в очереди 0 (RR, квант=2)")
        print("  2. Если не укладываются - переходят в очередь 1 (RR, квант=4)")
        print("  3. Если снова не укладываются - переходят в очередь 2 (FCFS)")
        print("  4. Процессы с абсолютным приоритетом выполняются немедленно")
        print("  5. При появлении абсолютного процесса текущий вытесняется")
        print("=" * 90)

        for step in range(steps):
            if not self.running:
                break

            print(f"\nШаг {step + 1}:")
            self.display_status()

            # Проверяем, есть ли процессы для выполнения
            has_processes = (any(not q.empty() for q in self.queues) or
                             self.absolute_queue or self.current_process)
            if not has_processes:
                print("\n[✓] Все процессы завершены!")
                break

            # Выполняем квант времени
            self.execute_time_slice()

            # Пауза между шагами
            if step < steps - 1:
                input("\nНажмите Enter для следующего шага...")

        # Вывод статистики
        self.display_final_statistics()

    def display_final_statistics(self):
        """Отображение финальной статистики"""
        print("\n" + "=" * 90)
        print("ФИНАЛЬНАЯ СТАТИСТИКА")
        print("=" * 90)

        # Собираем завершенные процессы
        completed_processes = [p for p in self.all_processes if p.completion_time]

        if completed_processes:
            total_turnaround = 0
            total_waiting = 0

            for process in completed_processes:
                turnaround = process.completion_time - process.arrival_time
                waiting = turnaround - process.burst_time
                total_turnaround += turnaround
                total_waiting += waiting

                print(f"\n{process.name}:")
                print(f"  Время выполнения: {process.burst_time:.1f}")
                print(f"  Оборотное время: {turnaround:.1f}")
                print(f"  Время ожидания: {waiting:.1f}")
                print(f"  Финальная очередь: {process.current_queue}")
                if process.absolute_priority:
                    print(f"  Тип: Абсолютный приоритет")

            avg_turnaround = total_turnaround / len(completed_processes)
            avg_waiting = total_waiting / len(completed_processes)
            print(f"\nСреднее оборотное время: {avg_turnaround:.2f}")
            print(f"Среднее время ожидания: {avg_waiting:.2f}")

        # Незавершенные процессы
        pending = [p for p in self.all_processes if not p.completion_time]
        if pending:
            print(f"\nНезавершенные процессы: {len(pending)}")
            for process in pending:
                print(f"  {process.name} - осталось: {process.remaining_time:.1f}")

        print(f"\nВсего переключений контекста: {self.total_context_switches}")
        print("=" * 90)


def create_demo_processes(scheduler):
    """Создание демонстрационных процессов"""
    print("\nСоздание демонстрационных процессов...")

    # Обычные процессы
    scheduler.add_process("System", 6.0, 0.0, 1)
    scheduler.add_process("Editor", 4.0, 1.0, 2)
    scheduler.add_process("Browser", 8.0, 2.0, 3)

    # Процесс с абсолютным приоритетом (прибудет позже)
    scheduler.add_process("Emergency", 3.0, 5.0, 0, absolute_priority=True)

    # Еще обычные процессы
    scheduler.add_process("Player", 5.0, 3.0, 2)
    scheduler.add_process("Calc", 2.0, 4.0, 1)


def main():
    """Основная функция"""
    print("МНОГОУРОВНЕВЫЙ ПЛАНИРОВЩИК С ОБРАТНОЙ СВЯЗЬЮ")
    print("=" * 90)
    print("Алгоритм работы:")
    print("  • Очередь 0: Round Robin, квант = 2")
    print("  • Очередь 1: Round Robin, квант = 4")
    print("  • Очередь 2: FCFS (без квантования)")
    print("  • Абсолютная очередь: наивысший приоритет, немедленное выполнение")
    print("=" * 90)

    # Создаем планировщик с заданными квантами
    scheduler = MultilevelFeedbackQueueScheduler(quantum_times=[2.0, 4.0, float('inf')])

    # Добавляем демонстрационные процессы
    create_demo_processes(scheduler)

    # Запускаем симуляцию
    try:
        scheduler.run_simulation(steps=30)
    except KeyboardInterrupt:
        print("\n\n[!] Симуляция прервана пользователем")
        scheduler.display_final_statistics()

    input("\nНажмите Enter для завершения...")


if __name__ == "__main__":
    main()