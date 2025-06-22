# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from api import rooms  # Импортируем роутер для комнат, содержит HTTP-эндпоинты
import uuid  # Для работы с UUID (например, ID комнат)

from websocket_manager import websocket_manager  # Менеджер для управления WebSocket-соединениями и рассылкой сообщений
from game_manager import game_manager  # Менеджер для управления логикой игры и данными комнат
from config import REDIS_URL  # Конфигурация, например, URL для Redis
from redis_manager import redis_manager  # Менеджер для работы с Redis-клиентом

import json  # Для работы с JSON-сообщениями в WebSocket

# Инициализация FastAPI приложения
app = FastAPI()

# Подключение роутера для API комнат.
# Все маршруты, определенные в api/rooms.py, будут доступны по префиксу /api.
app.include_router(rooms.router, prefix="/api", tags=["Rooms API"])


@app.on_event("startup")
async def startup_event():
    """
    Обработчик события запуска приложения.
    Инициализирует Redis-клиент и проверяет соединение с Redis.
    """
    print("Redis client initialized.")
    try:
        await redis_manager.get_client().ping()
        print("Successfully connected to Redis!")
    except Exception as e:
        print(f"Could not connect to Redis: {e}")
        # В реальном приложении здесь можно поднять исключение или предпринять другие действия,
        # если без Redis работа невозможна.


@app.on_event("shutdown")
async def shutdown_event():
    """
    Обработчик события остановки приложения.
    Закрывает соединение с Redis-клиентом.
    """
    print("Shutting down Redis client.")
    # Обработка исключения при закрытии, если клиент уже отключен,
    # чтобы избежать ошибок при повторном закрытии.
    try:
        await redis_manager.close_client()
    except Exception as e:
        print(f"Error closing Redis client: {e}")


@app.websocket("/ws/game/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: uuid.UUID):
    """
    Основной WebSocket-эндпоинт для игровой комнаты.
    Устанавливает и управляет WebSocket-соединением для каждого игрока.

    Параметры:
    - websocket (WebSocket): Объект WebSocket-соединения, предоставляемый FastAPI.
    - room_id (uuid.UUID): ID игровой комнаты, извлекается из URL-пути WebSocket (например, /ws/game/123e4567-e89b-12d3-a456-426614174000).

    Принимаемые сообщения (JSON):
    - type: "move"
      payload:
        figure_id (str): UUID фигуры, которую нужно переместить.
        new_row (int): Новая строка для фигуры.
        new_col (int): Новая колонка для фигуры.
        player_id (str): UUID игрока, который делает ход.
                         (Внимание: в будущих версиях должен извлекаться из токена авторизации для безопасности!)
    - type: "chat_message"
      payload:
        message (str): Текст сообщения чата.

    Отправляемые сообщения (JSON):
    - type: "error"
      message (str): Описание ошибки.
    - type: "game_state_update"
      state (dict): Сериализованное состояние доски (из BoardState.to_json_serializable()).
    - type: "chat_message"
      sender (str): ID отправителя (пока "Anonymous", будет player_id).
      message (str): Текст сообщения.
    """
    # Подключаем WebSocket к менеджеру, регистрируя его в соответствующей комнате.
    await websocket_manager.connect(websocket, room_id)
    print(f"WebSocket connected to room {room_id}")

    # Получаем начальное состояние комнаты для проверки и, возможно, использования player_ids.
    # Это делается здесь, чтобы избежать повторных загрузок при каждом сообщении чата,
    # но для хода все равно нужно получать актуальное состояние.
    room = await game_manager.get_room(room_id)
    if not room:
        await websocket.send_json({"type": "error", "message": "Game room not found. Disconnecting."})
        await websocket_manager.disconnect(websocket, room_id)
        return

    # Внешний try-блок для обработки отключения WebSocket-соединения (WebSocketDisconnect).
    try:
        while True:  # Бесконечный цикл для приема сообщений через WebSocket
            # Внутренний try-блок для обработки ошибок при приеме и парсинге КАЖДОГО отдельного сообщения.
            # Это позволяет соединению оставаться открытым, если ошибка не критична.
            try:
                message = await websocket.receive_json()  # Ожидаем JSON-сообщение от клиента

                # Обработка сообщения о ходе
                if message["type"] == "move":
                    payload = message["payload"]
                    figure_id = payload.get("figure_id")
                    new_row = payload.get("new_row")
                    new_col = payload.get("new_col")
                    # player_id временно передается клиентом для отладки логики ходов.
                    # В будущем: player_id должен извлекаться из токена авторизации.
                    player_making_move_id_str = payload.get("player_id")

                    # Базовая валидация входящих данных хода
                    if not all([figure_id, new_row is not None, new_col is not None, player_making_move_id_str]):
                        await websocket.send_json({"type": "error",
                                                   "message": "Missing move parameters (figure_id, new_row, new_col, player_id)."})
                        continue  # Продолжаем слушать следующие сообщения

                    # Преобразование player_id из строки в UUID
                    try:
                        player_making_move_id = uuid.UUID(player_making_move_id_str)
                    except ValueError:
                        await websocket.send_json({"type": "error", "message": "Invalid player_id format."})
                        continue  # Продолжаем слушать следующие сообщения

                    # Загружаем самое актуальное состояние комнаты из Redis перед обработкой хода.
                    # Это важно, чтобы избежать использования устаревших данных, если другое действие
                    # изменило комнату между приемом сообщения и его обработкой.
                    room_before_move = await game_manager.get_room(room_id)
                    if not room_before_move:
                        await websocket.send_json(
                            {"type": "error", "message": "Game room not found during move processing. Disconnecting."})
                        await websocket_manager.disconnect(websocket, room_id)
                        continue  # Продолжаем слушать следующие сообщения

                    # Вызываем метод move_piece на объекте BoardState.
                    # Метод move_piece теперь всегда возвращает обновленный объект BoardState,
                    # даже если ход невалиден (в этом случае ошибки записываются в game_log).
                    await room_before_move.board_state.move_piece(figure_id, new_row, new_col, player_making_move_id)

                    # Сохраняем обновленное состояние комнаты обратно в Redis.
                    # Это гарантирует, что изменения, включая записи в game_log, будут персистентны.
                    await game_manager.update_room_state(room_id, room_before_move.board_state)

                    # Отправляем обновленное состояние игры всем клиентам, подписанным на эту комнату.
                    # Клиент должен будет обработать это сообщение, чтобы обновить свою доску и UI.
                    update_message = {
                        "type": "game_state_update",
                        "state": room_before_move.board_state.to_json_serializable()
                        # Отправляем сериализованное состояние доски
                    }
                    await websocket_manager.publish_to_redis_channel(room_id, update_message)

                    # Проверяем, была ли добавлена ошибка в game_log (например, если ход невалиден)
                    # и отправляем специфическое сообщение об ошибке клиенту, который сделал запрос.
                    last_log_entry = room_before_move.board_state.game_log[
                        -1] if room_before_move.board_state.game_log else ""
                    if "Error:" in last_log_entry:
                        await websocket.send_json({"type": "error", "message": last_log_entry})
                    # else:
                    #      await websocket.send_json({"type": "success", "message": "Move processed successfully."})

                # Обработка сообщения чата
                elif message["type"] == "chat_message":
                    message_text = message.get("payload", {}).get("message")
                    if not message_text:
                        await websocket.send_json({"type": "error", "message": "Chat message cannot be empty."})
                        continue  # Продолжаем слушать следующие сообщения

                    # TODO: В будущем здесь необходимо получить player_id из авторизации.
                    # Пока используется player_making_move_id, если он был определен в предыдущем ходе,
                    # иначе "Anonymous". Это заглушка.
                    sender_id = str(player_making_move_id) if 'player_making_move_id' in locals() else "Anonymous"
                    chat_message = {
                        "type": "chat_message",
                        "sender": sender_id,
                        "message": message_text
                    }
                    # Публикуем сообщение чата через Redis channel, чтобы оно дошло до всех клиентов в комнате.
                    await websocket_manager.publish_to_redis_channel(room_id, chat_message)

                # Обработка неизвестных типов сообщений
                else:
                    await websocket.send_json({"type": "error", "message": "Unknown message type."})

            # Обработка ошибок парсинга JSON для отдельных сообщений.
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON format."})
            # Обработка любых других неожиданных ошибок при обработке сообщения.
            except Exception as e:
                print(f"Error processing WebSocket message for room {room_id}: {e}")
                await websocket.send_json({"type": "error", "message": f"Server error during message processing: {e}"})

    # Внешний except-блок для обработки отключения WebSocket-соединения.
    # WebSocketDisconnect является исключением, которое FastAPI вызывает при закрытии соединения.
    except WebSocketDisconnect:
        print(f"WebSocket disconnected from room {room_id}")
        await websocket_manager.disconnect(websocket, room_id)
        # При WebSocketDisconnect цикл while True автоматически завершается,
        # поэтому явный 'break' здесь не нужен.
    # Внешний except-блок для любых других критических ошибок, которые могут привести к разрыву соединения.
    except Exception as e:
        print(f"Critical WebSocket error in room {room_id}: {e}")
        await websocket.send_json({"type": "error", "message": f"Critical server error: {e}. Disconnecting."})
        await websocket_manager.disconnect(websocket, room_id)


@app.get("/")
async def read_root():
    """
    Корневой HTTP GET маршрут.
    Используется для проверки работоспособности сервера.
    Возвращает простую HTML-страницу.
    """
    return HTMLResponse("<h1>Chess Server is Running!</h1>")