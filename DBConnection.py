import sqlite3
from sqlite3 import Connection

class DatabaseConnection:
    _instance = None
    _connection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
            cls._connection = sqlite3.connect('nightdrive')
        return cls._instance

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
            print(f"Error: '{err}'")
        finally:
            cursor.close()