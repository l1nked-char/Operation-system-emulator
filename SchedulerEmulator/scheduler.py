import time
import signal
import sys
from collections import deque
from typing import List, Optional
from process import Process, ProcessState


class Scheduler:
    """Планировщик процессов"""

    def __init__(self, time_quantum: float = 1.0):
        self.processes: List[Process] = []
        self.ready_queue = deque()
        self.time_quantum = time_quantum
        self.current_time = 0.0
        self.current_process: Optional[Process] = None
        self.running = False
        self.paused = False
        self.pid_counter = 1
        self.interrupted = False

        # Устанавливаем обработчик сигнала
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, sig, frame):
        """Обработчик сигнала Ctrl+C - только устанавливает флаг"""
        self.interrupted = True

    def add_process(self, name: str, burst_time: float,
                    priority: int = 1, arrival_time: float = 0.0):
        """Добавление нового процесса"""
        if arrival_time < self.current_time:
            arrival_time = self.current_time

        process = Process(
            pid=self.pid_counter,
            name=name,
            arrival_time=arrival_time,
            burst_time=burst_time,
            priority=priority
        )

        self.processes.append(process)
        self.pid_counter += 1

        # Добавляем в очередь готовых, если процесс уже должен был прибыть
        if arrival_time <= self.current_time:
            self.ready_queue.append(process)
            process.state = ProcessState.READY

        print(f"\n[+] Добавлен процесс: {process.name} (PID: {process.pid})")
        return process

    def update_dynamic_priorities(self):
        """Обновление динамических приоритетов"""
        for process in self.processes:
            if process.state == ProcessState.READY:
                # Процесс в ожидании получает более высокий приоритет
                process.dynamic_priority = max(1, process.priority - 1)
            elif process.state == ProcessState.RUNNING:
                # Выполняемый процесс понижает приоритет
                process.dynamic_priority = process.priority + 1

    def schedule_next(self) -> Optional[Process]:
        """Выбор следующего процесса для выполнения"""
        if not self.ready_queue:
            return None

        # Сортируем по динамическим приоритетам (ниже число = выше приоритет)
        sorted_queue = sorted(
            self.ready_queue,
            key=lambda p: (p.dynamic_priority, p.arrival_time)
        )

        # Удаляем выбранный процесс из очереди
        process = sorted_queue[0]
        self.ready_queue.remove(process)

        return process

    def execute_time_slice(self):
        """Выполнение одного кванта времени"""
        if self.paused:
            return

        # Проверяем прерывание
        if self.interrupted:
            self.interrupted = False
            raise KeyboardInterrupt

        # Если текущий процесс завершился, выбираем следующий
        if (self.current_process is None or
                self.current_process.state != ProcessState.RUNNING):

            self.current_process = self.schedule_next()
            if self.current_process:
                self.current_process.state = ProcessState.RUNNING
                if self.current_process.start_time is None:
                    self.current_process.start_time = self.current_time
                print(f"\n[→] Начинает выполняться: {self.current_process.name}")

        # Если есть процесс для выполнения
        if self.current_process:
            # Определяем время выполнения (не больше кванта и оставшегося времени)
            exec_time = min(
                self.time_quantum,
                self.current_process.remaining_time
            )

            # Имитируем выполнение (без реального ожидания)
            time.sleep(0.3)  # Уменьшили для более отзывчивого интерфейса
            self.current_time += exec_time
            self.current_process.remaining_time -= exec_time

            print(f"[+] Выполнен квант {exec_time:.1f} для {self.current_process.name}")
            print(f"    Осталось времени: {self.current_process.remaining_time:.1f}")

            # Проверяем, завершился ли процесс
            if self.current_process.remaining_time <= 0:
                self.current_process.state = ProcessState.TERMINATED
                self.current_process.completion_time = self.current_time
                print(f"\n[✓] Процесс {self.current_process.name} завершен!")
                print(f"    Общее время выполнения: {self.current_time - self.current_process.start_time:.1f}")
                self.current_process = None
            else:
                # Возвращаем процесс в очередь с обновленным приоритетом
                self.current_process.state = ProcessState.READY
                self.current_process.dynamic_priority += 1  # Понижаем приоритет
                self.ready_queue.append(self.current_process)
                self.current_process = None

        # Обновляем динамические приоритеты
        self.update_dynamic_priorities()

        # Добавляем новые процессы, которые "прибыли"
        for process in self.processes:
            if (process.state == ProcessState.READY and
                    process not in self.ready_queue and
                    process.arrival_time <= self.current_time):
                self.ready_queue.append(process)

    def display_status(self):
        """Отображение статуса всех процессов"""
        print("\n" + "=" * 80)
        print(f"Текущее время: {self.current_time:.1f}")
        print(f"Текущий процесс: {self.current_process.name if self.current_process else 'Нет'}")
        print(f"Процессов в очереди готовых: {len(self.ready_queue)}")
        print("=" * 80)

        # Группируем процессы по состояниям
        by_state = {}
        for state in ProcessState:
            by_state[state] = [p for p in self.processes if p.state == state]

        for state, procs in by_state.items():
            if procs:
                print(f"\n{state.value}:")
                for process in procs:
                    print(f"  {process}")

        print("\nОчередь готовых процессов:")
        if self.ready_queue:
            for i, process in enumerate(self.ready_queue):
                print(f"  {i + 1}. {process.name} (приоритет: {process.dynamic_priority})")
        else:
            print("  Пусто")
        print("=" * 80)

    def run_simulation(self):
        """Запуск симуляции"""
        self.running = True
        self.paused = False

        print("\n" + "=" * 80)
        print("ЗАПУСК СИМУЛЯЦИИ")
        print("Нажмите Ctrl+C для приостановки и перехода в меню")
        print("=" * 80)

        try:
            while self.running and any(p.state != ProcessState.TERMINATED
                                       for p in self.processes):
                if not self.paused:
                    self.display_status()
                    self.execute_time_slice()

                    # Проверяем, завершены ли все процессы
                    if all(p.state == ProcessState.TERMINATED
                           for p in self.processes if p.arrival_time <= self.current_time):
                        print("\n[✓] Все процессы завершены!")
                        break

                    print("\n" + "-" * 40)
                    print("Нажмите Enter для следующего шага или Ctrl+C для меню...")

                    # Неблокирующий ввод с проверкой прерывания
                    try:
                        # Ждем ввод 1 секунду, затем продолжаем
                        if sys.platform == "win32":
                            # Для Windows
                            import msvcrt
                            start_time = time.time()
                            while time.time() - start_time < 1:
                                if msvcrt.kbhit():
                                    msvcrt.getch()  # Считываем клавишу
                                    break
                                time.sleep(0.1)
                        else:
                            # Для Linux/Mac
                            import select
                            ready, _, _ = select.select([sys.stdin], [], [], 1)
                            if ready:
                                sys.stdin.readline()
                    except (KeyboardInterrupt, EOFError):
                        self.interrupted = True
                        continue
                else:
                    time.sleep(0.1)

                if self.interrupted:
                    raise KeyboardInterrupt

        except KeyboardInterrupt:
            print("\n" + "=" * 60)
            print("Обнаружено нажатие Ctrl+C!")
            print("=" * 60)
            self.pause_simulation()
            self.show_menu()

    def pause_simulation(self):
        """Приостановка симуляции"""
        self.paused = True
        print("\n[!] Симуляция приостановлена")

    def resume_simulation(self):
        """Возобновление симуляции"""
        self.paused = False
        print("\n[!] Симуляция возобновлена")

    def clear_all_processes(self):
        """Очистка всех процессов"""
        confirmation = input("\n[?] Вы уверены, что хотите удалить все процессы? (y/n): ")
        if confirmation.lower() == 'y':
            self.processes = []
            self.ready_queue.clear()
            self.current_process = None
            self.current_time = 0.0
            self.pid_counter = 1
            print("[✓] Все процессы удалены!")
        else:
            print("[!] Отмена операции")

    def add_process_interactive(self):
        """Интерактивное добавление процесса"""
        print("\n" + "-" * 40)
        print("ДОБАВЛЕНИЕ НОВОГО ПРОЦЕССА")

        try:
            name = input("Имя процесса: ").strip()
            if not name:
                print("[!] Имя процесса не может быть пустым")
                return

            burst_time = float(input("Время выполнения: "))
            priority = int(input("Приоритет (1-10, где 1 - высший): "))

            print("\nВремя поступления процесса:")
            print("1. Текущее время (немедленно)")
            print("2. Указать время вручную")
            choice = input("Выберите (1/2): ").strip()

            if choice == '1':
                arrival_time = self.current_time
            elif choice == '2':
                arrival_time = float(input("Время поступления: "))
            else:
                print("[!] Используется текущее время")
                arrival_time = self.current_time

            self.add_process(name, burst_time, priority, arrival_time)
        except ValueError:
            print("[!] Ошибка ввода. Проверьте правильность данных")
        except KeyboardInterrupt:
            print("\n[!] Отмена добавления процесса")
            self.interrupted = True

    def show_menu(self):
        """Отображение меню управления"""
        while True:
            try:
                print("\n" + "=" * 80)
                print("МЕНЮ УПРАВЛЕНИЯ ПЛАНИРОВЩИКОМ")
                print("=" * 80)
                print("1. Добавить новый процесс")
                print("2. Просмотреть список процессов и статусы")
                print("3. Продолжить симуляцию")
                print("4. Очистить все процессы")
                print("5. Выйти из программы")
                print("=" * 80)

                choice = input("\nВыберите действие (1-5): ").strip()

                if choice == '1':
                    self.add_process_interactive()
                    if self.interrupted:
                        self.interrupted = False
                        continue
                elif choice == '2':
                    self.display_status()
                    input("\nНажмите Enter для возврата в меню...")
                elif choice == '3':
                    self.resume_simulation()
                    self.run_simulation()
                    break
                elif choice == '4':
                    self.clear_all_processes()
                elif choice == '5':
                    print("\n[!] Завершение работы...")
                    self.running = False
                    sys.exit(0)
                else:
                    print("[!] Неверный выбор. Попробуйте снова.")
            except KeyboardInterrupt:
                print("\n[!] Используйте пункты меню для управления")
                print("[!] Для выхода выберите пункт 5")
            except EOFError:
                print("\n[!] Завершение работы...")
                sys.exit(0)


def main():
    """Основная функция"""
    print("ЭМУЛЯТОР ПЛАНИРОВЩИКА ПРОЦЕССОВ")
    print("=" * 80)
    print("Поддерживаемые приоритеты:")
    print("  - Абсолютные (статический приоритет)")
    print("  - Динамические (меняется в зависимости от состояния)")
    print("  - Относительные (сравниваются между процессами)")
    print("=" * 80)
    print("\nУправление:")
    print("  - Enter: следующий шаг симуляции")
    print("  - Ctrl+C: приостановка и переход в меню")
    print("=" * 80)

    # Настройка кванта времени
    try:
        quantum = float(input("\nВведите квант времени (по умолчанию 1.0): ") or "1.0")
    except ValueError:
        quantum = 1.0
        print(f"[!] Используется значение по умолчанию: {quantum}")

    # Создание планировщика
    scheduler = Scheduler(time_quantum=quantum)

    # Добавление начальных процессов (опционально)
    try:
        add_initial = input("\nДобавить тестовые процессы? (y/n): ").lower()
        if add_initial == 'y':
            print("\n[+] Добавляю тестовые процессы...")
            scheduler.add_process("System", 4.0, 1, 0.0)
            scheduler.add_process("Browser", 6.0, 2, 1.0)
            scheduler.add_process("Editor", 3.0, 3, 2.0)
            scheduler.add_process("Player", 5.0, 2, 3.0)
    except (KeyboardInterrupt, EOFError):
        print("\n[!] Пропускаю добавление тестовых процессов")

    # Запуск симуляции
    try:
        scheduler.run_simulation()
    except KeyboardInterrupt:
        print("\n[!] Завершение программы...")
        sys.exit(0)

    # Если симуляция завершена, показываем статистику
    if all(p.state == ProcessState.TERMINATED for p in scheduler.processes):
        print("\n" + "=" * 80)
        print("ФИНАЛЬНАЯ СТАТИСТИКА")
        print("=" * 80)

        total_turnaround = 0
        total_waiting = 0
        completed = 0

        for process in scheduler.processes:
            if process.completion_time and process.start_time:
                turnaround = process.completion_time - process.arrival_time
                waiting = turnaround - process.burst_time
                total_turnaround += turnaround
                total_waiting += waiting
                completed += 1

                print(f"{process.name}:")
                print(f"  Время выполнения: {process.burst_time:.1f}")
                print(f"  Оборотное время: {turnaround:.1f}")
                print(f"  Время ожидания: {waiting:.1f}")
                print()

        if completed > 0:
            avg_turnaround = total_turnaround / completed
            avg_waiting = total_waiting / completed
            print(f"Среднее оборотное время: {avg_turnaround:.2f}")
            print(f"Среднее время ожидания: {avg_waiting:.2f}")

    input("\nНажмите Enter для завершения...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Программа завершена пользователем")
        sys.exit(0)
    except EOFError:
        print("\n\n[!] Программа завершена")
        sys.exit(0)