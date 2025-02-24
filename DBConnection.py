import sqlite3
import logging
from sqlite3 import Connection
import os
import aiosqlite
from dotenv import load_dotenv, set_key
import re

load_dotenv(dotenv_path="envs/databases.env")


class DatabaseConnectionManager:
    _instances = []

    @classmethod
    async def get_connection(cls, guild_id: int, guild_name: str) -> aiosqlite.Connection:
        instance = next(
            (conn for conn in cls._instances if conn['guild_id'] == guild_id), None)
        if instance is None:
            connection = await cls._create_connection(guild_id, guild_name)
            cls._instances.append(
                {'guild_id': guild_id, 'connection': connection})
        else:
            connection = instance['connection']
        return connection

    @classmethod
    async def _create_connection(cls, guild_id: int, guild_name: str) -> aiosqlite.Connection:
        db_name = cls._sanitize_db_name(guild_name.lower())
        db_path = os.path.join("databases", db_name)
        # db_path = cls._ensure_unique_db_path(db_path)
        connection = await aiosqlite.connect(db_path)
        cls._setup_logging(connection)
        cls._update_env_file(guild_id, db_name)

        # Test the connection
        try:
            async with connection.execute("SELECT COUNT(ID) FROM USER") as cursor:
                (await cursor.fetchone())
            logging.getLogger(f"DatabaseConnection_{connection}").info(
                "Connection to the database was successful.")
        except Exception as e:
            logging.getLogger(f"DatabaseConnection_{connection}").error(
                f"Failed to connect to the database: {e}")

        return connection

    @staticmethod
    def _sanitize_db_name(guild_name: str) -> str:
        # Remove spaces, special characters, and numbers
        sanitized_name = re.sub(r'[^a-zA-Z]', '', guild_name)
        return f"{sanitized_name}"

    @staticmethod
    def _ensure_unique_db_path(db_path: str) -> str:
        base, ext = os.path.splitext(db_path)
        counter = 2
        while os.path.exists(db_path):
            db_path = f"{base}_{counter}{ext}"
            counter += 1
        return db_path

    @staticmethod
    def _setup_logging(connection):
        logger = logging.getLogger(f"DatabaseConnection_{connection}")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        logger.setLevel(logging_level)

        if not logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    @staticmethod
    def _update_env_file(guild_id: int, db_name: str):
        env_path = "envs/databases.env"
        set_key(env_path, str(guild_id), db_name)

    @staticmethod
    async def execute_sql_statement(guild_id: int, guild_name: str, query: str, params: tuple = ()):
        connection = await DatabaseConnectionManager.get_connection(guild_id, guild_name)
        cursor = await connection.cursor()
        try:
            await cursor.execute(query, params)
            await connection.commit()
            return cursor
        except Exception as e:
            await connection.rollback()
            raise e

    @staticmethod
    async def create_tables(guild_id: int):
        tables = [
            """
            CREATE TABLE IF NOT EXISTS TIMEOUT (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID STRING,
                REASON TEXT,
                TIMEOUTTO TEXT,
                IMAGEPATH TEXT,
                INSERT_DATE TEXT,
                TIMEOUT_BY INTEGER DEFAULT 0,
                REMOVED INTEGER DEFAULT 0,
                REMOVED_BY INTEGER DEFAULT 0,
                REMOVED_REASON TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS BAN (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID STRING,
                REASON TEXT,
                DELETE_DAYS INTEGER DEFAULT 0,
                IMAGEPATH TEXT,
                BANNED_TO TEXT,
                BANNED_BY INTEGER DEFAULT 0,                
                INSERT_DATE TEXT,  
                UNBANNED INTEGER DEFAULT 0,              
                UNBANNED_BY INTEGER DEFAULT 0,
                UNBAN_REASON TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS WARN (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID STRING,
                REASON TEXT,                
                IMAGEPATH TEXT,
                LEVEL TEXT,                 
                INSERT_DATE TEXT,  
                REMOVED INTEGER DEFAULT 0,              
                REMOVED_BY INTEGER DEFAULT 0,
                REMOVED_REASON TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS BLACKLIST (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                WORD STRING
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS AUDITLOG (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                LOGTYPE TEXT,
                USERID TEXT NOT NULL,
                DETAILS TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS ANSWER (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                QUESTIONID INTEGER NOT NULL,
                ANSWER TEXT NOT NULL,
                UNIQUE(USERID, QUESTIONID)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS USER_SETTINGS (
            ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            USERID INTEGER NOT NULL,
            SETTING TEXT NOT NULL,
            VALUE TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS QUESTION (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                QUESTION TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS GIVEAWAY_ENTRIES (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                GIVEAWAY_ID INTEGER NOT NULL,
                USERID INTEGER NOT NULL,
                FOREIGN KEY (GIVEAWAY_ID) REFERENCES GIVEAWAY(ID)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS GIVEAWAY (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                CHANNELID INTEGER NOT NULL,
                TITLE TEXT NOT NULL,
                DESCRIPTION TEXT NOT NULL,
                PRIZE TEXT NOT NULL,
                LEVEL_BASED BOOLEAN NOT NULL,
                ALLOWED_ROLES TEXT,
                EXCLUDED_ROLES TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS EXPERIENCE (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                MESSAGE INTEGER DEFAULT 0,
                VOICE INTEGER DEFAULT 0,
                LEVEL INTEGER DEFAULT 1,
                INVITE INTEGER DEFAULT 0 
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS VOICE_XP (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                DATE TEXT NOT NULL,
                VOICE INTEGER DEFAULT 0                                
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS MESSAGE_XP (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                DATE TEXT NOT NULL,
                MESSAGE INTEGER DEFAULT 0                                
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS LEVELXP (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                LEVELNAME INTEGER NOT NULL,
                XP TEXT NOT NULL                
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS BONUS_XP (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                REASON TEXT NOT NULL,
                INSERT_DATE TEXT NOT NULL,
                ORIGINAL_XP INTEGER NOT NULL,
                CALCULATED_XP INTEGER NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS BEICHTEN (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            USERID INTEGER NOT NULL,
            MESSAGE TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS UNIQUE_MESSAGE (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                MESSAGEID TEXT,
                MESSAGETYPE TEXT                
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS TICKET (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                TICKETTYPE TEXT,
                USERID INTEGER NOT NULL,
                DONE INTEGER DEFAULT (0) NOT NULL,
                ASSIGNED INTEGER,
                CREATED_AT TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS KICK (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER,
                REASON TEXT,
                IMAGEPATH TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS TEAM_MEMBERS (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                ROLE TEXT NOT NULL,
                TEAM_ROLE BOOLEAN NOT NULL,
                FOREIGN KEY (USERID) REFERENCES USER(ID),
                UNIQUE (USERID, ROLE)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS BLACKLIST (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,            
                WORD TEXT NOT NULL,
                LEVEL INTEGER NOT NULL                        
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS BLACKLIST_CASSED (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                BLACKLISTID TEXT NOT NULL,
                INSERT_DATE BOOLEAN NOT NULL,
                FOREIGN KEY (USERID) REFERENCES USER(ID)                
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS BLOCKED_USERS (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER,
                VALUE INTEGER
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS CUSTOMCHANNEL (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                CHANNELID INTEGER,
                CHANNELOWNERID INTEGER,
                CREATEDAT TEXT                
            )
            """,

        ]

        connection = await DatabaseConnectionManager.get_connection(guild_id)
        async with connection.cursor() as cursor:
            try:
                for table in tables:
                    await cursor.execute(table)
                await connection.commit()
            except Exception as err:
                logging.getLogger(f"DatabaseConnection_{connection}").error(
                    f"Error creating tables: '{err}'")
