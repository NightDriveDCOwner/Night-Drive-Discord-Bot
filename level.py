import disnake
from disnake.ext import commands
import sqlite3
import logging
import datetime
import asyncio
from DBConnection import DatabaseConnection
from globalfile import Globalfile

class Level(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger("Experience")
        formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.db: sqlite3.Connection = DatabaseConnection()
        self.cursor: sqlite3.Cursor = self.db.connection.cursor()
        self.globalfile = Globalfile(bot)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS EXPERIENCE (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                MESSAGE INTEGER DEFAULT 0,
                VOICE INTEGER DEFAULT 0
            )
        """)        
        self.db.connection.commit()      

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS VOICE (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                USERID INTEGER NOT NULL,
                DATE TEXT NOT NULL,
                VOICE INTEGER DEFAULT 0                                
            )
        """)        
        self.db.connection.commit()              

        self.last_message_time = {}
        self.voice_check_task = self.bot.loop.create_task(self.check_voice_activity())

    async def check_voice_activity(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            current_date = self.globalfile.get_current_time().strftime('%Y-%m-%d')
            for guild in self.bot.guilds:
                for member in guild.members:
                    if member.voice and member.voice.channel:
                        self.cursor.execute("SELECT ID FROM USER WHERE DISCORDID = ?", (member.id,))
                        user_record = self.cursor.fetchone()
                        if user_record:
                            user_id = user_record[0]
                            self.cursor.execute("SELECT * FROM VOICE WHERE USERID = ? AND DATE = ?", (user_id, current_date))
                            result = self.cursor.fetchone()
                            if result:
                                self.cursor.execute("UPDATE VOICE SET VOICE = VOICE + 1 WHERE USERID = ? AND DATE = ?", (user_id, current_date))
                            else:
                                self.cursor.execute("INSERT INTO VOICE (USERID, DATE, VOICE) VALUES (?, ?, 1)", (user_id, current_date))
                            self.db.connection.commit()                        
                        if user_record:
                            user_id = user_record[0]
                            self.cursor.execute("UPDATE EXPERIENCE SET VOICE = VOICE + 1 WHERE USERID = ?", (user_id,))
                            self.db.connection.commit()                                                  
            await asyncio.sleep(30)

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.bot:
            return
        
        userrecord = self.globalfile.get_user_record(discordid=message.author.id)
        # Speichern der Nachricht in der Datenbank
        current_datetime = self.globalfile.get_current_time().strftime('%Y-%m-%d %H:%M:%S')
        image_paths = [attachment.url for attachment in message.attachments]
        if len(image_paths) != 0:
            image_path_fields = ", " + ', '.join([f"IMAGEPATH{i+1}" for i in range(len(image_paths))])
            image_path_values = ", " + ', '.join(['?' for _ in range(len(image_paths))])
        else:
            image_path_fields = ""
            image_path_values = ""            
        query = f"INSERT INTO MESSAGE (CONTENT, USERID, CHANNELID, MESSAGEID, INSERT_DATE {image_path_fields}) VALUES (?, ?, ?, ?, ?{image_path_values})"
        self.cursor.execute(query, (message.content, userrecord['ID'], message.channel.id, message.id, current_datetime, *image_paths))
        self.db.connection.commit()

        current_time = self.globalfile.get_current_time()
        last_time = self.last_message_time.get(message.author.id)

        if last_time and (current_time - last_time).total_seconds() < 30:
            return

        self.last_message_time[message.author.id] = current_time

        self.cursor.execute("SELECT ID FROM USER WHERE DISCORDID = ?", (message.author.id,))
        user_record = self.cursor.fetchone()
        if user_record:
            user_id = user_record[0]
            self.cursor.execute("SELECT * FROM EXPERIENCE WHERE USERID = ?", (user_id,))
            result = self.cursor.fetchone()
            if result:
                self.cursor.execute("UPDATE EXPERIENCE SET MESSAGE = MESSAGE + 1 WHERE USERID = ?", (user_id,))
            else:
                self.cursor.execute("INSERT INTO EXPERIENCE (USERID, MESSAGE) VALUES (?, 1)", (user_id,))
            self.db.connection.commit()
            self.cursor.execute("UPDATE MESSAGE SET RATED = 1 WHERE USERID = ?", (user_id,))

def setupLevel(bot):
    bot.add_cog(Level(bot))