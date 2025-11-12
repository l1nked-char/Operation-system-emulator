import hashlib
import os
import struct
from datetime import datetime


class FAT32Formatter:
    def __init__(self, disk_filename, volume_name, disk_size_gb=1):

        self.disk_filename = disk_filename
        self.volume_name = volume_name
        self.CLUSTER_SIZE = 4096
        self.SECTOR_SIZE = 512
        self.DISK_SIZE = disk_size_gb * 1024 * 1024 * 1024
        self.TOTAL_CLUSTERS = self.DISK_SIZE // self.CLUSTER_SIZE
        self.ROOT_DIR_CLUSTERS = 190
        self.ENTRIES_PER_CLUSTER = 99

        # Структуры смещений
        self.SUPERBLOCK_CLUSTER = 0
        self.FAT_START_CLUSTER = 1
        self.FAT_CLUSTERS = 256
        self.ROOT_DIR_START_CLUSTER = 257
        self.DATA_START_CLUSTER = 447
        self.FILE_RECORD_SIZE = 41
        self.OFFSET_TO_FREE_CLUSTER = 24
        self.OFFSET_TO_FILE_SIZE = 37
        self.PASSWORD_SIZE = 32

        if not os.path.exists(self.disk_filename):
            print(f"Диск {self.disk_filename} не найден. Создаем новый...")
            self.format_disk()
        self.load_disk_info()

    def format_disk(self, volume_name="MYVOLUME") -> bool:
        """Основная функция форматирования"""
        print(f"Форматирование диска {self.disk_filename}...")

        try:
            # Создаем файл-диск
            with open(self.disk_filename, 'wb') as disk:
                # Инициализируем весь диск нулями
                disk.write(b'\x00' * self.DISK_SIZE)

            # Создаем структуры файловой системы
            self.create_superblock(volume_name)
            self.create_fat_table()
            self.create_root_directory()
            self.create_system_files()

            print("Форматирование завершено успешно!")
            return True
        except:
            print("При форматировании диска произошла ошибка!")
            return False

    def load_disk_info(self) -> None:
        """Загрузка информации о диске из суперблока"""
        try:
            with open(self.disk_filename, 'rb') as disk:
                disk.seek(self.SUPERBLOCK_CLUSTER * self.CLUSTER_SIZE)
                superblock = disk.read(self.CLUSTER_SIZE)

                self.volume_name = superblock[0:10].decode('ascii').rstrip('\x00')
                self.sector_size = struct.unpack('>H', superblock[14:16])[0]
                self.sectors_per_cluster = superblock[16]
                self.fat_clusters = struct.unpack('>H', superblock[18:20])[0]

        except Exception as e:
            raise Exception(f"Ошибка загрузки диска: {e}")

    def create_superblock(self, volume_name) -> None:
        """Создание суперблока"""
        print("Создание суперблока...")

        superblock_data = bytearray()

        # Название ФС (10 байт)
        name = volume_name.ljust(10, '\x00')[:10].encode('ascii')
        superblock_data.extend(name)

        # Общее количество секторов (3 байта)
        total_sectors = self.DISK_SIZE // self.SECTOR_SIZE
        # Размер сектора (2 байта)
        # Секторов в кластере (1 байт)
        sectors_per_cluster = self.CLUSTER_SIZE // self.SECTOR_SIZE
        # Количество FAT-таблиц (1 байт)
        # Размер FAT в кластерах (2 байта)
        # Количество свободных кластеров (4 байта)
        free_clusters = self.TOTAL_CLUSTERS - (1 + self.FAT_CLUSTERS + self.ROOT_DIR_CLUSTERS)
        # Первый свободный кластер (4 байта)
        # Кластер корневой директории (4 байта)

        superblock_data.extend(struct.pack('>IHBBHIII', total_sectors, self.SECTOR_SIZE, sectors_per_cluster, 1,
                                            self.FAT_CLUSTERS, free_clusters, self.DATA_START_CLUSTER, self.ROOT_DIR_START_CLUSTER))

        superblock_data.extend(bytearray(self.CLUSTER_SIZE - len(superblock_data))) # должно быть 4096 - 31

        with open(self.disk_filename, 'r+b') as disk:
            disk.seek(self.SUPERBLOCK_CLUSTER * self.CLUSTER_SIZE)
            disk.write(superblock_data)

    def create_fat_table(self) -> None:
        """Создание FAT-таблицы"""
        print("Создание FAT-таблицы...")

        fat_entries = [0] * self.TOTAL_CLUSTERS

        # FAT-таблица пустая
        for i in range(self.FAT_START_CLUSTER, self.TOTAL_CLUSTERS):
            fat_entries[i] = 0x00000000

        # Конвертируем в байты и записываем
        fat_data = bytearray()
        for entry in fat_entries:
            fat_data.extend(struct.pack('>I', entry))

        with open(self.disk_filename, 'r+b') as disk:
            for cluster in range(self.FAT_START_CLUSTER, self.FAT_START_CLUSTER + self.FAT_CLUSTERS):
                cluster_offset = cluster * self.CLUSTER_SIZE
                disk.seek(cluster_offset)

                # Вычисляем часть FAT для этого кластера
                start_idx = (cluster - self.FAT_START_CLUSTER) * (self.CLUSTER_SIZE // 4)
                end_idx = start_idx + (self.CLUSTER_SIZE // 4)
                cluster_data = fat_data[start_idx * 4:end_idx * 4]

                # Дополняем до размера кластера если нужно
                if len(cluster_data) < self.CLUSTER_SIZE:
                    cluster_data += b'\x00' * (self.CLUSTER_SIZE - len(cluster_data))

                disk.write(cluster_data)

    def create_root_directory(self) -> None:
        """Создание корневого каталога"""
        print("Создание корневого каталога...")

        # Создаем пустые записи каталога (все нули)
        empty_entry = b'\x00' * self.FILE_RECORD_SIZE

        with open(self.disk_filename, 'r+b') as disk:
            for cluster in range(self.ROOT_DIR_START_CLUSTER,
                                 self.ROOT_DIR_START_CLUSTER + self.ROOT_DIR_CLUSTERS):
                cluster_offset = cluster * self.CLUSTER_SIZE
                disk.seek(cluster_offset)

                # Записываем пустые записи на весь кластер
                for i in range(self.ENTRIES_PER_CLUSTER):
                    disk.write(empty_entry)

                # Дополняем нулями если нужно
                current_pos = disk.tell()
                if current_pos < cluster_offset + self.CLUSTER_SIZE:
                    disk.write(b'\x00' * (cluster_offset + self.CLUSTER_SIZE - current_pos))

    def create_system_files(self) -> None:
        """Создание системных файлов"""
        print("Создание системных файлов...")

        if not self.create_file("users", 0, 0):
            print("Ошибка создания файла users")
            return

        if not self.create_file("groups", 0, 0):
            print("Ошибка создания файла groups")
            return

        if not self.write_initial_users():
            print("Не удалось создать начальных пользователей!")
            return
        if not self.write_initial_groups():
            print("Не удалось создать начальные группы!")
            return

    def write_initial_users(self) -> bool:
        """Запись начальных данных в файл users - ИСПРАВЛЕННЫЙ ВАРИАНТ"""
        try:
            user_data = bytearray()

            login = "root".ljust(30, '\x00')[:30].encode('ascii')
            user_data.extend(login)

            user_data.append(0)
            user_data.append(0)

            user_data.extend(b'\x00' * self.PASSWORD_SIZE)

            return self.write_file("users", user_data, overwrite=True, uid=0, gid=0)
        except Exception as e:
            print(f"Ошибка записи users: {e}")
            return False

    def write_initial_groups(self) -> bool:
        """Запись начальных данных в файл groups - ИСПРАВЛЕННЫЙ ВАРИАНТ"""
        try:
            group_data = bytearray()

            group_data.append(0)

            group_name = "root".ljust(31, '\x00')[:31].encode('ascii')
            group_data.extend(group_name)

            return self.write_file("groups", group_data, overwrite=True, uid=0, gid=0)
        except Exception as e:
            print(f"Ошибка записи groups: {e}")
            return False

    def update_file_size(self, filename, new_size) -> bool:
        """Обновление размера файла в записи каталога"""
        entry_data = self.find_file_entry(filename)
        if not entry_data:
            return False

        # Находим смещение записи
        with open(self.disk_filename, 'r+b') as disk:
            for cluster in range(self.ROOT_DIR_START_CLUSTER,
                                 self.ROOT_DIR_START_CLUSTER + self.ROOT_DIR_CLUSTERS):
                cluster_offset = cluster * self.CLUSTER_SIZE

                for entry_num in range(self.ENTRIES_PER_CLUSTER):
                    entry_offset = cluster_offset + (entry_num * self.FILE_RECORD_SIZE)
                    disk.seek(entry_offset)

                    current_entry = disk.read(self.FILE_RECORD_SIZE)
                    if len(current_entry) < self.FILE_RECORD_SIZE:
                        continue

                    current_name = current_entry[0:20].decode('ascii', errors='ignore').rstrip('\x00')
                    if current_name == filename:
                        # Обновляем размер файла
                        disk.seek(entry_offset + self.OFFSET_TO_FILE_SIZE)
                        disk.write(struct.pack('>I', new_size))
                        return True

        return False

    def read_users_file(self) -> list:
        """Чтение файла пользователей - ИСПРАВЛЕННЫЙ ВАРИАНТ"""
        try:
            data = self.read_file("users")
            if not data:
                return []

            users = []

            # Парсим записи пользователей (каждая по 64 байта)
            for i in range(0, len(data), 64):
                if i + 64 > len(data):
                    break

                user_data = data[i:i + 64]

                login = user_data[0:30].decode('ascii', errors='ignore').rstrip('\x00')
                uid = user_data[30]
                gid = user_data[31]
                password_hash = user_data[32:64]

                if login:
                    users.append({
                        'login': login,
                        'uid': uid,
                        'gid': gid,
                        'password_hash': password_hash
                    })

            return users
        except Exception as e:
            print(f"Ошибка чтения users: {e}")
            return []

    def write_users_file(self, users_data: list) -> None:
        """Запись файла пользователей - ИСПРАВЛЕННЫЙ ВАРИАНТ"""
        try:
            data = bytearray()

            for user in users_data:
                # Логин (30 байт) - смещение 0-29
                login_bytes = user['login'].ljust(30, '\x00')[:30].encode('ascii')
                data.extend(login_bytes)

                # UID и GID (по 1 байту) - правильные смещения!
                data.append(user['uid'])  # смещение 30
                data.append(user['gid'])  # смещение 31

                # Хэш пароля (32 байта) - смещение 32-63
                password_hash = user['password_hash']
                if isinstance(password_hash, str):
                    password_hash = password_hash.encode('ascii')
                data.extend(password_hash.ljust(32, b'\x00')[:32])

            # Записываем в файл users
            self.write_file("users", data, overwrite=True, uid=0, gid=0)
        except Exception as e:
            print(f"Ошибка записи users file: {e}")

    def read_groups_file(self) -> list:
        """Чтение файла групп - НОВАЯ ФУНКЦИЯ"""
        try:
            data = self.read_file("groups")
            if not data:
                return []

            groups = []

            for i in range(0, len(data), 32):
                if i + 32 > len(data):
                    break

                group_data = data[i:i + 32]

                gid = group_data[0]
                name = group_data[1:32].decode('ascii', errors='ignore').rstrip('\x00')  # Смещение 1-31

                if name:
                    groups.append({
                        'name': name,
                        'gid': gid
                    })

            return groups
        except Exception as e:
            print(f"Ошибка чтения groups: {e}")
            return []

    def is_first_run(self):
        """Проверка, первый ли это запуск (пароль root не установлен)"""
        users = self.read_users_file()
        for user in users:
            if user['login'] == 'root':
                # Проверяем, установлен ли пароль (не нулевой хэш)
                if user['password_hash'] != b'\x00' * 32:
                    return False
        return True

    def set_password(self, username: str, password: str) -> bool:
        """Установка пароля root"""
        users = self.read_users_file()

        password_hash = hashlib.sha256(password.encode()).digest()

        for user in users:
            if user['login'] == username:
                user['password_hash'] = password_hash
                break
        else:
            print(f"Пользователя с именем {username} не существует")
            return False


        self.write_users_file(users)
        return True

    def add_group(self, group_name: str, gid: int = None) -> bool:
        """Добавление новой группы - ИСПРАВЛЕННЫЙ ВАРИАНТ"""
        try:
            groups = self.read_groups_file()

            # Проверяем, не существует ли группа
            for group in groups:
                if group['name'] == group_name:
                    raise ValueError(f"Группа {group_name} уже существует")

            # Определяем GID если не указан
            if gid is None:
                max_gid = 99
                for group in groups:
                    if max_gid < group['gid'] < 1000:
                        max_gid = group['gid']
                gid = max_gid + 1

            # Создаем запись группы
            group_data = bytearray()
            group_data.append(gid)  # смещение 0
            group_data.extend(group_name.ljust(31, '\x00')[:31].encode('ascii'))  # смещение 1-31

            # Добавляем к существующим данным
            existing_data = self.read_file("groups")
            new_groups_data = existing_data + group_data

            # Записываем обновленный файл
            self.write_file("groups", new_groups_data, overwrite=True, uid=0, gid=0)
            return True
        except Exception as e:
            print(f"Ошибка добавления группы: {e}")
            return False

    def get_group_by_name(self, group_name: str):
        """Получение группы по имени"""
        groups = self.read_groups_file()
        for group in groups:
            if group['name'] == group_name:
                return group
        return None

    def get_group_by_gid(self, gid: int):
        """Получение группы по GID"""
        groups = self.read_groups_file()
        for group in groups:
            if group['gid'] == gid:
                return group
        return None

    def verify_password(self, login, password):
        """Проверка пароля пользователя"""
        users = self.read_users_file()
        password_hash = hashlib.sha256(password.encode()).digest()

        for user in users:
            if user['login'] == login:
                return user['password_hash'] == password_hash

        return False

    def change_owner(self, filename: str, new_uid: int, new_gid: int) -> bool:
        """Изменение владельца файла"""
        entry_offset = self.find_file_entry(filename, is_offset_needed=True)
        if not entry_offset:
            raise FileNotFoundError(f"Файл не найден: {filename}")

        with open(self.disk_filename, 'r+b') as disk:
            disk.seek(entry_offset + 29)  # смещение до uid
            disk.write(bytes([new_uid]))
            disk.seek(entry_offset + 30)  # смещение до gid
            disk.write(bytes([new_gid]))

        return True

    def list_directory(self):
        """Чтение содержимого корневой директории"""
        files = []

        with open(self.disk_filename, 'rb') as disk:
            for cluster in range(self.ROOT_DIR_START_CLUSTER,
                                 self.ROOT_DIR_START_CLUSTER + self.ROOT_DIR_CLUSTERS):
                cluster_offset = cluster * self.CLUSTER_SIZE

                for entry_num in range(self.ENTRIES_PER_CLUSTER):
                    entry_offset = cluster_offset + (entry_num * self.FILE_RECORD_SIZE)
                    disk.seek(entry_offset)

                    entry_data = disk.read(self.FILE_RECORD_SIZE)
                    if len(entry_data) < self.FILE_RECORD_SIZE:
                        continue

                    first_byte = entry_data[0]
                    if first_byte == 0x00:
                        break
                    if first_byte == 0xE5:
                        continue

                    filename = entry_data[0:20].decode('ascii', errors='ignore').rstrip('\x00')
                    attributes = entry_data[20]

                    # Извлекаем время и дату
                    create_time = self.unpack_time(entry_data[21:24])
                    modify_time = self.unpack_time(entry_data[24:27])
                    modify_date = self.unpack_date(entry_data[27:29])

                    uid = entry_data[29]
                    gid = entry_data[30]
                    permissions = struct.unpack('>H', entry_data[31:33])[0]
                    file_size = struct.unpack('>I', entry_data[33:37])[0]
                    first_cluster = struct.unpack('>I', entry_data[37:41])[0]

                    if filename in ['users', 'groups']:
                        continue

                    if filename:
                        files.append({
                            'name': filename,
                            'size': file_size,
                            'uid': uid,
                            'gid': gid,
                            'permissions': permissions,
                            'cluster': first_cluster,
                            'create_time': create_time,
                            'modify_time': modify_time,
                            'modify_date': modify_date
                        })

        return files

    def create_file(self, filename: str, uid: int, gid: int) -> bool:
        """Создание нового файла"""
        if len(filename) > 20:
            raise ValueError("Имя файла слишком длинное (макс. 20 символов)")

        if self.find_file_entry(filename):
            raise ValueError(f"Файл {filename} уже существует")

        entry_offset = self.find_free_directory_entry()
        if entry_offset == -1:
            raise Exception("Нет места в директории")

        file_entry = self.create_file_entry(filename, uid, gid)

        with open(self.disk_filename, 'r+b') as disk:
            disk.seek(entry_offset)
            disk.write(file_entry)

        return True

    def read_file(self, filename: str) -> bytes:
        """Чтение содержимого файла"""
        file_entry = self.find_file_entry(filename)
        if not file_entry:
            raise FileNotFoundError(f"Файл не найден: {filename}")

        file_size = struct.unpack('>I', file_entry[33:37])[0]
        first_cluster = struct.unpack('>I', file_entry[37:41])[0]

        if first_cluster == 0 or file_size == 0:
            return b""

        return self.read_file_data(first_cluster, file_size)

    def write_file(self, filename: str, content: str or bytearray,
                        append: bool=False, overwrite: bool=False,
                        uid: int=None, gid:int=None) -> bool:
        """Запись в файл"""
        content_bytes: bytearray = content.encode('ascii') if isinstance(content, str) else content

        if overwrite:
            # Удаляем и создаем заново
            self.delete_file(filename)
            self.create_file(filename, uid, gid)

        file_entry: bytes = self.find_file_entry(filename)
        if not file_entry:
            if uid is None or gid is None:
                raise ValueError("Для создания файла требуется uid и gid")
            self.create_file(filename, uid, gid)
            file_entry: bytes = self.find_file_entry(filename)

        old_size: int = struct.unpack('>I', file_entry[33:37])[0] if not append else \
                   struct.unpack('>I', file_entry[33:37])[0]
        first_cluster: int = struct.unpack('>I', file_entry[37:41])[0]

        if append and first_cluster != 0:
            old_data: bytearray = self.read_file_data(first_cluster, old_size)
            content_bytes: bytearray = old_data + content_bytes

        new_size = len(content_bytes)

        if first_cluster == 0:
            first_cluster = self.find_free_cluster()
            if first_cluster == -1:
                raise Exception("Нет свободного места")

        success = self.write_file_data(first_cluster, content_bytes, new_size)
        if success:
            self.update_file_metadata(filename, new_size, first_cluster)
            return True

        return False

    def delete_file(self, filename: str) -> bool:
        """Удаление файла"""
        file_entry = self.find_file_entry(filename)
        if not file_entry:
            raise FileNotFoundError(f"Файл не найден: {filename}")

        file_entry_offset: int = self.find_file_entry(filename, is_offset_needed=True)
        if not file_entry_offset:
            return False

        with open(self.disk_filename, 'r+b') as disk:
            disk.seek(file_entry_offset)
            disk.write(b'\xE5')

        first_cluster: int = struct.unpack('>I', file_entry[37:41])[0]
        if first_cluster != 0:
            self.free_cluster_chain(first_cluster)

        return True

    def change_permissions(self, filename: str, mode: str) -> bool:
        """Изменение прав доступа файла"""
        entry_offset: int = self.find_file_entry(filename, is_offset_needed=True)
        if not entry_offset:
            raise FileNotFoundError(f"Файл не найден: {filename}")

        try:
            if mode.startswith('0o'):
                mode_int: int = int(mode, 8)
            else:
                mode_int: int = int(mode, 8)
        except ValueError:
            raise ValueError("Неверный формат прав доступа")

        with open(self.disk_filename, 'r+b') as disk:
            disk.seek(entry_offset + 31)
            disk.write(struct.pack('>H', mode_int))

        return True

    def get_disk_usage(self) -> dict:
        """Получение информации об использовании диска"""
        total_clusters = 0
        free_clusters = 0
        used_clusters = 0

        with open(self.disk_filename, 'rb') as disk:
            for fat_cluster in range(self.FAT_START_CLUSTER, self.FAT_START_CLUSTER + self.FAT_CLUSTERS):
                cluster_offset = fat_cluster * self.CLUSTER_SIZE
                disk.seek(cluster_offset)

                for i in range(self.CLUSTER_SIZE // 4):
                    fat_entry = struct.unpack('>I', disk.read(4))[0]
                    if fat_entry == 0x00000000:
                        free_clusters += 1
                    else:
                        used_clusters += 1
                    total_clusters += 1

        total_space = total_clusters * self.CLUSTER_SIZE
        used_space = used_clusters * self.CLUSTER_SIZE
        free_space = free_clusters * self.CLUSTER_SIZE

        return {
            'total': total_space,
            'used': used_space,
            'free': free_space,
            'volume_name': self.volume_name
        }

    def create_file_entry(self, filename: str, uid: int, gid: int):
        """Создание структуры записи файла"""
        file_entry = bytearray()

        name_bytes = filename.ljust(20, '\x00')[:20].encode('ascii')
        file_entry.extend(name_bytes)
        file_entry.append(0x20)

        now = datetime.now()
        create_time = self.pack_time(now)
        file_entry.extend(create_time)
        update_time = self.pack_time(now)
        file_entry.extend(update_time)
        update_date = self.pack_date(now)
        file_entry.extend(update_date)

        file_entry.append(uid)
        file_entry.append(gid)
        file_entry.extend(struct.pack('>H', 0o644))
        file_entry.extend(struct.pack('>I', 0))
        file_entry.extend(struct.pack('>I', 0))

        return file_entry

    def find_file_entry(self, filename: str, is_offset_needed:bool = False) -> bytes or None or int:
        """Поиск записи файла"""
        with open(self.disk_filename, 'rb') as disk:
            for cluster in range(self.ROOT_DIR_START_CLUSTER,
                                 self.ROOT_DIR_START_CLUSTER + self.ROOT_DIR_CLUSTERS):
                cluster_offset: int = cluster * self.CLUSTER_SIZE

                for entry_num in range(self.ENTRIES_PER_CLUSTER):
                    entry_offset: int = cluster_offset + (entry_num * self.FILE_RECORD_SIZE)
                    disk.seek(entry_offset)

                    entry_data: bytes  = disk.read(self.FILE_RECORD_SIZE)
                    if len(entry_data) < self.FILE_RECORD_SIZE:
                        continue

                    first_byte = entry_data[0]
                    if first_byte == 0x00:
                        return None
                    if first_byte == 0xE5:
                        continue

                    entry_name: str = entry_data[0:20].decode('ascii', errors='ignore').rstrip('\x00')
                    if entry_name == filename:
                        return entry_data if not is_offset_needed else entry_offset

        return None

    def find_free_directory_entry(self) -> int:
        """Поиск свободной записи в директории"""
        with open(self.disk_filename, 'rb') as disk:
            for cluster in range(self.ROOT_DIR_START_CLUSTER,
                                 self.ROOT_DIR_START_CLUSTER + self.ROOT_DIR_CLUSTERS):
                cluster_offset: int = cluster * self.CLUSTER_SIZE

                for entry_num in range(self.ENTRIES_PER_CLUSTER):
                    entry_offset: int = cluster_offset + (entry_num * self.FILE_RECORD_SIZE)
                    disk.seek(entry_offset)

                    first_byte: bytes = disk.read(1)
                    if first_byte == b'\x00' or first_byte == b'\xE5':
                        return entry_offset

        return -1

    def find_free_cluster(self) -> int:
        """Поиск свободного кластера"""
        with open(self.disk_filename, 'rb'):
            for cluster in range(self.DATA_START_CLUSTER, self.DATA_START_CLUSTER + 1000):
                if self.is_cluster_free(cluster):
                    return cluster
        return -1

    def is_cluster_free(self, cluster: int) -> bool:
        """Проверка свободен ли кластер"""
        fat_cluster = cluster // (self.CLUSTER_SIZE // 4)
        fat_offset_in_cluster = (cluster % (self.CLUSTER_SIZE // 4)) * 4

        with open(self.disk_filename, 'rb') as disk:
            disk.seek((self.FAT_START_CLUSTER + fat_cluster) * self.CLUSTER_SIZE + fat_offset_in_cluster)
            fat_entry = struct.unpack('>I', disk.read(4))[0]

        return fat_entry == 0x00000000

    def read_file_data(self, first_cluster: int, file_size: int) -> bytearray:
        """Чтение данных файла"""
        data = bytearray()
        current_cluster = first_cluster
        bytes_read = 0

        with open(self.disk_filename, 'rb') as disk:
            while current_cluster != 0x0FFFFFFF and bytes_read < file_size:
                cluster_offset = current_cluster * self.CLUSTER_SIZE
                disk.seek(cluster_offset)

                bytes_to_read = min(self.CLUSTER_SIZE, file_size - bytes_read)
                cluster_data = disk.read(bytes_to_read)
                data.extend(cluster_data)
                bytes_read += len(cluster_data)

                fat_cluster = current_cluster // (self.CLUSTER_SIZE // 4)
                fat_offset_in_cluster = (current_cluster % (self.CLUSTER_SIZE // 4)) * 4

                disk.seek((self.FAT_START_CLUSTER + fat_cluster) * self.CLUSTER_SIZE + fat_offset_in_cluster)
                current_cluster = struct.unpack('>I', disk.read(4))[0]

        return data

    def write_file_data(self, first_cluster: int, data: bytearray, file_size: int) -> bool:
        """Запись данных файла"""
        current_cluster = first_cluster
        bytes_written = 0

        with open(self.disk_filename, 'r+b') as disk:
            while bytes_written < file_size:
                cluster_offset = current_cluster * self.CLUSTER_SIZE
                disk.seek(cluster_offset)

                bytes_to_write = min(self.CLUSTER_SIZE, file_size - bytes_written)
                chunk = data[bytes_written:bytes_written + bytes_to_write]
                disk.write(chunk)
                bytes_written += len(chunk)

                if bytes_written < file_size:
                    next_cluster = self.find_free_cluster()
                    if not next_cluster:
                        return False

                    self.mark_cluster_used(current_cluster, next_cluster)
                    current_cluster = next_cluster
                else:
                    self.mark_cluster_used(current_cluster, 0x0FFFFFFF)

        return True

    def mark_cluster_used(self, cluster, next_cluster):
        """Пометить кластер как использованный"""
        fat_cluster = cluster // (self.CLUSTER_SIZE // 4)
        fat_offset_in_cluster = (cluster % (self.CLUSTER_SIZE // 4)) * 4

        with open(self.disk_filename, 'r+b') as disk:
            disk.seek((self.FAT_START_CLUSTER + fat_cluster) * self.CLUSTER_SIZE + fat_offset_in_cluster)
            disk.write(struct.pack('>I', next_cluster))

    def free_cluster_chain(self, first_cluster):
        """Освобождение цепочки кластеров"""
        current_cluster = first_cluster

        while current_cluster != 0x0FFFFFFF:
            next_cluster = 0
            fat_cluster = current_cluster // (self.CLUSTER_SIZE // 4)
            fat_offset_in_cluster = (current_cluster % (self.CLUSTER_SIZE // 4)) * 4

            with open(self.disk_filename, 'r+b') as disk:
                disk.seek((self.FAT_START_CLUSTER + fat_cluster) * self.CLUSTER_SIZE + fat_offset_in_cluster)
                next_cluster_data = disk.read(4)
                if len(next_cluster_data) == 4:
                    next_cluster = struct.unpack('>I', next_cluster_data)[0]

                disk.seek((self.FAT_START_CLUSTER + fat_cluster) * self.CLUSTER_SIZE + fat_offset_in_cluster)
                disk.write(struct.pack('>I', 0x00000000))

            current_cluster = next_cluster

    def update_file_metadata(self, filename: str, new_size: int, first_cluster: int=None):
        """Обновление метаданных файла"""
        entry_offset: int = self.find_file_entry(filename, is_offset_needed=True)
        if entry_offset is None:
            return False

        with open(self.disk_filename, 'r+b') as disk:
            disk.seek(entry_offset)

            entry_data = bytearray(disk.read(self.FILE_RECORD_SIZE))

            entry_data[33:37] = struct.pack('>I', new_size)

            if first_cluster:
                entry_data[37:41] = struct.pack('>I', first_cluster)

            now = datetime.now()
            entry_data[24:27] = self.pack_time(now)
            entry_data[30:32] = self.pack_date(now)

            disk.seek(entry_offset)
            disk.write(entry_data)

        return True

    def add_user(self, login: str, password: str, uid: int = None, gid: int = 100) -> bool:
        """Добавление нового пользователя"""
        users = self.read_users_file()

        # Проверяем, не существует ли пользователь
        for user in users:
            if user['login'] == login:
                raise ValueError(f"Пользователь {login} уже существует")

        # Определяем UID если не указан
        if uid is None:
            max_uid = 0
            for user in users:
                if max_uid < user['uid'] < 1000:
                    max_uid = user['uid']
            uid = max_uid + 1

        # Хэшируем пароль
        password_hash = hashlib.sha256(password.encode()).digest()

        # Добавляем пользователя
        users.append({
            'login': login,
            'uid': uid,
            'gid': gid,
            'password_hash': password_hash
        })

        # Записываем обновленный список
        self.write_users_file(users)
        return True

    def add_group(self, group_name: str, gid: int = None) -> bool:
        """Добавление новой группы"""
        groups_data = self.read_file("groups")
        groups = []

        # Парсим существующие группы
        for i in range(0, len(groups_data), 32):
            if i + 32 <= len(groups_data):
                gid_existing = groups_data[i]
                name = groups_data[i + 1:i + 32].decode('ascii', errors='ignore').rstrip('\x00')
                if name:
                    groups.append({'gid': gid_existing, 'name': name})

        # Проверяем, не существует ли группа
        for group in groups:
            if group['name'] == group_name:
                raise ValueError(f"Группа {group_name} уже существует")

        # Определяем GID если не указан
        if gid is None:
            max_gid = 99
            for group in groups:
                if max_gid < group['gid'] < 1000:
                    max_gid = group['gid']
            gid = max_gid + 1

        # Создаем запись группы
        group_data = bytearray()
        group_data.append(gid)
        group_data.extend(group_name.ljust(31, '\x00')[:31].encode('ascii'))

        # Добавляем к существующим данным
        new_groups_data = groups_data + group_data

        # Записываем обновленный файл
        self.write_file("groups", new_groups_data, overwrite=True, uid=0, gid=0)
        return True

    def get_regular_users(self):
        """Получение списка обычных пользователей (не root)"""
        users = self.read_users_file()
        regular_users = []
        for user in users:
            if user['uid'] != 0:  # исключаем root
                regular_users.append(user)
        return regular_users

    def verify_user_password(self, login: str, password: str) -> bool:
        """Проверка пароля пользователя"""
        users = self.read_users_file()
        password_hash = hashlib.sha256(password.encode()).digest()

        for user in users:
            if user['login'] == login:
                return user['password_hash'] == password_hash

        return False

    def get_user_by_uid(self, uid: int):
        """Получение информации о пользователе по UID"""
        users = self.read_users_file()
        for user in users:
            if user['uid'] == uid:
                return user
        return None

    @staticmethod
    def pack_time(dt):
        """Упаковка времени в 3 байта"""
        packed = (dt.hour << 12) | (dt.minute << 6) | dt.second
        return struct.pack('>I', packed)[1:]

    @staticmethod
    def pack_date(dt):
        """Упаковка даты в 2 байта"""
        year = dt.year - 1980
        packed = (year << 9) | (dt.month << 5) | dt.day
        return struct.pack('>H', packed)

    @staticmethod
    def unpack_time(packed_time):
        """Распаковка времени из 3 байт"""
        if len(packed_time) != 3:
            return "00:00:00"

        value = struct.unpack('>I', b'\x00' + packed_time)[0]
        hour = (value >> 12) & 0x1F
        minute = (value >> 6) & 0x3F
        second = value & 0x3F
        return f"{hour:02d}:{minute:02d}:{second:02d}"

    @staticmethod
    def unpack_date(packed_date):
        """Распаковка даты из 2 байт"""
        if len(packed_date) != 2:
            return "1980-01-01"

        value = struct.unpack('>H', packed_date)[0]
        year = ((value >> 9) & 0x7F) + 1980  # 7 бит
        month = (value >> 5) & 0x0F  # 4 бита
        day = value & 0x1F  # 5 бит
        return f"{year:04d}-{month:02d}-{day:02d}"

    @staticmethod
    def format_permissions(permissions):
        """Форматирование прав доступа в строку"""
        perm_str = ''
        perm_str += 'r' if permissions & 0o400 else '-'
        perm_str += 'w' if permissions & 0o200 else '-'
        perm_str += 'x' if permissions & 0o100 else '-'
        perm_str += 'r' if permissions & 0o040 else '-'
        perm_str += 'w' if permissions & 0o020 else '-'
        perm_str += 'x' if permissions & 0o010 else '-'
        perm_str += 'r' if permissions & 0o004 else '-'
        perm_str += 'w' if permissions & 0o002 else '-'
        perm_str += 'x' if permissions & 0o001 else '-'
        return perm_str

    @staticmethod
    def format_size(size):
        """Форматирование размера в читаемый вид"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"