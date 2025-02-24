import disnake
import time
import os
import dotenv
from disnake.ext import commands
from globalfile import Globalfile
import logging
from dbconnection import DatabaseConnectionManager
import sqlite3
from datetime import datetime, timedelta, timedelta
import asyncio
from exceptionhandler import exception_handler
from rolehierarchy import rolehierarchy
import rolehierarchy
from rolemanager import RoleManager
from fuzzywuzzy import fuzz
import re
import datetime
from datetime import datetime


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager: RoleManager):
        self.bot = bot
        self.message = disnake.message
        self.userid = int
        self.logger = logging.getLogger("Moderation")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.globalfile: Globalfile = self.bot.get_cog('Globalfile')
        self.role_hierarchy = rolehierarchy.rolehierarchy()
        self.team_roles = [role for role in self.role_hierarchy.role_hierarchy]
        self.role_cache = {}
        self.rolemanager = rolemanager
        self.mod_channel = None

        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.debug("Bot is ready.")
        await self.sync_team_members()
        self.mod_channel = self.bot.guilds[0].get_channel(
            1090588808216596490)  # Set the channel ID

    @exception_handler
    def add_user_to_badwords_times(user_id: int):
        expiry_time = time.time() + 24 * 60 * 60  # 24 Stunden ab jetzt
        with open('badwords_times.txt', 'a', encoding='utf-8') as file:
            file.write(f"{user_id},{expiry_time}\n")

    @exception_handler
    def is_user_banned_from_badwords(self, user_id: int) -> bool:
        current_time = time.time()
        file_path = 'updated_badwords_times.txt'  # Geänderter Dateipfad
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as file:
                pass  # Erstellt die Datei, wenn sie nicht existiert
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                user_id_in_file, expiry_time = line.strip().split(',')
                if int(user_id_in_file) == user_id and float(expiry_time) > current_time:
                    return True
        return False

    @exception_handler
    async def delete_message_by_id(self, channel_id: int, message_id: int):
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            self.logger.warning(f"Kanal mit ID {channel_id} nicht gefunden.")
            return

        async for message in channel.history(limit=None):
            if message.id == message_id:
                await message.delete()
                self.logger.info(f"Nachricht mit ID {message_id} gelöscht.")
                return

        self.logger.warning(f"Nachricht mit ID {message_id} nicht gefunden.")

    @exception_handler
    async def check_message_for_blacklist(self, message: disnake.Message):
        if message is None:
            content = message.content.lower()
            user_id = message.author.id
            current_datetime = (await self.globalfile.get_current_time()).strftime('%Y-%m-%d %H:%M:%S')
            current_time = (await self.globalfile.get_current_time()).strftime('%H:%M:%S')

            # Fetch all blacklist words from the database
            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "SELECT ID, WORD, LEVEL FROM BLACKLIST")
            blacklist_words = await cursor.fetchall()
            # Split the message content into individual words
            words_in_message = re.findall(r'\w+', content)

            for id, word, level in blacklist_words:
                for msg_word in words_in_message:
                    # Adjust the threshold as needed
                    if fuzz.partial_ratio(word.lower(), msg_word) > 80:
                        await message.delete()
                        self.logger.info(
                            f"Nachricht von {message.author.name} (ID: {user_id}) gelöscht wegen Blacklist-Verstoß: {word}")

                        # Insert the blacklist case into the database
                        cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, """
                            INSERT INTO BLACKLIST_CASSED (USERID, BLACKLISTID, INSERT_DATE)
                            VALUES (?, ?, ?)
                        """, (user_id, id, current_datetime))

                        cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, """
                            SELECT SUM(BL.LEVEL)
                            FROM BLACKLIST_CASSED BC
                            JOIN BLACKLIST BL ON BC.BLACKLISTID = BL.ID
                            WHERE BC.USERID = ? AND BC.INSERT_DATE > ?
                        """, (user_id, current_datetime))
                        blacklist_level = (await cursor.fetchone())[0] or level
                        # Send an embed to the channel
                        embed = disnake.Embed(
                            title="Blacklist-Verstoß",
                            description=(
                                f"Eine Nachricht von {message.author.mention} wurde gelöscht, da sie ein verbotenes Wort enthielt."
                                f"Du hast Blacklistlevel {blacklist_level} von 3 erreicht. Bei Backlist Level 3 erhält der User einen Warn."
                            ),
                            color=disnake.Color.red()
                        )
                        embed.add_field(name="Verbotenes Wort",
                                        value=word, inline=False)
                        embed.set_footer(
                            text=f"ID: {user_id} - heute um {current_time} Uhr")
                        await message.channel.send(embed=embed)

                        # Check if the user should be warned
                        current_datetime_obj = datetime.strptime(
                            current_datetime, '%Y-%m-%d %H:%M:%S')
                        cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, """
                            SELECT SUM(BL.LEVEL)
                            FROM BLACKLIST_CASSED BC
                            JOIN BLACKLIST BL ON BC.BLACKLISTID = BL.ID
                            WHERE BC.USERID = ? AND BC.INSERT_DATE > ?
                        """, (user_id, current_datetime_obj - timedelta(days=30)))
                        total_violations_level = (await cursor.fetchone())[0] or 0

                        if total_violations_level >= 3:
                            await self._warn_add(
                                inter=None,  # Assuming you have a way to pass the interaction context
                                user=message.author,
                                reason="Mehrfache Verstöße gegen die Blacklist",
                                level=1
                            )
                        return  # Exit after handling the first match

    @exception_handler
    async def _timeout(self, inter: disnake.ApplicationCommandInteraction,
                       member: disnake.Member,
                       duration: str = commands.Param(
                           name="dauer", description="Dauer des Timeouts in Sek., Min., Std., Tagen oder Jahre.(Bsp.: 0s0m0h0d0j)"),
                       reason: str = commands.Param(
                           name="begründung", description="Grund für den Timeout", default="Kein Grund angegeben"),
                       warn: bool = commands.Param(
                           name="warn", description="Soll eine Warnung erstellt werden?", default=False),
                       warn_level: int = commands.Param(name="warnstufe", description="Warnstufe (1-3) | Default = 1 wenn warn_level = True", default=1)):
        """Timeout einen Benutzer für eine bestimmte Dauer und optional eine Warnung erstellen."""
        await inter.response.defer(ephemeral=True)

        # Berechnen der Timeout-Dauer
        duration_seconds = await self.globalfile.convert_duration_to_seconds(duration)
        if duration_seconds < 60 or duration_seconds > 28 * 24 * 60 * 60:
            await inter.edit_original_response(content="Die Timeout-Dauer muss zwischen 60 Sekunden und 28 Tagen liegen.")
            return

        timeout_end_time = (await self.globalfile.get_current_time()) + timedelta(seconds=duration_seconds)

        try:
            await member.timeout(duration=timedelta(seconds=duration_seconds), reason=reason)
            self.logger.info(
                f"Timeout for User {member.name} (ID: {member.id}) created by {inter.user.name} (ID: {inter.user.id})")
            embed = disnake.Embed(title="Benutzer getimeoutet",
                                  description=f"{member.mention} wurde erfolgreich getimeoutet!", color=disnake.Color.red())
            embed.set_author(
                name=member.name, icon_url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.add_field(name="Grund", value=reason, inline=False)
            embed.add_field(name="Dauer", value=duration, inline=True)
            embed.add_field(name="Ende des Timeouts", value=timeout_end_time.strftime(
                '%Y-%m-%d %H:%M:%S'), inline=True)
            await self.mod_channel.send(embed=embed)

            # Speichere den Timeout in der Datenbank
            current_datetime = (await self.globalfile.get_current_time()).strftime('%Y-%m-%d %H:%M:%S')
            await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "INSERT INTO TIMEOUT (USERID, REASON, TIMEOUTTO, INSERT_DATE) VALUES (?, ?, ?, ?)", (member.id, reason, timeout_end_time.strftime('%Y-%m-%d %H:%M:%S'), current_datetime))

        except disnake.Forbidden:
            await inter.edit_original_response(content=f"Ich habe keine Berechtigung, {member.mention} zu timeouten.")
            return
        except disnake.HTTPException as e:
            await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")

        if warn:
            # Warnung erstellen
            if warn_level < 1 or warn_level > 3:
                await inter.edit_original_response(content="Warnlevel muss zwischen 1 und 3 liegen.")
                return

            await self._warn_add(
                inter=inter,
                user=member,
                reason=reason,
                level=warn_level
            )
            await inter.edit_original_response(content=f"Timeout und Warnung erfolgreich erstellt. Logged in: {self.mod_channel.mention}")
        await inter.edit_original_response(content=f"Timeout erfolgreich erstellt. Logged in: {self.mod_channel.mention}")

    @exception_handler
    async def _timeout_remove(self, inter: disnake.ApplicationCommandInteraction, timeout_id: int, reason: str = commands.Param(name="begründung", description="Grund für das Entfernen des Timeouts", default="Kein Grund angegeben")):
        """Entfernt einen Timeout basierend auf der Timeout ID."""
        await inter.response.defer(ephemeral=True)

        cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "SELECT * FROM TIMEOUT WHERE ID = ?", (timeout_id,))
        timeout_record = (await cursor.fetchone())

        if not timeout_record:
            await inter.edit_original_response(content=f"Kein Timeout mit der ID {timeout_id} gefunden.")
            return

        user_id = timeout_record[1]
        user = await self.bot.fetch_user(user_id)

        try:
            await user.timeout(duration=None, reason=reason)
            self.logger.info(
                f"Timeout removed for User {user.name} (ID: {user.id}) by {inter.user.name} (ID: {inter.user.id})")
            userrecord = await self.globalfile.get_user_record(discordid=inter.author.id)
            await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "UPDATE TIMEOUT SET REMOVED = 1, REMOVED_BY = ?, REMOVED_REASON = ? WHERE ID = ?", (userrecord['ID'], reason, timeout_id))

            embed = disnake.Embed(
                title="Timeout entfernt", description=f"Der Timeout für {user.mention} wurde erfolgreich entfernt.", color=disnake.Color.green())
            embed.set_author(
                name=user.name, icon_url=user.avatar.url if user.avatar else user.default_avatar.url)
            embed.add_field(name="Grund", value=reason, inline=False)
            await self.mod_channel.send(embed=embed)
            await inter.edit_original_response(content=f"Timeout erfolgreich entfernt. Logged in: {self.mod_channel.mention}")
        except disnake.Forbidden:
            await inter.edit_original_response(content=f"Ich habe keine Berechtigung, den Timeout für {user.mention} zu entfernen.")
        except disnake.HTTPException as e:
            await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")

    @exception_handler
    async def _warn_add(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, reason: str, level: int = 1, proof: disnake.Attachment = None, show: str = "True"):
        """Erstellt eine Warnung für einen Benutzer."""
        # Überprüfe, ob ein Attachment in der Nachricht vorhanden ist
        if inter:
            if not inter.response.is_done():
                await inter.response.defer(ephemeral=True)
        image_path = None

        if level < 1 or level > 3:
            await inter.edit_original_response(content="Warnlevel muss zwischen 1 und 3 liegen.")
            return

        avatar_url = user.avatar.url if user.avatar else user.default_avatar.url

        if proof:
            image_path = await Globalfile.save_image(proof, f"{user.id}")

        userrecord = await self.globalfile.get_user_record(discordid=user.id)

        current_datetime = (await self.globalfile.get_current_time()).strftime('%Y-%m-%d %H:%M:%S')
        cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "INSERT INTO WARN (USERID, REASON, IMAGEPATH, LEVEL, INSERT_DATE) VALUES (?, ?, ?, ?, ?)", (userrecord['ID'], reason, image_path, level, current_datetime))

        # Hole die zuletzt eingefügte ID
        caseid = cursor.lastrowid

        # Aktualisiere das Warnlevel in der User-Tabelle
        cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "UPDATE USER SET WARNLEVEL = ? WHERE ID = ?", (level, userrecord['ID']))
        self.logger.info(
            f"Warn added to User {userrecord['USERNAME']} : {reason}")

        # Sende eine Warn-Nachricht an den Benutzer
        try:
            user_embed = disnake.Embed(
                title="Warnung erhalten", description=f"Du hast eine Warnung erhalten.", color=disnake.Color.red())
            user_embed.set_author(name=user.name, icon_url=avatar_url)
            user_embed.add_field(name="Grund", value=reason, inline=False)
            user_embed.add_field(
                name="Warnlevel", value=str(level), inline=False)
            if image_path:
                user_embed.add_field(
                    name="Bildpfad", value=image_path, inline=False)
            user_embed.set_footer(text=f"ID: {user.id} - heute um {((await self.globalfile.get_current_time()).strftime('%H:%M:%S'))} Uhr")
            await user.send(embed=user_embed)
        except Exception as e:
            if inter:
                await inter.edit_original_response(content=f"Fehler beim Senden der Warn-Nachricht: {e}")

        # Sende eine Bestätigungsnachricht
        embed = disnake.Embed(
            title=f"Warnung erstellt [ID: {caseid}]", description=f"Für {user.mention} wurde eine Warnung erstellt.", color=disnake.Color.red())
        embed.set_author(name=user.name, icon_url=avatar_url)
        embed.add_field(name="Grund", value=reason, inline=False)
        embed.add_field(name="Warnlevel", value=str(level), inline=False)
        if image_path:
            embed.add_field(name="Bildpfad", value=image_path, inline=False)
        embed.set_footer(text=f"ID: {user.id} - heute um {((await self.globalfile.get_current_time()).strftime('%H:%M:%S'))} Uhr")
        await self.mod_channel.send(embed=embed)
        if inter:
            await inter.edit_original_response(content=f"Warnung erfolgreich erstellt. Logged in: {self.mod_channel.mention}")

    @exception_handler
    async def _warn_delete(self, inter: disnake.ApplicationCommandInteraction, caseid: int):
        """Löscht eine Warn basierend auf der Warn ID und setzt das Warnlevel zurück."""
        await inter.response.defer(ephemeral=True)
        try:

            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "SELECT * FROM WARN WHERE ID = ?", (caseid,))
            warn = (await cursor.fetchone())

            if warn is None:
                embed = disnake.Embed(
                    title="Warn nicht gefunden", description=f"Es gibt keine Warnung mit der ID {caseid}.", color=disnake.Color.red())
                await inter.edit_original_response(embed=embed)
                self.logger.info(f"Warn not found: {caseid}")
                return

            # Assuming USERID is the second column in WARN table
            user_id = warn[1]
            # Assuming LEVEL is the fifth column in WARN table
            warn_level = warn[4]

            # Reduziere das Warnlevel des Benutzers
            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "SELECT WARNLEVEL FROM USER WHERE ID = ?", (user_id,))
            current_warn_level = (await cursor.fetchone())[0]
            new_warn_level = max(0, current_warn_level - warn_level)
            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "UPDATE USER SET WARNLEVEL = ? WHERE ID = ?", (new_warn_level, user_id))

            # Lösche die Warnung
            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "UPDATE WARN SET REMOVED = 1 WHERE ID = ?", (caseid,))
            embed = disnake.Embed(
                title="Warn gelöscht", description=f"Warn mit der ID {caseid} wurde gelöscht und das Warnlevel wurde angepasst.", color=disnake.Color.green())
            self.logger.info(
                f"Warn deleted: {caseid}, Warnlevel adjusted for user {user_id} to {new_warn_level} by {inter.author.name} (ID: {inter.author.id}).")
            await self.mod_channel.send(embed=embed)
            await inter.edit_original_response(content=f"Warnung erfolgreich gelöscht. Logged in: {self.mod_channel.mention}")
        except sqlite3.Error as e:
            embed = disnake.Embed(
                title="Fehler", description=f"Ein Fehler ist aufgetreten: {e}", color=disnake.Color.red())
            await inter.edit_original_response(embed=embed)
            self.logger.critical(f"An error occurred: {e}")

    @exception_handler
    async def _ban(self,
                   inter: disnake.ApplicationCommandInteraction,
                   member: disnake.Member = commands.Param(
                       name="benutzer", description="Der Benutzer, der gebannt werden soll."),
                   reason: str = commands.Param(
                       name="begründung", description="Grund warum der Benutzer gebannt werden soll", default="Kein Grund angegeben"),
                   duration: str = commands.Param(
                       name="dauer", description="Dauer des Bans in Sek., Min., Std., Tagen oder Jahre.(Bsp.: 0s0m0h0d0j) Nichts angegeben = Dauerhaft", default="0s"),
                   delete_days: int = commands.Param(
                       name="geloeschte_nachrichten", description="Anzahl der Tage, für die Nachrichten des Benutzers gelöscht werden sollen. (0-7, Default = 0)", default=0),
                   proof: disnake.Attachment = commands.Param(name="beweis", description="Ein Bild als Beweis für den Ban und zur Dokumentation", default=None)):
        """Banne einen Benutzer und speichere ein Bild als Beweis."""
        await inter.response.defer(ephemeral=True)  # Verzögere die Interaktion
        image_path = ""
        try:
            # Berechnen der Banndauer
            if duration != "0s":
                duration_seconds = await self.globalfile.convert_duration_to_seconds(duration)
                ban_end_time = (await self.globalfile.get_current_time()) + timedelta(seconds=duration_seconds)
                ban_end_timestamp = int(ban_end_time.timestamp())
                ban_end_formatted = ban_end_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                duration_seconds = await self.globalfile.convert_duration_to_seconds(duration)
                ban_end_timestamp = None
                ban_end_formatted = "Unbestimmt"

            userrecord = await self.globalfile.get_user_record(discordid=member.id)

            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "SELECT * FROM BAN WHERE USERID = ?", (userrecord['ID'],))
            bans = await cursor.fetchall()
            ban_found = False
            for ban in bans:
                if not ban[6] == 1:  # Assuming 'Unban' is a column in your BANS table
                    ban_found = True

            if not ban_found:
                # Sende dem Benutzer ein Embed mit den Bann-Details
                embed = disnake.Embed(
                    title="Du wurdest gebannt", description="Du wurdest von diesem Server gebannt.", color=disnake.Color.red())
                embed.add_field(name="Grund", value=reason, inline=False)
                embed.add_field(name="Dauer", value=duration, inline=True)
                embed.add_field(name="Ende des Banns",
                                value=ban_end_formatted, inline=True)
                embed.add_field(name="Gelöschte Nachrichten (Tage)",
                                value=str(delete_days), inline=True)
                if proof:
                    # Setze das Bild des Beweises, falls vorhanden
                    embed.set_image(url=proof.url)

                try:
                    await member.send(embed=embed)
                except disnake.Forbidden:
                    self.logger.warning(
                        f"Could not send ban details to {member.id}. User has DMs disabled.")

                try:
                    asyncio.create_task(self.delete_messages_background(
                        inter.guild, member, delete_days))
                    await member.ban(reason=reason)
                    ban_successful = True
                except disnake.Forbidden:
                    ban_successful = False
                    await inter.edit_original_response(content=f"Ich habe keine Berechtigung, {member.mention} zu bannen.")
                except disnake.HTTPException as e:
                    ban_successful = False
                    await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")

                if ban_successful:
                    if proof:
                        if duration_seconds is None:
                            image_path = await self.globalfile.save_image(proof, f"{member.id}_infinitely")
                        else:
                            image_path = await self.globalfile.save_image(proof, f"{member.id}_{duration_seconds}")

                    userrecord = await self.globalfile.get_user_record(discordid=inter.user.id)
                    user_id = userrecord['ID']
                    userrecord = await self.globalfile.get_user_record(discordid=member.id)
                    current_datetime = (await self.globalfile.get_current_time()).strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(
                        "INSERT INTO BAN (USERID, REASON, BANNED_TO, DELETED_DAYS, IMAGEPATH, INSERT_DATE, BANNED_BY) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (userrecord['ID'], reason, ban_end_formatted, str(
                            delete_days), image_path, current_datetime, user_id)
                    )

                    embed = disnake.Embed(
                        title="Benutzer gebannt", description=f"{member.mention} wurde erfolgreich gebannt!", color=disnake.Color.red())
                    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                    embed.set_author(name=member.name, icon_url=avatar_url)
                    embed.set_footer(
                        text=f"User ID: {member.id} | {userrecord['ID']}")
                    embed.add_field(name="Grund", value=reason, inline=False)
                    embed.add_field(name="Dauer", value=duration, inline=True)
                    embed.add_field(name="Ende des Banns",
                                    value=ban_end_formatted, inline=True)
                    embed.add_field(name="Gelöschte Nachrichten (Tage)", value=str(
                        delete_days), inline=True)
                    embed.add_field(name="Erstellt am",
                                    value=current_datetime, inline=True)
                    embed.add_field(name="Gebannt von",
                                    value=inter.user.name, inline=True)
                    if proof:
                        # Setze das Bild des Beweises, falls vorhanden
                        embed.set_image(url=proof.url)

                    await self.mod_channel.send(embed=embed)
                    await inter.edit_original_response(content=f"Benutzer erfolgreich gebannt. Logged in: {self.mod_channel.mention}")
            else:
                await inter.edit_original_response(content=f"{member.mention} ist bereits gebannt! Ban nicht möglich.")
                self.logger.info(
                    f"User {member.id} ban not possible. User is already banned.")
        except disnake.ext.commands.errors.MemberNotFound:
            await inter.edit_original_response(content="Der angegebene Benutzer wurde nicht gefunden.")
            self.logger.error(
                f"MemberNotFound: Der Benutzer mit der ID {member.id} wurde nicht gefunden.")

    @exception_handler
    async def _unban(self, inter: disnake.ApplicationCommandInteraction,
                     userid: int = commands.param(
                         name="userid", description="Hier kannst du die UserID unserer Datenbank angeben.", default=0),
                     username: str = commands.Param(
                         name="username", description="Hier kannst du den Benutzernamen angeben, falls die UserID nicht bekannt ist.", default=""),
                     reason: str = commands.Param(name="begruendung", description="Bitte gebe eine Begründung für den Unban an.", default="Kein Grund angegeben")):
        """Entbanne einen Benutzer von diesem Server."""
        await inter.response.defer(ephemeral=True)  # Verzögere die Interaktion und mache sie nur für den Benutzer sichtbar
        try:
            userrecord = await self.globalfile.get_user_record(user_id=userid, username=username)
            user = await self.bot.fetch_user(int(userrecord['DISCORDID']))

            # Überprüfen, ob ein offener Ban existiert

            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "SELECT * FROM BAN WHERE USERID = ?", (str(userrecord['ID']),))
            bans = await cursor.fetchall()
            ban_found = False
            for ban in bans:
                if not ban[6] == "1":  # Assuming 'Unban' is a column in your BANS table
                    ban_found = True

            if not ban_found:
                await inter.edit_original_response(content=f"{user.mention} ist nicht gebannt! Unban nicht möglich.")
                self.logger.info(
                    f"User {user.id} unban not possible. User is not banned.")
            else:
                guild = inter.guild
                await guild.unban(user)
                teamuser_record = await self.globalfile.get_user_record(discordid=inter.author.id)
                cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "UPDATE BAN SET UNBANNED = 1, UNBANNED_BY = ?, UNBANNED_REASON = ? WHERE USERID = ? AND UNBANNED = 0", (teamuser_record['ID'], reason, str(userrecord['ID'])))

                embed = disnake.Embed(
                    title="Benutzer entbannt", description=f"{user.mention} wurde erfolgreich entbannt!", color=disnake.Color.green())
                avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
                embed.set_author(name=user.name, icon_url=avatar_url)
                embed.set_footer(
                    text=f"User ID: {userrecord['DISCORDID']} | {userrecord['ID']}")

                await self.mod_channel.send(embed=embed)
                await inter.edit_original_response(content=f"Benutzer erfolgreich entbannt. Logged in: {self.mod_channel.mention}")
                self.logger.info(f"User {user.id} unbanned.")
        except Exception as e:
            self.logger.critical(f"An error occurred: {e}")
            await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")

    @exception_handler
    async def _kick(self,
                    inter: disnake.ApplicationCommandInteraction,
                    member: disnake.Member = commands.Param(
                        name="benutzer", description="Der Benutzer, der gekickt werden soll."),
                    reason: str = commands.Param(
                        name="begründung", description="Grund warum der Benutzer gekickt werden soll", default="Kein Grund angegeben"),
                    proof: disnake.Attachment = commands.Param(name="beweis", description="Ein Bild als Beweis für den Kick und zur Dokumentation", default=None)):
        """Kicke einen Benutzer und speichere ein Bild als Beweis."""
        await inter.response.defer(ephemeral=True)  # Verzögere die Interaktion
        image_path = ""

        try:
            await member.kick(reason=reason)
            kick_successful = True
        except disnake.Forbidden:
            kick_successful = False
            await inter.edit_original_response(content=f"Ich habe keine Berechtigung, {member.mention} zu kicken.")
        except disnake.HTTPException as e:
            kick_successful = False
            await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")

        if kick_successful:
            if proof:
                image_path = await self.globalfile.save_image(proof, f"{member.id}_kick")

            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name,
                                                                           "INSERT INTO KICK (USERID, REASON, IMAGEPATH) VALUES (?, ?, ?)",
                                                                           (member.id, reason,
                                                                            image_path)
                                                                           )

            embed = disnake.Embed(
                title="Benutzer gekickt", description=f"{member.mention} wurde erfolgreich gekickt!", color=disnake.Color.red())
            avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
            embed.set_author(name=member.name, icon_url=avatar_url)
            embed.set_footer(text=f"User ID: {member.id}")
            embed.add_field(name="Grund", value=reason, inline=False)
            if proof:
                # Setze das Bild des Beweises, falls vorhanden
                embed.set_image(url=proof.url)

            await self.mod_channel.send(embed=embed)
            await inter.edit_original_response(content=f"Benutzer erfolgreich gekickt. Logged in: {self.mod_channel.mention}")

    @exception_handler
    async def _delete_messages_after(self, inter: disnake.ApplicationCommandInteraction,
                                     channel: disnake.TextChannel = commands.Param(
                                         name="channel", description="Der Kanal, in dem die Nachrichten gelöscht werden sollen."),
                                     timestamp: str = commands.Param(name="timestamp", description="Der Zeitpunkt (im Format YYYY-MM-DD HH:MM:SS) nach dem die Nachrichten gelöscht werden sollen.")):
        """Lösche alle Nachrichten in einem Kanal nach einer bestimmten Uhrzeit."""
        await inter.response.defer()

        try:
            delete_after = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            await inter.edit_original_response(content="Ungültiges Zeitformat. Bitte verwende das Format YYYY-MM-DD HH:MM:SS.")
            return

        deleted_messages = 0
        async for message in channel.history(after=delete_after, oldest_first=False):
            try:
                await message.delete()
                deleted_messages += 1
            except disnake.Forbidden:
                await inter.edit_original_response(content="Ich habe keine Berechtigung, Nachrichten zu löschen.")
                return
            except disnake.HTTPException as e:
                await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")
                return
            except disnake.errors.NotFound:
                # Nachricht existiert nicht mehr, einfach überspringen
                continue

        await inter.edit_original_response(content=f"{deleted_messages} Nachrichten wurden gelöscht.")

    @exception_handler
    async def delete_messages_background(self, guild: disnake.Guild, member: disnake.Member, days: int):
        """Löscht Nachrichten eines bestimmten Mitglieds aus allen Kanälen, die innerhalb der angegebenen Anzahl von Tagen geschrieben wurden."""
        delete_after = await self.globalfile.get_current_time() - timedelta(days=days)
        formatted_time = delete_after.strftime('%Y-%m-%d %H:%M:%S')

        for channel in guild.text_channels:
            async for message in channel.history(limit=None, after=delete_after):
                if message.author == member:
                    try:
                        await message.delete()
                    except disnake.Forbidden:
                        print(
                            f"Keine Berechtigung zum Löschen von Nachrichten in {channel.name}")
                    except disnake.HTTPException as e:
                        print(
                            f"Fehler beim Löschen von Nachrichten in {channel.name}: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before: disnake.Member, after: disnake.Member):
        # Überprüfe, ob sich die Rollen geändert haben
        if before.roles != after.roles:
            # Extrahiere die Rollen-IDs
            before_roles = set(role.id for role in before.roles)
            after_roles = set(role.id for role in after.roles)

            # Neue Rollen, die hinzugefügt wurden
            added_roles = after_roles - before_roles
            # Rollen, die entfernt wurden
            removed_roles = before_roles - after_roles

            # Aktualisiere die Datenbank für hinzugefügte Rollen
            for role_id in added_roles:
                role_name = self.rolemanager.get_role_name(
                    self.bot.guilds[0].id, role_id)
                if role_name and role_name in self.team_roles:
                    await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, """
                        INSERT INTO TEAM_MEMBERS (USERID, ROLE, TEAM_ROLE)
                        VALUES (?, ?, ?)
                        ON CONFLICT(USERID, ROLE) DO UPDATE SET TEAM_ROLE=excluded.TEAM_ROLE
                    """, (after.id, role_name, True))

                    self.logger.info(
                        f"Role {role_name} added to user {after.id} in TEAM_MEMBERS table.")

            # Aktualisiere die Datenbank für entfernte Rollen
            for role_id in removed_roles:
                role_name = self.rolemanager.get_role_name(
                    self.bot.guilds[0].id, role_id)
                if role_name and role_name in self.team_roles:
                    cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, """
                        DELETE FROM TEAM_MEMBERS WHERE USERID = ? AND ROLE = ?
                    """, (after.id, role_name))

                    self.logger.info(
                        f"Role {role_name} removed from user {after.id} in TEAM_MEMBERS table.")

    @exception_handler
    async def sync_team_members(self):
        """Synchronize the TEAM_MEMBERS table with the current roles of members."""
        # Fetch all current team members from the database
        cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, "SELECT USERID, ROLE FROM TEAM_MEMBERS")
        db_team_members = await cursor.fetchall()
        # Create a set of current team members from the database
        db_team_members_set = {(user_id, role)
                               for user_id, role in db_team_members}

        # Create a set of current team members from the server
        server_team_members_set = set()
        for guild in self.bot.guilds:
            for member in guild.members:
                for role in member.roles:
                    role_name = self.rolemanager.get_role_name(
                        self.bot.guilds[0].id, role.id)
                    if role_name and role_name in self.team_roles:
                        # Fetch USERID from USER table using get_user_record
                        user_record = await self.globalfile.get_user_record(discordid=member.id)
                        if user_record:
                            user_id = user_record['ID']
                            server_team_members_set.add((user_id, role_name))

        # Determine which members need to be added or removed
        members_to_add = server_team_members_set - db_team_members_set
        members_to_remove = db_team_members_set - server_team_members_set

        # Add new members to the database
        for user_id, role_name in members_to_add:
            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, """
                INSERT OR IGNORE INTO TEAM_MEMBERS (USERID, ROLE, TEAM_ROLE)
                VALUES (?, ?, ?)
            """, (user_id, role_name, True))
            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, """
                UPDATE TEAM_MEMBERS SET TEAM_ROLE = ? WHERE USERID = ? AND ROLE = ?
            """, (True, user_id, role_name))

            self.logger.info(
                f"Role {role_name} added to user {user_id} in TEAM_MEMBERS table.")

        # Remove members from the database
        for user_id, role_name in members_to_remove:
            cursor = await DatabaseConnectionManager.execute_sql_statement(self.bot.guilds[0].id, self.bot.guilds[0].name, """
                DELETE FROM TEAM_MEMBERS WHERE USERID = ? AND ROLE = ?
            """, (user_id, role_name))

            self.logger.info(
                f"Role {role_name} removed from user {user_id} in TEAM_MEMBERS table.")


def setupModeration(bot: commands.Bot, rolemanager: RoleManager):
    bot.add_cog(Moderation(bot, rolemanager))
