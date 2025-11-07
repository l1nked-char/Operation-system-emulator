import os
import getpass
from FAT32FS.format_function import FAT32Formatter



class FAT32Emulator:
    """Главный класс эмулятора - управляет подмодулями и командами"""

    def __init__(self, disk_filename: str, formatter: FAT32Formatter):
        self.disk_filename = disk_filename
        self.fs = formatter

        # Текущий пользователь
        self.current_user = None
        self.current_uid = None
        self.current_gid = None

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
                        self.fs.set_root_password(password)
                        print("Пароль успешно установлен!")
                        break
                    else:
                        print("Пароль должен содержать минимум 4 символа")
                else:
                    print("Пароли не совпадают, попробуйте снова")
        else:
            print("=" * 50)
            print("ВХОД В СИСТЕМУ")
            print("=" * 50)

            attempts = 3
            while attempts > 0:
                password = getpass.getpass("Пароль для root: ")

                if self.fs.verify_password("root", password):
                    print("Аутентификация успешна!")
                    break
                else:
                    attempts -= 1
                    if attempts > 0:
                        print(f"Неверный пароль. Осталось попыток: {attempts}")
                    else:
                        print("Доступ запрещен. Превышено количество попыток.")
                        return False

        # Устанавливаем текущего пользователя
        self.current_user = "root"
        self.current_uid = 0
        self.current_gid = 0

        return True

    def execute_command(self, command):
        """Выполнение команды"""
        parts = command.split()
        if not parts:
            return True

        cmd = parts[0]
        args = parts[1:]

        try:
            if cmd == "ls":
                self.do_ls()
            elif cmd == "touch" and args:
                self.do_touch(args[0])
            elif cmd == "cat" and args:
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
                self.do_rm(args[0])
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
            elif cmd == "exit" or cmd == "quit":
                return False
            else:
                print(f"Неизвестная команда: {cmd}")
                self.show_help()

        except Exception as e:
            print(f"Ошибка: {e}")

        return True

    def do_ls(self):
        """Команда ls - список файлов"""
        files = self.fs.list_directory()

        print("Содержимое корневой директории:")
        print("{:<20} {:<8} {:<8} {:<10} {:<12}".format(
            "Имя", "Размер", "Владелец", "Права", "Кластер"
        ))
        print("-" * 60)

        if not files:
            print("Директория пуста")
            return

        for file_info in files:
            owner_name = f"user{file_info['uid']}"
            perm_str = self.fs.format_permissions(file_info['permissions'])

            print("{:<20} {:<8} {:<8} {:<10} {:<12}".format(
                file_info['name'],
                file_info['size'],
                owner_name,
                perm_str,
                file_info['cluster']
            ))

    def do_touch(self, filename):
        """Команда touch - создание файла"""
        self.fs.create_file(filename, self.current_uid, self.current_gid)
        print(f"Создан файл: {filename}")

    def do_cat(self, filename):
        """Команда cat - чтение файла"""
        data = self.fs.read_file(filename)
        print(data.decode('ascii', errors='ignore'))

    def do_echo(self, content, filename, append=False):
        """Команда echo - запись в файл"""
        self.fs.write_file(filename, content, append, self.current_uid, self.current_gid)
        mode = "дописано в" if append else "записано в"
        print(f"Текст {mode} файл: {filename}")

    def do_rm(self, filename):
        """Команда rm - удаление файла"""
        self.fs.delete_file(filename)
        print(f"Удален файл: {filename}")

    def do_chmod(self, filename, mode_str):
        """Команда chmod - изменение прав доступа"""
        self.fs.change_permissions(filename, mode_str)
        print(f"Права доступа {filename} изменены на {mode_str}")

    def do_chown(self, filename, owner_str):
        """Команда chown - изменение владельца (заглушка)"""
        print("Заглушка: chown - изменение владельца временно не поддерживается")

    def do_df(self):
        """Команда df - информация о диске"""
        usage = self.fs.get_disk_usage()

        print(f"Файловая система: {usage['volume_name']}")
        print(f"Общий размер: {self.fs.format_size(usage['total'])}")
        print(f"Использовано: {self.fs.format_size(usage['used'])}")
        print(f"Свободно: {self.fs.format_size(usage['free'])}")
        usage_percent = (usage['used'] / usage['total']) * 100
        print(f"Использование: {usage_percent:.1f}%")

    def do_clear(self):
        """Команда clear - очистка экрана"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def do_whoami(self):
        """Команда whoami - информация о текущем пользователе"""
        print(f"Текущий пользователь: {self.current_user} (UID: {self.current_uid}, GID: {self.current_gid})")

    def do_passwd(self):
        """Команда passwd - смена пароля"""
        if self.current_user != "root":
            print("Ошибка: смена пароля доступна только для пользователя root")
            return

        while True:
            current = getpass.getpass("Текущий пароль: ")
            if not self.fs.verify_password("root", current):
                print("Неверный текущий пароль")
                continue

            new_password = getpass.getpass("Новый пароль: ")
            confirm = getpass.getpass("Подтвердите новый пароль: ")

            if new_password == confirm:
                if len(new_password) >= 4:
                    self.fs.set_root_password(new_password)
                    print("Пароль успешно изменен!")
                    break
                else:
                    print("Пароль должен содержать минимум 4 символа")
            else:
                print("Пароли не совпадают")

    def show_help(self):
        """Показать справку по командам"""
        print("Доступные команды:")
        print("  ls                    - список файлов")
        print("  touch <file>          - создать файл")
        print("  cat <file>            - показать содержимое файла")
        print("  echo <text> > <file>  - записать текст в файл")
        print("  echo <text> >> <file> - добавить текст в файл")
        print("  rm <file>             - удалить файл")
        print("  chmod <mode> <file>   - изменить права доступа")
        print("  chown <owner> <file>  - изменить владельца")
        print("  df                    - информация о диске")
        print("  whoami                - информация о текущем пользователе")
        print("  passwd                - сменить пароль")
        print("  clear                 - очистить экран")
        print("  exit/quit             - выход")


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
            command = input(f"{emulator.current_user}@myfs:~$ ").strip()
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