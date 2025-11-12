import os
import getpass
from FAT32FS.format_function import FAT32Formatter
from FAT32FS.permissions import PermissionChecker



class FAT32Emulator:
    """Главный класс эмулятора - управляет подмодулями и командами"""

    def __init__(self, disk_filename: str, formatter: FAT32Formatter):
        self.disk_filename = disk_filename
        self.fs = formatter

        # Текущий пользователь
        self.current_user = None
        self.current_uid = None
        self.current_gid = None

        # Флаг root-прав для текущей команды
        self.sudo_mode = False

        print(f"Эмулятор FAT32 загружен. ФС: {self.fs.volume_name}")

    def authenticate(self):
        """Аутентификация пользователя"""
        if self.fs.is_first_run():
            print("=" * 50)
            print("ПЕРВЫЙ ЗАПУСК СИСТЕМЫ")
            print("Необходимо установить пароль для пользователя root")
            print("=" * 50)

            while True:
                password = getpass.getpass("Введите новый пароль для root: ")
                confirm = getpass.getpass("Подтвердите пароль: ")

                if password == confirm:
                    if len(password) >= 4:
                        self.fs.set_password("root", password)
                        print("Пароль успешно установлен!")

                        # Создаем стандартные группы
                        try:
                            self.fs.add_group("users", 100)
                            self.fs.add_group("admins", 101)
                            print("Созданы стандартные группы: users, admins")
                        except Exception as e:
                            print(f"Предупреждение: {e}")

                        break
                    else:
                        print("Пароль должен содержать минимум 4 символа")
                else:
                    print("Пароли не совпадают, попробуйте снова")

            self.current_user = "root"
            self.current_uid = 0
            self.current_gid = 0
            return True
        else:
            print("=" * 50)
            print("ВХОД В СИСТЕМУ")
            print("=" * 50)

            # Показываем обычных пользователей
            regular_users = self.fs.get_regular_users()

            if not regular_users:
                print("Нет обычных пользователей. Войдите как root.")
                return self.authenticate_user("root")
            else:
                print("Доступные пользователи:")
                for i, user in enumerate(regular_users, 1):
                    print(f"  {i}. {user['login']}")
                print("  r. Войти как root")
                print("  n. Создать нового пользователя")

                while True:
                    choice = input("Выберите пользователя: ").strip().lower()

                    if choice == 'r':
                        return self.authenticate_user("root")
                    elif choice == 'n':
                        if self.create_new_user_interactive():
                            continue
                        else:
                            continue
                    elif choice.isdigit():
                        idx = int(choice) - 1
                        if 0 <= idx < len(regular_users):
                            selected_user = regular_users[idx]
                            return self.authenticate_user(selected_user['login'])

                    print("Неверный выбор")

    def authenticate_user(self, username: str):
        """Аутентификация пользователя"""
        attempts = 3
        while attempts > 0:
            password = getpass.getpass(f"Пароль для {username}: ")

            if self.fs.verify_user_password(username, password):
                users = self.fs.read_users_file()
                for user in users:
                    if user['login'] == username:
                        self.current_user = username
                        self.current_uid = user['uid']
                        self.current_gid = user['gid']
                        print("Аутентификация успешна!")
                        return True

            attempts -= 1
            if attempts > 0:
                print(f"Неверный пароль. Осталось попыток: {attempts}")
            else:
                print("Доступ запрещен. Превышено количество попыток.")
                return False

        return False

    def create_new_user_interactive(self):
        """Интерактивное создание нового пользователя"""
        print("\nСоздание нового пользователя:")

        while True:
            username = input("Имя пользователя: ").strip()
            if not username:
                print("Имя пользователя не может быть пустым")
                continue

            if len(username) > 20:
                print("Имя пользователя слишком длинное (макс. 20 символов)")
                continue

            users = self.fs.read_users_file()
            for user in users:
                if user['login'] == username:
                    print(f"Пользователь {username} уже существует")
                    continue

            break

        while True:
            password = getpass.getpass("Пароль: ")
            confirm = getpass.getpass("Подтвердите пароль: ")

            if password == confirm:
                if len(password) >= 4:
                    try:
                        self.fs.add_user(username, password)
                        print(f"Пользователь {username} успешно создан!")
                        return True
                    except Exception as e:
                        print(f"Ошибка создания пользователя: {e}")
                        return False
                else:
                    print("Пароль должен содержать минимум 4 символа")
            else:
                print("Пароли не совпадают")

    def execute_command(self, command):
        """Выполнение команды"""
        parts = command.split()
        if not parts:
            return True

        cmd = parts[0]
        args = parts[1:]

        # Проверяем sudo
        if cmd == "sudo":
            if len(args) > 0:
                return self.execute_sudo_command(args)
            else:
                print("Использование: sudo <команда>")
                return True

        try:
            if cmd == "ls":
                self.do_ls()
            elif cmd == "touch" and args:
                for filename in args:
                    self.do_touch(filename)
            elif cmd == "cat" and args:
                if len(args) >= 2 and args[0] == ">":
                    self.do_cat_write(args[1])
                elif len(args) >= 2 and args[0] == ">>":
                    self.do_cat_write(args[1], append=True)
                else:
                    self.do_cat(args[0])
            elif cmd == "echo" and len(args) >= 2 and args[1] == ">":
                filename = args[2] if len(args) > 2 else args[0]
                content = " ".join(args[0:1]) if len(args) > 2 else ""
                self.do_echo(content, filename, append=False)
            elif cmd == "echo" and len(args) >= 2 and args[1] == ">>":
                filename = args[2] if len(args) > 2 else args[0]
                content = " ".join(args[0:1]) if len(args) > 2 else ""
                self.do_echo(content, filename, append=True)
            elif cmd == "rm" and args:
                for filename in args:
                    self.do_rm(filename)
            elif cmd == "chmod" and len(args) >= 2:
                self.do_chmod(args[1], args[0])
            elif cmd == "chown" and len(args) >= 2:
                self.do_chown(args[1], args[0])
            elif cmd == "df":
                self.do_df()
            elif cmd == "clear":
                self.do_clear()
            elif cmd == "whoami":
                self.do_whoami()
            elif cmd == "passwd":
                self.do_passwd()
            elif cmd == "useradd" and args:
                self.do_useradd(args)
            elif cmd == "users":
                self.do_users()
            elif cmd == "login":
                return self.do_login()
            elif cmd == "exit" or cmd == "quit":
                return False
            else:
                print(f"Неизвестная команда: {cmd}")
                self.show_help()

        except Exception as e:
            print(f"Ошибка: {e}")

        return True

    def execute_sudo_command(self, command_parts):
        """Выполнение команды с правами root"""
        if not command_parts:
            print("Использование: sudo <команда>")
            return True

        cmd = command_parts[0]
        args = command_parts[1:]

        # Запрашиваем пароль root
        password = getpass.getpass("[sudo] пароль для root: ")
        if not self.fs.verify_password("root", password):
            print("Неверный пароль")
            return True

        # Сохраняем текущего пользователя
        old_user = self.current_user
        old_uid = self.current_uid
        old_gid = self.current_gid

        # Временно становимся root
        self.current_user = "root"
        self.current_uid = 0
        self.current_gid = 0
        self.sudo_mode = True

        try:
            # Выполняем команду
            sudo_command = " ".join(command_parts)
            self.execute_command(sudo_command)
        finally:
            # Возвращаем исходного пользователя
            self.current_user = old_user
            self.current_uid = old_uid
            self.current_gid = old_gid
            self.sudo_mode = False

        return True

    def do_useradd(self, args):
        """Команда useradd - добавление пользователя"""
        if self.current_uid != 0 and not self.sudo_mode:
            print("Ошибка: недостаточно прав. Только root может создавать пользователей.")
            return

        if len(args) < 1:
            print("Использование: useradd <имя_пользователя>")
            return

        username = args[0]

        try:
            # Запрашиваем пароль
            password = getpass.getpass(f"Введите пароль для {username}: ")
            confirm = getpass.getpass("Подтвердите пароль: ")

            if password != confirm:
                print("Пароли не совпадают")
                return

            self.fs.add_user(username, password)
            print(f"Пользователь {username} успешно создан!")

        except Exception as e:
            print(f"Ошибка создания пользователя: {e}")

    def do_users(self):
        """Команда users - список пользователей"""
        users = self.fs.read_users_file()

        print("Список пользователей:")
        print("{:<20} {:<8} {:<8}".format("Имя", "UID", "GID"))
        print("-" * 40)

        for user in users:
            print("{:<20} {:<8} {:<8}".format(
                user['login'], user['uid'], user['gid']
            ))

    def do_login(self):
        """Команда login - смена пользователя"""
        print("Смена пользователя...")

        # Сбрасываем текущего пользователя
        self.current_user = None
        self.current_uid = None
        self.current_gid = None

        # Запускаем аутентификацию заново
        if self.authenticate():
            return True
        else:
            print("Не удалось войти в систему")
            return False

    def do_ls(self):
        """Команда ls - список файлов"""
        files = self.fs.list_directory()
        users = self.fs.read_users_file()

        print("Содержимое корневой директории:")
        print("{:<20} {:<8} {:<8} {:<10} {:<12} {:<10}".format(
            "Имя", "Размер", "Владелец", "Права", "Дата", "Время"
        ))
        print("-" * 80)

        if not files:
            print("Директория пуста")
            return

        for file_info in files:
            owner_name = '?'
            for user in users:
                if user["uid"] == file_info["uid"]:
                    owner_name = user["login"]
                    break

            perm_str = self.fs.format_permissions(file_info['permissions'])

            print("{:<20} {:<8} {:<8} {:<10} {:<12} {:<10}".format(
                file_info['name'],
                file_info['size'],
                owner_name,
                perm_str,
                file_info['modify_date'],
                file_info['modify_time']
            ))

    def do_chown(self, filename: str, owner_str: str) -> None:
        """Команда chown - изменение владельца"""
        if self.current_uid != 0 and not self.sudo_mode:
            print("Ошибка: недостаточно прав. Только root может менять владельца.")
            return

        # Реализация chown из предыдущего ответа
        try:
            if ':' in owner_str:
                user_part, group_part = owner_str.split(':', 1)
            else:
                user_part, group_part = owner_str, None

            # Определяем UID
            if user_part.isdigit():
                new_uid = int(user_part)
            else:
                users = self.fs.read_users_file()
                new_uid = None
                for user in users:
                    if user['login'] == user_part:
                        new_uid = user['uid']
                        break
                if new_uid is None:
                    print(f"Ошибка: пользователь '{user_part}' не найден")
                    return

            # Определяем GID
            new_gid = None
            if group_part:
                if group_part.isdigit():
                    new_gid = int(group_part)
                else:
                    groups_data = self.fs.read_file("groups")
                    new_gid = None
                    for i in range(0, len(groups_data), 32):
                        group_entry = groups_data[i:i + 32]
                        if len(group_entry) >= 32:
                            gid = group_entry[0]
                            group_name = group_entry[1:32].decode('ascii', errors='ignore').rstrip('\x00')
                            if group_name == group_part:
                                new_gid = gid
                                break
                    if new_gid is None:
                        print(f"Ошибка: группа '{group_part}' не найдена")
                        return

            if new_gid is None:
                file_entry = self.fs.find_file_entry(filename)
                if file_entry:
                    new_gid = file_entry[30]

            self.fs.change_owner(filename, new_uid, new_gid)
            print(f"Владелец {filename} изменен на UID:{new_uid}, GID:{new_gid}")

        except Exception as e:
            print(f"Ошибка изменения владельца: {e}")

    def do_touch(self, filename):
        """Команда touch - создание файла"""
        self.fs.create_file(filename, self.current_uid, self.current_gid)
        print(f"Создан файл: {filename}")

    def do_cat(self, filename):
        """Команда cat - чтение файла с проверкой прав"""
        # Проверяем право на чтение
        if not PermissionChecker.check_file_permission(
                self.fs, filename, self.current_uid, self.current_gid, 'read'
        ):
            raise PermissionError("Недостаточно прав для чтения файла")

        data = self.fs.read_file(filename)
        print(data.decode('ascii', errors='ignore'))

    def do_cat_write(self, filename, append=False):
        """Команда cat > filename - многострочная запись в файл с проверкой прав"""
        # Проверяем право на запись (если файл существует)
        file_entry = self.fs.find_file_entry(filename)
        if file_entry:
            if not PermissionChecker.check_file_permission(
                    self.fs, filename, self.current_uid, self.current_gid, 'write'
            ):
                raise PermissionError("Недостаточно прав для записи в файл")

        print(f"Режим многострочного ввода для файла '{filename}'")
        print("Введите содержимое (для завершения ввода нажмите Ctrl+C):")
        print("-" * 50)

        content_lines = []
        try:
            while True:
                try:
                    line = input()
                    content_lines.append(line)
                except EOFError:
                    break
        except KeyboardInterrupt:
            print("\nЗавершение ввода...")

        if content_lines:
            content = "\n".join(content_lines)
            self.fs.write_file(filename, content, append=append,
                               uid=self.current_uid, gid=self.current_gid)
            print(f"Содержимое записано в файл: {filename}")
        else:
            print("Файл оставлен пустым")

    def do_echo(self, content: str, filename: str, append: bool = False) -> None:
        """Команда echo - запись в файл с проверкой прав"""
        # Проверяем право на запись (если файл существует)
        file_entry = self.fs.find_file_entry(filename)
        if file_entry:
            if not PermissionChecker.check_file_permission(
                self.fs, filename, self.current_uid, self.current_gid, 'write'
            ):
                raise PermissionError("Недостаточно прав для записи в файл")

        self.fs.write_file(filename, content, append=append,
                           uid=self.current_uid, gid=self.current_gid)
        mode = "дописан в" if append else "записан в"
        print(f"Текст {mode} файл: {filename}")

    def do_rm(self, filename: str) -> None:
        """Команда rm - удаление файла с проверкой прав"""
        file_entry = self.fs.find_file_entry(filename)
        if not file_entry:
            raise FileNotFoundError(f"Файл не найден: {filename}")

        # Проверяем права: владелец или root может удалять
        file_uid = file_entry[29]
        if self.current_uid != file_uid and self.current_uid != 0 and not self.sudo_mode:
            raise PermissionError("Недостаточно прав для удаления файла")

        # Дополнительная проверка: право на запись в файл
        if not PermissionChecker.check_write_permission(file_entry, self.current_uid, self.current_gid):
            raise PermissionError("Недостаточно прав для удаления файла")

        self.fs.delete_file(filename)
        print(f"Удален файл: {filename}")

    def do_chmod(self, filename: str, mode_str: str) -> None:
        """Команда chmod - изменение прав доступа с проверкой прав"""
        file_entry = self.fs.find_file_entry(filename)
        if not file_entry:
            raise FileNotFoundError(f"Файл не найден: {filename}")

        # Проверяем права: владелец или root может менять права
        file_uid = file_entry[29]
        if self.current_uid != file_uid and self.current_uid != 0 and not self.sudo_mode:
            raise PermissionError("Недостаточно прав для изменения прав доступа")

        self.fs.change_permissions(filename, mode_str)
        print(f"Права доступа {filename} изменены на {mode_str}")


    def do_df(self) -> None:
        """Команда df - информация о диске"""
        usage = self.fs.get_disk_usage()

        print(f"Файловая система: {usage['volume_name']}")
        print(f"Общий размер: {self.fs.format_size(usage['total'])}")
        print(f"Использовано: {self.fs.format_size(usage['used'])}")
        print(f"Свободно: {self.fs.format_size(usage['free'])}")
        usage_percent = (usage['used'] / usage['total']) * 100
        print(f"Использование: {usage_percent:.1f}%")

    @staticmethod
    def do_clear():
        """Команда clear - очистка экрана"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def check_file_executable(self, filename: str) -> bool:
        """Проверка, является ли файл исполняемым для текущего пользователя"""
        file_entry = self.fs.find_file_entry(filename)
        if not file_entry:
            return False

        return PermissionChecker.check_execute_permission(
            file_entry, self.current_uid, self.current_gid
        )

    def do_whoami(self):
        """Команда whoami - информация о текущем пользователе"""
        print(f"Текущий пользователь: {self.current_user} (UID: {self.current_uid}, GID: {self.current_gid})")

    def do_passwd(self):
        """Команда passwd - смена пароля"""
        while True:
            current = getpass.getpass("Текущий пароль: ")
            if not self.fs.verify_password(self.current_user, current):
                print("Неверный текущий пароль")
                continue

            new_password = getpass.getpass("Новый пароль: ")
            confirm = getpass.getpass("Подтвердите новый пароль: ")

            if new_password == confirm:
                if len(new_password) >= 4:
                    self.fs.set_password(self.current_user, new_password)
                    print("Пароль успешно изменен!")
                    break
                else:
                    print("Пароль должен содержать минимум 4 символа")
            else:
                print("Пароли не совпадают")

    @staticmethod
    def show_help():
        """Показать справку по командам"""
        print("Доступные команды:")
        print("  ls                    - список файлов")
        print("  touch <file>          - создать файл")
        print("  cat <file>            - показать содержимое файла")
        print("  echo <text> > <file>  - записать текст в файл")
        print("  echo <text> >> <file> - добавить текст в файл")
        print("  rm <file>             - удалить файл")
        print("  chmod <mode> <file>   - изменить права доступа")
        print("  chown <owner> <file>  - изменить владельца (user[:group])")
        print("  df                    - информация о диске")
        print("  whoami                - информация о текущем пользователе")
        print("  passwd                - сменить пароль")
        print("  useradd <user>        - добавить пользователя (только root)")
        print("  users                 - список пользователей")
        print("  login                 - сменить пользователя")
        print("  sudo <command>        - выполнить команду как root")
        print("  clear                 - очистить экран")
        print("  exit/quit             - выход")

    def get_prompt(self):
        """Получение приглашения командной строки"""
        if self.sudo_mode:
            return f"[sudo] {self.current_user}@myfs:~$ "
        else:
            return f"{self.current_user}@myfs:~$ "


def main():
    """Главная функция эмулятора"""
    print("Эмулятор FAT32 файловой системы")
    print("=" * 50)

    disk_file = "my_disk.bin"

    formatter = FAT32Formatter(disk_file, "MYVOLUME", disk_size_gb=1)
    emulator = FAT32Emulator(disk_file, formatter)

    # Проходим аутентификацию
    if not emulator.authenticate():
        print("Аутентификация не пройдена. Выход.")
        return

    print(f"\nДобро пожаловать, {emulator.current_user}!")
    print("Введите 'help' для списка команд\n")

    # Основной цикл команд
    while True:
        try:
            prompt = emulator.get_prompt()
            command = input(prompt).strip()

            if command == "help":
                emulator.show_help()
                continue

            if not emulator.execute_command(command):
                break

        except KeyboardInterrupt:
            print("\nВыход из эмулятора")
            break
        except Exception as e:
            print(f"Критическая ошибка: {e}")


if __name__ == "__main__":
    main()