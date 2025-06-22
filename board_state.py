# board_state.py
import uuid  # Для работы с UUID
from typing import Dict, List, Optional, Any, Union  # Для указания типов данных
from enum import Enum  # Для создания перечислений (Enum)
import copy  # Для создания глубоких копий объектов
import time  # Для работы со временем (например, фиксации времени хода)

from pydantic import BaseModel, Field, ConfigDict  # Для создания моделей данных и валидации с Pydantic


class GameStatus(str, Enum):
    """
    Перечисление статусов игры.
    Каждый статус представлен строковым значением для удобства хранения и использования.
    """
    WAITING = "waiting"  # Ожидание второго игрока
    IN_PROGRESS = "in_progress"  # Игра идет
    FINISHED = "finished"  # Игра завершена (без конкретного победителя, например, ничья)
    RESIGNED = "resigned"  # Один из игроков сдался
    DRAW = "draw"  # Ничья
    CHECK = "check"  # Король под шахом
    CHECKMATE = "checkmate"  # Мат (победа)
    STALEMATE = "stalemate"  # Пат (ничья)


class Piece(BaseModel):
    """
    Модель данных для представления одной шахматной фигуры.
    Использует Pydantic для валидации и удобной сериализации/десериализации.
    """
    figure_id: str  # Уникальный ID фигуры (UUID)
    name: str  # Название фигуры (e.g., "Rook", "Pawn", "King")
    color: str  # Цвет фигуры ("white" или "black")
    row: int  # Текущая строка на доске (0-7)
    col: int  # Текущая колонка на доске (0-7)
    is_first_move: bool = True  # Флаг, указывающий, был ли это первый ход фигуры (для пешек, рокировки)
    description: str = ""  # Описание фигуры (для будущих механик)
    copied_figure: Optional[str] = None  # ID скопированной фигуры (для будущих механик)
    unavailable_copy: List[str] = Field(
        default_factory=list)  # Список ID фигур, которые нельзя скопировать (для будущих механик)
    mode: int = 1  # Режим фигуры (для будущих механик)
    hero: Optional[str] = None  # Статус "героя" (для будущих механик)
    death: int = 0  # Статус "смерти" или счетчик смертей (для будущих механик)
    aura: int = 0  # Сила ауры (для будущих механик)
    condition: int = 0  # Состояние фигуры (для будущих механик)
    move_creation: int = 0  # Счетчик создания ходов (для будущих механик)
    walk_count: int = 0  # Количество сделанных ходов фигурой

    # Конфигурация Pydantic модели.
    # arbitrary_types_allowed=True позволяет использовать произвольные типы (например, Piece в BoardState)
    # без явного объявления их Pydantic моделью, хотя это не лучший подход для сложных структур.
    model_config = ConfigDict(arbitrary_types_allowed=True)


class BoardState:
    """
    Класс BoardState управляет текущим состоянием шахматной доски и логикой игры.
    Он хранит фигуры, отслеживает текущего игрока, логирует ходы и события.
    """

    def __init__(self, initial_data: Dict[str, Any]):
        """
        Инициализирует объект BoardState на основе предоставленных начальных данных.

        Параметры:
        - initial_data (Dict[str, Any]): Словарь с начальными параметрами игры,
          обычно берется из config.INITIAL_GAME_STATE.
          Ожидаемые ключи:
            - "current_player" (str): Кто ходит первым ("white" или "black").
            - "white_hand" (List[Dict]): Рука белых (пока пустой список).
            - "black_hand" (List[Dict]): Рука черных (пока пустой список).
            - "white_double_add" (int): Дополнительные очки белых.
            - "black_double_add" (int): Дополнительные очки черных.
            - "game_log" (List[str]): Журнал событий игры.
            - "moves_log" (List[str]): Журнал выполненных ходов.
            - "cards_count" (int): Количество карт.
            - "game_status" (str/GameStatus): Текущий статус игры.
            - "day_night_cycle" (str): Цикл дня/ночи.
            - "turn_number" (int): Номер текущего хода.
            - "players" (Dict[str, str]): Словарь {цвет: UUID игрока}.
            - "last_move_at" (Optional[int/float]): Время последнего хода (Unix timestamp).
            - "board_pieces" (List[Dict]): Список словарей, описывающих начальное положение фигур.
                                             Каждый словарь должен содержать данные для создания объекта Piece.
        """
        # Основные метаданные игры
        self.board_size: int = 8  # Размер доски (8x8)
        self.current_player: str = initial_data.get("current_player", "white")  # Чей сейчас ход
        self.white_hand: List[Dict] = initial_data.get("white_hand", [])  # Карты в руке белых
        self.black_hand: List[Dict] = initial_data.get("black_hand", [])  # Карты в руке черных
        self.white_double_add: int = initial_data.get("white_double_add", 0)  # Доп. очки белых
        self.black_double_add: int = initial_data.get("black_double_add", 0)  # Доп. очки черных
        self.game_log: List[str] = initial_data.get("game_log", [])  # Лог всех событий игры (включая ошибки)
        self.moves_log: List[str] = initial_data.get("moves_log", [])  # Лог только успешных ходов
        self.cards_count: int = initial_data.get("cards_count", 0)  # Общее количество карт
        # Преобразуем строковое значение статуса в Enum GameStatus
        self.game_status: GameStatus = GameStatus(initial_data.get("game_status", "waiting"))
        self.day_night_cycle: str = initial_data.get("day_night_cycle", "day")  # Текущий цикл (день/ночь)
        self.turn_number: int = initial_data.get("turn_number", 0)  # Номер текущего хода
        # Словарь соответствия цвета игрока и его UUID
        self.players: Dict[str, Optional[str]] = initial_data.get("players", {"white": None, "black": None})
        self.last_move_at: Optional[float] = initial_data.get("last_move_at", None)  # Время последнего хода

        # Инициализация доски (2D-массив) и карт фигур
        self.board: List[List[Optional[Dict]]] = [[None for _ in range(self.board_size)] for _ in
                                                  range(self.board_size)]
        self._figure_id_to_piece_map: Dict[str, Piece] = {}  # Карта UUID фигуры к объекту Piece
        self._coord_to_piece_map: Dict[str, Piece] = {}  # Карта координат "row_col" к объекту Piece

        # Заполнение доски и карт фигур из начальных данных
        # initial_data["board_pieces"] - это список словарей, каждый из которых представляет фигуру.
        for piece_data in initial_data.get("board_pieces", []):
            piece = Piece(**piece_data)  # Создаем объект Piece из словаря
            self.board[piece.row][piece.col] = piece.model_dump()  # Сохраняем сериализованную фигуру в 2D-массив доски
            self._figure_id_to_piece_map[piece.figure_id] = piece  # Добавляем фигуру в карту по ID
            self._coord_to_piece_map[f"{piece.row}_{piece.col}"] = piece  # Добавляем фигуру в карту по координатам

    def _remove_piece_from_board(self, piece: Piece):
        """
        Удаляет фигуру с доски (с 2D-массива и из внутренних карт).

        Параметры:
        - piece (Piece): Объект фигуры, которую нужно удалить.
        """
        if piece:
            self.board[piece.row][piece.col] = None  # Устанавливаем None на месте фигуры в 2D-массиве
            if f"{piece.row}_{piece.col}" in self._coord_to_piece_map:
                del self._coord_to_piece_map[f"{piece.row}_{piece.col}"]  # Удаляем из карты координат
            if piece.figure_id in self._figure_id_to_piece_map:
                del self._figure_id_to_piece_map[piece.figure_id]  # Удаляем из карты по ID

    def _get_piece_at(self, row: int, col: int) -> Optional[Piece]:
        """
        Возвращает объект фигуры по заданным координатам.

        Параметры:
        - row (int): Строка.
        - col (int): Колонка.

        Возвращает:
        - Optional[Piece]: Объект Piece, если фигура найдена, иначе None.
        """
        return self._coord_to_piece_map.get(f"{row}_{col}")

    def to_json_serializable(self) -> Dict[str, Any]:
        """
        Преобразует текущее состояние доски в словарь, пригодный для JSON-сериализации.
        Этот метод используется для сохранения состояния в Redis и отправки клиентам.

        Возвращает:
        - Dict[str, Any]: Словарь, представляющий текущее состояние доски,
          где все объекты Piece сериализованы в словари.
        """
        # Преобразуем объекты Piece из _figure_id_to_piece_map обратно в словари
        # (или можно использовать self.board, где они уже в виде словарей).
        # Предпочтительнее использовать _figure_id_to_piece_map, чтобы получить все фигуры,
        # включая те, что могли быть "захвачены" и все еще хранятся, но не на доске.
        serializable_pieces = [piece.model_dump() for piece in self._figure_id_to_piece_map.values()]

        return {
            "board_size": self.board_size,
            "board_pieces": serializable_pieces,  # Все фигуры, включая те, что вне доски
            "current_player": self.current_player,
            "white_hand": self.white_hand,
            "black_hand": self.black_hand,
            "white_double_add": self.white_double_add,
            "black_double_add": self.black_double_add,
            "game_log": self.game_log,
            "moves_log": self.moves_log,
            "cards_count": self.cards_count,
            "game_status": self.game_status.value,  # Важно преобразовать Enum в строку
            "day_night_cycle": self.day_night_cycle,
            "turn_number": self.turn_number,
            "players": self.players,
            "last_move_at": self.last_move_at
        }

    def clone(self) -> 'BoardState':
        """
        Создает глубокую копию текущего состояния доски.
        Используется для симуляций (например, для проверки шаха/мата) без изменения текущего состояния.

        Возвращает:
        - BoardState: Новая копия объекта BoardState.
        """
        # Создаем глубокую копию всех изменяемых атрибутов, чтобы избежать побочных эффектов.
        cloned_initial_data = {
            "current_player": self.current_player,
            "white_hand": copy.deepcopy(self.white_hand),
            "black_hand": copy.deepcopy(self.black_hand),
            "white_double_add": self.white_double_add,
            "black_double_add": self.black_double_add,
            "game_log": copy.deepcopy(self.game_log),
            "moves_log": copy.deepcopy(self.moves_log),
            "cards_count": self.cards_count,
            "game_status": self.game_status.value,  # Клонируем значение Enum
            "day_night_cycle": self.day_night_cycle,
            "turn_number": self.turn_number,
            "players": copy.deepcopy(self.players),
            "last_move_at": self.last_move_at,
            "board_pieces": [piece.model_dump() for piece in self._figure_id_to_piece_map.values()]
            # Сериализуем фигуры для клонирования
        }
        # Создаем новый экземпляр BoardState из клонированных данных.
        return BoardState(cloned_initial_data)

    async def move_piece(self, figure_id: str, new_row: int, new_col: int,
                         player_making_move_id: uuid.UUID) -> 'BoardState':
        """
        Обрабатывает попытку перемещения шахматной фигуры.
        Выполняет различные проверки на валидность хода согласно базовым правилам.
        Обновляет состояние доски и game_log.

        Параметры:
        - figure_id (str): UUID фигуры, которую нужно переместить.
                           Берется из payload WebSocket-сообщения клиента.
        - new_row (int): Целевая строка для фигуры.
                         Берется из payload WebSocket-сообщения клиента.
        - new_col (int): Целевая колонка для фигуры.
                         Берется из payload WebSocket-сообщения клиента.
        - player_making_move_id (uuid.UUID): UUID игрока, который инициировал ход.
                                            Временно берется из payload WebSocket-сообщения.
                                            (В будущем: должен извлекаться из авторизационного токена).

        Возвращает:
        - BoardState: Обновленный объект BoardState (self).
                      Даже если ход невалиден, game_log будет обновлен сообщением об ошибке,
                      и объект BoardState будет возвращен для сохранения его состояния.
        """
        piece = self._figure_id_to_piece_map.get(figure_id)
        if not piece:
            self.game_log.append(f"Error: Piece with ID {figure_id} not found.")
            return self  # Возвращаем себя, чтобы изменения в логе сохранились

        # Определяем цвет игрока, который делает ход, на основе его UUID.
        actual_player_color = None
        if str(player_making_move_id) == self.players.get('white'):
            actual_player_color = 'white'
        elif str(player_making_move_id) == self.players.get('black'):
            actual_player_color = 'black'

        if actual_player_color is None:
            self.game_log.append(f"Error: Player {player_making_move_id} is not a registered player in this game.")
            return self  # Возвращаем себя

        # Проверка, что ход делает правильный игрок по очередности (т.е. его цвет соответствует current_player).
        if actual_player_color != self.current_player:
            self.game_log.append(
                f"Error: It's {self.current_player}'s turn, but {actual_player_color} player tried to move.")
            return self  # Возвращаем себя

        # Проверка, что перемещается фигура СВОЕГО цвета.
        if piece.color != actual_player_color:
            self.game_log.append(f"Error: {actual_player_color} player tried to move a {piece.color} piece.")
            return self  # Возвращаем себя

        # Проверка на выход за границы доски
        if not (0 <= new_row < self.board_size and 0 <= new_col < self.board_size):
            self.game_log.append(f"Error: Invalid coordinates ({new_row}, {new_col}) for piece {piece.figure_id}.")
            return self  # Возвращаем себя

        old_row, old_col = piece.row, piece.col

        target_piece = self._get_piece_at(new_row, new_col)  # Проверяем, есть ли фигура на целевой клетке
        if target_piece:
            if target_piece.color != piece.color:
                # Взятие фигуры: если фигура на целевой клетке другого цвета
                self._remove_piece_from_board(target_piece)  # Удаляем захваченную фигуру с доски
                self.game_log.append(
                    f"Piece {piece.figure_id} ({piece.name} {piece.color}) took {target_piece.figure_id} ({target_piece.name} {target_piece.color}) at ({new_row}, {new_col}).")
            else:
                # Целевая клетка занята своей фигурой
                self.game_log.append(
                    f"Error: Destination ({new_row}, {new_col}) occupied by own piece {target_piece.name} ({target_piece.figure_id}).")
                return self  # Возвращаем себя

        # --- Выполнение хода (обновление состояния) ---

        # Очищаем старую позицию на 2D-массиве доски
        self.board[old_row][old_col] = None
        # Удаляем старую запись из _coord_to_piece_map
        if f"{old_row}_{old_col}" in self._coord_to_piece_map:
            del self._coord_to_piece_map[f"{old_row}_{old_col}"]

        # Обновляем координаты объекта Piece
        piece.row = new_row
        piece.col = new_col
        piece.is_first_move = False  # Отмечаем, что фигура сделала свой первый ход
        piece.walk_count += 1  # Увеличиваем счетчик ходов фигуры

        # Добавляем обновленную фигуру в _coord_to_piece_map по новой позиции
        self._coord_to_piece_map[f"{new_row}_{new_col}"] = piece
        # Обновляем состояние доски (2D-массив) с сериализованным представлением фигуры
        self.board[new_row][new_col] = piece.model_dump()

        # Добавляем запись об успешном ходе в moves_log (краткий лог ходов)
        self.moves_log.append(f"{self.current_player} {piece.name} from ({old_row},{old_col}) to ({new_row},{new_col})")

        # --- Обновление общего состояния игры ---

        # Переключаем текущего игрока на следующего
        self.current_player = "black" if self.current_player == "white" else "white"
        self.turn_number += 1  # Увеличиваем номер хода
        self.last_move_at = time.time()  # Фиксируем время последнего хода
        # Добавляем запись об успешном ходе в общий game_log
        self.game_log.append(
            f"Successful move: {piece.name} {piece.color} from ({old_row}, {old_col}) to ({new_row}, {new_col}). New current player: {self.current_player}.")

        return self  # Возвращаем обновленный объект BoardState
