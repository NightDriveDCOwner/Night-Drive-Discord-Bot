import sqlite3
import logging
from sqlite3 import Connection
import os


class DatabaseConnection:
    _instance = None
    _connection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
            cls._connection = sqlite3.connect('nightdrive')
            cls._setup_logging(cls)
        return cls._instance    

    @staticmethod
    def _setup_logging(cls):
        cls.logger = logging.getLogger("DatabaseConnection")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        cls.logger.setLevel(logging_level)

        if not cls.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            cls.logger.addHandler(handler)

    @property
    def connection(self) -> Connection:
        return self._connection

    def execute_sql_statement(self, query: str, params: tuple = ()):
        cursor = self._connection.cursor()
        try:
            cursor.execute(query, params)
            self._connection.commit()
            return cursor
        except Exception as err:
            self.logger.error(f"Error: '{err}'")
        finally:
            cursor.close()