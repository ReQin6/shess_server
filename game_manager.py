# game_manager.py
import uuid  # Для работы с UUID
import json  # Для сериализации/десериализации JSON
import time  # Для работы со временем (timestamps)
import copy
from typing import Dict, Optional, List, Any  # Для указания типов данных
from enum import Enum  # Для работы с перечислениями

# !!! ИМПОРТИРУЕМ run_in_threadpool !!!
# Используется для выполнения синхронных операций Redis в асинхронном контексте,
# предотвращая блокировку основного цикла событий FastAPI.
from starlette.concurrency import run_in_threadpool

from redis_manager import redis_manager  # Импорт синглтона RedisManager
from config import INITIAL_GAME_STATE  # Импорт начального состояния игры

# Импортируем BoardState и GameStatus из board_state.py
from board_state import BoardState, GameStatus

# Pydantic модель для комнат (для валидации и сериализации/десериализации)
from pydantic import BaseModel, Field, ConfigDict


class GameRoomInfo(BaseModel):
    """
    Pydantic модель для хранения информации об игровой комнате.
    Используется для сериализации и десериализации данных комнат в Redis.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4)  # Уникальный ID комнаты, генерируется по умолчанию
    name: str  # Название комнаты
    player1_id: Optional[uuid.UUID] = None  # ID первого игрока (белых)
    player2_id: Optional[uuid.UUID] = None  # ID второго игрока (черных)
    status: GameStatus = GameStatus.WAITING  # Текущий статус комнаты (ожидание, в игре, завершена)
    board_state: BoardState  # Состояние доски (объект BoardState), содержит всю игровую логику

    created_at: int = Field(default_factory=lambda: int(time.time()))  # Unix timestamp создания комнаты
    updated_at: int = Field(default_factory=lambda: int(time.time()))  # Unix timestamp последнего обновления комнаты

    # Конфигурация Pydantic модели.
    # arbitrary_types_allowed=True: разрешает использовать типы, которые не являются Pydantic моделями
    #                              (например, BoardState), без явной конвертации.
    # use_enum_values=True: при сериализации Enum-значения будут преобразованы в их строковые значения.
    model_config = ConfigDict(arbitrary_types_allowed=True, use_enum_values=True)

    def to_json(self) -> str:
        """
        Сериализует объект GameRoomInfo в JSON-строку для хранения в Redis.

        Возвращает:
        - str: JSON-строка, представляющая объект GameRoomInfo.
        """
        # Преобразуем board_state в сериализуемый словарь
        board_state_serializable = self.board_state.to_json_serializable() if self.board_state else None

        data_to_dump = {
            "id": str(self.id),  # UUID в строку
            "name": self.name,
            "player1_id": str(self.player1_id) if self.player1_id else None,  # UUID в строку
            "player2_id": str(self.player2_id) if self.player2_id else None,  # UUID в строку
            "status": self.status.value,  # Enum в строку
            "board_state": board_state_serializable,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
        return json.dumps(data_to_dump)

    @staticmethod
    def from_json(json_str: str) -> 'GameRoomInfo':
        """
        Десериализует JSON-строку обратно в объект GameRoomInfo.

        Параметры:
        - json_str (str): JSON-строка, полученная из Redis.

        Возвращает:
        - GameRoomInfo: Десериализованный объект GameRoomInfo.
        """
        data = json.loads(json_str)
        # Обратная конвертация UUID из строк
        data['id'] = uuid.UUID(data['id'])
        if data['player1_id']:
            data['player1_id'] = uuid.UUID(data['player1_id'])
        if data['player2_id']:
            data['player2_id'] = uuid.UUID(data['player2_id'])

        # Десериализация board_state: создаем объект BoardState из словаря
        # Важно: здесь мы передаем десериализованный словарь board_state в конструктор BoardState.
        # В BoardState __init__ уже содержит логику создания Piece объектов из этого словаря.
        data['board_state'] = BoardState(data['board_state'])

        # Используем Pydantic для создания объекта, который выполнит оставшуюся валидацию.
        return GameRoomInfo(**data)


class GameManager:
    """
    Класс GameManager управляет логикой игровых комнат, их созданием, получением и обновлением.
    Взаимодействует с Redis для персистентного хранения данных комнат.
    Реализует паттерн Singleton.
    """
    _instance = None  # Для паттерна Singleton
    ROOM_PREFIX = "room:"  # Префикс для ключей комнат в Redis

    def __new__(cls):
        """
        Реализация Singleton-паттерна: гарантирует, что существует только один экземпляр GameManager.
        """
        if cls._instance is None:
            cls._instance = super(GameManager, cls).__new__(cls)
            cls._instance.redis = redis_manager.get_client()  # Получаем Redis-клиент через RedisManager
            print("GameManager initialized.")
        return cls._instance

    async def create_room(self, room_name: str, player1_id: uuid.UUID) -> GameRoomInfo:
        """
        Создает новую игровую комнату и сохраняет ее в Redis.

        Параметры:
        - room_name (str): Название комнаты.
        - player1_id (uuid.UUID): ID первого игрока (создателя комнаты).

        Возвращает:
        - GameRoomInfo: Объект созданной игровой комнаты.
        """
        # Создаем глубокую копию INITIAL_GAME_STATE, чтобы каждая комната имела свое независимое состояние.
        # Это критически важно, иначе все комнаты будут ссылаться на один и тот же объект,
        # и изменения в одной комнате повлияют на другие.
        initial_board_state_data = copy.deepcopy(INITIAL_GAME_STATE)

        # Обновляем player_id для белых в начальном состоянии доски
        initial_board_state_data["players"]["white"] = str(player1_id)

        # Создаем объект BoardState для новой комнаты
        board_state = BoardState(initial_board_state_data)

        # Создаем объект GameRoomInfo
        room = GameRoomInfo(name=room_name, player1_id=player1_id, board_state=board_state)

        # Сериализуем комнату в JSON и сохраняем в Redis.
        # Используем run_in_threadpool, так как методы Redis синхронны,
        # а FastAPI асинхронен.
        await run_in_threadpool(self.redis.set, f"{self.ROOM_PREFIX}{room.id}", room.to_json())
        print(f"Room created: {room.id} by {player1_id}")
        return room

    async def get_room(self, room_id: uuid.UUID) -> Optional[GameRoomInfo]:
        """
        Получает информацию об игровой комнате из Redis по ее ID.

        Параметры:
        - room_id (uuid.UUID): ID комнаты.

        Возвращает:
        - Optional[GameRoomInfo]: Объект GameRoomInfo, если комната найдена, иначе None.
        """
        # Получаем JSON-строку из Redis.
        # !!! Оборачиваем синхронный вызов Redis в run_in_threadpool !!!
        room_data = await run_in_threadpool(self.redis.get, f"{self.ROOM_PREFIX}{room_id}")
        if room_data:
            return GameRoomInfo.from_json(room_data)  # Десериализуем из JSON
        return None

    async def get_all_rooms(self) -> List[GameRoomInfo]:
        """
        Получает список всех существующих игровых комнат из Redis.

        Возвращает:
        - List[GameRoomInfo]: Список объектов GameRoomInfo.
        """
        # Получаем все ключи комнат, используя паттерн.
        # !!! Оборачиваем синхронный вызов Redis в run_in_threadpool !!!
        redis_keys = await run_in_threadpool(self.redis.keys, f"{self.ROOM_PREFIX}*")
        rooms = []
        for key in redis_keys:
            # Получаем каждую комнату по ключу и десериализуем.
            # !!! Оборачиваем синхронный вызов Redis в run_in_threadpool !!!
            room_data = await run_in_threadpool(self.redis.get, key)
            if room_data:
                rooms.append(GameRoomInfo.from_json(room_data))
        return rooms

    async def join_room(self, room_id: uuid.UUID, player2_id: uuid.UUID) -> Optional[GameRoomInfo]:
        """
        Позволяет второму игроку присоединиться к существующей комнате.

        Параметры:
        - room_id (uuid.UUID): ID комнаты, к которой нужно присоединиться.
        - player2_id (uuid.UUID): ID присоединяющегося игрока.

        Возвращает:
        - Optional[GameRoomInfo]: Обновленный объект GameRoomInfo, если присоединение успешно, иначе None.

        Вызывает:
        - ValueError: Если комната уже полная или игрок уже в комнате.
        """
        room = await self.get_room(room_id)
        if not room:
            return None  # Комната не найдена

        if room.player2_id is not None:
            raise ValueError("Room is already full.")
        if room.player1_id == player2_id:  # Проверка, если игрок пытается присоединиться сам к себе
            raise ValueError("Player is already player1 in this room.")

        room.player2_id = player2_id
        room.status = GameStatus.IN_PROGRESS  # Меняем статус игры на "в процессе"
        room.updated_at = int(time.time())

        # Обновляем player_id для черных в состоянии доски
        room.board_state.players['black'] = str(player2_id)

        # Сохраняем обновленную комнату в Redis.
        # !!! Оборачиваем синхронный вызов Redis в run_in_threadpool !!!
        await run_in_threadpool(self.redis.set, f"{self.ROOM_PREFIX}{room.id}", room.to_json())
        print(f"Player {player2_id} joined room {room.id}")
        return room

    async def update_room_state(self, room_id: uuid.UUID, updated_board_state_obj: BoardState) -> Optional[
        GameRoomInfo]:
        """
        Обновляет состояние доски для конкретной комнаты и сохраняет его в Redis.
        Используется после каждого хода или изменения состояния игры.

        Параметры:
        - room_id (uuid.UUID): ID комнаты, состояние которой нужно обновить.
        - updated_board_state_obj (BoardState): Обновленный объект BoardState.

        Возвращает:
        - Optional[GameRoomInfo]: Обновленный объект GameRoomInfo, если комната найдена, иначе None.
        """
        room = await self.get_room(room_id)
        if not room:
            return None

        # Просто заменяем старый объект BoardState на новый
        room.board_state = updated_board_state_obj
        room.updated_at = int(time.time())  # Обновляем timestamp последнего изменения

        # Сохраняем комнату обратно в Redis
        # !!! Оборачиваем синхронный вызов Redis в run_in_threadpool !!!
        await run_in_threadpool(self.redis.set, f"{self.ROOM_PREFIX}{room.id}", room.to_json())
        return room

    async def surrender_room(self, room_id: uuid.UUID, player_id: uuid.UUID) -> Optional[GameRoomInfo]:
        """
        Обрабатывает сдачу партии игроком. Обновляет статус комнаты и доски, логирует событие.

        Параметры:
        - room_id (uuid.UUID): ID комнаты, в которой игрок сдается.
        - player_id (uuid.UUID): ID игрока, который сдается.

        Возвращает:
        - Optional[GameRoomInfo]: Обновленный объект GameRoomInfo, если операция успешна, иначе None.

        Вызывает:
        - ValueError: Если игрок не является участником комнаты.
        """
        room = await self.get_room(room_id)
        if not room:
            return None  # Комната не найдена

        # Проверяем, является ли игрок участником этой комнаты
        if str(player_id) != str(room.player1_id) and str(player_id) != str(room.player2_id):
            raise ValueError("Player is not a participant of this room.")

        # Устанавливаем статус комнаты и статус игры на доске как "сдался"
        room.status = GameStatus.RESIGNED
        room.board_state.game_status = GameStatus.RESIGNED
        # Добавляем запись в лог игры
        room.board_state.game_log.append(f"Player {player_id} resigned the game.")
        room.updated_at = int(time.time())

        # Сохраняем обновленную комнату в Redis.
        # !!! Оборачиваем синхронный вызов Redis в run_in_threadpool !!!
        await run_in_threadpool(self.redis.set, f"{self.ROOM_PREFIX}{room.id}", room.to_json())
        return room

    async def delete_all_rooms(self):
        """
        Удаляет все комнаты из Redis.
        Используйте эту функцию ОСТОРОЖНО, так как она безвозвратно удаляет все игровые данные.
        Полезна для отладки и сброса состояния базы данных.
        """
        # Получаем все ключи комнат по паттерну.
        redis_keys = await run_in_threadpool(self.redis.keys, f"{self.ROOM_PREFIX}*")
        if redis_keys:
            # Если ключи найдены, удаляем их все.
            await run_in_threadpool(self.redis.delete, *redis_keys)
            print(f"Deleted {len(redis_keys)} rooms from Redis.")
        else:
            print("No rooms found to delete.")


# Для удобства доступа к единственному экземпляру GameManager.
# В других модулях достаточно импортировать 'game_manager'.
game_manager = GameManager()