import disnake
import os
from disnake.ext import commands
from disnake.ui import Button, View
from disnake import ApplicationCommandInteraction, User, Member, Role
import disnake.file
import time
import re
from globalfile import Globalfile
from rolehierarchy import rolehierarchy
from datetime import datetime, timedelta, timedelta, date, timezone
import pytz
from dotenv import load_dotenv
import logging
import sqlite3
from dbconnection import DatabaseConnectionManager
import asyncio
import platform
import psutil
import os
from dotenv import load_dotenv, set_key
from exceptionhandler import exception_handler
from rolemanager import RoleManager


class Tmp(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager: RoleManager):
        self.bot = bot
        self.logger = logging.getLogger("Commands")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.globalfile : Globalfile = self.bot.get_cog('Globalfile')
        load_dotenv(dotenv_path="envs/settings.env")
        self.last_info_message = None
        self.last_info_time = None
        self.level_cog = self.bot.get_cog('Level')
        self.rolemanager = rolemanager

        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def cog_unload(self):
        Globalfile.unban_task.cancel()

    @commands.Cog.listener()
    async def on_ready(self):        
        self.mod_channel = self.bot.get_channel(1090588808216596490)
        self.logger.info("Tmp Cog is ready.")

    @exception_handler
    async def _info(self, inter: ApplicationCommandInteraction):
        await inter.response.defer(ephemeral=True)
        # Gather technical information
        programming_language = "Python"
        guild = inter.guild
        author = inter.guild.owner.mention
        server_os = platform.system()
        guild_info = {
            "user_count": guild.member_count,
            "boosts": guild.premium_subscription_count,
            "bots": sum(1 for member in guild.members if member.bot),
            "created_date": guild.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            "owner": guild.owner.mention,
            "guild_lang": guild.preferred_locale
        }
        meta_info = {
            "uptime": time.time() - psutil.boot_time(),
            "system_cpu_time": psutil.cpu_times().system,
            "user_cpu_time": psutil.cpu_times().user,
            "ram_usage": psutil.virtual_memory().used / (1024 ** 3),
            "bot_verified": False
        }

        # Create embed
        embed = disnake.Embed(
            title="Technische Informationen", color=disnake.Color.blue())
        embed.add_field(name="💻 **Programmiersprache**",
                        value=programming_language, inline=True)
        embed.add_field(name="👤 **Autor**", value=author, inline=True)
        embed.add_field(name="🖥️ **Betriebssystem**",
                        value=server_os, inline=True)
        embed.add_field(
            name="🏰 **Gilde**", value=f"Useranzahl: {guild_info['user_count']}\nBoosts: {guild_info['boosts']}\nBots: {guild_info['bots']}\nErstellt am: {guild_info['created_date']}\nBesitzer: {guild_info['owner']}\nSprache: {guild_info['guild_lang']}", inline=False)
        embed.add_field(
            name="📊 **Meta**", value=f"Uptime: {meta_info['uptime'] // 3600:.0f} Stunden\nSystem CPU Zeit: {meta_info['system_cpu_time']:.2f} Sekunden\nUser CPU Zeit: {meta_info['user_cpu_time']:.2f} Sekunden\nRAM Nutzung: {meta_info['ram_usage']:.2f} GB\nBot Verifiziert: {meta_info['bot_verified']}", inline=False)

        message = await inter.edit_original_response(embed=embed)

        # Update cooldown
        self.last_info_message = message
        self.last_info_time = datetime.now(timezone.utc)

    @exception_handler
    async def _server(self, inter: ApplicationCommandInteraction):
        await inter.response.send_message(
            f"Server name: {inter.guild.name}\nTotal members: {inter.guild.member_count}",
            ephemeral=True
        )

    @exception_handler
    async def _user(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.send_message(
            f"Your tag: {inter.author}\nYour ID: {inter.author.id}",
            ephemeral=True
        )

    @exception_handler
    async def _list_banned_users(self, inter: disnake.ApplicationCommandInteraction):
        """Listet alle gebannten Benutzer auf und zeigt den Entbannzeitpunkt an, falls vorhanden."""
        await inter.response.defer(ephemeral=True)  # Verzögere die Interaktion
        try:
            cursor = await DatabaseConnectionManager.execute_sql_statement(
                inter.guild.id, inter.guild.name,
                "SELECT USERID, BANNED_TO FROM BAN WHERE UNBANNED = 0 ORDER BY BANNED_TO DESC"
            )
            bans = await cursor.fetchall()
        except sqlite3.Error as e:
            await inter.edit_original_response(f"Ein Fehler ist aufgetreten: {e}")
            return

        if not bans:
            await inter.edit_original_response("Es gibt keine gebannten Benutzer.")
            return

        async def create_embed(page):
            embed = disnake.Embed(
                title="Liste der gebannten Benutzer", color=disnake.Color.red()
            )
            start = page * 10
            end = start + 10
            for ban in bans[start:end]:
                user_id, unban_time = ban
                cursor = await DatabaseConnectionManager.execute_sql_statement(
                    inter.guild.id, inter.guild.name,
                    "SELECT USERNAME FROM USER WHERE ID = ?", (user_id,)
                )
                username_result = (await cursor.fetchone())
                username = username_result[0] if username_result else "Unbekannt"

                if unban_time:
                    unban_date = datetime.fromtimestamp(
                        float(unban_time)
                    ).strftime('%Y-%m-%d %H:%M:%S')
                    embed.add_field(
                        name=f"User ID: {user_id}",
                        value=f"Username: {username}\nEntbannzeitpunkt: {unban_date}",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name=f"User ID: {user_id}",
                        value=f"Username: {username}\nEntbannzeitpunkt: Nicht festgelegt",
                        inline=False
                    )
            embed.set_footer(
                text=f"Seite {page + 1} von {len(bans) // 10 + 1}"
            )
            return embed

        async def update_embed(interaction, page):
            embed = await create_embed(page)
            await interaction.response.edit_message(embed=embed, view=await create_view(page))

        async def create_view(page):
            view = View()
            if page > 0:
                view.add_item(Button(
                    label="Zurück", style=disnake.ButtonStyle.primary, custom_id=f"prev_{page}"
                ))
            if (page + 1) * 10 < len(bans):
                view.add_item(Button(
                    label="Weiter", style=disnake.ButtonStyle.primary, custom_id=f"next_{page}"
                ))
            return view

        current_page = 0
        embed = await create_embed(current_page)
        view = await create_view(current_page)

        message = await inter.edit_original_response(embed=embed, view=view)

        def check(interaction: disnake.MessageInteraction):
            return interaction.message.id == message.id and interaction.user.id == inter.user.id

        while True:
            interaction = await self.bot.wait_for("message_interaction", check=check)
            if interaction.data["custom_id"].startswith("prev_"):
                current_page -= 1
            elif interaction.data["custom_id"].startswith("next_"):
                current_page += 1
            await update_embed(interaction, current_page)

    @exception_handler
    async def _blacklist_add(self, inter: disnake.ApplicationCommandInteraction, word: str, level: int = 1):
        """Füge ein Wort zur Blacklist-Liste hinzu, wenn es noch nicht existiert."""
        await inter.response.defer()  # Verzögere die Interaktion

        word = word.strip()  # Entferne führende und abschließende Leerzeichen

        # Überprüfe, ob das Wort bereits in der Tabelle existiert
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT word FROM BLACKLIST WHERE WORD = ?", (word,))
        result = (await cursor.fetchone())

        embed = disnake.Embed(title="Blacklist Hinzufügen",
                              color=disnake.Color.green())

        if not result:
            # Wort existiert nicht, füge es hinzu
            await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "INSERT INTO BLACKLIST (WORD,LEVEL) VALUES (?,?)", (word, level))

            embed.description = f"{word} wurde zur Blacklist-Liste hinzugefügt."
        else:
            embed.description = f"{word} existiert bereits in der Blacklist-Liste."

        await inter.edit_original_response(embed=embed)

    @exception_handler
    async def _blacklist_remove(self, inter: disnake.ApplicationCommandInteraction, word: str):
        """Entferne ein Wort von der Blacklist-Liste."""
        await inter.response.defer()  # Verzögere die Interaktion

        word = word.strip()  # Entferne führende und abschließende Leerzeichen

        # Überprüfe, ob das Wort in der Tabelle existiert
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT word FROM Blacklist WHERE word = ?", (word,))
        result = (await cursor.fetchone())

        embed = disnake.Embed(title="Blacklist Entfernen",
                              color=disnake.Color.red())

        if result:
            # Wort existiert, entferne es
            cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "DELETE FROM Blacklist WHERE word = ?", (word,))

            embed.description = f"{word} wurde von der Blacklist-Liste entfernt."
        else:
            embed.description = f"{word} existiert nicht in der Blacklist-Liste."

        await inter.edit_original_response(embed=embed)

    @exception_handler
    async def _blacklist(self, inter: disnake.ApplicationCommandInteraction):
        """Zeige die aktuelle Blacklist-Liste."""
        await inter.response.defer()  # Verzögere die Interaktion

        # Hole alle Wörter aus der Tabelle
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT word FROM Blacklist")
        badwords = await cursor.fetchall()
        embed = disnake.Embed(title="Aktuelle Badwords",
                              color=disnake.Color.red())

        if badwords:
            badwords_list = "\n".join(word[0] for word in badwords)
            embed.add_field(name="Badwords", value=badwords_list, inline=False)
        else:
            embed.add_field(
                name="Badwords", value="Die Blacklist-Liste ist leer.", inline=False)

        await inter.edit_original_response(embed=embed)

    @exception_handler
    async def _add_user_to_ticket(self, inter: disnake.ApplicationCommandInteraction, ticket_id: int, user: disnake.User):
        """Fügt einen Benutzer zu einem Ticket-Channel hinzu."""
        await inter.response.defer()
        # Suche nach dem Ticket-Channel
        ticket_channel = None
        for channel in inter.guild.text_channels:
            if "ticket" in channel.name.lower() and str(ticket_id) in channel.name:
                ticket_channel = channel
                break

        if not ticket_channel:
            await inter.response.send_message("Ticket-Channel nicht gefunden.")
            return

        # Berechtigungen setzen
        overwrite = disnake.PermissionOverwrite()
        overwrite.read_messages = True
        overwrite.send_messages = True

        # Benutzer zum Channel hinzufügen
        try:
            await ticket_channel.set_permissions(user, overwrite=overwrite)
            await inter.edit_original_response(f"{user.mention} wurde zum Ticket-Channel hinzugefügt.")
        except Exception as e:
            await inter.edit_original_response(f"Fehler beim Hinzufügen des Benutzers: {e}")

    @exception_handler
    async def _note_add(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, reason: str, proof: disnake.Attachment = None):
        """Erstellt eine Notiz für einen Benutzer."""
        await inter.response.defer()
        # Überprüfe, ob ein Attachment in der Nachricht vorhanden ist
        image_path = None

        avatar_url = user.avatar.url if user.avatar else user.default_avatar.url

        if proof:
            image_path = await self.globalfile.save_image(proof, f"{user.id}")

        userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=user.id)

        current_datetime = (await self.globalfile.get_current_time()).strftime('%Y-%m-%d %H:%M:%S')
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "INSERT INTO NOTE (NOTE, USERID, IMAGEPATH, INSERT_DATE) VALUES (?, ?, ?, ?)", (reason, userrecord['ID'], image_path, current_datetime))

        # Hole die zuletzt eingefügte ID
        caseid = cursor.lastrowid

        self.logger.info(f"Note added: {reason}")

        # Sende eine Bestätigungsnachricht
        embed = disnake.Embed(
            title=f"Notiz erstellt [ID: {caseid}]", description=f"Für {user.mention} wurde eine Notiz erstellt.", color=disnake.Color.green())
        embed.set_author(name=user.name, icon_url=avatar_url)
        embed.add_field(name="Grund", value=reason, inline=False)
        if image_path:
            embed.add_field(name="Bildpfad", value=image_path, inline=False)
        embed.set_footer(text=f"ID: {user.id} - heute um {((await self.globalfile.get_current_time()).strftime('%H:%M:%S'))} Uhr")
        await inter.edit_original_response(content=f"Notiz für {user.mention} erstellt. Logged in {self.mod_channel.mention} als [ID: {caseid}]")
        await self.mod_channel.send(embed=embed)

    @exception_handler
    async def _note_delete(self, inter: disnake.ApplicationCommandInteraction, caseid: int, reason: str):
        """Markiert eine Note als gelöscht basierend auf der Note ID."""
        await inter.response.defer(ephemeral=True)
        try:
            userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
            await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "UPDATE NOTE SET REMOVED = 1, REMOVED_REASON = ?, REMOVED_BY = ? WHERE ID = ?", (caseid, reason, userrecord['ID']))

            embed = disnake.Embed(
                title="Note gelöscht", description=f"Note mit der ID {caseid} wurde als gelöscht markiert.", color=disnake.Color.green())
            self.logger.info(f"Note marked as deleted: {caseid}")
            await self.mod_channel.send(embed=embed)
            await inter.edit_original_response(f"Note mit der ID {caseid} wurde als gelöscht markiert.")
        except sqlite3.Error as e:
            await inter.edit_original_response(f"Ein Fehler ist aufgetreten: {e}")
            self.logger.critical(f"An error occurred: {e}")    

    @exception_handler
    async def _disconnect(self, inter: disnake.ApplicationCommandInteraction):
        """Schließt alle Verbindungen des Bots und beendet den Bot-Prozess."""
        await inter.response.send_message("Der Bot wird nun alle Verbindungen schließen und beendet werden.", ephemeral=True)
        self.logger.warning("Bot wird heruntergefahren.")
        await self.bot.close()

    @exception_handler
    async def _sync_users(self, inter: disnake.ApplicationCommandInteraction):
        """Synchronisiere alle Benutzer des Servers mit der Users Tabelle."""
        await inter.response.defer()
        guild = inter.guild
        members = guild.members

        synced_count = 0

        for member in members:
            # Überprüfen, ob der Benutzer bereits in der Tabelle Users existiert
            cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT ID, USERNAME FROM USER WHERE DISCORDID = ?", (str(member.id),))
            result = (await cursor.fetchone())

            if not result:
                # Benutzer existiert nicht, füge ihn in die Tabelle Users ein
                await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "INSERT INTO USER (DISCORDID, USERNAME) VALUES (?, ?)", (str(member.id), member.name))

                synced_count += 1
            else:
                # Benutzer existiert, überprüfe den Benutzernamen
                user_id, db_username = result
                if db_username != member.name:
                    # Benutzername ist nicht korrekt, aktualisiere ihn
                    cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "UPDATE USER SET USERNAME = ? WHERE ID = ?", (member.name, user_id))

                    synced_count += 1

        self.logger.info(
            f"User synchronization completed started by {inter.author.name}. (ID: {inter.author.id})")
        await inter.edit_original_response(content=f"Benutzer-Synchronisation abgeschlossen. {synced_count} Benutzer wurden synchronisiert.")

    @exception_handler
    async def _remove_role_from_all(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        """Entfernt eine bestimmte Rolle bei allen Benutzern in der Gilde."""
        await inter.response.defer()
        guild = inter.guild
        members = guild.members

        removed_count = 0

        for member in members:
            if role in member.roles:
                try:
                    await member.remove_roles(role)
                    removed_count += 1
                except disnake.Forbidden:
                    await inter.edit_original_response(content=f"Ich habe keine Berechtigung, die Rolle {role.name} bei {member.mention} zu entfernen.")
                    return
                except disnake.HTTPException as e:
                    await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")
                    return
        await inter.edit_original_response(content=f"Die Rolle {role.name} wurde bei {removed_count} Benutzern entfernt.")
        self.logger.info(
            f"Role {role.name} removed from {removed_count} users.")

    @exception_handler
    async def _unban_all_users(self, inter: disnake.ApplicationCommandInteraction):
        """Entbannt alle gebannten Benutzer in der Gilde."""
        await inter.response.defer()
        guild = inter.guild

        try:
            bans = await guild.bans().flatten()
            if not bans:
                await inter.edit_original_response(content="Es gibt keine gebannten Benutzer.")
                return

            unbanned_count = 0
            for ban_entry in bans:
                user = ban_entry.user
                try:
                    await guild.unban(user)
                    unbanned_count += 1
                except disnake.Forbidden:
                    await inter.edit_original_response(content=f"Ich habe keine Berechtigung, {user.mention} zu entbannen.")
                    return
                except disnake.HTTPException as e:
                    await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")
                    return

            await inter.edit_original_response(content=f"Alle gebannten Benutzer wurden entbannt. Anzahl der entbannten Benutzer: {unbanned_count}")
            self.logger.info(
                f"All banned users have been unbanned. Number of unbanned users: {unbanned_count}")
        except disnake.HTTPException as e:
            await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")

    @exception_handler
    async def _warn_inactive_users(self, inter: disnake.ApplicationCommandInteraction, days: int, role: disnake.Role, channel: disnake.TextChannel):
        """Warnt alle Benutzer, die innerhalb der angegebenen Tage keine Nachrichten geschrieben haben."""
        await inter.response.defer(ephemeral=True)

        guild = inter.guild
        cutoff_date = (await self.globalfile.get_current_time()) - timedelta(days=days)
        active_users = set()
        channelid = channel.id

        if not role:
            await inter.edit_original_response(content="Die angegebene Rolle existiert nicht.")
            return

        if not channel:
            await inter.edit_original_response(content="Der angegebene Kanal existiert nicht.")
            return

        # Sammle alle aktiven Benutzer
        for channel in guild.text_channels:
            async for message in channel.history(limit=None, after=cutoff_date):
                active_users.add(message.author.id)

        # Vergib die Rolle an inaktive Benutzer
        inactive_users = [
            member for member in guild.members if member.id not in active_users and not member.bot]
        for member in inactive_users:
            await member.add_roles(role, reason=f"Inaktiv für {days} Tage")

        # Pinge die Rolle im angegebenen Kanal
        channel = await inter.guild.fetch_channel(channelid)
        await channel.send(f"{role.mention} Bitte schreibt mal wieder etwas, sonst gibt es Stress! Danke❤️")

        await inter.edit_original_response(content=f"Rolle wurde an {len(inactive_users)} inaktive Benutzer vergeben und Nachricht wurde gesendet.")

    @exception_handler
    async def _kick_inactive_users(self, inter: disnake.ApplicationCommandInteraction, months: int, execute: bool = False):
        """Kicke alle Benutzer, die innerhalb der angegebenen Monate keine Nachrichten geschrieben haben."""
        await inter.response.defer()
        await inter.edit_original_response(content=f"Starte das Überprüfen von inaktiven Benutzern, die in den letzten {months} Monaten nichts geschrieben haben.")
        await self.kick_inactive_users_task(inter, months, execute)

    @exception_handler
    async def _kick_inactive_users_task(self, inter: disnake.ApplicationCommandInteraction, months: int, execute: bool):

        async def split_into_chunks(text, max_length):
            """Splits text into chunks of a maximum length."""
            return [text[i:i + max_length] for i in range(0, len(text), max_length)]

        async def create_embed(title, color, fields):
            embed = disnake.Embed(title=title, color=color)
            for name, value in fields:
                embed.add_field(name=name, value=value, inline=False)
            return embed

        MAX_EMBED_FIELD_LENGTH = 1024
        MAX_EMBED_TOTAL_LENGTH = 5000
        guild = inter.guild
        cutoff_date = self.globalfile.get_current_time - \
            timedelta(days=months*30)
        active_users = set()
        kicked_users = []
        failed_kicks = []
        self.logger.info(
            f"Starte Kick-Prozess (started by {inter.user.name})) für inaktive Benutzer, die in den letzten {months} Monaten nichts geschrieben haben...")
        embeds = []
        current_embed_fields = []
        current_embed_length = 0

        semaphore = asyncio.Semaphore(500)
        tasks = []

        start_time = time.time()  # Startzeit erfassen

        for channel in guild.text_channels:
            tasks.append(self.log_active_users(
                channel, cutoff_date, semaphore, active_users))

        await asyncio.gather(*tasks)

        end_time = time.time()  # Endzeit erfassen
        elapsed_time = end_time - start_time  # Zeitdifferenz berechnen

        inactive_users = [
            member for member in guild.members if member.id not in active_users and not member.bot]

        self.logger.info(
            f"Lesevorgang abgeschlossen. {len(inactive_users)} inaktive Benutzer gefunden, die gekickt werden sollen.")
        self.logger.info(
            f"Das Einlesen der Channels hat {elapsed_time:.2f} Sekunden gedauert.")
        i = 0

        for member in inactive_users:
            if execute:
                try:
                    # Sende Nachricht an den Benutzer
                    invite = await guild.text_channels[0].create_invite(max_uses=1, unique=True)
                    embed = disnake.Embed(
                        title="Du wurdest gekickt von {self.bot.user.name}", color=disnake.Color.dark_blue())
                    embed.set_author(name=self.bot.user.name,
                                     icon_url=guild.icon.url)
                    embed.add_field(
                        name="Grund", value=f"Inaktiv für {months} Monate. Grund für diesen Prozess ist das entfernen von inaktiven/Scammer Accounts.", inline=False)
                    embed.add_field(
                        name="Wiederbeitreten", value=f"[Hier klicken]({invite.url}) um dem Server wieder beizutreten. Wir empfangen dich gerne erneut, solltest du dem Server wieder beitreten wollen.", inline=False)
                    try:
                        await member.send(embed=embed)
                    except disnake.Forbidden:
                        self.logger.warning(
                            f"Keine Berechtigung, Nachricht an {member.name} (ID: {member.id}) zu senden.")
                        await member.kick(reason=f"Inaktiv für {months} Monate")
                        kicked_users.append(member)
                        self.logger.info(
                            f"User {member.name} (ID: {member.id}) wurde gekickt. {i}/{len(inactive_users)}")
                except disnake.Forbidden:
                    failed_kicks.append(member)
                    self.logger.warning(
                        f"Keine Berechtigung, {member.name} (ID: {member.id}) zu kicken.")
                except disnake.HTTPException as e:
                    failed_kicks.append(member)
                    self.logger.error(
                        f"Fehler beim Kicken von {member.name} (ID: {member.id}): {e}")
            else:
                kicked_users.append(member)

        embed = disnake.Embed(
            title="Kick Inaktive Benutzer", color=disnake.Color.red())
        embed.add_field(name="Anzahl der gekickten Benutzer",
                        value=len(kicked_users), inline=False)

        if kicked_users:
            kicked_list = "\n".join(
                [f"{member.name} (ID: {member.id})" for member in kicked_users])
            if len(kicked_list) > MAX_EMBED_FIELD_LENGTH:
                chunks = await split_into_chunks(kicked_list, MAX_EMBED_FIELD_LENGTH)
                for i, chunk in enumerate(chunks):
                    field_name = f"Gekickte Benutzer (Teil {i+1})" if execute else f"Benutzer, die gekickt werden würden (Teil {i+1})"
                    current_embed_fields.append((field_name, chunk))
                    current_embed_length += len(field_name) + len(chunk)
                    if current_embed_length > MAX_EMBED_TOTAL_LENGTH:
                        embeds.append(await create_embed(
                            "Kick Inaktive Benutzer", disnake.Color.red(), current_embed_fields))
                        current_embed_fields = []
                        current_embed_length = 0
            else:
                current_embed_fields.append(
                    ("Gekickte Benutzer" if execute else "Benutzer, die gekickt werden würden", kicked_list))
                current_embed_length += len(
                    "Gekickte Benutzer" if execute else "Benutzer, die gekickt werden würden") + len(kicked_list)

        # Add failed kicks to embed fields
        if failed_kicks:
            failed_list = "\n".join(
                [f"{member.name} (ID: {member.id})" for member in failed_kicks])
            if len(failed_list) > MAX_EMBED_FIELD_LENGTH:
                chunks = await split_into_chunks(failed_list, MAX_EMBED_FIELD_LENGTH)
                for i, chunk in enumerate(chunks):
                    field_name = f"Fehlgeschlagene Kicks (Teil {i+1})"
                    current_embed_fields.append((field_name, chunk))
                    current_embed_length += len(field_name) + len(chunk)
                    if current_embed_length > MAX_EMBED_TOTAL_LENGTH:
                        embeds.append(await create_embed(
                            "Kick Inaktive Benutzer", disnake.Color.red(), current_embed_fields))
                        current_embed_fields = []
                        current_embed_length = 0
            else:
                current_embed_fields.append(
                    ("Fehlgeschlagene Kicks", failed_list))
                current_embed_length += len("Fehlgeschlagene Kicks") + \
                    len(failed_list)

        if current_embed_fields:
            embeds.append(await create_embed("Kick Inaktive Benutzer",
                          disnake.Color.red(), current_embed_fields))

        # Send all embeds
        first_embed = True
        channel = inter.channel
        for embed in embeds:
            if first_embed:
                await inter.edit_original_response(embed=embed)
                first_embed = False
            else:
                await channel.send(embed=embed)

        self.logger.info(
            f"Kick-Prozess abgeschlossen. {len(kicked_users)} Benutzer wurden gekickt." if execute else f"{len(kicked_users)} Benutzer würden gekickt werden.")

    @exception_handler
    async def _log_active_users(self, channel, cutoff_date, semaphore, active_users):
        async with semaphore:
            try:
                async for message in channel.history(limit=None):
                    if message.created_at < cutoff_date:
                        break
                    active_users.add(message.author.id)
            except Exception as e:
                self.logger.warning(
                    f"Fehler beim Durchsuchen der Nachrichten in Kanal {channel.name}: {e}")

    @exception_handler
    async def _help_moderation(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt alle Moderationsbefehle an."""
        await inter.response.defer(ephemeral=True)
        commands_list = [
            {"name": "/ping", "description": "Get the bot's current websocket latency.",
                "rank": "Test-Supporter"},
            {"name": "/server", "description": "Get the server's name and member count.",
                "rank": "Test-Supporter"},
            {"name": "/ban", "description": "Banne einen Benutzer und speichere ein Bild als Beweis.",
                "rank": "Senior Supporter"},
            {"name": "/unban", "description": "Entbanne einen Benutzer von diesem Server.",
                "rank": "Senior Supporter"},
            {"name": "/list_banned_users", "description": "Listet alle gebannten Benutzer auf und zeigt den Entbannzeitpunkt an, falls vorhanden.", "rank": "Senior Supporter"},
            {"name": "/note_add", "description": "Erstellt eine Notiz für einen Benutzer.",
                "rank": "Test-Supporter"},
            {"name": "/note_delete", "description": "Löscht eine Note basierend auf der Note ID.",
                "rank": "Senior Supporter"},
            {"name": "/warn_add", "description": "Erstellt eine Warnung für einen Benutzer.",
                "rank": "Test-Supporter"},
            {"name": "/warn_delete", "description": "Löscht eine Warn basierend auf der Warn ID und setzt das Warnlevel zurück.",
                "rank": "Senior Supporter"},
            {"name": "/timeout", "description": "Timeout einen Benutzer für eine bestimmte Dauer und optional eine Warnung erstellen.",
                "rank": "Senior Supporter"},
            {"name": "/timeout_remove",
                "description": "Entfernt einen Timeout basierend auf der Timeout ID.", "rank": "Moderator"},
            {"name": "/badword_add", "description": "Füge ein Wort zur Blacklist-Liste hinzu, wenn es noch nicht existiert.", "rank": "Moderator"},
            {"name": "/badword_remove",
                "description": "Entferne ein Wort von der Blacklist-Liste.", "rank": "Moderator"},
            {"name": "/badwords_list",
                "description": "Zeige die aktuelle Blacklist-Liste.", "rank": "Moderator"},
            {"name": "/kick_inactive_users",
                "description": "Kicke alle Benutzer, die innerhalb der angegebenen Monate keine Nachrichten geschrieben haben.", "rank": "Leitung"},
            {"name": "/remove_role_from_all",
                "description": "Entfernt eine bestimmte Rolle bei allen Benutzern in der Gilde.", "rank": "Administrator"},
            {"name": "/unban_all_users",
                "description": "Entbannt alle gebannten Benutzer in der Gilde.", "rank": "Administrator"},
            {"name": "/sync_users", "description": "Synchronisiere alle Benutzer des Servers mit der Users Tabelle.", "rank": "Moderator"},
            {"name": "/disconnect", "description": "Schließt alle Verbindungen des Bots und beendet den Bot-Prozess.",
                "rank": "Administrator"},
            {"name": "/verify_user", "description": "Verifiziert einen Benutzer und gibt ihm die Rolle 'Verified'.", "rank": "Supporter"},
            {"name": "/set_ai_open", "description": "Setzt den Wert von AI_OPEN in der .env Datei auf true oder false.", "rank": "Administrator"}
        ]
        self.logger.info(
            f"Command /help_moderation was executed by {inter.user.name} (ID: {inter.user.id}).")

        await self.paginate_commands(inter, commands_list, "Moderationsbefehle")

    @exception_handler
    async def _help_user(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt alle Benutzerbefehle an."""
        await inter.response.defer(ephemeral=True)
        commands_list = [
            {"name": "/help_user",
                "description": "Zeigt alle Benutzerbefehle an.", "rank": "Level 1+"},
            {"name": "/user", "description": "Get your tag and ID.", "rank": "Level 1+"},
            {"name": "/add_user_to_ticket",
                "description": "Fügt einen Benutzer zu einem Ticket-Channel hinzu.", "rank": "Level 1+"},
            {"name": "/me", "description": "Zeigt das eigene Profil an, einschließlich Notizen und Warnungen.", "rank": "Level 1+"},
            {"name": "/info", "description": "Zeigt Informationen über den Bot an.",
                "rank": "Level 1+"},
            {"name": "/top_users",
                "description": "Zeigt alle Moderationsbefehle an.", "rank": "Level 1+"},

        ]
        self.logger.info(
            f"Command /help_user was executed by {inter.user.name} (ID: {inter.user.id}).")
        await self.paginate_commands(inter, commands_list, "Benutzerbefehle")

    @exception_handler
    async def paginate_commands(self, inter: disnake.ApplicationCommandInteraction, commands_list, title):
        MAX_COMMANDS_PER_PAGE = 5

        async def get_role_mention(role_name):
            role = disnake.utils.get(inter.guild.roles, name=role_name)
            return role.mention if role else role_name

        async def create_embed(page):
            embed = disnake.Embed(title=title, color=disnake.Color.blue())
            start = page * MAX_COMMANDS_PER_PAGE
            end = start + MAX_COMMANDS_PER_PAGE
            for command in commands_list[start:end]:
                embed.add_field(
                    name=f"📜 {command['name']}",
                    value=f"📝 {command['description']}\n🔒 Rang: {await get_role_mention(command['rank'])}",
                    inline=False
                )
            embed.set_footer(
                text=f"Seite {page + 1} von {len(commands_list) // MAX_COMMANDS_PER_PAGE + 1}")
            return embed

        async def update_embed(interaction, page):
            embed = await create_embed(page)
            await interaction.response.edit_message(embed=embed, view=await create_view(page))

        async def create_view(page):
            view = View()
            if page > 0:
                view.add_item(Button(
                    label="Zurück", style=disnake.ButtonStyle.primary, custom_id=f"prev_{page}"))
            if (page + 1) * MAX_COMMANDS_PER_PAGE < len(commands_list):
                view.add_item(Button(
                    label="Weiter", style=disnake.ButtonStyle.primary, custom_id=f"next_{page}"))
            return view

        current_page = 0
        embed = await create_embed(current_page)
        view = await create_view(current_page)

        message = await inter.edit_original_response(embed=embed, view=view)

        def check(interaction: disnake.MessageInteraction):
            return interaction.message.id == message.id and interaction.user.id == inter.user.id

        while True:
            interaction = await self.bot.wait_for("message_interaction", check=check)
            if interaction.data["custom_id"].startswith("prev_"):
                current_page -= 1
            elif interaction.data["custom_id"].startswith("next_"):
                current_page += 1
            await update_embed(interaction, current_page)

    @exception_handler
    async def _verify_user(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Verifiziert einen Benutzer und gibt ihm die Rolle 'Verified'."""
        await inter.response.defer()

        userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=member.id)

        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "UPDATE USER SET verified = 1 WHERE ID = ?", (userrecord['ID'],))
        verified_role = self.rolemanager.get_role(inter.guild.id, int(os.getenv("VERIFIED_ROLE_ID")))
        if verified_role:
            await member.add_roles(verified_role)
            await inter.edit_original_response(content=f"{member.mention} wurde verifiziert und die Rolle {verified_role.mention} wurde hinzugefügt.")
            self.logger.info(
                f"User {user.name} (ID: {user.id}) was verified by {inter.user.name} (ID: {inter.user.id}).")
        else:
            await inter.edit_original_response(content="Die Rolle 'Verified' wurde nicht gefunden.")
            self.logger.warning(f"The role 'Verified' was not found.")

    @exception_handler
    async def _add_image(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, image: disnake.Attachment):
        """Fügt ein Bild zu einem Benutzer hinzu."""
        await inter.response.defer()

        # Überprüfe, ob ein Attachment in der Nachricht vorhanden ist
        if not image:
            await inter.edit_original_response(content="Bitte füge ein Bild hinzu.")
            self.logger.warning(
                f"No attachment found in the command(/add_image) by {inter.user.name} (ID: {inter.user.id}).")
            return

        # Hole die Benutzerinformationen aus der Tabelle User
        userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=user.id)

        # Hole den aktuellen Bildpfad

        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT imagepath FROM USER WHERE ID = ?", (userrecord['ID'],))
        current_imagepath = (await cursor.fetchone())[0]

        # Bestimme den neuen Bildpfad
        base_path = f"{user.id}_image"
        if current_imagepath:
            image_paths = current_imagepath.split(';')
            new_image_index = len(image_paths)
            new_image_path = await self.globalfile.save_image(image, f"{base_path}_{new_image_index}")
            updated_imagepath = f"{current_imagepath};{new_image_path}"
        else:
            new_image_path = await self.globalfile.save_image(image, base_path)
            updated_imagepath = new_image_path

        # Aktualisiere den Bildpfad in der Datenbank
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "UPDATE USER SET imagepath = ? WHERE ID = ?", (updated_imagepath, userrecord['ID']))

        self.logger.info(
            f"A new image was added for User {user.name} (ID: {user.id}) by {inter.user.name} (ID: {inter.user.id}).")

        await inter.edit_original_response(content=f"Ein Bild wurde für {user.mention} hinzugefügt.")

    @exception_handler
    async def _set_ai_open(self, inter: disnake.ApplicationCommandInteraction, value: bool):
        """Setzt den Wert von AI_OPEN in der .env Datei auf true oder false."""
        await inter.response.defer()

        env_path = "envs/settings.env"
        load_dotenv(dotenv_path=env_path)

        # Setze den Wert von AI_OPEN
        set_key(env_path, "AI_OPEN", str(value).upper())
        self.logger.info(
            f"AI_OPEN was set to {value} by {inter.user.name} (ID: {inter.user.id}).")
        await inter.edit_original_response(content=f"AI_OPEN wurde auf {value} gesetzt.")

    @exception_handler
    async def _set_birthday(self, inter: disnake.ApplicationCommandInteraction, birthday: str):
        """Setzt den Geburtstag eines Benutzers im Format YYYY-MM-DD."""
        await inter.response.defer()

        try:
            # Parse the birthday string to a date object
            birthday_date = datetime.strptime(birthday, "%Y-%m-%d").date()
        except ValueError:
            await inter.edit_original_response(content="Ungültiges Datum. Bitte verwende das Format YYYY-MM-DD.")
            return

        # Update the user's birthday in the database
        userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)

        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "UPDATE USER SET BIRTHDAY = ? WHERE ID = ?", (birthday_date, userrecord['ID']))

        # Calculate the days until the next birthday
        today = date.today()
        next_birthday = birthday_date.replace(year=today.year)
        if next_birthday < today:
            next_birthday = next_birthday.replace(year=today.year + 1)
        days_until_birthday = (next_birthday - today).days

        # Create an embed for the response
        embed = disnake.Embed(
            title="🎉 Geburtstag gesetzt!",
            description=f"Der Geburtstag von {inter.user.mention} wurde auf **{birthday_date}** gesetzt.",
            color=disnake.Color.blue()
        )
        embed.add_field(name="📅 Nächster Geburtstag",
                        value=f"In **{days_until_birthday}** Tagen", inline=False)
        self.logger.info(
            f"User {inter.user.name} (ID: {inter.user.id}) has set their birthday to {birthday_date}.")

        await inter.edit_original_response(embed=embed)

    @exception_handler
    async def _set_setting(self, inter: disnake.ApplicationCommandInteraction, key: str, value: str):
        """Ändert einen Wert in der settings.env Datei."""
        await inter.response.defer()
        if key not in self.settings_keys:
            await inter.response.send_message(f"Ungültiger Schlüssel: {key}", ephemeral=True)
            return

        await inter.response.send_message(f"Der Wert für {key} wurde auf {value} gesetzt.", ephemeral=True)
        if key == "FACTOR" or key == "MESSAGE_WORTH_PER_VOICEMIN":
            load_dotenv(dotenv_path="envs/settings.env", override=True)
            self.factor = int(value)  # Faktor als Prozentwert
            self.message_worth_per_voicemin = float(
                os.getenv("MESSAGE_WORTH_PER_VOICEMIN"))
            if key == "FACTOR":
                set_key("envs/settings.env", "FACTOR", str(value))
            if key == "MESSAGE_WORTH_PER_VOICEMIN":
                set_key("envs/settings.env",
                        "MESSAGE_WORTH_PER_VOICEMIN", str(value))

            # Aktualisiere die EXPERIENCE Tabelle
            cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT USERID FROM EXPERIENCE")
            experience_data = await cursor.fetchall()
            for user_id in experience_data:
                user_id = user_id[0]
                cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT SUM(MESSAGE) FROM MESSAGE_XP WHERE USERID = ?", (user_id,))
                total_message_xp = (await cursor.fetchone())[0] or 0
                cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT SUM(VOICE) FROM VOICE_XP WHERE USERID = ?", (user_id,))
                total_voice_xp = (await cursor.fetchone())[0] or 0

                new_message_xp = total_message_xp * self.factor
                new_voice_xp = total_voice_xp * self.message_worth_per_voicemin * self.factor
                cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "UPDATE EXPERIENCE SET MESSAGE = ?, VOICE = ? WHERE USERID = ?", (new_message_xp, new_voice_xp, user_id))

            inter.channel.send(
                f"Der Faktor wurde auf {value}% gesetzt und die EXPERIENCE Tabelle wurde aktualisiert.")
        elif key == "INVITEXP_FACTOR":
            set_key("envs/settings.env", "INVITEXP_FACTOR", str(value))
            self.factor = value
            if self.level_cog:
                await self.level_cog.recalculate_experience(inter)
                await inter.edit_original_response(content=f"INVITEXP Faktor wurde auf {value} gesetzt und die Werte wurden neu berechnet.")
        else:
            set_key("envs/settings.env", key, value)

    @exception_handler
    async def _send_message(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel, message: str):
        """Sendet eine Nachricht in einen angegebenen Kanal."""
        await inter.response.defer(ephemeral=True)

        try:
            await channel.send(message)
            await inter.edit_original_response(content=f"Nachricht erfolgreich in {channel.mention} gesendet.")
        except disnake.Forbidden:
            await inter.edit_original_response(content=f"Ich habe keine Berechtigung, Nachrichten in {channel.mention} zu senden.")
        except Exception as e:
            await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")

    @exception_handler
    async def _send_unofficalwarn_message(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, reason: str):
        """Sendet eine ephemere Nachricht an einen anderen Benutzer und benachrichtigt einen bestimmten Kanal."""
        await inter.response.defer(ephemeral=True)
        # Ersetze dies durch die tatsächliche ID deines Benachrichtigungskanals
        notification_channel_id = 1090588808216596490

        # Nachricht an den Benutzer senden
        user_embed = disnake.Embed(
            title="Hinweis auf Fehlverhalten",
            description="Dies ist ein Hinweis auf ein Fehlverhalten. Diese Nachricht ist noch keine offizielle Warnung.",
            color=disnake.Color.orange()
        )
        user_embed.set_author(name=self.bot.user.name,
                              icon_url=self.bot.user.avatar.url)
        user_embed.add_field(name="Grund", value=reason, inline=False)
        user_embed.set_footer(
            text="Bitte achte in Zukunft auf dein Verhalten.")

        try:
            await user.send(embed=user_embed)
            await inter.edit_original_response(content=f"Nachricht erfolgreich an {user.mention} gesendet.")
        except disnake.Forbidden:
            await inter.edit_original_response(content=f"Ich kann {user.mention} keine Nachricht senden.")
            return
        except Exception as e:
            await inter.edit_original_response(content=f"Ein Fehler ist aufgetreten: {e}")
            return

        # Benachrichtigung in den Kanal senden
        notification_channel = self.bot.get_channel(notification_channel_id)
        if notification_channel:
            notification_embed = disnake.Embed(
                title="Hinweis auf Fehlverhalten gesendet",
                description=f"Ein Hinweis auf Fehlverhalten wurde an {user.mention} gesendet.",
                color=disnake.Color.blue()
            )
            notification_embed.add_field(
                name="Grund", value=reason, inline=False)
            notification_embed.add_field(
                name="Gesendet von", value=inter.user.mention, inline=False)
            await notification_channel.send(embed=notification_embed)

    @exception_handler
    async def _add_second_account(self, inter: ApplicationCommandInteraction, second_user: User, main_user: User):
        """Fügt einem Benutzer die Zweitaccount-Rolle hinzu und aktualisiert die Datenbank."""
        await inter.response.defer(ephemeral=True)

        # IDs der Rollen
        # Ersetze dies durch die tatsächliche ID der Zweitaccount-Rolle
        second_account_role_id = 1329202926916472902

        # Finde die Mitglieder
        second_member = inter.guild.get_member(second_user.id)
        main_member = inter.guild.get_member(main_user.id)

        if not second_member or not main_member:
            await inter.edit_original_response(content="Einer der Benutzer konnte nicht gefunden werden.")
            return

        # Füge die Zweitaccount-Rolle hinzu
        second_account_role = inter.guild.get_role(second_account_role_id)
        await second_member.add_roles(second_account_role)

        # Aktualisiere die Datenbank

        userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=second_user.id)
        # Setze SECONDACC_USERID im Hauptaccount
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "UPDATE USER SET SECONDACC_USERID = ? WHERE DISCORDID = ?", (userrecord['ID'], main_user.id))

        # Setze XP und Level des Zweitaccounts auf 0 und 1
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "UPDATE EXPERIENCE SET MESSAGE = 0, VOICE = 0, LEVEL = 1, INVITE = 0 WHERE USERID = (SELECT ID FROM USER WHERE DISCORDID = ?)", (second_user.id,))

        # Entferne alle Levelrollen vom Zweitaccount
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT ROLE_ID FROM LEVELXP")
        level_roles_ids = [row[0] for row in cursor.fetchall()]
        level_roles = [
            role for role in second_member.roles if role.id in level_roles_ids]
        for role in level_roles:
            await second_member.remove_roles(role)

        await inter.edit_original_response(content=f"Zweitaccount-Rolle wurde {second_user.mention} hinzugefügt und Datenbank aktualisiert.")        

def setupTmp(bot: commands.Bot, rolemanager: RoleManager):
    bot.add_cog(Tmp(bot, rolemanager))
