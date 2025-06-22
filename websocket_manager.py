# websocket_manager.py
from fastapi import WebSocket  # Импортируем класс WebSocket из FastAPI
import json  # Для работы с JSON-сообщениями
import asyncio  # Для асинхронного программирования (задачи, таймауты)
import uuid  # Для работы с UUID
from typing import Dict, List, Set, Any  # Для указания типов данных

# !!! НОВЫЙ ИМПОРТ: run_in_threadpool !!!
# Используется для выполнения синхронных операций Redis в асинхронном контексте.
from starlette.concurrency import run_in_threadpool

from redis_manager import redis_manager  # Импорт синглтона RedisManager для Pub/Sub

# Словарь для хранения активных WebSocket-соединений.
# Ключ: room_id (UUID), Значение: set() активных WebSocket-соединений для этой комнаты.
# Это позволяет быстро находить и отправлять сообщения всем клиентам в конкретной комнате.
active_connections: Dict[uuid.UUID, Set[WebSocket]] = {}


class WebSocketManager:
    """
    Класс WebSocketManager управляет жизненным циклом WebSocket-соединений,
    их подключением, отключением и рассылкой сообщений.
    Использует Redis Pub/Sub для синхронизации сообщений между различными экземплярами сервера
    (если их несколько) и для централизованной рассылки сообщений внутри одного сервера.
    """
    _instance = None  # Для паттерна Singleton
    # Словарь для хранения задач (asyncio.Task) слушателей Redis Pub/Sub.
    # Ключ: room_id (UUID), Значение: asyncio.Task (задача, которая слушает Redis-канал).
    _pubsub_listeners: Dict[uuid.UUID, asyncio.Task] = {}

    def __new__(cls):
        """
        Реализация Singleton-паттерна: гарантирует, что существует только один экземпляр WebSocketManager.
        Инициализирует Redis-клиент для Pub/Sub.
        """
        if cls._instance is None:
            cls._instance = super(WebSocketManager, cls).__new__(cls)
            cls._instance.redis_client = redis_manager.get_client()  # Получаем Redis-клиент через RedisManager
            print("WebSocketManager initialized.")
        return cls._instance

    async def connect(self, websocket: WebSocket, room_id: uuid.UUID):
        """
        Устанавливает новое WebSocket-соединение.
        Принимает соединение и регистрирует его для указанной комнаты.
        Если для комнаты еще нет слушателя Redis Pub/Sub, запускает его.

        Параметры:
        - websocket (WebSocket): Объект WebSocket-соединения.
        - room_id (uuid.UUID): ID игровой комнаты, к которой подключается клиент.
        """
        await websocket.accept()  # Принимаем WebSocket-соединение

        # Добавляем WebSocket в набор соединений для данной комнаты.
        # .setdefault() безопасно создает новый set, если room_id еще нет.
        active_connections.setdefault(room_id, set()).add(websocket)

        # Если это первое соединение для данной комнаты, запускаем слушатель Redis Pub/Sub.
        # Этот слушатель будет принимать сообщения из Redis-канала и пересылать их всем клиентам в этой комнате.
        if room_id not in self._pubsub_listeners or self._pubsub_listeners[room_id].done():
            # Создаем фоновую задачу для прослушивания Redis Pub/Sub.
            # Это позволяет синхронизировать состояния между несколькими экземплярами сервера
            # и является централизованным способом рассылки сообщений.
            self._pubsub_listeners[room_id] = asyncio.create_task(self._listen_for_redis_messages(room_id))
            print(f"Started Redis Pub/Sub listener for room {room_id}")

    async def disconnect(self, websocket: WebSocket, room_id: uuid.UUID):
        """
        Отключает WebSocket-соединение.
        Удаляет соединение из списка активных и, если в комнате не осталось клиентов,
        останавливает слушатель Redis Pub/Sub для этой комнаты.

        Параметры:
        - websocket (WebSocket): Объект WebSocket-соединения, которое отключается.
        - room_id (uuid.UUID): ID игровой комнаты, от которой отключается клиент.
        """
        if room_id in active_connections:
            active_connections[room_id].remove(websocket)  # Удаляем WebSocket из набора соединений комнаты
            if not active_connections[room_id]:  # Если в комнате не осталось активных соединений
                del active_connections[room_id]  # Удаляем запись о комнате из словаря
                print(f"No more active connections for room {room_id}. Stopping Redis Pub/Sub listener.")
                # Отменяем задачу слушателя Redis Pub/Sub для этой комнаты
                if room_id in self._pubsub_listeners:
                    self._pubsub_listeners[room_id].cancel()  # Отменяем задачу
                    del self._pubsub_listeners[room_id]  # Удаляем задачу из словаря
        else:
            print(f"Attempted to disconnect from non-existent room {room_id} or websocket already removed.")

    async def broadcast(self, room_id: uuid.UUID, message: Dict[str, Any]):
        """
        Отправляет JSON-сообщение всем активным WebSocket-клиентам в указанной комнате.

        Параметры:
        - room_id (uuid.UUID): ID комнаты, в которую нужно отправить сообщение.
        - message (Dict[str, Any]): Словарь, представляющий JSON-сообщение, которое будет отправлено.
        """
        if room_id in active_connections:
            # Создаем список задач для асинхронной отправки сообщений.
            # Защищаем отправку в блоке try...except, чтобы отловить возможные ошибки (например, закрытые соединения).
            closed_websockets = []
            for connection in list(
                    active_connections[room_id]):  # Итерируем по копии, чтобы безопасно удалять из оригинала
                try:
                    await connection.send_json(message)  # Отправляем сообщение
                except RuntimeError as e:
                    # Например, WebSocket уже был закрыт с другой стороны
                    print(f"Could not send message to WebSocket in room {room_id}: {e}")
                    closed_websockets.append(connection)
                except Exception as e:
                    print(f"Unexpected error sending message to WebSocket in room {room_id}: {e}")
                    closed_websockets.append(connection)

            # Удаляем все соединения, которые вызвали ошибку при отправке
            for ws in closed_websockets:
                if ws in active_connections[room_id]:
                    active_connections[room_id].remove(ws)
                    print(f"Removed unresponsive WebSocket from room {room_id}.")

            # Если после очистки список подключений пуст, можно также остановить Pub/Sub listener
            if not active_connections[room_id]:
                print(f"All connections in room {room_id} are gone after broadcast. Stopping Redis Pub/Sub listener.")
                if room_id in self._pubsub_listeners:
                    self._pubsub_listeners[room_id].cancel()
                    del self._pubsub_listeners[room_id]

    async def publish_to_redis_channel(self, room_id: uuid.UUID, message: Dict[str, Any]):
        """
        Публикует JSON-сообщение в Redis Pub/Sub канал для указанной комнаты.
        Это позволяет синхронизировать сообщения между различными экземплярами сервера
        и обеспечивает централизованную рассылку.

        Параметры:
        - room_id (uuid.UUID): ID комнаты, для которой публикуется сообщение.
        - message (Dict[str, Any]): Словарь, представляющий JSON-сообщение.
        """
        channel_name = f"game_updates:{room_id}"  # Формируем имя канала
        json_message = json.dumps(message)  # Сериализуем сообщение в JSON-строку

        # Публикуем сообщение в Redis-канал.
        # !!! Оборачиваем синхронный вызов Redis в run_in_threadpool !!!
        await run_in_threadpool(self.redis_client.publish, channel_name, json_message)
        print(f"Published message to Redis channel {channel_name}: {json_message}")

    async def _listen_for_redis_messages(self, room_id: uuid.UUID):
        """
        Внутренний асинхронный метод для прослушивания Redis Pub/Sub канала
        и рассылки полученных сообщений локально подключенным клиентам.
        Запускается как фоновая задача при первом подключении клиента к комнате.

        Параметры:
        - room_id (uuid.UUID): ID комнаты, канал которой нужно слушать.
        """
        channel_name = f"game_updates:{room_id}"  # Имя канала для подписки
        # Создаем объект PubSub-клиента Redis.
        # Важно: pubsub() сам по себе не является асинхронным, но методы get_message, subscribe, unsubscribe
        # могут быть обернуты в asyncio.to_thread или run_in_threadpool.
        pubsub = self.redis_client.pubsub()

        # Подписываемся на канал.
        # !!! Оборачиваем синхронный вызов Redis в run_in_threadpool !!!
        await run_in_threadpool(pubsub.subscribe, channel_name)
        print(f"Subscribed to Redis channel {channel_name}")

        try:
            while True:  # Бесконечный цикл для постоянного прослушивания
                # Получаем сообщение из канала с таймаутом.
                # ignore_subscribe_messages=True: игнорируем служебные сообщения Redis (подписка/отписка).
                # timeout=1.0: делает get_message неблокирующим, позволяя циклу периодически проверять отмену задачи.
                # !!! Оборачиваем синхронный вызов Redis в run_in_threadpool !!!
                message = await run_in_threadpool(pubsub.get_message, ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    if message['type'] == 'message':  # Убеждаемся, что это обычное сообщение
                        try:
                            # Декодируем полученные байты (message['data']) в строку, а затем в JSON.
                            data = json.loads(message['data'])
                            print(f"Received from Redis channel {message['channel']}: {data}")
                            # Рассылаем полученное сообщение всем локально подключенным клиентам этой комнаты.
                            await self.broadcast(room_id, data)
                        except json.JSONDecodeError as e:
                            print(f"Error decoding JSON from Redis message: {e}")
                # Небольшая задержка, чтобы избежать 100% загрузки ЦПУ, когда нет сообщений.
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            # Это исключение выбрасывается, когда asyncio.Task.cancel() вызывается.
            print(f"Redis Pub/Sub listener for room {room_id} cancelled.")
        except Exception as e:
            # Ловим любые другие неожиданные ошибки, чтобы задача не упала полностью.
            print(f"Error in Redis Pub/Sub listener for room {room_id}: {e}")
        finally:
            # Гарантируем отписку от канала при завершении задачи.
            # !!! Оборачиваем синхронный вызов Redis в run_in_threadpool !!!
            await run_in_threadpool(pubsub.unsubscribe, channel_name)
            print(f"Unsubscribed from Redis channel {channel_name}")


# Для удобства доступа к единственному экземпляру WebSocketManager.
# В других модулях достаточно импортировать 'websocket_manager'.
websocket_manager = WebSocketManager()