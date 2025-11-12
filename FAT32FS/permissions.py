import struct


class PermissionChecker:
    """Подсистема проверки прав доступа"""

    @staticmethod
    def check_read_permission(file_entry, current_uid, current_gid):
        """Проверка права на чтение файла"""
        permissions = struct.unpack('>H', file_entry[31:33])[0]
        file_uid = file_entry[29]
        file_gid = file_entry[30]

        # Владелец имеет права, если установлен бит владельца
        if current_uid == file_uid:
            return (permissions & 0o400) != 0  # r--------

        # Участник группы имеет права, если установлен бит группы
        if current_gid == file_gid:
            return (permissions & 0o040) != 0  # ---r-----

        # Все остальные
        return (permissions & 0o004) != 0  # ------r--

    @staticmethod
    def check_write_permission(file_entry, current_uid, current_gid):
        """Проверка права на запись в файл"""
        permissions = struct.unpack('>H', file_entry[31:33])[0]
        file_uid = file_entry[29]
        file_gid = file_entry[30]

        # Владелец имеет права, если установлен бит владельца
        if current_uid == file_uid:
            return (permissions & 0o200) != 0  # -w-------

        # Участник группы имеет права, если установлен бит группы
        if current_gid == file_gid:
            return (permissions & 0o020) != 0  # ----w----

        # Все остальные
        return (permissions & 0o002) != 0  # -------w-

    @staticmethod
    def check_execute_permission(file_entry, current_uid, current_gid):
        """Проверка права на выполнение файла"""
        permissions = struct.unpack('>H', file_entry[31:33])[0]
        file_uid = file_entry[29]
        file_gid = file_entry[30]

        # Владелец имеет права, если установлен бит владельца
        if current_uid == file_uid:
            return (permissions & 0o100) != 0  # --x------

        # Участник группы имеет права, если установлен бит группы
        if current_gid == file_gid:
            return (permissions & 0o010) != 0  # -----x---

        # Все остальные
        return (permissions & 0o001) != 0  # --------x

    @staticmethod
    def check_file_permission(fs, filename, current_uid, current_gid, operation):
        """
        Общая проверка прав доступа к файлу

        Args:
            operation: 'read', 'write', 'execute'
        """
        file_entry = fs.find_file_entry(filename)
        if not file_entry:
            raise FileNotFoundError(f"Файл не найден: {filename}")

        # Root имеет все права
        if current_uid == 0:
            return True

        if operation == 'read':
            return PermissionChecker.check_read_permission(file_entry, current_uid, current_gid)
        elif operation == 'write':
            return PermissionChecker.check_write_permission(file_entry, current_uid, current_gid)
        elif operation == 'execute':
            return PermissionChecker.check_execute_permission(file_entry, current_uid, current_gid)
        else:
            raise ValueError(f"Неизвестная операция: {operation}")