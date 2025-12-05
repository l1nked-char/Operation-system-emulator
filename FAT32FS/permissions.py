from FAT32FS.config import Config
import struct


class PermissionChecker:
    @staticmethod
    def check_attributes(attributes, operation, is_root=False):
        """Проверка атрибутов файла по значениям (без битовых операций)"""
        temp_attrs = attributes

        has_system = (temp_attrs >= Config.ATTR_SYSTEM)
        if has_system:
            temp_attrs -= Config.ATTR_SYSTEM

        has_hidden = (temp_attrs >= Config.ATTR_HIDDEN)
        if has_hidden:
            temp_attrs -= Config.ATTR_HIDDEN

        has_read_only = (temp_attrs % 2 == 1)
        if has_read_only:
            temp_attrs -= Config.ATTR_READ_ONLY

        if has_system and not is_root:
            return False

        if has_read_only:
            if operation == 'read':
                return True
            elif operation in ['write', 'delete', 'rename'] and is_root:
                return None
            elif operation in ['write', 'delete', 'rename'] and not is_root:
                return False
            else:
                return None

        return None


    @staticmethod
    def check_read_permission(file_entry, current_uid, current_gid):
        """Проверка права на чтение файла с Unix-правами"""
        permissions = struct.unpack('>H', file_entry[Config.OFFSET_PERMISSIONS:Config.OFFSET_PERMISSIONS + 2])[0]
        file_uid = file_entry[Config.OFFSET_UID]
        file_gid = file_entry[Config.OFFSET_GID]

        # Владелец
        if current_uid == file_uid:
            return (permissions & 0o400) != 0  # rwx------

        # Участник группы
        if current_gid == file_gid:
            return (permissions & 0o040) != 0  # ---rwx---

        # Все остальные
        return (permissions & 0o004) != 0  # ------r--

    @staticmethod
    def check_write_permission(file_entry, current_uid, current_gid):
        """Проверка права на запись в файл с Unix-правами"""
        permissions = struct.unpack('>H', file_entry[Config.OFFSET_PERMISSIONS:Config.OFFSET_PERMISSIONS + 2])[0]
        file_uid = file_entry[Config.OFFSET_UID]
        file_gid = file_entry[Config.OFFSET_GID]

        # Владелец
        if current_uid == file_uid:
            return (permissions & 0o200) != 0  # -w-------

        # Участник группы
        if current_gid == file_gid:
            return (permissions & 0o020) != 0  # ----w-----

        # Все остальные
        return (permissions & 0o002) != 0  # -------w-

    @staticmethod
    def check_execute_permission(file_entry, current_uid, current_gid):
        """Проверка права на выполнение файла с Unix-правами"""
        permissions = struct.unpack('>H', file_entry[Config.OFFSET_PERMISSIONS:Config.OFFSET_PERMISSIONS + 2])[0]
        file_uid = file_entry[Config.OFFSET_UID]
        file_gid = file_entry[Config.OFFSET_GID]

        # Владелец
        if current_uid == file_uid:
            return (permissions & 0o100) != 0  # --x------

        # Участник группы
        if current_gid == file_gid:
            return (permissions & 0o010) != 0  # -----x---

        # Все остальные
        return (permissions & 0o001) != 0  # --------x

    @staticmethod
    def check_file_permission(fs, filename, current_uid, current_gid, operation):
        file_entry = fs.find_file_entry(filename)
        if not file_entry:
            raise FileNotFoundError(f"Файл не найден: {filename}")

        attributes = file_entry[Config.OFFSET_ATTRIBUTE]
        is_root = (current_uid == 0)

        attr_check = PermissionChecker.check_attributes(attributes, operation, is_root)
        if attr_check is not None:
            return attr_check

        if is_root:
            return True

        if operation == 'read':
            return PermissionChecker.check_read_permission(file_entry, current_uid, current_gid)
        elif operation == 'write':
            return PermissionChecker.check_write_permission(file_entry, current_uid, current_gid)
        elif operation == 'execute':
            return PermissionChecker.check_execute_permission(file_entry, current_uid, current_gid)
        elif operation in ['delete', 'rename']:
            return PermissionChecker.check_write_permission(file_entry, current_uid, current_gid)
        else:
            raise ValueError(f"Неизвестная операция: {operation}")

    @staticmethod
    def is_file_hidden(attributes, current_uid):
        """Проверка, является ли файл скрытым для текущего пользователя"""
        if current_uid == 0:
            return False

        temp_attrs = attributes

        has_system = (temp_attrs >= Config.ATTR_SYSTEM)
        if has_system:
            temp_attrs -= Config.ATTR_SYSTEM

        return temp_attrs >= Config.ATTR_HIDDEN

    @staticmethod
    def is_file_system(attributes, current_uid):
        """Проверка, является ли файл скрытым для текущего пользователя"""
        return attributes >= Config.ATTR_SYSTEM and current_uid != 0
