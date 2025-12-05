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


class PriorityType(Enum):
    """Типы приоритетов"""
    RELATIVE = "Относительный"  # Задается статически, сравнивается с другими
    DYNAMIC = "Динамический"  # Изменяется системой в зависимости от поведения
    ABSOLUTE = "Абсолютный"  # Наивысший, вытесняет любые другие процессы


@dataclass
class Process:
    """Класс для представления процесса"""
    pid: int
    name: str
    burst_time: float
    arrival_time: float = 0.0

    # Приоритеты
    relative_priority: int = 1  # Относительный приоритет (1-10, где 1 - высший)
    dynamic_priority: int = field(init=False)  # Динамический приоритет
    priority_type: PriorityType = PriorityType.RELATIVE

    # Внутренние поля
    remaining_time: float = field(init=False)
    state: ProcessState = ProcessState.READY
    start_time: Optional[float] = None
    completion_time: Optional[float] = None
    current_queue: int = 0  # Очередь, в которой находится процесс
    quantum_used: float = 0.0  # Сколько времени использовано в текущем кванте
    last_cpu_burst: float = 0.0  # Последний отрезок времени на CPU
    total_cpu_time: float = 0.0  # Общее время на CPU
    waiting_time: float = 0.0  # Время ожидания
    times_executed: int = 0  # Сколько раз процесс получал CPU

    def __post_init__(self):
        self.remaining_time = self.burst_time
        self.dynamic_priority = self.relative_priority

    def __str__(self):
        priority_str = f"{self.priority_type.value}: "
        if self.priority_type == PriorityType.RELATIVE:
            priority_str += f"{self.relative_priority}"
        elif self.priority_type == PriorityType.DYNAMIC:
            priority_str += f"{self.dynamic_priority} (отн: {self.relative_priority})"
        else:
            priority_str += "∞"

        return (f"PID: {self.pid:3} | Имя: {self.name:10} | "
                f"Состояние: {self.state.value:12} | Очередь: {self.current_queue} | "
                f"Приоритет: {priority_str} | "
                f"Осталось: {self.remaining_time:.1f}/{self.burst_time:.1f}")


class ProcessQueue:
    """Класс-обертка для очереди процессов с поддержкой приоритетов"""

    def __init__(self, queue_id: int, quantum: float = float('inf'), algorithm: str = "RR"):
        self.queue = Queue()
        self.queue_id = queue_id
        self.quantum = quantum
        self.algorithm = algorithm  # "RR" или "FCFS"
        self.process_list = []  # Для отображения содержимого без удаления

    def put(self, process: Process):
        """Добавление процесса в очередь"""
        process.current_queue = self.queue_id
        process.state = ProcessState.READY

        # Для FCFS просто добавляем в конец
        if self.algorithm == "FCFS":
            self.queue.put(process)
            self.process_list.append(process)
        # Для RR учитываем динамические приоритеты при добавлении
        else:
            # Создаем кортеж для сравнения (приоритет, время поступления, процесс)
            priority_key = process.dynamic_priority
            self.queue.put((priority_key, process.arrival_time, process))
            self.process_list.append(process)

    def get(self) -> Optional[Process]:
        """Получение процесса из очереди"""
        if self.queue.empty():
            return None

        if self.algorithm == "FCFS":
            process = self.queue.get()
            self.process_list = [p for p in self.process_list if p.pid != process.pid]
            return process
        else:
            # Для RR с динамическими приоритетами используем приоритетную очередь
            # В реальной реализации нужно перебрать все элементы, чтобы найти с наивысшим приоритетом
            # Для простоты берем первый
            try:
                # Преобразуем очередь в список для поиска наивысшего приоритета
                items = []
                while not self.queue.empty():
                    items.append(self.queue.get())

                # Находим элемент с наивысшим приоритетом (наименьшее значение)
                if items:
                    items.sort(key=lambda x: (x[0], x[1]))  # Сортируем по приоритету, затем по времени прибытия
                    _, _, process = items[0]

                    # Возвращаем остальные элементы обратно в очередь
                    for item in items[1:]:
                        self.queue.put(item)

                    self.process_list = [p for p in self.process_list if p.pid != process.pid]
                    return process
            except Exception as e:
                print(f"Ошибка при получении процесса: {e}")

        return None

    def get_nowait(self) -> Optional[Process]:
        """Получение процесса без ожидания"""
        return self.get()

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
    """Многоуровневый планировщик с обратной связью и поддержкой трех типов приоритетов"""

    def __init__(self, quantum_times: List[float] = None):
        # Очереди: 0 - высший приоритет, 1 - средний, 2 - низший
        self.queues = [
            ProcessQueue(0, quantum_times[0] if quantum_times else 2.0, "RR"),
            ProcessQueue(1, quantum_times[1] if quantum_times else 4.0, "RR"),
            ProcessQueue(2, quantum_times[2] if quantum_times and len(quantum_times) > 2 else float('inf'), "FCFS")
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
        self.last_update_time = 0.0  # Время последнего обновления динамических приоритетов

        # Статистика
        self.total_context_switches = 0
        self.scheduling_events = []  # История событий планирования

    def update_dynamic_priorities(self):
        """Обновление динамических приоритетов всех процессов"""
        current_time = self.current_time
        time_since_last_update = current_time - self.last_update_time

        if time_since_last_update >= 1.0:  # Обновляем каждую единицу времени
            for process in self.all_processes:
                if process.state == ProcessState.READY:
                    # Увеличиваем динамический приоритет для процессов в ожидании
                    # (чтобы избежать голодания)
                    process.dynamic_priority = max(1, process.dynamic_priority - 1)
                elif process.state == ProcessState.RUNNING:
                    # Снижаем приоритет выполняющимся процессам
                    process.dynamic_priority = min(10, process.dynamic_priority + 1)

            self.last_update_time = current_time
            return True
        return False

    def calculate_priority(self, process: Process) -> int:
        """Вычисление приоритета процесса для планирования"""
        if process.priority_type == PriorityType.ABSOLUTE:
            return -1  # Наивысший приоритет (отрицательное значение)
        elif process.priority_type == PriorityType.DYNAMIC:
            # Комбинируем относительный и динамический приоритеты
            base_priority = process.relative_priority
            # Учитываем время ожидания (чем дольше ждет, тем выше приоритет)
            if process.state == ProcessState.READY:
                waiting_boost = int(process.waiting_time / 2)  # Увеличение за время ожидания
            else:
                waiting_boost = 0

            # Учитываем выполнение (чем больше выполнился, тем ниже приоритет)
            execution_penalty = int(process.total_cpu_time / 3)

            dynamic_priority = max(1, min(10, base_priority - waiting_boost + execution_penalty))
            process.dynamic_priority = dynamic_priority
            return dynamic_priority
        else:  # RELATIVE
            return process.relative_priority

    def add_process(self, name: str, burst_time: float,
                    arrival_time: float = 0.0,
                    relative_priority: int = 1,
                    priority_type: PriorityType = PriorityType.RELATIVE):
        """Добавление нового процесса"""
        if arrival_time < self.current_time:
            arrival_time = self.current_time

        process = Process(
            pid=self.pid_counter,
            name=name,
            arrival_time=arrival_time,
            burst_time=burst_time,
            relative_priority=relative_priority,
            priority_type=priority_type
        )

        self.pid_counter += 1

        # Добавляем в соответствующую очередь
        if priority_type == PriorityType.ABSOLUTE:
            self.absolute_queue.append(process)
            print(f"\n[!] Добавлен процесс с АБСОЛЮТНЫМ приоритетом: {process.name}")
        else:
            self.queues[0].put(process)
            print(f"\n[+] Добавлен процесс: {process.name} ({priority_type.value})")

        self.all_processes.append(process)
        self.scheduling_events.append({
            'time': self.current_time,
            'event': f'Добавлен процесс {process.name}',
            'process': process
        })

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
                    # Обновляем приоритет для динамических процессов
                    if process.priority_type == PriorityType.DYNAMIC:
                        self.calculate_priority(process)
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

        # Обновляем статистику вытесненного процесса
        self.current_process.times_executed += 1

        # Сбрасываем счетчик кванта для вытесненного процесса
        self.current_process.quantum_used = 0.0

        # Возвращаем в соответствующую очередь
        if self.current_process.priority_type == PriorityType.ABSOLUTE:
            self.absolute_queue.append(self.current_process)
        else:
            queue_idx = self.current_process.current_queue
            self.queues[queue_idx].put(self.current_process)

        # Увеличиваем счетчик переключений
        self.total_context_switches += 1

        self.scheduling_events.append({
            'time': self.current_time,
            'event': f'Вытеснение {self.current_process.name} процессом {new_process.name}',
            'preempted': self.current_process,
            'new': new_process
        })

    def execute_time_slice(self, time_slice: float = 1.0):
        """Выполнение одного кванта времени"""
        # Обновляем динамические приоритеты
        self.update_dynamic_priorities()

        # Обновляем время ожидания для всех готовых процессов
        for process in self.all_processes:
            if process.state == ProcessState.READY:
                process.waiting_time += time_slice

        # Проверяем, нужно ли переключить процесс из-за абсолютного приоритета
        if self.absolute_queue and self.current_process:
            next_absolute = self.absolute_queue[0]
            if (next_absolute != self.current_process and
                    self.current_process.priority_type != PriorityType.ABSOLUTE):
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
                self.scheduling_events.append({
                    'time': self.current_time,
                    'event': f'Начало выполнения абсолютного процесса {self.current_process.name}',
                    'process': self.current_process
                })

        # Если нет текущего процесса, получаем следующий
        if not self.current_process:
            next_process = self.get_next_process()
            if next_process:
                self.current_process = next_process
                self.current_process.state = ProcessState.RUNNING
                if self.current_process.start_time is None:
                    self.current_process.start_time = self.current_time

                # Обновляем динамический приоритет при получении CPU
                if self.current_process.priority_type == PriorityType.DYNAMIC:
                    # Повышаем приоритет при получении CPU после ожидания
                    self.current_process.dynamic_priority = max(
                        1, self.current_process.dynamic_priority - 2
                    )

                print(f"\n[→] Начинает выполняться: {self.current_process.name} "
                      f"(очередь: {self.current_process.current_queue}, "
                      f"приоритет: {self.current_process.priority_type.value})")
                self.total_context_switches += 1
                self.scheduling_events.append({
                    'time': self.current_time,
                    'event': f'Начало выполнения {self.current_process.name}',
                    'process': self.current_process
                })

        # Выполняем текущий процесс
        if self.current_process:
            # Определяем доступное время выполнения
            if self.current_process.priority_type == PriorityType.ABSOLUTE:
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
            self.current_process.total_cpu_time += exec_time
            self.current_process.last_cpu_burst = exec_time

            print(f"[+] Выполнено {exec_time:.1f} для {self.current_process.name}")
            print(f"    Осталось времени: {self.current_process.remaining_time:.1f}, "
                  f"использовано кванта: {self.current_process.quantum_used:.1f}/{quantum if quantum != float('inf') else '∞'}")

            # Проверяем завершение процесса
            if self.current_process.remaining_time <= 0:
                self.current_process.state = ProcessState.TERMINATED
                self.current_process.completion_time = self.current_time
                print(f"\n[✓] Процесс {self.current_process.name} завершен!")
                self.scheduling_events.append({
                    'time': self.current_time,
                    'event': f'Завершение процесса {self.current_process.name}',
                    'process': self.current_process
                })
                self.current_process = None
                return

            # Проверяем исчерпание кванта (только для RR очередей 0 и 1)
            if self.current_process.priority_type != PriorityType.ABSOLUTE:
                queue_idx = self.current_process.current_queue
                if queue_idx < 2 and self.current_process.quantum_used >= self.quantum_times[queue_idx]:
                    # Обновляем динамический приоритет для исчерпавших квант
                    if self.current_process.priority_type == PriorityType.DYNAMIC:
                        self.current_process.dynamic_priority = min(
                            10, self.current_process.dynamic_priority + 1
                        )

                    # Перемещаем процесс в следующую очередь
                    self.move_to_next_queue()
                    return

    def move_to_next_queue(self):
        """Перемещение процесса в следующую очередь"""
        if not self.current_process or self.current_process.priority_type == PriorityType.ABSOLUTE:
            return

        current_queue = self.current_process.current_queue

        if current_queue < 2:  # Если это не последняя очередь
            next_queue = current_queue + 1
            self.current_process.current_queue = next_queue
            self.current_process.quantum_used = 0.0
            self.current_process.state = ProcessState.READY
            self.current_process.times_executed += 1

            print(f"\n[↓] Процесс {self.current_process.name} перемещен "
                  f"из очереди {current_queue} в очередь {next_queue}")

            # Возвращаем процесс в конец новой очереди
            self.queues[next_queue].put(self.current_process)
            self.scheduling_events.append({
                'time': self.current_time,
                'event': f'Перемещение {self.current_process.name} из очереди {current_queue} в {next_queue}',
                'process': self.current_process
            })
            self.current_process = None

            self.total_context_switches += 1

    def display_status(self):
        """Отображение статуса всех процессов"""
        print("\n" + "=" * 100)
        print(f"Текущее время: {self.current_time:.1f}")
        print(f"Текущий процесс: {self.current_process.name if self.current_process else 'Нет'}")
        if self.current_process:
            if self.current_process.priority_type == PriorityType.ABSOLUTE:
                print(f"  Тип: АБСОЛЮТНЫЙ приоритет, Квант: ∞")
            else:
                queue_idx = self.current_process.current_queue
                quantum = self.quantum_times[queue_idx] if queue_idx < 2 else "∞"
                print(f"  Очередь: {queue_idx}, Квант: {quantum}, "
                      f"Приоритет: {self.current_process.priority_type.value}")
        print(f"Переключений контекста: {self.total_context_switches}")
        print("=" * 100)

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
        print("\n" + "-" * 100)
        print("ОЧЕРЕДИ:")

        # Абсолютная очередь
        print(f"\nАбсолютная очередь (приоритет ∞, квант: ∞):")
        if self.absolute_queue:
            for i, process in enumerate(self.absolute_queue):
                print(f"  {i + 1}. {process.name} (PID: {process.pid}) - "
                      f"осталось: {process.remaining_time:.1f}, "
                      f"время ожидания: {process.waiting_time:.1f}")
        else:
            print("  Пусто")

        # Обычные очереди
        for i, queue in enumerate(self.queues):
            quantum = self.quantum_times[i] if i < 2 else "FCFS"
            print(f"\nОчередь {i} (приоритет {i}, квант: {quantum}, алгоритм: {queue.algorithm}):")
            if queue.process_list:
                # Сортируем для отображения по приоритету
                sorted_procs = sorted(queue.process_list,
                                      key=lambda p: (p.dynamic_priority if p.priority_type == PriorityType.DYNAMIC
                                                     else p.relative_priority))
                for j, process in enumerate(sorted_procs):
                    priority_info = ""
                    if process.priority_type == PriorityType.DYNAMIC:
                        priority_info = f"дин: {process.dynamic_priority}"
                    elif process.priority_type == PriorityType.RELATIVE:
                        priority_info = f"отн: {process.relative_priority}"

                    print(f"  {j + 1}. {process.name} (PID: {process.pid}) - "
                          f"осталось: {process.remaining_time:.1f}, "
                          f"исп. кванта: {process.quantum_used:.1f}, "
                          f"приоритет: {priority_info}")
            else:
                print("  Пусто")

        print("=" * 100)

    def display_priority_info(self):
        """Отображение информации о приоритетах"""
        print("\n" + "=" * 100)
        print("ИНФОРМАЦИЯ О ПРИОРИТЕТАХ")
        print("=" * 100)
        print("Типы приоритетов:")
        print("  1. АБСОЛЮТНЫЙ - наивысший приоритет, вытесняет любые другие процессы")
        print("  2. ОТНОСИТЕЛЬНЫЙ - статический приоритет, задается при создании")
        print("  3. ДИНАМИЧЕСКИЙ - изменяется системой в зависимости от поведения процесса")
        print("\nПравила изменения динамических приоритетов:")
        print("  - Увеличивается при длительном использовании CPU")
        print("  - Уменьшается при длительном ожидании")
        print("  - Увеличивается при исчерпании кванта времени")
        print("  - Уменьшается при получении CPU после ожидания")
        print("=" * 100)

    def run_simulation(self, steps: int = 30):
        """Запуск симуляции"""
        self.running = True

        print("\n" + "=" * 100)
        print("ЗАПУСК СИМУЛЯЦИИ МНОГОУРОВНЕВОГО ПЛАНИРОВЩИКА")
        print("=" * 100)
        print("Алгоритм:")
        print("  1. Процессы начинают в очереди 0 (RR, квант=2)")
        print("  2. Если не укладываются - переходят в очередь 1 (RR, квант=4)")
        print("  3. Если снова не укладываются - переходят в очередь 2 (FCFS)")
        print("  4. Процессы с абсолютным приоритетом выполняются немедленно")
        print("  5. Три типа приоритетов: абсолютные, относительные, динамические")
        print("=" * 100)

        self.display_priority_info()

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
        print("\n" + "=" * 100)
        print("ФИНАЛЬНАЯ СТАТИСТИКА")
        print("=" * 100)

        # Собираем завершенные процессы
        completed_processes = [p for p in self.all_processes if p.completion_time]
        pending_processes = [p for p in self.all_processes if not p.completion_time]

        if completed_processes:
            total_turnaround = 0
            total_waiting = 0

            print("\nЗавершенные процессы:")
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
                print(f"  Тип приоритета: {process.priority_type.value}")
                if process.priority_type == PriorityType.DYNAMIC:
                    print(f"  Финальный динамический приоритет: {process.dynamic_priority}")
                print(f"  Всего выполнений: {process.times_executed}")

            avg_turnaround = total_turnaround / len(completed_processes)
            avg_waiting = total_waiting / len(completed_processes)
            print(f"\nСреднее оборотное время: {avg_turnaround:.2f}")
            print(f"Среднее время ожидания: {avg_waiting:.2f}")

        # Незавершенные процессы
        if pending_processes:
            print(f"\nНезавершенные процессы: {len(pending_processes)}")
            for process in pending_processes:
                print(f"  {process.name} - осталось: {process.remaining_time:.1f}, "
                      f"очередь: {process.current_queue}, "
                      f"приоритет: {process.priority_type.value}")

        print(f"\nВсего переключений контекста: {self.total_context_switches}")
        print(f"Всего событий планирования: {len(self.scheduling_events)}")
        print("=" * 100)

        # История событий
        print("\nПоследние 10 событий планирования:")
        for event in self.scheduling_events[-10:]:
            print(f"  Время {event['time']:.1f}: {event['event']}")


def create_demo_processes(scheduler):
    """Создание демонстрационных процессов с разными типами приоритетов"""
    print("\nСоздание демонстрационных процессов...")

    # Процессы с относительными приоритетами
    scheduler.add_process("System", 6.0, 0.0, relative_priority=1,
                          priority_type=PriorityType.RELATIVE)
    scheduler.add_process("Editor", 4.0, 1.0, relative_priority=2,
                          priority_type=PriorityType.RELATIVE)
    scheduler.add_process("Browser", 8.0, 2.0, relative_priority=3,
                          priority_type=PriorityType.RELATIVE)

    # Процесс с абсолютным приоритетом (прибудет позже)
    scheduler.add_process("Emergency", 3.0, 5.0, relative_priority=1,
                          priority_type=PriorityType.ABSOLUTE)

    # Процессы с динамическими приоритетами
    scheduler.add_process("Player", 5.0, 3.0, relative_priority=2,
                          priority_type=PriorityType.DYNAMIC)
    scheduler.add_process("Calc", 2.0, 4.0, relative_priority=1,
                          priority_type=PriorityType.DYNAMIC)

    # Еще один процесс с динамическим приоритетом
    scheduler.add_process("Download", 7.0, 6.0, relative_priority=3,
                          priority_type=PriorityType.DYNAMIC)


def main():
    """Основная функция"""
    print("МНОГОУРОВНЕВЫЙ ПЛАНИРОВЩИК С ТРЕМЯ ТИПАМИ ПРИОРИТЕТОВ")
    print("=" * 100)
    print("Алгоритм работы:")
    print("  • Очередь 0: Round Robin, квант = 2")
    print("  • Очередь 1: Round Robin, квант = 4")
    print("  • Очередь 2: FCFS (без квантования)")
    print("\nТипы приоритетов:")
    print("  • Абсолютные: наивысший приоритет, немедленное выполнение")
    print("  • Относительные: статические приоритеты (1-10, где 1 - высший)")
    print("  • Динамические: изменяются системой в зависимости от поведения")
    print("=" * 100)

    # Создаем планировщик с заданными квантами
    scheduler = MultilevelFeedbackQueueScheduler(quantum_times=[2.0, 4.0, float('inf')])

    # Добавляем демонстрационные процессы
    create_demo_processes(scheduler)

    # Запускаем симуляцию
    try:
        scheduler.run_simulation(steps=40)
    except KeyboardInterrupt:
        print("\n\n[!] Симуляция прервана пользователем")
        scheduler.display_final_statistics()

    input("\nНажмите Enter для завершения...")


if __name__ == "__main__":
    main()