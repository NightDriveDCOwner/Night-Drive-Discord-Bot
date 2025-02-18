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

    def create_tables(self):
        tables = [
            """
            CREATE TABLE IF NOT EXISTS TIMEOUT (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID STRING,
                REASON TEXT,
                TIMEOUTTO TEXT,
                IMAGEPATH TEXT,
                REMOVED INTEGER DEFAULT 0,
                REMOVEDBY INTEGER DEFAULT 0,
                REMOVEDREASON TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS BAN (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID STRING,
                BANNEDTO TEXT,
                UNBAN INTEGER DEFAULT 0
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS BLACKLIST (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                WORD STRING
            )
            """
            # Fügen Sie hier weitere SQL-Anweisungen für andere Tabellen hinzu
        ]

        cursor = self._connection.cursor()
        try:
            for table in tables:
                cursor.execute(table)
            self._connection.commit()
        except Exception as err:
            self.logger.error(f"Error creating tables: '{err}'")
        finally:
            cursor.close()            