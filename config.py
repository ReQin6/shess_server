# config.py
import uuid  # Для генерации UUID
import time  # Для работы со временем (например, timestamp создания/обновления)

# --- Конфигурация Redis ---
REDIS_URL = "redis://localhost:6379"  # URL для подключения к Redis-серверу.

# --- Конфигурация для будущей авторизации (пока не используется в полной мере) ---
SECRET_KEY = "47f347fe87ed83gf3d387f3ufgd83g"  # Секретный ключ для подписи JWT токенов. Должен быть сложным и храниться в безопасности.
ALGORITHM = "HS256"  # Алгоритм хеширования для JWT.
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Время жизни токена доступа в минутах.


def generate_figure_id() -> str:
    """
    Генерирует уникальный UUID для идентификации шахматных фигур.

    Возвращает:
    - str: Строковое представление нового UUID.
    """
    return str(uuid.uuid4())


# --- Начальное состояние доски ---
# Этот список определяет начальное расположение всех фигур на доске.
# Каждая фигура представляет собой словарь с ее свойствами.
INITIAL_BOARD_STATE_PIECES = [
    # Черные фигуры
    {"figure_id": generate_figure_id(), "name": "Rook", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 0, "col": 0, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Knight", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 0, "col": 1, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Bishop", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 0, "col": 2, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Queen", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 0, "col": 3, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "King", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 0, "col": 4, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Bishop", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 0, "col": 5, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Knight", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 0, "col": 6, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Rook", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 0, "col": 7, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 1, "col": 0, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 1, "col": 1, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 1, "col": 2, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 1, "col": 3, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 1, "col": 4, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 1, "col": 5, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 1, "col": 6, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "black", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 1, "col": 7, "move_creation": 0, "walk_count": 0},

    # Белые фигуры
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 6, "col": 0, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 6, "col": 1, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 6, "col": 2, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 6, "col": 3, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 6, "col": 4, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 6, "col": 5, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 6, "col": 6, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Pawn", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 6, "col": 7, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Rook", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 7, "col": 0, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Knight", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 7, "col": 1, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Bishop", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 7, "col": 2, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Queen", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 7, "col": 3, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "King", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 7, "col": 4, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Bishop", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 7, "col": 5, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Knight", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 7, "col": 6, "move_creation": 0, "walk_count": 0},
    {"figure_id": generate_figure_id(), "name": "Rook", "color": "white", "description": "", "copied_figure": None, "unavailable_copy": [], "mode": 1, "hero": None, "death": 0, "aura": 0, "condition": 0, "row": 7, "col": 7, "move_creation": 0, "walk_count": 0}
]

# Общая структура INITIAL_GAME_STATE, которая будет передаваться в BoardState.
# Это централизованное место для определения начального состояния игры.
INITIAL_GAME_STATE = {
    "board_pieces": INITIAL_BOARD_STATE_PIECES, # Список всех фигур на доске
    "current_player": "white", # Игрок, который ходит первым
    "white_hand": [],          # Карты в руке белых (пока пусто)
    "black_hand": [],          # Карты в руке черных (пока пусто)
    "white_double_add": 0,     # Дополнительные очки/ресурсы для белых (пока 0)
    "black_double_add": 0,     # Дополнительные очки/ресурсы для черных (пока 0)
    "game_log": [],            # Журнал событий игры (пустой на старте)
    "moves_log": [],           # Журнал совершенных ходов (пустой на старте)
    "cards_count": 0,          # Общее количество карт в игре (пока 0)
    "game_status": "waiting",  # Текущий статус игры (ожидание игроков)
    "day_night_cycle": "day",  # Текущий цикл дня/ночи (по умолчанию "day")
    "turn_number": 0,          # Номер текущего хода (начинается с 0)
    "players": {               # Словарь для сопоставления цвета игрока с его UUID (будет заполнен при создании/присоединении комнаты)
        "white": None,
        "black": None
    },
    "last_move_at": None       # Время последнего хода (None на старте)
}