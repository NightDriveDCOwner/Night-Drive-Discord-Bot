import disnake, os, logging
import disnake.audit_logs
from disnake.ext import commands, tasks
from datetime import datetime, timedelta, timedelta
from collections import namedtuple
import asyncio
import time
import re
from typing import Union
from DBConnection import DatabaseConnection


class Globalfile(commands.Cog):
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Globalfile, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, bot: commands.Bot):
        if not hasattr(self, 'bot'):
            self.bot = bot
            self.user_data = {}
            self.TimerMustReseted = True
            self.UserRecord = namedtuple('UserRecord', ['user','username','userid'])
            self.db = DatabaseConnection()             
            
        self.logger = logging.getLogger("Globalfile")
        self.logger.setLevel(logging.INFO)           

        # Überprüfen, ob der Handler bereits hinzugefügt wurde
        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        if not self.unban_task.is_running():
            self.unban_task.start()
        if not self.check_warn_levels.is_running():
            self.check_warn_levels.start()          

    def convert_duration_to_seconds(self, duration: str) -> int:
        """Konvertiere eine Zeitangabe in Sekunden."""
        seconds = 0
        matches = re.findall(r'(\d+)([smhdj])', duration)
        for match in matches:
            value, unit = match
            if unit == 's':
                seconds += int(value)
            elif unit == 'm':
                seconds += int(value) * 60
            elif unit == 'h':
                seconds += int(value) * 3600
            elif unit == 'd':
                seconds += int(value) * 86400
            elif unit == 'j':
                seconds += int(value) * 31536000 # Ein Jahr hat etwa 365 Tage
        return seconds
    
    def calculate_future_time(self, seconds: int) -> str:
        """Berechne die zukünftige Zeit basierend auf der aktuellen Zeit und einer Anzahl von Sekunden."""
        now: datetime.now
        future_time = now + datetime.timedelta(seconds=seconds)
        return future_time.strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    async def save_image(attachment: disnake.Attachment, file_name: str):
        # Speichere das Bild mit dem neuen Dateinamen
        save_path = "proofs"
        
        # Überprüfen, ob der Ordner existiert, und falls nicht, erstellen
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        
        # Speichere das Bild mit dem neuen Dateinamen
        await attachment.save(f"{save_path}/{file_name}.png")
        return f"{save_path}/{file_name}.png"
    
    @tasks.loop(minutes=1)
    async def unban_task(self):
        """Überprüft regelmäßig die Banndauer und entbannt Benutzer, deren Banndauer abgelaufen ist."""
        cursor = self.db.connection.cursor()
        cursor.execute("SELECT USERID, BANNEDTO FROM BAN WHERE UNBAN = 0")
        bans = cursor.fetchall()

        for ban in bans:
            user_id, ban_end_timestamp = ban
            if ban_end_timestamp and datetime.now().timestamp() > ban_end_timestamp:
                # Banndauer ist abgelaufen, Benutzer entbannen
                guild = self.bot.get_guild(854698446996766730)  # Ersetzen Sie dies durch die tatsächliche ID Ihres Servers
                user = await self.bot.fetch_user(user_id)
                await guild.unban(user)
                cursor.execute("UPDATE BAN SET UNBAN = 1 WHERE USERID = ?", (user_id,))
                self.db.connection.commit()
                self.logger.info(f"User {user_id} wurde automatisch entbannt.")
        

    def get_user_record(self, user_id: int = None, username: str = "", discordid: str = "") -> dict:
        """Holt die ID, den Benutzernamen und die Discord-ID des Datensatzes aus der Tabelle User basierend auf Benutzername und User ID."""
        cursor = self.db.connection.cursor()
        query = "SELECT ID, USERNAME, DISCORDID FROM USER WHERE USERNAME = ? OR DISCORDID = ? OR ID = ?"
        cursor.execute(query, (username, discordid, user_id))
        results = cursor.fetchall()

        if len(results) > 2:
            raise ValueError("Mehr als zwei Datensätze gefunden. Abbruch.")

        if results:
            result = results[0]
            return {
                'ID': result[0],
                "USERNAME": result[1],
                'DISCORDID': result[2]
            }
        return None

    def reset_timer(self):
        asyncio.create_task(self.clear_user_data_after_6_minutes())

    async def clear_user_data_after_6_minutes(self):
        await asyncio.sleep(6 * 60)
        self.user_data.clear()
        self.TimerMustReseted = True   

    async def admin_did_something(self, action: disnake.AuditLogAction, handleduser: Union[disnake.User, disnake.Member]):
        DeletedbyAdmin = False
        guild = self.bot.get_guild(854698446996766730)
        async for entry in guild.audit_logs(limit=5, action=action, after=datetime.now() - timedelta(minutes=5)):                                            
            if action == disnake.AuditLogAction.message_delete or action == disnake.AuditLogAction.member_disconnect:
                if entry.extra.count is not None:
                    if self.TimerMustReseted:
                        self.reset_timer()
                        self.TimerMustReseted = False
                    if entry.user.id in self.user_data:
                        if entry.extra.count > self.user_data[entry.user.id]:
                            self.user_data[entry.user.id] = entry.extra.count
                            DeletedbyAdmin = True
                            break
                        else: 
                            DeletedbyAdmin = False                        
                            break
                    else:
                        self.user_data[entry.user.id] = entry.extra.count
                        DeletedbyAdmin = True
                        break  
                else:
                    DeletedbyAdmin = False                                
                    break
            else:
                if self.TimerMustReseted:
                    self.reset_timer()
                    self.TimerMustReseted = False
                if entry.user.id not in self.user_data:
                    self.user_data[entry.user.id] = 1
                self.user_data[entry.user.id] += 1
                DeletedbyAdmin = True
                break  

        if action == disnake.AuditLogAction.message_delete or action == disnake.AuditLogAction.member_disconnect or action == disnake.AuditLogAction.member_update:
            if DeletedbyAdmin:
                user = entry.user
                username = user.name
                userid = user.id
            else:
                user = handleduser
                username = handleduser.name
                userid = handleduser.id     
        return self.UserRecord(user,username,userid)  
    
    async def delete_message_by_id(self, channel_id: int, message_id: int):
        """Löscht eine Nachricht basierend auf ihrer ID in einem bestimmten Kanal."""
        try:
            channel = self.bot.get_channel(channel_id)
            if channel:
                message = await channel.fetch_message(message_id)
                await message.delete()
                print(f"Nachricht mit der ID {message_id} wurde gelöscht.")
            else:
                print(f"Kanal mit der ID {channel_id} wurde nicht gefunden.")
        except disnake.NotFound:
            print(f"Nachricht mit der ID {message_id} wurde nicht gefunden.")
        except disnake.Forbidden:
            print("Ich habe nicht die Berechtigung, diese Nachricht zu löschen.")
        except Exception as e:
            print(f"Ein Fehler ist aufgetreten: {e}")

    async def delete_message_by_id_anywhere(self, message_id: int):
        """Versucht, eine Nachricht basierend auf ihrer ID in allen Kanälen zu finden und zu löschen."""
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                try:
                    message = await channel.fetch_message(message_id)
                    await message.delete()
                    print(f"Nachricht mit der ID {message_id} wurde gelöscht.")
                    return # Nachricht wurde gefunden und gelöscht, also abbrechen
                except disnake.NotFound:
                    pass # Nachricht nicht in diesem Kanal gefunden, also weiter suchen
                except disnake.Forbidden:
                    print("Ich habe nicht die Berechtigung, diese Nachricht zu löschen.")
                    return # Berechtigung fehlt, also abbrechen
                except Exception as e:
                    self.logger.critical(f"Ein Fehler ist aufgetreten: {e}")
                    return # Ein anderer Fehler ist aufgetreten, also abbrechen
        print(f"Nachricht mit der ID {message_id} wurde nicht gefunden.")

    def get_user_record_id(self, username: str = None, user_id: int = None) -> int:
            """Holt die ID des Datensatzes aus der Tabelle User basierend auf Benutzername und/oder User ID."""
            cursor = self.db.connection.cursor()
            
            if username and user_id:
                query = "SELECT ID FROM USER WHERE USERNAME = ? AND USERID = ?"
                cursor.execute(query, (username, user_id))
            elif username:
                query = "SELECT ID FROM User WHERE USERNAME = ?"
                cursor.execute(query, (username,))
            elif user_id:
                query = "SELECT ID FROM User WHERE USERID = ?"
                cursor.execute(query, (user_id,))
            else:
                return None
            
            result = cursor.fetchone()
            return result[0] if result else None        

    def get_message_record_id(self, message_id: int) -> int:
        """Holt die ID des Datensatzes aus der Tabelle Message basierend auf der Message ID."""
        cursor = self.db.connection.cursor()
        query = "SELECT ID FROM Message WHERE MESSAGEID = ?"
        cursor.execute(query, (message_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    async def get_member_from_user(self, user: disnake.User, guild_id: int) -> Union[disnake.Member, None]:
        """Konvertiert einen disnake.User in einen disnake.Member, sofern der Benutzer Mitglied der Gilde ist."""
        guild = self.bot.get_guild(guild_id)
        if guild:
            member = guild.get_member(user.id)
            return member
        return None    
    
    @tasks.loop(hours=1)
    async def check_warn_levels(self):
        """Überprüft regelmäßig die Warnlevel und reduziert sie gegebenenfalls."""
        cursor = self.db.connection.cursor()
        current_time = datetime.now()
        four_months_ago = current_time - timedelta(days=4*30)  # Grobe Schätzung für 4 Monate

        # Hole alle Benutzer mit WARNLEVEL > 0
        cursor.execute("SELECT ID, WARNLEVEL FROM USER WHERE WARNLEVEL > 0")
        users = cursor.fetchall()

        for user_id, warnlevel in users:
            # Überprüfe, wann der letzte Warn für diesen Benutzer war
            cursor.execute("SELECT MAX(INSERTDATE) FROM WARN WHERE USERID = ?", (user_id,))
            last_warn_date = cursor.fetchone()[0]

            if last_warn_date and datetime.strptime(last_warn_date, '%Y-%m-%d %H:%M:%S') < four_months_ago:
                # Überprüfe, wann die letzte System-Note für die Reduzierung des Warnlevels war
                cursor.execute("SELECT MAX(INSERTDATE) FROM NOTE WHERE USERID = ? AND NOTE LIKE 'System Note: Warnlevel reduced%'", (user_id,))
                last_note_date = cursor.fetchone()[0]

                if not last_note_date or datetime.strptime(last_note_date, '%Y-%m-%d %H:%M:%S') < four_months_ago:
                    # Reduziere das Warnlevel um 1
                    new_warnlevel = max(0, warnlevel - 1)
                    cursor.execute("UPDATE USER SET WARNLEVEL = ? WHERE ID = ?", (new_warnlevel, user_id))
                    self.db.connection.commit()

                    # Füge eine System-Note hinzu
                    system_note = f"System Note: Warnlevel reduced from {warnlevel} to {new_warnlevel}"
                    cursor.execute("INSERT INTO NOTE (NOTE, USERID, INSERTDATE) VALUES (?, ?, ?)", (system_note, user_id, current_time.strftime('%Y-%m-%d %H:%M:%S')))
                    self.db.connection.commit()

                    self.logger.info(f"Warnlevel for user {user_id} reduced from {warnlevel} to {new_warnlevel}")    
    
    tasks.loop(hours=24)
    async def sync_users(self):
        """Synchronisiert die Benutzerdatenbank mit den Mitgliedern des Servers."""
        guild = self.bot.get_guild(854698446996766730)
        members = guild.members

        cursor = self.db.connection.cursor()

        for member in members:
            # Überprüfen, ob der Benutzer bereits in der Tabelle Users existiert
            cursor.execute("SELECT ID, USERNAME FROM USER WHERE DISCORDID = ?", (str(member.id),))
            result = cursor.fetchone()

            if not result:
                # Benutzer existiert nicht, füge ihn in die Tabelle Users ein
                cursor.execute("INSERT INTO USER (DISCORDID, USERNAME) VALUES (?, ?)", (str(member.id), member.name))
                self.db.connection.commit()
            else:
                # Benutzer existiert, überprüfe den Benutzernamen
                user_id, db_username = result
                if db_username != member.name:
                    # Benutzername ist nicht korrekt, aktualisiere ihn
                    cursor.execute("UPDATE USER SET USERNAME = ? WHERE ID = ?", (member.name, user_id))
                    self.db.connection.commit()


def setupGlobal(bot):
    bot.add_cog(Globalfile(bot))
