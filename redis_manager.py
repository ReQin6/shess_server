# redis_manager.py
import redis  # Импортируем библиотеку Redis
from config import REDIS_URL # Импортируем URL для подключения к Redis из файла конфигурации

class RedisManager:
    """
    Класс RedisManager реализует паттерн Singleton для управления подключением к Redis.
    Это гарантирует, что в приложении будет только один активный клиент Redis,
    предотвращая создание множества соединений.
    """
    _instance = None # Приватная переменная для хранения единственного экземпляра класса

    def __new__(cls):
        """
        Метод __new__ вызывается до __init__ и контролирует создание экземпляра класса.
        Он проверяет, существует ли уже экземпляр, и если нет, создает его.
        """
        if cls._instance is None:
            cls._instance = super(RedisManager, cls).__new__(cls)
            # Инициализация Redis-клиента.
            # decode_responses=True позволяет получать строковые значения из Redis вместо байтов.
            cls._instance.redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)
            print("Redis client initialized.")
        return cls._instance

    def get_client(self):
        """
        Возвращает активный Redis-клиент.

        Возвращает:
        - redis.StrictRedis: Экземпляр Redis-клиента.
        """
        return self.redis_client

    async def close_client(self):
        """
        Асинхронно закрывает соединение с Redis-клиентом.
        Используется при завершении работы приложения для корректного освобождения ресурсов.
        """
        # Проверяем, существует ли клиент и является ли он экземпляром Redis-клиента
        if self._instance and hasattr(self._instance, 'redis_client') and self._instance.redis_client:
            await self._instance.redis_client.close()
            print("Redis client connection closed.")
        else:
            print("No active Redis client to close.")

# Для удобства доступа к единственному экземпляру RedisManager
# В других модулях можно просто импортировать 'redis_manager'
redis_manager = RedisManager()