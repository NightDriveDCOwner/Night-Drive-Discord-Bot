import disnake, os, logging
import disnake.audit_logs
from disnake.ext import commands, tasks
from datetime import datetime, timedelta, timedelta, timezone, time
from collections import namedtuple
import asyncio
import pytz
import re
from typing import Union
from dbconnection import DatabaseConnection


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
        
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()                    
        self.logger = logging.getLogger("Globalfile")
        self.logger.setLevel(logging_level)           

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
        if not self.check_birthdays.is_running():
            self.check_birthdays.start()              

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
        cursor.execute("""
            SELECT BAN.USERID, BAN.BANNEDTO, USER.DISCORDID 
            FROM BAN 
            JOIN USER ON BAN.USERID = USER.ID 
            WHERE BAN.UNBAN = 0
        """)
        bans = cursor.fetchall()

        for ban in bans:
            user_id, ban_end_timestamp, discordid = ban
            if ban_end_timestamp:
                # Konvertiere ban_end_timestamp von einem String zu einem Float
                ban_end_timestamp = float(ban_end_timestamp)
                # Konvertiere den Unix-Timestamp in ein datetime-Objekt
                ban_end_datetime = datetime.fromtimestamp(ban_end_timestamp, tz=timezone.utc)
                current_time = self.get_current_time()
                if current_time > ban_end_datetime:
                    # Banndauer ist abgelaufen, Benutzer entbannen
                    guild = self.bot.get_guild(854698446996766730)  # Ersetzen Sie dies durch die tatsächliche ID Ihres Servers
                    if guild is None:
                        self.logger.error(f"Guild mit ID 854698446996766730 konnte nicht gefunden werden.")
                        # Debugging: Liste alle Gilden auf, die der Bot geladen hat
                        self.logger.debug(f"Geladene Gilden: {[g.id for g in self.bot.guilds]}")
                        continue
                    try:
                        # Überprüfen, ob der Benutzer tatsächlich gebannt ist
                        async for ban_entry in guild.bans():
                            if ban_entry.user.id == int(discordid):
                                # Unban den Benutzer direkt mit der Benutzer-ID
                                await guild.unban(disnake.Object(id=int(discordid)))
                                cursor.execute("UPDATE BAN SET UNBAN = 1 WHERE USERID = ?", (user_id,))
                                self.db.connection.commit()
                                self.logger.info(f"User {user_id} mit DiscordID {discordid} wurde automatisch entbannt.")
                        else:
                            self.logger.warning(f"User {user_id} mit DiscordID {discordid} ist nicht gebannt.")
                    except disnake.NotFound:
                        self.logger.warning(f"User {user_id} mit DiscordID {discordid} konnte nicht gefunden werden.")
                    except Exception as e:
                        self.logger.error(f"Fehler beim Entbannen von User {user_id} mit DiscordID {discordid}: {e}")

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

    async def log_audit_entry(self, logtype: str, userid: int, details: str):
        """Loggt einen Audit-Eintrag in die Datenbank."""
        cursor = self.db.connection.cursor()
        cursor.execute("INSERT INTO AUDITLOG (LOGTYPE, USERID, DETAILS) VALUES (?, ?, ?)", (logtype, userid, details))
        self.db.connection.commit()
    
    async def delete_message_by_id(self, channel_id: int, message_id: int):
        """Löscht eine Nachricht basierend auf ihrer ID in einem bestimmten Kanal."""
        try:
            channel = self.bot.get_channel(channel_id)
            if channel:
                message = await channel.fetch_message(message_id)
                await message.delete()
                self.logger.info(f"Nachricht mit der ID {message_id} wurde gelöscht.")
            else:
                self.logger.warning(f"Kanal mit der ID {channel_id} wurde nicht gefunden.")
        except disnake.NotFound:
            self.logger.warning(f"Nachricht mit der ID {message_id} wurde nicht gefunden.")
        except disnake.Forbidden:
            self.logger.warning("Ich habe nicht die Berechtigung, diese Nachricht zu löschen.")
        except Exception as e:
            self.logger.error(f"Ein Fehler ist aufgetreten: {e}")

    async def delete_message_by_id_anywhere(self, message_id: int):
        """Versucht, eine Nachricht basierend auf ihrer ID in allen Kanälen zu finden und zu löschen."""
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                try:
                    message = await channel.fetch_message(message_id)
                    await message.delete()
                    self.logger.info(f"Nachricht mit der ID {message_id} wurde gelöscht.")
                    return # Nachricht wurde gefunden und gelöscht, also abbrechen
                except disnake.NotFound:
                    pass # Nachricht nicht in diesem Kanal gefunden, also weiter suchen
                except disnake.Forbidden:
                    self.logger.warning("Ich habe nicht die Berechtigung, diese Nachricht zu löschen.")
                    return # Berechtigung fehlt, also abbrechen
                except Exception as e:
                    self.logger.critical(f"Ein Fehler ist aufgetreten: {e}")
                    return # Ein anderer Fehler ist aufgetreten, also abbrechen
        self.logger.warning(f"Nachricht mit der ID {message_id} wurde nicht gefunden.")

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
        current_time = self.get_current_time()
        four_months_ago = current_time - timedelta(days=4*30)  # Grobe Schätzung für 4 Monate

        # Hole alle Benutzer mit WARNLEVEL > 0
        cursor.execute("SELECT ID, WARNLEVEL FROM USER WHERE WARNLEVEL > 0")
        users = cursor.fetchall()

        for user_id, warnlevel in users:
            # Überprüfe, wann der letzte Warn für diesen Benutzer war
            cursor.execute("SELECT MAX(INSERTDATE) FROM WARN WHERE USERID = ?", (user_id,))
            last_warn_date = cursor.fetchone()[0]

            if last_warn_date:
                last_warn_date = datetime.strptime(last_warn_date, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                if last_warn_date < four_months_ago:
                    # Überprüfe, wann die letzte System-Note für die Reduzierung des Warnlevels war
                    cursor.execute("SELECT MAX(INSERT_DATE) FROM NOTE WHERE USERID = ? AND NOTE LIKE 'System Note: Warnlevel reduced%'", (user_id,))
                    last_note_date = cursor.fetchone()[0]

                    if not last_note_date or datetime.strptime(last_note_date, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc) < four_months_ago:
                        # Reduziere das Warnlevel um 1
                        new_warnlevel = max(0, warnlevel - 1)
                        cursor.execute("UPDATE USER SET WARNLEVEL = ? WHERE ID = ?", (new_warnlevel, user_id))
                        self.db.connection.commit()

                        # Füge eine System-Note hinzu
                        system_note = f"System Note: Warnlevel reduced from {warnlevel} to {new_warnlevel}"
                        cursor.execute("INSERT INTO NOTE (NOTE, USERID, INSERT_DATE) VALUES (?, ?, ?)", (system_note, user_id, current_time.strftime('%Y-%m-%d %H:%M:%S')))
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

    @tasks.loop(minutes=1)
    async def track_voice_minutes(self):
        """Überprüft jede Minute, wer sich in den Voice-Channels befindet, und erhöht den Wert TOTALVOICEMIN in der Tabelle USER."""
        guild = self.bot.get_guild(854698446996766730)  # Ersetzen Sie dies durch die tatsächliche ID Ihres Servers
        if guild:
            cursor = self.db.connection.cursor()
            for channel in guild.voice_channels:
                for member in channel.members:
                    userrecord = self.get_user_record(discordid=member.id)
                    if userrecord:
                        cursor.execute("UPDATE USER SET TOTALVOICEMIN = TOTALVOICEMIN + 1 WHERE ID = ?", (userrecord['ID'],))
            self.db.connection.commit()

    def get_current_time(self):
        """Gibt die aktuelle Zeit in der deutschen Zeitzone zurück."""
        german_timezone = pytz.timezone('Europe/Berlin')
        return datetime.now(german_timezone)
        
    @tasks.loop(time=time(hour=12, minute=0, second=0, tzinfo=pytz.timezone('Europe/Berlin')))
    async def check_birthdays(self):
        """Überprüft täglich um 12 Uhr, ob ein Benutzer Geburtstag hat."""
        cursor = self.db.connection.cursor()
        today = self.get_current_time().date()

        cursor.execute("SELECT DISCORDID, USERNAME FROM USER WHERE strftime('%m-%d', BIRTHDAY) = ?", (today.strftime('%m-%d'),))
        birthday_users = cursor.fetchall()

        if birthday_users:
            guild = self.bot.get_guild(854698446996766730)  # Ersetzen Sie dies durch die tatsächliche ID Ihres Servers
            if guild:
                for user in birthday_users:
                    discord_id, username = user
                    member = guild.get_member(int(discord_id))
                    if member:
                        # Server Embed
                        server_embed = disnake.Embed(
                            title="🎉 Herzlichen Glückwunsch zum Geburtstag!",
                            description=f"{member.mention} hat heute Geburtstag! 🎂",
                            color=disnake.Color.green()
                        )
                        server_embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                        server_embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
                        server_embed.add_field(name="🎁 Geschenk", value="Du erhältst heute doppelte EP!", inline=False)
                        server_embed.set_footer(text="Wir wünschen dir einen tollen Tag!")

                        # Sende die Nachricht im Server
                        birthday_channel = guild.system_channel  # Ersetzen Sie dies durch den gewünschten Kanal
                        if birthday_channel:
                            await birthday_channel.send(embed=server_embed)

                        # DM Embed
                        dm_embed = disnake.Embed(
                            title="🎉 Alles Gute zum Geburtstag!",
                            description=f"Lieber {username},",
                            color=disnake.Color.blue()
                        )
                        dm_embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
                        dm_embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
                        dm_embed.add_field(name="🎁 Geschenk", value="Du erhältst heute doppelte EP!", inline=False)
                        dm_embed.add_field(name="🎉 Dankeschön", value="Vielen Dank, dass du Teil unserer Community bist!", inline=False)
                        dm_embed.add_field(name="📞 Unterstützung", value="Wenn du irgendwelche Probleme hast, kannst du dich jederzeit an uns wenden.", inline=False)
                        dm_embed.set_footer(text="Wir wünschen dir einen tollen Tag!")

                        # Sende die private Nachricht
                        try:
                            await member.send(embed=dm_embed)
                        except disnake.Forbidden:
                            self.logger.warning(f"Konnte keine Nachricht an {username} ({discord_id}) senden. Möglicherweise hat der Benutzer DMs deaktiviert.")
                    else:
                        self.logger.warning(f"Benutzer {username} ({discord_id}) ist nicht auf dem Server.")
    
def setupGlobal(bot):
    bot.add_cog(Globalfile(bot))
