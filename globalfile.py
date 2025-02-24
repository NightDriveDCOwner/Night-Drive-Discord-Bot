import aiosqlite.cursor
import disnake
import os
import logging
import threading
import disnake.audit_logs
from disnake.ext import commands, tasks
from datetime import datetime, timedelta, timedelta, timezone, time
from collections import namedtuple
import asyncio
import pytz
import re
from typing import Union
from dbconnection import DatabaseConnectionManager
import sqlite3
from exceptionhandler import exception_handler
from rolemanager import RoleManager
import aiosqlite


class Globalfile(commands.Cog):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Globalfile, cls).__new__(
                cls, *args, **kwargs)
        return cls._instance

    def __init__(self, bot: commands.Bot, rolemanager: RoleManager):
        if not hasattr(self, 'bot'):
            self.bot = bot
            self.user_data = {}
            self.TimerMustReseted = True
            self.UserRecord = namedtuple(
                'UserRecord', ['user', 'username', 'userid'])

        self.rolemanager = rolemanager
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger = logging.getLogger("Globalfile")
        self.logger.setLevel(logging_level)
        self.self_reveal_channel = None

        # Überprüfen, ob der Handler bereits hinzugefügt wurde
        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    async def on_ready(self):
        self.self_reveal_channel = self.bot.get_channel(1061444217076994058)
        if not self.unban_task.is_running():
            self.unban_task.start()
        if not self.check_warn_levels.is_running():
            self.check_warn_levels.start()
        if not self.check_birthdays.is_running():
            self.check_birthdays.start()
        if not self.archive_old_threads.is_running():
            self.archive_old_threads.start()
        self.logger.debug(f"{self.__class__.__name__} Cog geladen.")
        self.logger.debug(
            f"Check Birthday is running: {self.check_birthdays.is_running()}")
        self.logger.debug(
            f"Archive old threads is running: {self.archive_old_threads.is_running()}")
        self.logger.debug(
            f"Check warn levels is running: {self.check_warn_levels.is_running()}")
        self.logger.debug(
            f"Unban Task is running: {self.unban_task.is_running()}")

    @exception_handler
    async def convert_duration_to_seconds(self, duration: str) -> int:
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
                seconds += int(value) * 31536000  # Ein Jahr hat etwa 365 Tage
        return seconds

    @exception_handler
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

        cursor: aiosqlite.Cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, """
            SELECT BAN.USERID, BAN.BANNED_TO, USER.DISCORDID 
            FROM BAN 
            JOIN USER ON BAN.USERID = USER.ID 
            WHERE BAN.UNBANNED = 0
        """)
        bans = await cursor.fetchall()
        await cursor.close()
        for ban in bans:
            user_id, ban_end_timestamp, discordid = ban
            if ban_end_timestamp:
                try:
                    # Konvertiere ban_end_timestamp von einem String zu einem Float, falls nötig
                    ban_end_timestamp = float(ban_end_timestamp)
                except ValueError:
                    # Falls es sich um einen String handelt, der kein Timestamp ist, überspringen
                    self.logger.warning(
                        f"Ungültiges ban_end_timestamp Format für UserID {user_id}: {ban_end_timestamp}")
                    continue

                # Konvertiere den Unix-Timestamp in ein datetime-Objekt
                ban_end_datetime = datetime.fromtimestamp(
                    ban_end_timestamp, tz=timezone.utc)
                current_time = await self.get_current_time()
                if current_time > ban_end_datetime:
                    # Banndauer ist abgelaufen, Benutzer entbannen
                    # Ersetzen Sie dies durch die tatsächliche ID Ihres Servers
                    guild = self.bot.get_guild(854698446996766730)
                    if guild is None:
                        self.logger.error(
                            f"Guild mit ID 854698446996766730 konnte nicht gefunden werden.")
                        # Debugging: Liste alle Gilden auf, die der Bot geladen hat
                        self.logger.debug(
                            f"Geladene Gilden: {[g.id for g in self.bot.guilds]}")
                        continue
                    try:
                        # Überprüfen, ob der Benutzer tatsächlich gebannt ist
                        async for ban_entry in guild.bans():
                            if ban_entry.user.id == int(discordid):
                                # Unban den Benutzer direkt mit der Benutzer-ID
                                await guild.unban(disnake.Object(id=int(discordid)))
                                await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "UPDATE BAN SET UNBANNED = 1 WHERE USERID = ?", (user_id,))

                                self.logger.info(
                                    f"User {user_id} mit DiscordID {discordid} wurde automatisch entbannt.")
                        else:
                            self.logger.warning(
                                f"User {user_id} mit DiscordID {discordid} ist nicht gebannt.")
                            await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "UPDATE BAN SET UNBANNED = 1 WHERE USERID = ?", (user_id,))
                    except disnake.NotFound:
                        self.logger.warning(
                            f"User {user_id} mit DiscordID {discordid} konnte nicht gefunden werden.")
                    except Exception as e:
                        self.logger.error(
                            f"Fehler beim Entbannen von User {user_id} mit DiscordID {discordid}: {e}")

    @exception_handler
    async def get_user_record(self, user_id: int = None, username: str = "", discordid="") -> dict:
        """Holt die ID, den Benutzernamen und die Discord-ID des Datensatzes aus der Tabelle User basierend auf Benutzername und User ID."""

        query = "SELECT ID, USERNAME, DISCORDID FROM USER WHERE USERNAME = ? OR DISCORDID = ? OR ID = ?"
        cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, query, (username, str(discordid), user_id))
        results = await cursor.fetchall()
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

    @exception_handler
    async def reset_timer(self):
        await asyncio.create_task(self.clear_user_data_after_6_minutes())

    @exception_handler
    async def clear_user_data_after_6_minutes(self):
        await asyncio.sleep(6 * 60)
        self.user_data.clear()
        self.TimerMustReseted = True

    @exception_handler
    async def admin_did_something(self, action: disnake.AuditLogAction, handleduser: Union[disnake.User, disnake.Member]):
        DeletedbyAdmin = False
        guild = self.bot.get_guild(854698446996766730)
        async for entry in guild.audit_logs(limit=5, action=action, after=datetime.now() - timedelta(minutes=5)):
            if action in [disnake.AuditLogAction.message_delete, disnake.AuditLogAction.member_disconnect]:
                if entry.extra.count is not None:
                    if self.TimerMustReseted:
                        await self.reset_timer()
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
                    await self.reset_timer()
                    self.TimerMustReseted = False
                if entry.user.id not in self.user_data:
                    self.user_data[entry.user.id] = 1
                self.user_data[entry.user.id] += 1
                DeletedbyAdmin = True
                break

        if action in [disnake.AuditLogAction.message_delete, disnake.AuditLogAction.member_disconnect, disnake.AuditLogAction.member_update]:
            if DeletedbyAdmin:
                user = entry.user
                username = user.name
                userid = user.id
            else:
                user = handleduser
                username = handleduser.name
                userid = handleduser.id
        else:
            user = handleduser
            username = handleduser.name
            userid = handleduser.id

        return self.UserRecord(user, username, userid)

    @exception_handler
    async def log_audit_entry(self, logtype: str, userid: int, details: str):
        """Loggt einen Audit-Eintrag in die Datenbank."""

        await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "INSERT INTO AUDITLOG (LOGTYPE, USERID, DETAILS) VALUES (?, ?, ?)", (logtype, userid, details))

    @exception_handler
    async def delete_message_by_id(self, channel_id: int, message_id: int):
        """Löscht eine Nachricht basierend auf ihrer ID in einem bestimmten Kanal."""
        try:
            channel = self.bot.get_channel(channel_id)
            if channel:
                message = await channel.fetch_message(message_id)
                await message.delete()
                self.logger.info(
                    f"Nachricht mit der ID {message_id} wurde gelöscht.")
            else:
                self.logger.warning(
                    f"Kanal mit der ID {channel_id} wurde nicht gefunden.")
        except disnake.NotFound:
            self.logger.warning(
                f"Nachricht mit der ID {message_id} wurde nicht gefunden.")
        except disnake.Forbidden:
            self.logger.warning(
                "Ich habe nicht die Berechtigung, diese Nachricht zu löschen.")
        except Exception as e:
            self.logger.error(f"Ein Fehler ist aufgetreten: {e}")

    @exception_handler
    async def delete_message_by_id_anywhere(self, message_id: int):
        """Versucht, eine Nachricht basierend auf ihrer ID in allen Kanälen zu finden und zu löschen."""
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                try:
                    message = await channel.fetch_message(message_id)
                    await message.delete()
                    self.logger.info(
                        f"Nachricht mit der ID {message_id} wurde gelöscht.")
                    return  # Nachricht wurde gefunden und gelöscht, also abbrechen
                except disnake.NotFound:
                    pass  # Nachricht nicht in diesem Kanal gefunden, also weiter suchen
                except disnake.Forbidden:
                    self.logger.warning(
                        "Ich habe nicht die Berechtigung, diese Nachricht zu löschen.")
                    return  # Berechtigung fehlt, also abbrechen
                except Exception as e:
                    self.logger.critical(f"Ein Fehler ist aufgetreten: {e}")
                    return  # Ein anderer Fehler ist aufgetreten, also abbrechen
        self.logger.warning(
            f"Nachricht mit der ID {message_id} wurde nicht gefunden.")

    @exception_handler
    async def get_user_record_id(self, username: str = None, user_id: int = None) -> int:
        """Holt die ID des Datensatzes aus der Tabelle User basierend auf Benutzername und/oder User ID."""

        if username and user_id:
            query = "SELECT ID FROM USER WHERE USERNAME = ? AND USERID = ?"
            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, query, (username, user_id))
        elif username:
            query = "SELECT ID FROM User WHERE USERNAME = ?"
            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, query, (username,))
        elif user_id:
            query = "SELECT ID FROM User WHERE USERID = ?"
            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, query, (user_id,))
        else:
            return None

        result = (await cursor.fetchone())
        return result[0] if result else None

    @exception_handler
    async def get_message_record_id(self, message_id: int) -> int:
        """Holt die ID des Datensatzes aus der Tabelle Message basierend auf der Message ID."""

        query = "SELECT ID FROM Message WHERE MESSAGEID = ?"
        cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, query, (message_id,))
        result = (await cursor.fetchone())
        return result[0] if result else None

    @exception_handler
    async def get_member_from_user(self, user: disnake.User, guild_id: int) -> Union[disnake.Member, None]:
        """Konvertiert einen disnake.User in einen disnake.Member, sofern der Benutzer Mitglied der Gilde ist."""
        guild = self.bot.get_guild(guild_id)
        if guild:
            member = guild.get_member(user.id)
            return member
        return None

    @tasks.loop(hours=1)
    async def check_warn_levels(self):
        """Überprüft das Warnlevel jedes Benutzers und reduziert es, wenn die letzte Warnung länger als 4 Monate zurückliegt."""

        current_time = await self.get_current_time()
        if current_time is None:
            self.logger.error("Konnte die aktuelle Zeit nicht abrufen.")
            return

        four_months_ago = current_time - \
            timedelta(days=4*30)  # Annahme: 1 Monat = 30 Tage

        # Hole alle Benutzer, deren Warnlevel angepasst werden muss
        cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, """
            SELECT ID, WARNLEVEL, WARNLEVEL_ADJUSTED
            FROM USER
            WHERE WARNLEVEL > 0
        """)
        users = await cursor.fetchall()
        for user in users:
            user_id, warn_level, warnlevel_adjusted = user

            # Überprüfe, ob die letzte Warnung länger als 4 Monate zurückliegt
            cursor: aiosqlite.Cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, """
                SELECT MAX(INSERT_DATE)
                FROM WARN
                WHERE USERID = ?
                AND REMOVED <> 1
            """, (user_id,))
            last_warn_date = (await cursor.fetchone())

        if last_warn_date:
            # Extract the string from the tuple
            last_warn_date_str = last_warn_date[0]
            if last_warn_date_str:  # Check if the string is not None
                last_warn_date = datetime.strptime(
                    last_warn_date_str, '%Y-%m-%d %H:%M:%S')
                last_warn_date = last_warn_date.replace(
                    tzinfo=timezone.utc)  # Offset-bewusst machen
                if last_warn_date < four_months_ago:
                    # Überprüfe, ob die letzte Warnlevel-Anpassung auch länger als 4 Monate zurückliegt
                    if not warnlevel_adjusted or datetime.strptime(warnlevel_adjusted, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc) < four_months_ago:
                        # Reduziere das Warnlevel um 1
                        new_warn_level = max(0, warn_level - 1)
                        current_time_str = current_time.strftime(
                            '%Y-%m-%d %H:%M:%S')
                        cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, """
                            UPDATE USER
                            SET WARNLEVEL = ?, WARNLEVEL_ADJUSTED = ?
                            WHERE ID = ?
                        """, (new_warn_level, current_time_str, user_id))

                        self.logger.info(
                            f"Warnlevel für Benutzer {user_id} auf {new_warn_level} reduziert.")

    tasks.loop(hours=24)

    async def sync_users(self):
        """Synchronisiert die Benutzerdatenbank mit den Mitgliedern des Servers."""
        guild = self.bot.get_guild(854698446996766730)
        members = guild.members

        for member in members:
            # Überprüfen, ob der Benutzer bereits in der Tabelle Users existiert
            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "SELECT ID, USERNAME FROM USER WHERE DISCORDID = ?", (str(member.id),))
            result = (await cursor.fetchone())

            if not result:
                # Benutzer existiert nicht, füge ihn in die Tabelle Users ein
                await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "INSERT INTO USER (DISCORDID, USERNAME) VALUES (?, ?)", (str(member.id), member.name))

            else:
                # Benutzer existiert, überprüfe den Benutzernamen
                user_id, db_username = result
                if db_username != member.name:
                    # Benutzername ist nicht korrekt, aktualisiere ihn
                    await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "UPDATE USER SET USERNAME = ? WHERE ID = ?", (member.name, user_id))

    @tasks.loop(minutes=1)
    async def track_voice_minutes(self):
        """Überprüft jede Minute, wer sich in den Voice-Channels befindet, und erhöht den Wert TOTALVOICEMIN in der Tabelle USER."""
        guild = self.bot.get_guild(
            854698446996766730)  # Ersetzen Sie dies durch die tatsächliche ID Ihres Servers
        if guild:

            for channel in guild.voice_channels:
                for member in channel.members:
                    userrecord = self.get_user_record(discordid=member.id)
                    if userrecord:
                        await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "UPDATE USER SET TOTALVOICEMIN = TOTALVOICEMIN + 1 WHERE ID = ?", (userrecord['ID'],))

    @exception_handler
    async def get_current_time(self):
        """Gibt die aktuelle Zeit in der deutschen Zeitzone zurück."""
        german_timezone = pytz.timezone('Europe/Berlin')
        current_time = datetime.now(german_timezone)
        if current_time is None:
            raise ValueError("Konnte die aktuelle Zeit nicht abrufen.")
        return current_time

    @tasks.loop(time=time(hour=12, minute=0, second=0, tzinfo=pytz.timezone('Europe/Berlin')))
    async def check_birthdays(self):
        """Überprüft täglich um 12 Uhr, ob ein Benutzer Geburtstag hat."""

        # Hole das Datum
        today = await self.get_current_time()
        cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "SELECT DISCORDID, USERNAME FROM USER WHERE strftime('%m-%d', BIRTHDAY) = ?", (today.strftime('%m-%d'),))
        birthday_users = await cursor.fetchall()
        if birthday_users:
            # Ersetzen Sie dies durch die tatsächliche ID Ihres Servers
            guild = self.bot.get_guild(854698446996766730)
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
                        server_embed.set_thumbnail(
                            url=member.avatar.url if member.avatar else member.default_avatar.url)
                        server_embed.set_author(
                            name=guild.name, icon_url=guild.icon.url if guild.icon else None)
                        server_embed.add_field(
                            name="🎁 Geschenk", value="Du erhältst heute doppelte EP!", inline=False)
                        server_embed.set_footer(
                            text="Wir wünschen dir einen tollen Tag!")

                        # Sende die Nachricht im Server
                        # Ersetzen Sie dies durch den gewünschten Kanal
                        birthday_channel = guild.get_channel(
                            854698447247769630)
                        if birthday_channel:
                            await birthday_channel.send(embed=server_embed)

                        # DM Embed
                        dm_embed = disnake.Embed(
                            title="🎉 Alles Gute zum Geburtstag!",
                            description=f"Lieber {username},",
                            color=disnake.Color.blue()
                        )
                        dm_embed.set_thumbnail(
                            url=member.avatar.url if member.avatar else member.default_avatar.url)
                        dm_embed.set_author(
                            name=guild.name, icon_url=guild.icon.url if guild.icon else None)
                        dm_embed.add_field(
                            name="🎁 Geschenk", value="Du erhältst heute doppelte EP!", inline=False)
                        dm_embed.add_field(
                            name="🎉 Dankeschön", value="Vielen Dank, dass du Teil unserer Community bist!", inline=False)
                        dm_embed.add_field(
                            name="📞 Unterstützung", value="Wenn du irgendwelche Probleme hast, kannst du dich jederzeit an uns wenden.", inline=False)
                        dm_embed.set_footer(
                            text="Wir wünschen dir einen tollen Tag!")

                        # Sende die private Nachricht
                        try:
                            await member.send(embed=dm_embed)
                        except disnake.Forbidden:
                            self.logger.warning(
                                f"Konnte keine Nachricht an {username} ({discord_id}) senden. Möglicherweise hat der Benutzer DMs deaktiviert.")
                    else:
                        self.logger.warning(
                            f"Benutzer {username} ({discord_id}) ist nicht auf dem Server.")

    @exception_handler
    async def delete_user_data(self, user_id):
        # Lösche alle Antworten des Benutzers
        await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "DELETE FROM ANSWER WHERE USERID = ?", (user_id,))

        # Lösche alle gesetzten Einstellungen des Benutzers
        await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "DELETE FROM USER_SETTINGS WHERE USERID = ?", (user_id,))

    @exception_handler
    async def get_emoji_by_name(self, emoji_name: str) -> Union[disnake.Emoji, disnake.PartialEmoji, None]:
        # Check custom emojis in the guild
        guild: disnake.Guild = self.bot.get_guild(854698446996766730)
        for emoji in guild.emojis:
            if emoji.name == emoji_name:
                return emoji

        # Check general Discord emojis
        try:
            return disnake.PartialEmoji(name=emoji_name)
        except ValueError:
            return None

    @exception_handler
    async def get_emoji_string_by_name(self, emoji_name: str) -> Union[str, None]:
        # Check custom emojis in the guild
        guild: disnake.Guild = self.bot.get_guild(854698446996766730)
        for emoji in guild.emojis:
            if emoji.name == emoji_name:
                return f"<:{emoji.name}:{emoji.id}>"

        # Check general Discord emojis
        try:
            partial_emoji = disnake.PartialEmoji(name=emoji_name)
            return str(partial_emoji)
        except ValueError:
            return None

    @exception_handler
    async def get_manual_emoji(self, emoji_name: str) -> disnake.Emoji:
        emoji_dict = {
            "new": "🆕",
            "incoming_envelope": "📨",
            "keycap_ten": "🔟",
            "capital_abcd": "🔠",
            "newspaper": "📰",
            "sparkler": "🎇",
            "sparkles": "✨",
            "microphone2": "🎙️",
            "night_with_stars": "🌃",
            "bell": "🔔",
            "no_bell": "🔕",
            "question": "❓",
            "zero": "0️⃣",
            "one": "1️⃣",
            "two": "2️⃣",
            "three": "3️⃣",
            "four": "4️⃣",
            "five": "5️⃣",
            "six": "6️⃣",
            "seven": "7️⃣",
            "eight": "8️⃣",
            "nine": "9️⃣",
            "ten": "🔟",
            "circle": "⚪",
            "blue_circle": "🔵",
            "red_circle": "🔴",
            "black_circle": "⚫",
            "white_circle": "⚪",
            "purple_circle": "🟣",
            "green_circle": "🟢",
            "yellow_circle": "🟡",
            "brown_circle": "🟤",
            "orange_circle": "🟠",
            "pink_circle": "🟣",
            "large_blue_circle": "🔵",
            "gun": "🔫",
            "space_invader": "👾",
            "crossed_swords": "⚔️",
            "knife": "🔪",
            "pick": "⛏️",
            "smile": "😊",
            "heart": "❤️",
            "thumbs_up": "👍",
            "fire": "🔥",
            "star": "⭐",
            "check_mark": "✔️",
            "cross_mark": "❌",
            "clap": "👏",
            "wave": "👋",
            "rocket": "🚀",
            "sun": "☀️",
            "moon": "🌙",
            "cloud": "☁️",
            "snowflake": "❄️",
            "zap": "⚡",
            "umbrella": "☔",
            "coffee": "☕",
            "soccer": "⚽",
            "basketball": "🏀",
            "football": "🏈",
            "baseball": "⚾",
            "tennis": "🎾",
            "volleyball": "🏐",
            "rugby": "🏉",
            "golf": "⛳",
            "trophy": "🏆",
            "medal": "🏅",
            "crown": "👑",
            "gem": "💎",
            "money_bag": "💰",
            "dollar": "💵",
            "yen": "💴",
            "euro": "💶",
            "pound": "💷",
            "credit_card": "💳",
            "shopping_cart": "🛒",
            "gift": "🎁",
            "balloon": "🎈",
            "party_popper": "🎉",
            "confetti_ball": "🎊",
            "tada": "🎉",
            "sparkles": "✨",
            "boom": "💥",
            "collision": "💥",
            "dizzy": "💫",
            "speech_balloon": "💬",
            "thought_balloon": "💭",
            "zzz": "💤",
            "wave": "👋",
            "raised_hand": "✋",
            "ok_hand": "👌",
            "victory_hand": "✌️",
            "crossed_fingers": "🤞",
            "love_you_gesture": "🤟",
            "call_me_hand": "🤙",
            "backhand_index_pointing_left": "👈",
            "backhand_index_pointing_right": "👉",
            "backhand_index_pointing_up": "👆",
            "backhand_index_pointing_down": "👇",
            "index_pointing_up": "☝️",
            "raised_fist": "✊",
            "oncoming_fist": "👊",
            "left_facing_fist": "🤛",
            "right_facing_fist": "🤜",
            "clapping_hands": "👏",
            "raising_hands": "🙌",
            "open_hands": "👐",
            "palms_up_together": "🤲",
            "handshake": "🤝",
            "folded_hands": "🙏",
            "writing_hand": "✍️",
            "nail_polish": "💅",
            "selfie": "🤳",
            "muscle": "💪",
            "mechanical_arm": "🦾",
            "mechanical_leg": "🦿",
            "leg": "🦵",
            "foot": "🦶",
            "ear": "👂",
            "ear_with_hearing_aid": "🦻",
            "nose": "👃",
            "brain": "🧠",
            "anatomical_heart": "🫀",
            "lungs": "🫁",
            "tooth": "🦷",
            "bone": "🦴",
            "eyes": "👀",
            "eye": "👁️",
            "tongue": "👅",
            "mouth": "👄",
            "baby": "👶",
            "child": "🧒",
            "boy": "👦",
            "girl": "👧",
            "person": "🧑",
            "man": "👨",
            "woman": "👩",
            "older_person": "🧓",
            "old_man": "👴",
            "old_woman": "👵",
            "person_frowning": "🙍",
            "person_pouting": "🙎",
            "person_gesturing_no": "🙅",
            "person_gesturing_ok": "🙆",
            "person_tipping_hand": "💁",
            "person_raising_hand": "🙋",
            "deaf_person": "🧏",
            "person_bowing": "🙇",
            "person_facepalming": "🤦",
            "person_shrugging": "🤷",
            "health_worker": "🧑‍⚕️",
            "student": "🧑‍🎓",
            "teacher": "🧑‍🏫",
            "judge": "🧑‍⚖️",
            "farmer": "🧑‍🌾",
            "cook": "🧑‍🍳",
            "mechanic": "🧑‍🔧",
            "factory_worker": "🧑‍🏭",
            "office_worker": "🧑‍💼",
            "scientist": "🧑‍🔬",
            "technologist": "🧑‍💻",
            "singer": "🧑‍🎤",
            "artist": "🧑‍🎨",
            "pilot": "🧑‍✈️",
            "astronaut": "🧑‍🚀",
            "firefighter": "🧑‍🚒",
            "police_officer": "👮",
            "detective": "🕵️",
            "guard": "💂",
            "ninja": "🥷",
            "construction_worker": "👷",
            "prince": "🤴",
            "princess": "👸",
            "person_wearing_turban": "👳",
            "person_with_skullcap": "👲",
            "woman_with_headscarf": "🧕",
            "person_in_tuxedo": "🤵",
            "person_with_veil": "👰",
            "pregnant_woman": "🤰",
            "breast_feeding": "🤱",
            "woman_feeding_baby": "👩‍🍼",
            "man_feeding_baby": "👨‍🍼",
            "person_feeding_baby": "🧑‍🍼",
            "angel": "👼",
            "santa_claus": "🎅",
            "mrs_claus": "🤶",
            "mx_claus": "🧑‍🎄",
            "superhero": "🦸",
            "supervillain": "🦹",
            "mage": "🧙",
            "fairy": "🧚",
            "vampire": "🧛",
            "merperson": "🧜",
            "elf": "🧝",
            "genie": "🧞",
            "zombie": "🧟",
            "person_getting_massage": "💆",
            "person_getting_haircut": "💇",
            "person_walking": "🚶",
            "person_standing": "🧍",
            "person_kneeling": "🧎",
            "person_with_probing_cane": "🧑‍🦯",
            "person_in_motorized_wheelchair": "🧑‍🦼",
            "person_in_manual_wheelchair": "🧑‍🦽",
            "person_running": "🏃",
            "woman_dancing": "💃",
            "man_dancing": "🕺",
            "person_in_suit_levitating": "🕴️",
            "people_with_bunny_ears": "👯",
            "person_in_steamy_room": "🧖",
            "person_climbing": "🧗",
            "person_fencing": "🤺",
            "horse_racing": "🏇",
            "skier": "⛷️",
            "snowboarder": "🏂",
            "person_golfing": "🏌️",
            "person_surfing": "🏄",
            "person_rowing_boat": "🚣",
            "person_swimming": "🏊",
            "person_bouncing_ball": "⛹️",
            "person_lifting_weights": "🏋️",
            "person_biking": "🚴",
            "person_mountain_biking": "🚵",
            "person_cartwheeling": "🤸",
            "people_wrestling": "🤼",
            "person_playing_water_polo": "🤽",
            "person_playing_handball": "🤾",
            "person_juggling": "🤹",
            "person_in_lotus_position": "🧘",
            "person_taking_bath": "🛀",
            "person_in_bed": "🛌",
            "people_holding_hands": "🧑‍🤝‍🧑",
            "women_holding_hands": "👭",
            "woman_and_man_holding_hands": "👫",
            "men_holding_hands": "👬",
            "kiss": "💏",
            "couple_with_heart": "💑",
            "family": "👪",
            "speaking_head": "🗣️",
            "bust_in_silhouette": "👤",
            "busts_in_silhouette": "👥",
            "footprints": "👣",
            "monkey_face": "🐵",
            "monkey": "🐒",
            "gorilla": "🦍",
            "orangutan": "🦧",
            "dog_face": "🐶",
            "dog": "🐕",
            "guide_dog": "🦮",
            "service_dog": "🐕‍🦺",
            "poodle": "🐩",
            "wolf": "🐺",
            "fox": "🦊",
            "raccoon": "🦝",
            "cat_face": "🐱",
            "cat": "🐈",
            "black_cat": "🐈‍⬛",
            "lion": "🦁",
            "tiger_face": "🐯",
            "tiger": "🐅",
            "leopard": "🐆",
            "horse_face": "🐴",
            "horse": "🐎",
            "unicorn": "🦄",
            "zebra": "🦓",
            "deer": "🦌",
            "bison": "🦬",
            "cow_face": "🐮",
            "ox": "🐂",
            "water_buffalo": "🐃",
            "cow": "🐄",
            "pig_face": "🐷",
            "pig": "🐖",
            "boar": "🐗",
            "pig_nose": "🐽",
            "ram": "🐏",
            "ewe": "🐑",
            "goat": "🐐",
            "camel": "🐪",
            "two_hump_camel": "🐫",
            "llama": "🦙",
            "giraffe": "🦒",
            "elephant": "🐘",
            "mammoth": "🦣",
            "rhinoceros": "🦏",
            "hippopotamus": "🦛",
            "mouse_face": "🐭",
            "mouse": "🐁",
            "rat": "🐀",
            "hamster": "🐹",
            "rabbit_face": "🐰",
            "rabbit": "🐇",
            "chipmunk": "🐿️",
            "beaver": "🦫",
            "hedgehog": "🦔",
            "bat": "🦇",
            "bear": "🐻",
            "polar_bear": "🐻‍❄️",
            "koala": "🐨",
            "panda": "🐼",
            "sloth": "🦥",
            "otter": "🦦",
            "skunk": "🦨",
            "kangaroo": "🦘",
            "badger": "🦡",
            "paw_prints": "🐾",
            "turkey": "🦃",
            "chicken": "🐔",
            "rooster": "🐓",
            "hatching_chick": "🐣",
            "baby_chick": "🐤",
            "front_facing_baby_chick": "🐥",
            "bird": "🐦",
            "penguin": "🐧",
            "dove": "🕊️",
            "eagle": "🦅",
            "duck": "🦆",
            "swan": "🦢",
            "owl": "🦉",
            "dodo": "🦤",
            "feather": "🪶",
            "flamingo": "🦩",
            "peacock": "🦚",
            "parrot": "🦜",
            "frog": "🐸",
            "crocodile": "🐊",
            "turtle": "🐢",
            "lizard": "🦎",
            "snake": "🐍",
            "dragon_face": "🐲",
            "dragon": "🐉",
            "sauropod": "🦕",
            "t_rex": "🦖",
            "spouting_whale": "🐳",
            "whale": "🐋",
            "dolphin": "🐬",
            "seal": "🦭",
            "fish": "🐟",
            "tropical_fish": "🐠",
            "blowfish": "🐡",
            "shark": "🦈",
            "octopus": "🐙",
            "spiral_shell": "🐚",
            "snail": "🐌",
            "butterfly": "🦋",
            "bug": "🐛",
            "ant": "🐜",
            "honeybee": "🐝",
            "beetle": "🪲",
            "lady_beetle": "🐞",
            "cricket": "🦗",
            "cockroach": "🪳",
            "spider": "🕷️",
            "spider_web": "🕸️",
            "scorpion": "🦂",
            "mosquito": "🦟",
            "fly": "🪰",
            "worm": "🪱",
            "microbe": "🦠",
            "bouquet": "💐",
            "cherry_blossom": "🌸",
            "white_flower": "💮",
            "rosette": "🏵️",
            "rose": "🌹",
            "wilted_flower": "🥀",
            "hibiscus": "🌺",
            "sunflower": "🌻",
            "blossom": "🌼",
            "tulip": "🌷",
            "seedling": "🌱",
            "potted_plant": "🪴",
            "evergreen_tree": "🌲",
            "deciduous_tree": "🌳",
            "palm_tree": "🌴",
            "cactus": "🌵",
            "sheaf_of_rice": "🌾",
            "herb": "🌿",
            "shamrock": "☘️",
            "four_leaf_clover": "🍀",
            "maple_leaf": "🍁",
            "fallen_leaf": "🍂",
            "leaf_fluttering_in_wind": "🍃",
            "grapes": "🍇",
            "melon": "🍈",
            "watermelon": "🍉",
            "tangerine": "🍊",
            "lemon": "🍋",
            "banana": "🍌",
            "pineapple": "🍍",
            "mango": "🥭",
            "red_apple": "🍎",
            "green_apple": "🍏",
            "pear": "🍐",
            "peach": "🍑",
            "cherries": "🍒",
            "strawberry": "🍓",
            "blueberries": "🫐",
            "kiwi_fruit": "🥝",
            "tomato": "🍅",
            "olive": "🫒",
            "coconut": "🥥",
            "avocado": "🥑",
            "eggplant": "🍆",
            "potato": "🥔",
            "carrot": "🥕",
            "ear_of_corn": "🌽",
            "hot_pepper": "🌶️",
            "bell_pepper": "🫑",
            "cucumber": "🥒",
            "leafy_green": "🥬",
            "broccoli": "🥦",
            "garlic": "🧄",
            "onion": "🧅",
            "mushroom": "🍄",
            "peanuts": "🥜",
            "chestnut": "🌰",
            "bread": "🍞",
            "croissant": "🥐",
            "baguette_bread": "🥖",
            "flatbread": "🫓",
            "pretzel": "🥨",
            "bagel": "🥯",
            "pancakes": "🥞",
            "waffle": "🧇",
            "cheese_wedge": "🧀",
            "meat_on_bone": "🍖",
            "poultry_leg": "🍗",
            "cut_of_meat": "🥩",
            "bacon": "🥓",
            "face_with_tears_of_joy": "😂",
            "smiling_face_with_heart_eyes": "😍",
            "face_with_rolling_eyes": "🙄",
            "face_with_medical_mask": "😷",
            "face_with_thermometer": "🤒",
            "face_with_head_bandage": "🤕",
            "nauseated_face": "🤢",
            "sneezing_face": "🤧",
            "hot_face": "🥵",
            "cold_face": "🥶",
            "woozy_face": "🥴",
            "partying_face": "🥳",
            "smiling_face_with_tear": "🥲",
            "disguised_face": "🥸",
            "pinched_fingers": "🤌",
            "anatomical_heart": "🫀",
            "lungs": "🫁",
            "people_hugging": "🫂",
            "blueberries": "🫐",
            "bell_pepper": "🫑",
            "olive": "🫒",
            "flatbread": "🫓",
            "tamale": "🫔",
            "fondue": "🫕",
            "teapot": "🫖",
            "bubble_tea": "🧋",
            "beaver": "🦫",
            "polar_bear": "🐻‍❄️",
            "feather": "🪶",
            "seal": "🦭",
            "beetle": "🪲",
            "cockroach": "🪳",
            "fly": "🪰",
            "worm": "🪱",
            "rock": "🪨",
            "wood": "🪵",
            "hut": "🛖",
            "pickup_truck": "🛻",
            "roller_skate": "🛼",
            "magic_wand": "🪄",
            "piñata": "🪅",
            "nesting_dolls": "🪆",
            "coin": "🪙",
            "boomerang": "🪃",
            "carpentry_saw": "🪚",
            "screwdriver": "🪛",
            "hook": "🪝",
            "ladder": "🪜",
            "mirror": "🪞",
            "window": "🪟",
            "plunger": "🪠",
            "sewing_needle": "🪡",
            "knots": "🪢",
            "bucket": "🪣",
            "mouse_trap": "🪤",
            "toothbrush": "🪥",
            "headstone": "🪦",
            "placard": "🪧",
            "transgender_flag": "🏳️‍⚧️",
            "transgender_symbol": "⚧️",
            "arrow_up": "⬆️",
            "arrow_down": "⬇️",
        }
        return emoji_dict.get(emoji_name, None)

    @tasks.loop(time=time(hour=0, minute=0, second=0, tzinfo=pytz.timezone('Europe/Berlin')))
    async def archive_old_threads(self):
        """Archiviert Threads im self_reveal_channel, die älter als 7 Tage sind."""
        if self.self_reveal_channel:
            if self.self_reveal_channel:
                current_time = await self.get_current_time()
                seven_days_ago = current_time - timedelta(days=7)

                for thread in self.self_reveal_channel.threads:
                    if thread.created_at < seven_days_ago:
                        await thread.edit(archived=True)
                        self.logger.info(
                            f"Thread {thread.name} wurde archiviert, da er älter als 7 Tage ist.")


def setupGlobal(bot: commands.Bot, rolemanager: RoleManager):
    bot.add_cog(Globalfile(bot, rolemanager))
