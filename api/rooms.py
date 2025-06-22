# api/rooms.py
from fastapi import APIRouter, Depends, HTTPException, status  # Импорт компонентов FastAPI
from pydantic import BaseModel, ConfigDict  # Импорт BaseModel и ConfigDict из Pydantic
import uuid  # Для работы с UUID
from typing import List, Optional, Dict, Any  # Для указания типов данных

from game_manager import game_manager, GameRoomInfo, GameStatus  # Импорт менеджера игры и моделей
from board_state import BoardState  # Импорт BoardState для работы с состоянием доски
from websocket_manager import websocket_manager  # Импорт WebSocketManager для отправки обновлений

# Создаем новый APIRouter для маршрутов, связанных с комнатами
router = APIRouter()


class CreateRoomRequest(BaseModel):
    """
    Pydantic модель для валидации тела запроса при создании новой комнаты.
    Ожидается только название комнаты.
    """
    room_name: str  # Название создаваемой комнаты


class RoomInfoResponse(BaseModel):
    """
    Pydantic модель для стандартизированного ответа при получении краткой информации о комнате.
    Используется для списка комнат.
    """
    id: uuid.UUID  # Уникальный ID комнаты
    name: str  # Название комнаты
    status: GameStatus  # Текущий статус игры (ожидание, в процессе и т.д.)
    player1_id: Optional[uuid.UUID] = None  # ID первого игрока (белые)
    player2_id: Optional[uuid.UUID] = None  # ID второго игрока (черные)

    # Конфигурация Pydantic модели.
    # arbitrary_types_allowed=True: позволяет использовать произвольные типы (например, UUID).
    # use_enum_values=True: при сериализации Enum-значения будут преобразованы в их строковые значения.
    model_config = ConfigDict(arbitrary_types_allowed=True, use_enum_values=True)


class FullGameInfoResponse(BaseModel):
    """
    Pydantic модель для стандартизированного ответа при получении полной информации о комнате.
    Включает в себя полное состояние доски.
    """
    id: uuid.UUID  # Уникальный ID комнаты
    name: str  # Название комнаты
    status: GameStatus  # Текущий статус игры
    player1_id: Optional[uuid.UUID] = None  # ID первого игрока
    player2_id: Optional[uuid.UUID] = None  # ID второго игрока
    board_state: Dict[str, Any]  # Сериализованное состояние доски (словарь, а не объект BoardState)
    # Используем Dict[str, Any], т.к. BoardState.to_json_serializable() возвращает словарь.
    created_at: int  # Время создания комнаты (Unix timestamp)
    updated_at: int  # Время последнего обновления (Unix timestamp)

    # Конфигурация Pydantic модели.
    model_config = ConfigDict(arbitrary_types_allowed=True, use_enum_values=True)


@router.post("/rooms", response_model=FullGameInfoResponse, status_code=status.HTTP_201_CREATED)
async def create_room(request: CreateRoomRequest):
    """
    Создает новую игровую комнату.

    Принимает:
    - request (CreateRoomRequest): Объект запроса, содержащий 'room_name'.

    Возвращает:
    - FullGameInfoResponse: Полная информация о созданной комнате.

    Raises:
    - HTTPException 400: Если комната с таким именем уже существует (не реализовано, но может быть добавлено).
    """
    # Временное решение для MVP: генерируем player_id.
    # В будущем здесь должен использоваться ID авторизованного пользователя.
    player1_id = uuid.uuid4()
    # Создаем комнату через GameManager
    new_room = await game_manager.create_room(request.room_name, player1_id)
    print(f"Room {new_room.name} created by player {player1_id}. Room ID: {new_room.id}")

    # Подготавливаем ответ: board_state должен быть словарем
    room_data = new_room.model_dump()
    room_data['board_state'] = new_room.board_state.to_json_serializable()
    return room_data


@router.get("/rooms", response_model=List[RoomInfoResponse])
async def get_rooms():
    """
    Возвращает список всех существующих игровых комнат с краткой информацией.

    Возвращает:
    - List[RoomInfoResponse]: Список объектов RoomInfoResponse.
    """
    rooms = await game_manager.get_all_rooms()
    # Возвращаем только краткую информацию, исключая полное состояние доски для списка.
    return [RoomInfoResponse.model_validate(room.model_dump()) for room in rooms]


@router.get("/rooms/{room_id}", response_model=FullGameInfoResponse)
async def get_room_info(room_id: uuid.UUID):
    """
    Возвращает полную информацию о конкретной игровой комнате по её ID.

    Параметры:
    - room_id (uuid.UUID): ID комнаты.

    Возвращает:
    - FullGameInfoResponse: Полная информация о комнате, включая состояние доски.

    Raises:
    - HTTPException 404: Если комната с указанным ID не найдена.
    """
    room = await game_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.")

    # Подготавливаем ответ: board_state должен быть словарем
    room_data = room.model_dump()
    room_data['board_state'] = room.board_state.to_json_serializable()
    return room_data


@router.post("/rooms/{room_id}/join", response_model=FullGameInfoResponse)
async def join_room(room_id: uuid.UUID):
    """
    Позволяет игроку присоединиться к существующей комнате.
    Если комната уже полна, возвращает ошибку.

    Параметры:
    - room_id (uuid.UUID): ID комнаты, к которой нужно присоединиться.

    Возвращает:
    - FullGameInfoResponse: Обновленная информация о комнате.

    Raises:
    - HTTPException 404: Если комната не найдена.
    - HTTPException 400: Если комната уже полна или игрок уже в комнате.
    """
    # Временное решение для MVP: генерируем player_id.
    # В будущем здесь должен использоваться ID авторизованного пользователя.
    player2_id = uuid.uuid4()

    try:
        updated_room = await game_manager.join_room(room_id, player2_id)
        if not updated_room:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found.")

        print(f"Player {player2_id} joined room {room_id}. Room status: {updated_room.status.value}")

        # Оповещаем всех клиентов в комнате об изменении статуса (игрок присоединился)
        # Это будет принято WebSocket-клиентами
        update_message = {
            "type": "room_update",  # Тип сообщения для клиента
            "room_id": str(updated_room.id),
            "status": updated_room.status.value,
            "player1_id": str(updated_room.player1_id),
            "player2_id": str(updated_room.player2_id),
            "board_state": updated_room.board_state.to_json_serializable(),  # Полное состояние доски
            "message": f"Player {player2_id} joined the room."
        }
        # Публикуем сообщение в Redis Pub/Sub, чтобы все подключенные клиенты (даже на других серверах) получили его.
        await websocket_manager.publish_to_redis_channel(room_id, update_message)

        # Подготавливаем ответ для HTTP-клиента
        room_data = updated_room.model_dump()
        room_data['board_state'] = updated_room.board_state.to_json_serializable()
        return room_data

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"An unexpected error occurred: {e}")


@router.post("/games/{room_id}/move", response_model=FullGameInfoResponse)
async def make_move(
        room_id: uuid.UUID,
        figure_id: str,
        new_row: int,
        new_col: int,
        # Временное решение: player_id передается в теле запроса.
        # В реальном приложении он должен извлекаться из JWT токена авторизации.
        player_id: uuid.UUID
):
    """
    Обрабатывает ход игрока. Принимает ID фигуры и новые координаты.

    Параметры:
    - room_id (uuid.UUID): ID комнаты, в которой делается ход.
    - figure_id (str): UUID фигуры, которую нужно переместить.
    - new_row (int): Новая строка (0-7).
    - new_col (int): Новая колонка (0-7).
    - player_id (uuid.UUID): ID игрока, который делает ход.

    Возвращает:
    - FullGameInfoResponse: Обновленное состояние комнаты после хода.

    Raises:
    - HTTPException 404: Если комната или фигура не найдены.
    - HTTPException 400: Если ход невалиден (неправильный игрок, некорректные координаты и т.д.).
    - HTTPException 500: При внутренних ошибках сервера.
    """
    room = await game_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found.")

    # Выполняем ход, используя метод move_piece из BoardState.
    # Метод move_piece обновляет внутреннее состояние BoardState (game_log, moves_log, позиции фигур).
    updated_board_state = await room.board_state.move_piece(figure_id, new_row, new_col, player_id)

    # Проверяем, были ли ошибки в процессе хода (записываются в game_log).
    # Если move_piece добавил ошибку в game_log, мы можем вернуть HTTP 400.
    # (Это простая проверка, более сложная логика может понадобиться для разных типов ошибок)
    if updated_board_state.game_log and "Error:" in updated_board_state.game_log[-1]:
        # Сохраняем состояние с логом ошибки перед возвратом ошибки клиенту
        await game_manager.update_room_state(room_id, updated_board_state)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=updated_board_state.game_log[-1].replace("Error: ", ""))

    # Обновляем состояние комнаты в GameManager (который затем сохранит его в Redis).
    # Это важно, чтобы персистировать изменения, сделанные методом move_piece.
    updated_room = await game_manager.update_room_state(room_id, updated_board_state)

    if updated_room:
        # Если комната успешно обновлена, отправляем оповещение всем клиентам через WebSocket.
        update_message = {
            "type": "game_state_update",  # Тип сообщения для клиентов WebSocket
            "state": updated_room.board_state.to_json_serializable()
            # Отправляем полное сериализованное состояние доски
        }
        # Публикуем сообщение в Redis Pub/Sub. WebSocketManager позаботится о рассылке.
        await websocket_manager.publish_to_redis_channel(room_id, update_message)

        # Подготавливаем ответ для HTTP-клиента
        room_data = updated_room.model_dump()
        room_data['board_state'] = updated_room.board_state.to_json_serializable()
        return room_data
    else:
        # Если по какой-то причине update_room_state вернул None (например, комната пропала)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update game state.")


@router.post("/game/{room_id}/surrender", response_model=FullGameInfoResponse)
async def surrender_game(room_id: uuid.UUID, player_id: uuid.UUID):  # player_id пока в теле запроса
    """
    Обрабатывает сдачу партии игроком. Обновляет статус игры и оповещает клиентов.

    Параметры:
    - room_id (uuid.UUID): ID комнаты, в которой игрок сдается.
    - player_id (uuid.UUID): ID игрока, который сдается.

    Возвращает:
    - FullGameInfoResponse: Обновленное состояние комнаты со статусом "resigned".

    Raises:
    - HTTPException 404: Если комната не найдена.
    - HTTPException 400: Если игрок не является участником комнаты.
    """
    room = await game_manager.get_room(room_id)
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found.")

    try:
        updated_room = await game_manager.surrender_room(room_id, player_id)

        if updated_room:
            # Оповестить всех клиентов в комнате о смене статуса
            update_message = {
                "type": "game_state_update",
                "state": updated_room.board_state.to_json_serializable()  # Отправляем обновленное состояние доски
            }
            # Публикуем в Redis, чтобы все экземпляры сервера получили и разослали
            await websocket_manager.publish_to_redis_channel(room_id, update_message)

            # Подготавливаем ответ для HTTP-клиента
            room_data = updated_room.model_dump()
            room_data['board_state'] = updated_room.board_state.to_json_serializable()
            return room_data

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"An unexpected error occurred: {e}")


@router.delete("/rooms/clear_all", status_code=status.HTTP_204_NO_CONTENT)
async def clear_all_rooms():
    """
    Удаляет все игровые комнаты из системы.
    ЭТО ДЕЙСТВИЕ НЕОБРАТИМО И ДОЛЖНО ИСПОЛЬЗОВАТЬСЯ ОСТОРОЖНО,
    предпочтительно только в DEV/TEST окружениях.

    Возвращает:
    - 204 No Content: В случае успешного удаления.
    - HTTPException 500: В случае внутренней ошибки сервера.
    """
    try:
        await game_manager.delete_all_rooms()
        # Можно добавить широковещательное сообщение через WebSocket,
        # если есть общая комната или канал для всех клиентов.
        print("All rooms cleared successfully.")
        return {"message": "All rooms cleared."}  # FastAPI вернет 204 No Content, если тело пустое,
        # но можно и явно вернуть {"message": ...}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to clear all rooms: {e}")