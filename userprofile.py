import disnake
from disnake import ButtonStyle, Embed, Button
from disnake.ext import commands
from disnake.ui import View
from typing import Dict
import datetime
import sqlite3
import logging
import os
from typing import Union
import emoji
from rolehierarchy import rolehierarchy
from disnake.ui import Button, View
from globalfile import Globalfile
from exceptionhandler import exception_handler
import rolehierarchy
from rolehierarchy import rolehierarchy
from rolemanager import RoleManager
from dbconnection import DatabaseConnectionManager
from datetime import datetime, timedelta
from dotenv import load_dotenv
import asyncio

class UserProfile(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager: RoleManager):
        self.bot = bot
        self.logger = logging.getLogger("UserProfile")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.globalfile : Globalfile = self.bot.get_cog('Globalfile')
        self.role_hierarchy = rolehierarchy()
        self.team_roles = []
        self.rolemanager = rolemanager

        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    @commands.Cog.listener()
    async def on_ready(self):
        load_dotenv(dotenv_path="envs/settings.env",override=True)
        self.team_role = self.rolemanager.get_role(self.bot.guilds[0].id, int(os.getenv("TEAM_ROLE")))
        self.logger.info("UserProfile cog ready.")

    @exception_handler
    async def _me(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt dein eigenes Profil an, einschließlich Notizen und Warnungen."""
        await inter.response.defer(ephemeral=True)

        userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)

        # Hole die Benutzerinformationen aus der Tabelle User
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT * FROM USER WHERE ID = ?", (userrecord['ID'],))
        user_info = (await cursor.fetchone())

        if not user_info:
            await inter.edit_original_response(content=f"Keine Informationen für Benutzer {inter.user.mention} gefunden.")
            return

        # Hole alle Notizen des Benutzers aus der Tabelle Note
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT * FROM NOTE WHERE USERID = ? AND REMOVED <> 1", (userrecord['ID'],))
        notes = await cursor.fetchall()
        # Hole alle Warnungen des Benutzers aus der Tabelle Warn
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT * FROM WARN WHERE USERID = ? AND REMOVED <> 1", (userrecord['ID'],))
        warns = await cursor.fetchall()
        # Hole die Anzahl der geschriebenen Nachrichten
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT COUNT(*) FROM MESSAGE WHERE USERID = ?", (userrecord['ID'],))
        message_count = ((await cursor.fetchone()))[0]

        # Hole die Minuten der bisherigen Voice-Aktivität
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT SUM(VOICE) FROM VOICE_XP WHERE USERID = ?", (userrecord['ID'],))
        voice_minutes = (await cursor.fetchone())[0] or 0

        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT SUM(COUNT) FROM INVITE_XP WHERE USERID = ?", (userrecord['ID'],))
        invites = (await cursor.fetchone())[0] or 0

        # Hole die XP und das Level des Benutzers
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT (MESSAGE + VOICE + INVITE + BONUS) AS TOTAL_XP, LEVEL, MESSAGE, VOICE, INVITE, BONUS FROM EXPERIENCE WHERE USERID = ?", (userrecord['ID'],))
        xp_info = (await cursor.fetchone())
        total_xp = xp_info[0]
        current_level = xp_info[1]
        message_xp = xp_info[2]
        voice_xp = xp_info[3]
        invite_xp = xp_info[4]
        bonus_xp = xp_info[5]

        # Berechne die XP für das nächste Level
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT XP FROM LEVELXP WHERE LEVELNAME = ?", (current_level,))
        current_level_xp = (await cursor.fetchone())
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT XP FROM LEVELXP WHERE LEVELNAME = ?", (current_level+1,))
        next_level_xp = (await cursor.fetchone())

        if current_level_xp and next_level_xp:
            current_level_xp_value = int(current_level_xp[0])
            next_level_xp_value = int(next_level_xp[0])
            xp_to_next_level = next_level_xp_value - total_xp
            value1 = (total_xp - current_level_xp_value)
            value2 = (next_level_xp_value - current_level_xp_value)
            xp_percentage = (value1 / value2) * 100
        else:
            xp_to_next_level = 0
            xp_percentage = 100

        # Erstelle ein Embed
        embed = disnake.Embed(
            title=f"Profil von {inter.user.name}", color=disnake.Color.blue())
        embed.set_author(name=self.bot.user.name,
                         icon_url=inter.guild.icon.url)
        embed.set_thumbnail(
            url=inter.user.avatar.url if inter.user.avatar else inter.user.default_avatar.url)

        # Füge Benutzerinformationen hinzu
        current_time = (await self.globalfile.get_current_time()).strftime('%H:%M:%S')
        embed.set_footer(
            text=f"ID: {user_info[1]} | {user_info[0]} - heute um {current_time} Uhr")

        # Füge Nachrichtenzähler und Voice-Aktivität hinzu
        embed.add_field(name="✍️ **Nachrichten**",
                        value=f"{message_count} Nachrichten", inline=False)
        embed.add_field(name="🎙️ **Voice-Aktivität**",
                        value=f"{int(voice_minutes//2)} Minuten", inline=False)
        embed.add_field(name="📩 **Einladungen**",
                        value=f"{invites} Einladungen", inline=False)

        # Füge XP und Level hinzu
        embed.add_field(name="✨ **Level**", value=(
                        f"Aktuelle Level: {current_level}\n"
                        f"XP: {int(total_xp//10)} XP\n"
                        f"XP bis zum nächsten Level: {int(xp_to_next_level//10)} XP ({xp_percentage:.2f}%)"
                        ), inline=False)

        # Füge detaillierte XP-Informationen hinzu
        embed.add_field(name="📊 **XP Details**", value=(
                        f"Nachrichten XP: {int(message_xp//10)} XP\n"
                        f"Voice XP: {int(voice_xp//10)} XP\n"
                        f"Invite XP: {int(invite_xp//10)} XP\n"
                        f"Bonus XP: {int(bonus_xp//10)} XP"
                        ), inline=False)

        # Füge Geburtsdatum hinzu, falls vorhanden
        if user_info[6]:
            embed.add_field(name="🎂 **Geburtstag**",
                            value=user_info[6], inline=False)

        warn_level = user_info[3]
        warnlevel_adjusted = user_info[8]

        # Berechne das Datum, wann das nächste Warnlevel entfernt wird
        if warnlevel_adjusted:
            last_warn_date = datetime.strptime(
                warnlevel_adjusted, '%Y-%m-%d %H:%M:%S')
        else:
            # Hole das Datum des letzten Warns
            cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT MAX(INSERT_DATE) FROM WARN WHERE USERID = ? AND REMOVED <> 1", (userrecord['ID'],))
            last_warn_date = (await cursor.fetchone())[0]
            if last_warn_date:
                last_warn_date = datetime.strptime(
                    last_warn_date, '%Y-%m-%d %H:%M:%S')
            else:
                last_warn_date = None

        if last_warn_date:
            next_warnlevel_removal = last_warn_date + \
                timedelta(days=4*30)  # 4 months later
            next_warnlevel_removal_str = next_warnlevel_removal.strftime(
                '%Y-%m-%d %H:%M:%S')
        else:
            next_warnlevel_removal_str = "N/A"

        embed.add_field(name="⚠️ **Warnlevel**",
                        value=f"Aktuelles Warnlevel: {warn_level}\nNächstes Warnlevel-Entfernung: {next_warnlevel_removal_str}", inline=False)
        # Füge Notizen hinzu
        if notes:
            for note in notes:
                caseid = note[0]
                reason = note[2]
                image_path = note[3]
                # Annahme: Das Erstellungsdatum ist das fünfte Element im Tupel
                created_at = note[4]
                note_text = f"Grund: {reason}\nErstellt am: {created_at}"
                if image_path:
                    note_text += f"\nBildpfad: {image_path}"
                embed.add_field(
                    name=f"Note [ID: {caseid}]", value=note_text, inline=False)
                if image_path and os.path.exists(image_path):
                    embed.set_image(file=disnake.File(image_path))
        else:
            embed.add_field(
                name="Notizen", value="Keine Notizen vorhanden.", inline=False)

        if warns:
            for warn in warns:
                caseid = warn[0]
                reason = warn[2]
                level = warn[4]
                created_at = warn[5]
                image_path = warn[3]
                warn_text = f"Grund: {reason}\nLevel: {level}\nErstellt am: {created_at}"
                if image_path:
                    note_text += f"\nBildpfad: {image_path}"
                embed.add_field(
                    name=f"Warnung [ID: {caseid}]", value=warn_text, inline=False)
                if image_path and os.path.exists(image_path):
                    embed.set_image(file=disnake.File(image_path))
        else:
            embed.add_field(name="Warnungen",
                            value="Keine Warnungen vorhanden.", inline=False)

        self.logger.info(f"User profile for {inter.user.name} requested by {inter.user.name}")
        await inter.edit_original_response(embed=embed)

    @exception_handler
    async def _user_profile(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        """Zeigt das Profil eines Benutzers an, einschließlich Notizen, Warnungen und Bans."""
        await inter.response.defer(ephemeral=True)

        userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=user.id)

        # Hole die Benutzerinformationen aus der Tabelle User
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT * FROM USER WHERE ID = ?", (userrecord['ID'],))
        user_info = (await cursor.fetchone())

        if not user_info:
            await inter.edit_original_response(content=f"Keine Informationen für Benutzer {user.mention} gefunden.")
            return

        # Hole die Privatsphäre-Einstellungen des Benutzers
        privacy_settings = await self.globalfile.get_user_privacy_settings(user.id, inter.guild)

        # Überprüfe, ob der anfragende Benutzer mit dem Zielbenutzer befreundet ist
        other_user_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=user.id)

        is_friend = await self.globalfile.are_user_friends(userrecord['ID'], other_user_record['ID'], inter.guild)
        is_blocked = await self.globalfile.is_user_blocked(userrecord['ID'], other_user_record['ID'], inter.guild)

        def can_view(setting: str) -> bool:
            # Überprüfen, ob der Benutzer die Teamrolle hat
            if self.team_role in inter.user.roles:
                return True

            return (
                privacy_settings.get(setting, 'nobody') == 'everyone' or
                (privacy_settings.get(setting, 'nobody') == 'friends' and is_friend) or
                (privacy_settings.get(setting, 'nobody') == 'blocked' and not is_blocked)
            )

        # Hole alle Notizen des Benutzers aus der Tabelle Note
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT * FROM NOTE WHERE USERID = ? AND REMOVED <> 1", (userrecord['ID'],))
        notes = await cursor.fetchall()
        # Hole alle Warnungen des Benutzers aus der Tabelle Warn
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT * FROM WARN WHERE USERID = ? AND REMOVED <> 1", (userrecord['ID'],))
        warns = await cursor.fetchall()
        # Hole alle Bans des Benutzers aus der Tabelle Ban
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT * FROM BAN WHERE USERID = ?", (userrecord['ID'],))
        bans = await cursor.fetchall()
        # Hole die Anzahl der geschriebenen Nachrichten
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT COUNT(*) FROM MESSAGE WHERE USERID = ?", (userrecord['ID'],))
        message_count = (await cursor.fetchone())[0]

        # Hole die Minuten der bisherigen Voice-Aktivität
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT SUM(VOICE) FROM VOICE_XP WHERE USERID = ?", (userrecord['ID'],))
        voice_minutes = (await cursor.fetchone())[0] or 0

        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT SUM(COUNT) FROM INVITE_XP WHERE USERID = ?", (userrecord['ID'],))
        invites = (await cursor.fetchone())[0] or 0

        # Hole die XP und das Level des Benutzers
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT (MESSAGE + VOICE + INVITE + BONUS) AS TOTAL_XP, LEVEL, MESSAGE, VOICE, INVITE, BONUS FROM EXPERIENCE WHERE USERID = ?", (userrecord['ID'],))
        xp_info = (await cursor.fetchone())
        total_xp = xp_info[0]
        current_level = xp_info[1]
        message_xp = xp_info[2]
        voice_xp = xp_info[3]
        invite_xp = xp_info[4]
        bonus_xp = xp_info[5]

        # Berechne die XP für das nächste Level
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT XP FROM LEVELXP WHERE LEVELNAME = ?", (current_level,))
        current_level_xp = (await cursor.fetchone())
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT XP FROM LEVELXP WHERE LEVELNAME = ?", (current_level+1,))
        next_level_xp = (await cursor.fetchone())

        if current_level_xp and next_level_xp:
            xp_to_next_level = int(next_level_xp[0]) - total_xp
            xp_percentage = (total_xp - int(current_level_xp[0])) / (
                int(next_level_xp[0]) - int(current_level_xp[0])) * 100
        else:
            xp_to_next_level = 0
            xp_percentage = 100

        # Erstelle ein Embed
        embed = disnake.Embed(
            title=f"Profil von {user.name}", color=disnake.Color.blue())
        embed.set_author(name=self.bot.user.name,
                        icon_url=inter.guild.icon.url)
        embed.set_thumbnail(
            url=user.avatar.url if inter.user.avatar else inter.user.default_avatar.url)

        # Füge Benutzerinformationen hinzu
        current_time = (await self.globalfile.get_current_time()).strftime('%H:%M:%S')
        embed.set_footer(
            text=f"ID: {user_info[1]} | {user_info[0]} - heute um {current_time} Uhr")

        # Füge Nachrichtenzähler und Voice-Aktivität hinzu
        embed.add_field(name="📨 **Nachrichten**",
                        value=f"{message_count} Nachrichten", inline=False)
        embed.add_field(name="🎙️ **Voice-Aktivität**",
                        value=f"{int(voice_minutes//2)} Minuten", inline=False)
        embed.add_field(name="📩 **Einladungen**",
                        value=f"{invites} Einladungen", inline=False)

        # Füge XP und Level hinzu, wenn die Einstellung es erlaubt
        if can_view('xp'):
            embed.add_field(name="✨ **Level**", value=(
                            f"Aktuelle Level: {current_level}\n"
                            f"XP: {int(total_xp//10)} XP\n"
                            f"XP bis zum nächsten Level: {int(xp_to_next_level//10)} XP ({xp_percentage:.2f}%)"
                            ), inline=False)
            embed.add_field(name="📊 **XP Details**", value=(
                            f"Nachrichten XP: {int(message_xp//10)} XP\n"
                            f"Voice XP: {int(voice_xp//10)} XP\n"
                            f"Invite XP: {int(invite_xp//10)} XP\n"
                            f"Bonus XP: {int(bonus_xp//10)} XP"
                            ), inline=False)

        # Füge Geburtsdatum hinzu, falls vorhanden und die Einstellung es erlaubt
        if user_info[6] and can_view('birthday'):
            embed.add_field(name="🎂 **Geburtstag**",
                            value=user_info[6], inline=False)

        warn_level = user_info[3]
        warnlevel_adjusted = user_info[8]

        # Berechne das Datum, wann das nächste Warnlevel entfernt wird
        if warnlevel_adjusted:
            last_warn_date = datetime.strptime(
                warnlevel_adjusted, '%Y-%m-%d %H:%M:%S')
        else:
            # Hole das Datum des letzten Warns
            cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT MAX(INSERT_DATE) FROM WARN WHERE USERID = ? AND REMOVED <> 1", (userrecord['ID'],))
            last_warn_date = (await cursor.fetchone())[0]
            if last_warn_date:
                last_warn_date = datetime.strptime(
                    last_warn_date, '%Y-%m-%d %H:%M:%S')
            else:
                last_warn_date = None

        if last_warn_date:
            next_warnlevel_removal = last_warn_date + \
                timedelta(days=4*30)  # 4 months later
            next_warnlevel_removal_str = next_warnlevel_removal.strftime(
                '%Y-%m-%d %H:%M:%S')
        else:
            next_warnlevel_removal_str = "N/A"

        # Füge Warnlevel hinzu, wenn die Einstellung es erlaubt
        if can_view('warnings'):
            embed.add_field(name="⚠️ **Warnlevel**",
                            value=f"Aktuelles Warnlevel: {warn_level}\nNächstes Warnlevel-Entfernung: {next_warnlevel_removal_str}", inline=False)
        else:
            embed.add_field(name="⚠️ **Warnlevel**",
                            value="Keinen Zugriff", inline=False)

        # Füge Notizen hinzu, wenn die Einstellung es erlaubt
        if can_view('notes'):
            if notes:
                for note in notes:
                    caseid = note[0]
                    reason = note[2]
                    image_path = note[3]
                    # Annahme: Das Erstellungsdatum ist das fünfte Element im Tupel
                    created_at = note[4]
                    note_text = f"Grund: {reason}\nErstellt am: {created_at}"
                    if image_path:
                        note_text += f"\nBildpfad: {image_path}"
                    embed.add_field(
                        name=f"Note [ID: {caseid}]", value=note_text, inline=False)
                    if image_path and os.path.exists(image_path):
                        embed.set_image(file=disnake.File(image_path))
            else:
                embed.add_field(
                    name="Notizen", value="Keine Notizen vorhanden.", inline=False)
        else:
            embed.add_field(
                name="Notizen", value="Keinen Zugriff", inline=False)
        
        if can_view('warnings'):
            if warns:
                for warn in warns:
                    caseid = warn[0]
                    reason = warn[2]
                    level = warn[4]
                    created_at = warn[5]
                    image_path = warn[3]
                    warn_text = f"Grund: {reason}\nLevel: {level}\nErstellt am: {created_at}"
                    if image_path:
                        note_text += f"\nBildpfad: {image_path}"
                    embed.add_field(
                        name=f"Warnung [ID: {caseid}]", value=warn_text, inline=False)
                    if image_path and os.path.exists(image_path):
                        embed.set_image(file=disnake.File(image_path))
            else:
                embed.add_field(name="Warnungen",
                                value="Keine Warnungen vorhanden.", inline=False)
        else:
            embed.add_field(name="Warnungen",
                            value="Keinen Zugriff", inline=False)

        await inter.edit_original_response(embed=embed)
        self.logger.info(f"User profile for {user.name} requested by {inter.user.name}")

    async def _privacy_settings(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt die Privatsphäre-Einstellungen an und erlaubt Änderungen."""
        user_id = inter.user.id
        settings = await self.globalfile.get_user_privacy_settings(user_id, inter.guild)

        embed = Embed(
            title="Privatsphäre-Einstellungen",
            description=(
                "Wähle aus, wer die folgenden Informationen sehen darf:\n\n"
                "🔵 **Niemand**\n"
                "🟢 **Nur Freunde**\n"
                f"{await self.globalfile.get_emoji_by_name("Gray", guild=inter.guild)} **Jeder auf dem Server**\n"
                "🔴 **Jeder außer geblockte User (per /block)**"
            ),
            color=disnake.Color.blue()
        )

        view = View(timeout=None)
        for key, value in settings.items():
            button = Button(
                label=key.replace("_", " ").title(),
                style=self.get_button_style(value),
                custom_id=f"privacy_{key}"
            )
            view.add_item(button)

        self.logger.info(f"Privacy settings requested by {inter.user.name}")
        await inter.response.send_message(embed=embed, view=view, ephemeral=True)

    def get_button_style(self, value: str) -> ButtonStyle:
        if value == "nobody":
            return ButtonStyle.blurple
        elif value == "friends":
            return ButtonStyle.green
        elif value == "everyone":
            return ButtonStyle.grey  # Changed from yellow to blurple
        elif value == "blocked":
            return ButtonStyle.red

    @commands.Cog.listener()
    async def on_button_click(self, interaction: disnake.MessageInteraction):
        custom_id = interaction.component.custom_id
        if custom_id.startswith("privacy_"):
            key = custom_id.split("_")[1]
            user_id = interaction.user.id
            settings = await self.globalfile.get_user_privacy_settings(user_id, interaction.guild)

            current_value = settings[key]
            new_value = self.get_next_privacy_setting(current_value)
            settings[key] = new_value
            await self.save_user_privacy_setting(user_id, key, new_value, interaction.guild)

            await interaction.response.edit_message(view=self.create_privacy_view(settings))

    def get_next_privacy_setting(self, current_value: str) -> str:
        options = ["nobody", "friends", "everyone", "blocked"]
        current_index = options.index(current_value)
        return options[(current_index + 1) % len(options)]

    def create_privacy_view(self, settings: Dict[str, str]) -> View:
        view = View(timeout=None)
        for key, value in settings.items():
            button = Button(
                label=key.replace("_", " ").title(),
                style=self.get_button_style(value),
                custom_id=f"privacy_{key}"
            )
            view.add_item(button)
        return view
    
    async def save_user_privacy_setting(self, user_id: int, setting: str, value: str, guild: disnake.Guild):
        try:
            user_record = await self.globalfile.get_user_record(guild=guild, discordid=user_id)
            await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, """
                INSERT INTO USER_SETTINGS (USERID, SETTING, VALUE)
                VALUES (?, ?, ?)
                ON CONFLICT(USERID, SETTING) DO UPDATE SET VALUE = excluded.VALUE
            """, (user_record['ID'], setting, value))
            self.logger.info(f"Updated privacy setting for user {user_id}: {setting} = {value}")
        except Exception as e:
            self.logger.error(f"Failed to update privacy setting for user {user_id}: {setting} = {value}. Error: {e}")

    async def _block(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
        blockedrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=user.id)
        await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, """INSERT INTO BLOCK (USERID, BLOCKEDID) VALUES (?, ?)""", (userrecord['ID'], blockedrecord['ID']))
        await inter.response.send_message(f"{user.mention} wurde blockiert.", ephemeral=True)
        self.logger.info(f"User {inter.user.name} blocked {user.name}")

    async def _unblock(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
        blockedrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=user.id)
        await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, """DELETE FROM BLOCK WHERE USERID = ? AND BLOCKEDID = ?""", (userrecord['ID'], blockedrecord['ID']))
        await inter.response.send_message(f"{user.mention} wurde entblockiert.", ephemeral=True)
        self.logger.info(f"User {inter.user.name} unblocked {user.name}")

    async def _blocklist(self, inter: disnake.ApplicationCommandInteraction):
        userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, """SELECT BLOCKEDID FROM BLOCK WHERE USERID = ?""", (userrecord['ID'],))
        blocked_users = await cursor.fetchall()
        
        if not blocked_users:
            await inter.response.send_message("Keine blockierten Benutzer.", ephemeral=True)
            return
        
        blocked_mentions = [f"<@{(await self.globalfile.get_user_record(guild=inter.guild, user_id=row[0]))['DISCORDID']}>" for row in blocked_users]

        await inter.response.send_message("\n".join(blocked_mentions), ephemeral=True)
        self.logger.info(f"Blocklist requested by {inter.user.name}")

    @exception_handler
    async def _set_introduction(self, inter: disnake.ApplicationCommandInteraction):
        """Setzt die Beschreibung des Benutzers."""
        userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
        
        await inter.response.send_message("Bitte sende deine Vorstellung innerhalb der nächsten 3 Minuten.", ephemeral=True)

        def check(m):
            return m.author == inter.user and m.channel == inter.channel

        try:
            msg = await self.bot.wait_for('message', timeout=180.0, check=check)
        except asyncio.TimeoutError:
            await inter.followup.send("Zeit abgelaufen. Bitte versuche es erneut.", ephemeral=True)
            return

        introduction = await self.globalfile.get_emoji_string_by_name(msg.content)
        
        await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, """
            UPDATE USER SET INTRODUCTION = ? WHERE ID = ?
        """, (introduction, userrecord['ID']))
        
        await msg.delete()
        await inter.followup.send("Deine Beschreibung wurde erfolgreich aktualisiert und die Nachricht wurde gelöscht.", ephemeral=True)
        self.logger.info(f"User {inter.user.name} updated their introduction.")

    @exception_handler
    async def _get_introduction(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        """Ruft die Beschreibung eines Benutzers ab, wenn die Berechtigungen es erlauben."""
        userrecord = await self.globalfile.get_user_record(guild=inter.guild, discordid=user.id)
        privacy_settings = await self.globalfile.get_user_privacy_settings(user.id, inter.guild)
        
        # Überprüfe, ob der anfragende Benutzer mit dem Zielbenutzer befreundet ist
        other_user_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
        is_friend = await self.globalfile.are_user_friends(userrecord['ID'], other_user_record['ID'], inter.guild)
        is_blocked = await self.globalfile.is_user_blocked(userrecord['ID'], other_user_record['ID'], inter.guild)

        def can_view(setting: str) -> bool:
            # Überprüfen, ob der Benutzer die Teamrolle hat
            if self.team_role in inter.user.roles:
                return True

            return (
                privacy_settings.get(setting, 'nobody') == 'everyone' or
                (privacy_settings.get(setting, 'nobody') == 'friends' and is_friend) or
                (privacy_settings.get(setting, 'nobody') == 'blocked' and not is_blocked)
            )

        if not can_view('introduction'):
            await inter.response.send_message("Du hast keine Berechtigung, die Beschreibung dieses Benutzers zu sehen.", ephemeral=True)
            return

        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT INTRODUCTION FROM USER WHERE ID = ?", (userrecord['ID'],))
        introduction = (await cursor.fetchone())[0]

        if not introduction:
            await inter.response.send_message("Dieser Benutzer hat keine Beschreibung hinterlegt.", ephemeral=True)
            return

        # Ersetze Emojis in der Introduction
        async def replace_emojis(text: str, guild: disnake.Guild) -> str:
            import re
            emoji_pattern = re.compile(r':(\w+):|<:(\w+):(\d+)>')
            matches = emoji_pattern.findall(text)
            for match in matches:
                if match[0]:
                    emoji_name = match[0]
                    emoji = await self.globalfile.get_emoji_by_name(emoji_name, guild)
                    if not emoji:
                        emoji = await self.globalfile.get_manual_emoji(emoji_name)
                    if emoji:
                        text = text.replace(f':{emoji_name}:', str(emoji))
                elif match[1] and match[2]:
                    emoji_name = match[1]
                    emoji_id = match[2]
                    emoji = await self.globalfile.get_emoji_by_name(emoji_name, guild)
                    if not emoji:
                        emoji = await self.globalfile.get_manual_emoji(emoji_name)
                    if emoji:
                        text = text.replace(f'<:{emoji_name}:{emoji_id}>', str(emoji))
            return text

        introduction = await replace_emojis(introduction, inter.guild)

        await inter.response.send_message(f"Beschreibung von {user.mention}:\n{introduction}", ephemeral=True)
        self.logger.info(f"User {inter.user.name} requested the introduction of {user.name}.")
    

def setupProfile(bot: commands.Bot, rolemanager: RoleManager):
    bot.add_cog(UserProfile(bot, rolemanager))        