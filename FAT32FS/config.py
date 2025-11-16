class Config:
    # Атрибуты файлов
    ATTR_READ_ONLY = 0x01
    ATTR_HIDDEN = 0x02
    ATTR_SYSTEM = 0x04
    # ATTR_VOLUME_ID = 0x08
    # ATTR_DIRECTORY = 0x10
    # ATTR_ARCHIVE = 0x20

    USER_FLAG_LOCKED = 0x01
    CLUSTER_SIZE = 4096

    # Структуры смещений
    SUPERBLOCK_CLUSTER = 0
    FAT_START_CLUSTER = 1
    FAT_CLUSTERS = 256
    ROOT_DIR_START_CLUSTER = 257
    DATA_START_CLUSTER = 447

    # Размеры записей
    FILE_RECORD_SIZE = 61
    USER_RECORD_SIZE = 65
    GROUP_RECORD_SIZE = 32
    PASSWORD_SIZE = 32

    # Смещения в записи файла (61 байт)
    OFFSET_FILENAME = 0  # 40 байт
    OFFSET_ATTRIBUTE = 40  # 1 байт
    OFFSET_CREATE_TIME = 41  # 3 байта
    OFFSET_MODIFY_TIME = 44  # 3 байта
    OFFSET_MODIFY_DATE = 47  # 2 байта
    OFFSET_UID = 49  # 1 байт
    OFFSET_GID = 50  # 1 байт
    OFFSET_PERMISSIONS = 51  # 2 байта
    OFFSET_FILE_SIZE = 53  # 4 байта
    OFFSET_FIRST_CLUSTER = 57  # 4 байта

    # Обновляем смещения для записи пользователя (65 байта)
    OFFSET_USER_LOGIN = 0  # 30 байт
    OFFSET_USER_UID = 30  # 1 байт
    OFFSET_USER_GID = 31  # 1 байт
    OFFSET_USER_FLAGS = 32  # 1 байт
    OFFSET_USER_PASSWORD = 33  # 32 байт

    # Смещения в записи группы (32 байта)
    OFFSET_GROUP_GID = 0  # 1 байт
    OFFSET_GROUP_NAME = 1  # 31 байт

    # Смещения в суперблоке
    OFFSET_SUPERBLOCK_VOLUME_NAME = 0  # 10 байт
    OFFSET_SUPERBLOCK_TOTAL_SECTORS = 10  # 4 байта
    OFFSET_SUPERBLOCK_SECTOR_SIZE = 14  # 2 байта
    OFFSET_SUPERBLOCK_SECTORS_PER_CLUSTER = 16  # 1 байт
    OFFSET_SUPERBLOCK_FAT_COUNT = 17  # 1 байт
    OFFSET_SUPERBLOCK_FAT_CLUSTERS = 18  # 2 байта
    OFFSET_SUPERBLOCK_FREE_CLUSTERS = 20  # 4 байта
    OFFSET_SUPERBLOCK_FIRST_FREE_CLUSTER = 24  # 4 байта
    OFFSET_SUPERBLOCK_ROOT_DIR_CLUSTER = 28  # 4 байта
    OFFSET_SUPERBLOCK_MAX_UID = 32  # 2 байта
    OFFSET_SUPERBLOCK_MAX_GID = 34  # 2 байта