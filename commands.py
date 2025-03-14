import disnake
import re
from disnake.ext import commands, tasks
from disnake.ui import Button, View
from disnake import ApplicationCommandInteraction, User, Member, Role
from disnake import ApplicationCommandPermissions, ApplicationCommandPermissionType
import disnake.file
import re
from globalfile import Globalfile
from rolehierarchy import rolehierarchy
from dotenv import load_dotenv
import logging
import sqlite3
from dbconnection import DatabaseConnectionManager
import os
from dotenv import load_dotenv, set_key
from tmp import Tmp
from cupid import Cupid
from join import Join
from level import Level
from moderation import Moderation
from ticket import Ticket
from roleassignment import RoleAssignment
from voice import Voice
from giveaway import Giveaway
from typing import Optional
from rolemanager import RoleManager
from friend import Friend
from userprofile import UserProfile

class MyCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager: RoleManager):
        self.bot = bot
        # Logger initialisieren
        self.logger = logging.getLogger("Commands")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.globalfile: Globalfile = self.bot.get_cog('Globalfile')
        load_dotenv(dotenv_path="envs/settings.env")
        self.last_info_message = None
        self.last_info_time = None
        self.level_cog = self.bot.get_cog('Level')
        self.tmp_instance: Tmp = self.bot.get_cog('Tmp')
        self.cupid_instance: Cupid = self.bot.get_cog('Cupid')
        self.join_instance: Join = self.bot.get_cog('Join')
        self.level_instance: Level = self.bot.get_cog('Level')
        self.mod_instance: Moderation = self.bot.get_cog('Moderation')
        self.ticket_instance: Ticket = self.bot.get_cog('Ticket')
        self.friend_instance: Friend = self.bot.get_cog('Friend')
        self.userprofile_instance: UserProfile = self.bot.get_cog('UserProfile')
        self.roleassignment_instance: RoleAssignment = self.bot.get_cog(
            'RoleAssignment')
        self.voice_instance: Voice = self.bot.get_cog('Voice')
        self.giveaway_instance: Giveaway = self.bot.get_cog('Giveaway')
        self.rolemanager: RoleManager = rolemanager
        self.settings_keys = self.load_settings_keys_with_captions()

        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        load_dotenv(dotenv_path="envs/settings.env")
        settings_keys = [key for key in os.environ.keys()]
        self.settings_keys = settings_keys
                
    def cog_unload(self):
        Globalfile.unban_task.cancel()

    async def load_settings_keys_with_captions(self):
        settings_keys = {}
        with open("envs/settings.env") as f:
            for line in f:
                match = re.match(r"^(\w+)\s*=\s*.*?#\s*(.*)$", line)
                if match:
                    key, caption = match.groups()
                    settings_keys[key] = caption
                else:
                    match = re.match(r"^(\w+)\s*=", line)
                    if match:
                        key = match.group(1)
                        settings_keys[key] = key
        return settings_keys

    @commands.Cog.listener()
    async def on_ready(self):
        self.settings_keys = await self.load_settings_keys_with_captions()
        self.logger.info("Commands Cog is ready.")

    @commands.slash_command(guild_ids=[854698446996766730])
    async def info(self, inter: disnake.ApplicationCommandInteraction):
        """Get technical information about the bot and server."""
        await self.tmp_instance._info(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def server(self, inter: disnake.ApplicationCommandInteraction):
        """Get information about the server."""
        await self.tmp_instance._server(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def user(self, inter: disnake.ApplicationCommandInteraction):
        await self.tmp_instance._user(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    async def list_banned_users(self, inter: disnake.ApplicationCommandInteraction):
        """Listet alle gebannten Benutzer auf und zeigt den Entbannzeitpunkt an, falls vorhanden."""
        await self.tmp_instance._list_banned_users(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Moderator")
    async def blacklist_add(self, inter: disnake.ApplicationCommandInteraction, word: str = commands.Param(name="wort", description="Das Wort, das zur Blacklist hinzugefügt werden soll")):
        """Füge ein Wort zur Blacklist-Liste hinzu, wenn es noch nicht existiert."""
        await self.tmp_instance._blacklist_add(inter, word)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Moderator")
    async def blacklist_remove(self, inter: disnake.ApplicationCommandInteraction, word: str):
        """Entferne ein Wort von der Blacklist-Liste."""
        await self.tmp_instance._blacklist_remove(inter, word)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Moderator")
    async def blacklist(self, inter: disnake.ApplicationCommandInteraction):
        """Zeige die aktuelle Blacklist-Liste."""
        await self.tmp_instance._blacklist(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Test-Supporter")
    async def add_user_to_ticket(self, inter: disnake.ApplicationCommandInteraction, ticket_id: int, user: disnake.User):
        """Fügt einen Benutzer zu einem Ticket-Channel hinzu."""
        await self.tmp_instance._add_user_to_ticket(inter, ticket_id, user)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Test-Supporter")
    async def note_add(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, reason: str, proof: disnake.Attachment = None):
        """Erstellt eine Notiz für einen Benutzer."""
        await self.tmp_instance._note_add(inter, user, reason, proof)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Senior Supporter")
    async def note_delete(self, inter: disnake.ApplicationCommandInteraction, caseid: int, reason: str = "Kein Grund angegeben"):
        """Markiert eine Note als gelöscht basierend auf der Note ID."""
        await self.tmp_instance._note_delete(inter, caseid, reason)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Test-Supporter")
    async def user_profile(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User = None, username: str = None, discordid: int = None):
        """Zeigt das Profil eines Benutzers an, einschließlich Notizen, Warnungen und Bans."""
        if user is None:
            if username is None:
                if discordid is None:
                    self.logger.info("No user, username or discordid provided.")
                else:
                    await self.userprofile_instance._user_profile(inter, discordid=discordid)
            else:
                await self.userprofile_instance._user_profile(inter, username=username)
        else:
            await self.userprofile_instance._user_profile(inter, user=user)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Co Owner")
    async def disconnect(self, inter: disnake.ApplicationCommandInteraction):
        """Schließt alle Verbindungen des Bots und beendet den Bot-Prozess."""
        await self.tmp_instance._disconnect(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Senior Moderator")
    async def sync_users(self, inter: disnake.ApplicationCommandInteraction):
        """Synchronisiere alle Benutzer des Servers mit der Users Tabelle."""
        await self.tmp_instance._sync_users(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Co Owner")
    async def remove_role_from_all(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        """Entfernt eine bestimmte Rolle bei allen Benutzern in der Gilde."""
        await self.tmp_instance._remove_role_from_all(inter, role)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def unban_all_users(self, inter: disnake.ApplicationCommandInteraction):
        """Entbannt alle gebannten Benutzer in der Gilde."""
        await self.tmp_instance._unban_all_users(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def warn_inactive_users(self, inter: disnake.ApplicationCommandInteraction, days: int, role: disnake.Role, channel: disnake.TextChannel):
        """Warnt alle Benutzer, die innerhalb der angegebenen Tage keine Nachrichten geschrieben haben."""
        await self.tmp_instance._warn_inactive_users(inter, days, role, channel)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Co Owner")
    async def kick_inactive_users(self, inter: disnake.ApplicationCommandInteraction, months: int, execute: bool = False):
        """Kicke alle Benutzer, die innerhalb der angegebenen Monate keine Nachrichten geschrieben haben."""
        await self.tmp_instance._kick_inactive_users(inter, months, execute)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Test-Supporter")
    async def help_moderation(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt alle Moderationsbefehle an."""
        await self.tmp_instance._help_moderation(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Test-Supporter")
    async def help_user(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt alle Benutzerbefehle an."""
        await self.tmp_instance._help_user(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Supporter")
    async def verify_user(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Verifiziert einen Benutzer und gibt ihm die Rolle 'Verified'."""
        await self.tmp_instance._verify_user(inter, member)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Supporter")
    async def add_image(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, image: disnake.Attachment):
        """Fügt ein Bild zu einem Benutzer hinzu."""
        await self.tmp_instance._add_image(inter, user, image)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def set_ai_open(self, inter: disnake.ApplicationCommandInteraction, value: bool):
        """Setzt den Wert von AI_OPEN in der .env Datei auf true oder false."""
        await self.tmp_instance._set_ai_open(inter, value)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def set_birthday(self, inter: disnake.ApplicationCommandInteraction, birthday: str):
        """Setzt den Geburtstag eines Benutzers im Format YYYY-MM-DD."""
        await self.tmp_instance._set_birthday(inter, birthday)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def me(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt dein eigenes Profil an, einschließlich Notizen und Warnungen."""
        await self.userprofile_instance._me(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def set_setting(self, inter: disnake.ApplicationCommandInteraction, key: str, value: str):
        """Ändert einen Wert in der settings.env Datei."""
        set_key("envs/settings.env", key, value)        
        await inter.response.send_message(f"Der Wert für `{key}` wurde auf `{value}` gesetzt.")

    @set_setting.autocomplete("key")
    async def set_setting_autocomplete(self, inter: disnake.ApplicationCommandInteraction, key: str):
        return [f"{k} ({v})" for k, v in self.settings_keys.items() if k.startswith(key)]

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Supporter")
    async def send_message(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel, message: str):
        """Sendet eine Nachricht in einen angegebenen Kanal."""
        await self.tmp_instance._send_message(inter, channel, message)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Supporter")
    async def send_unofficalwarn_message(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, reason: str):
        """Sendet eine ephemere Nachricht an einen anderen Benutzer und benachrichtigt einen bestimmten Kanal."""
        await self.tmp_instance._send_unofficalwarn_message(inter, user, reason)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Supporter")
    async def add_second_account(self, inter: ApplicationCommandInteraction, second_user: User, main_user: User):
        """Fügt einem Benutzer die Zweitaccount-Rolle hinzu und aktualisiert die Datenbank."""
        await self.tmp_instance._add_second_account(inter, second_user, main_user)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def dating_info(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt Informationen über das Dating-System an."""
        await self.cupid_instance._dating_info(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def debug_top_matches(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt die Top-Matches für jeden Benutzer an."""
        await self.cupid_instance._debug_top_matches(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def recalculate_invite_xp(self, inter: disnake.ApplicationCommandInteraction):
        """Berechnet die XP für Einladungen neu."""
        await self.cupid_instance._recalculate_invite_xp(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def deletedata_for_nonexistent_user(self, inter: disnake.ApplicationCommandInteraction):
        """Löscht Daten für Benutzer, die nicht mehr existieren."""
        await self.cupid_instance._deletedata_for_nonexistent_user(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def random_anime_gif(self, inter: disnake.ApplicationCommandInteraction):
        """Sendet ein zufälliges Anime-GIF."""
        await self.join_instance._random_anime_gif(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def update_all_users_roles(self, inter: disnake.ApplicationCommandInteraction, send_level_up_messages: bool = False):
        """Aktualisiert die Rollen aller Benutzer basierend auf ihrem Level."""
        await self.level_instance._update_all_users_roles(inter, send_level_up_messages)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def calculate_message_xp(self, inter: disnake.ApplicationCommandInteraction):
        """Berechnet die XP für Nachrichten neu."""
        await self.level_instance._calculate_message_xp(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def recalculate_experience(self, inter: disnake.ApplicationCommandInteraction, send_level_up_messages: bool = False):
        """Berechnet die XP für alle Benutzer neu."""
        await self.level_instance._recalculate_experience(inter, send_level_up_messages)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def update_levels(self, inter: disnake.ApplicationCommandInteraction):
        """Aktualisiert die Level aller Benutzer."""
        await self.level_instance._update_levels(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def top_users(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt die Top Benutzer basierend auf ihrer XP an."""
        await self.level_instance._top_users(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def add_xp_to_levels(self, inter: disnake.ApplicationCommandInteraction, addxp: int):
        """Fügt XP zu allen Benutzern hinzu."""
        await self.level_instance._add_xp_to_levels(inter, addxp)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def add_xp_to_user(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, xp: int, reason: str):
        """Fügt einem Benutzer XP hinzu."""
        await self.level_instance._add_xp_to_user(inter, user, xp, reason)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def add_xp_to_voice_channel(self, inter: disnake.ApplicationCommandInteraction, channel_id: int, xp: int, reason: str):
        """Fügt einem Sprachkanal XP hinzu."""
        await self.level_instance._add_xp_to_voice_channel(inter, channel_id, xp, reason)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Team")
    async def activity_since(self, inter: disnake.ApplicationCommandInteraction, start_date: str, user: disnake.User = None):
        """Zeigt die Aktivität eines Benutzers seit einem bestimmten Datum an."""
        await self.level_instance._activity_since(inter, start_date, user)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Supporter")
    async def timeout(self, inter: disnake.ApplicationCommandInteraction,
                      member: disnake.Member,
                      duration: str = commands.Param(
                          name="dauer", description="Dauer des Timeouts in Sek., Min., Std., Tagen oder Jahre.(Bsp.: 0s0m0h0d0j)"),
                      reason: str = commands.Param(
                          name="begründung", description="Grund für den Timeout", default="Kein Grund angegeben"),
                      warn: bool = commands.Param(
                          name="warn", description="Soll eine Warnung erstellt werden?", default=False),
                      warn_level: int = commands.Param(name="warnstufe", description="Warnstufe (1-3) | Default = 1 wenn warn_level = True", default=1)):
        """Timeout einen Benutzer für eine bestimmte Dauer und optional eine Warnung erstellen."""
        await self.mod_instance._timeout(inter, member, duration, reason, warn, warn_level)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Moderator")
    async def timeout_remove(self, inter: disnake.ApplicationCommandInteraction, timeout_id: int, reason: str = commands.Param(name="begründung", description="Grund für das Entfernen des Timeouts", default="Kein Grund angegeben")):
        """Entfernt einen Timeout basierend auf der Timeout ID."""
        await self.mod_instance._timeout_remove(inter, timeout_id, reason)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Test-Supporter")
    async def warn_add(self, inter: disnake.ApplicationCommandInteraction,
                       user: disnake.User,
                       reason: str = commands.Param(
                           name="begründung", description="Grund für die Warnung", default="Kein Grund angegeben"),
                       level: int = commands.Param(
                           name="warnstufe", description="Warnstufe (1-3) | Default = 1", default=1),
                       proof: disnake.Attachment = commands.Param(
                           name="beweis", description="Ein Bild als Beweis für die Warnung und zur Dokumentation", default=None),
                       show: str = commands.Param(name="anzeigen", description="Soll die Warnung angezeigt werden?", default="True")):
        """Erstellt eine Warnung für einen Benutzer."""
        await self.mod_instance._warn_add(inter, user, reason, level, proof, show)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Moderator")
    async def warn_delete(self, inter: disnake.ApplicationCommandInteraction,
                          caseid: int = commands.Param(name="warn_id", description="ID der Warnung, die gelöscht werden soll"),
                          reason: str = commands.Param(name="begründung", description="Grund für das Löschen der Warnung", default="Kein Grund angegeben")):
        """Markiert eine Warnung als gelöscht basierend auf der Warn ID."""
        await self.mod_instance._warn_delete(inter, caseid, reason)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Supporter")
    async def ban(self,
                  inter: disnake.ApplicationCommandInteraction,
                  member: disnake.Member = commands.Param(
                      name="benutzer", description="Der Benutzer, der gebannt werden soll.", default=None),
                  reason: str = commands.Param(
                      name="begründung", description="Grund warum der Benutzer gebannt werden soll", default="Kein Grund angegeben"),
                  duration: str = commands.Param(
                      name="dauer", description="Dauer des Bans in Sek., Min., Std., Tagen oder Jahre.(Bsp.: 0s0m0h0d0j) Nichts angegeben = Dauerhaft", default="0s"),
                  delete_days: int = commands.Param(
                      name="geloeschte_nachrichten", description="Anzahl der Tage, für die Nachrichten des Benutzers gelöscht werden sollen. (0-7, Default = 0)", default=0),
                  proof: disnake.Attachment = commands.Param(name="beweis", description="Ein Bild als Beweis für den Ban und zur Dokumentation", default=None),
                  username: str = commands.Param(name="username", description="Der Benutzername, falls der Benutzer nicht mehr auf dem Server ist.", default=None),
                  discordid: int = commands.Param(name="discordid", description="Die Discord ID, falls der Benutzer nicht mehr auf dem Server ist.", default=None)
                  ):
        """Banne einen Benutzer und speichere ein Bild als Beweis."""
        await self.mod_instance._ban(inter, member, reason, duration, delete_days, proof, username=username, discordid=discordid)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Senior Supporter")
    async def unban(self, inter: disnake.ApplicationCommandInteraction,
                    userid: int = commands.param(
                        name="userid", description="Hier kannst du die UserID unserer Datenbank angeben.", default=0),
                    username: str = commands.Param(
                        name="username", description="Hier kannst du den Benutzernamen angeben, falls die UserID nicht bekannt ist.", default=""),
                    reason: str = commands.Param(name="begruendung", description="Bitte gebe eine Begründung für den Unban an.", default="Kein Grund angegeben")):
        """Entbanne einen Benutzer von diesem Server."""
        await self.mod_instance._unban(inter, userid, username, reason)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Supporter")
    async def kick(self,
                   inter: disnake.ApplicationCommandInteraction,
                   member: disnake.Member = commands.Param(
                       name="benutzer", description="Der Benutzer, der gekickt werden soll."),
                   reason: str = commands.Param(
                       name="begründung", description="Grund warum der Benutzer gekickt werden soll", default="Kein Grund angegeben"),
                   proof: disnake.Attachment = commands.Param(name="beweis", description="Ein Bild als Beweis für den Kick und zur Dokumentation", default=None)):
        """Kicke einen Benutzer und speichere ein Bild als Beweis."""
        await self.mod_instance._kick(inter, member, reason, proof)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @commands.has_permissions(manage_messages=True)
    async def delete_messages_after(self, inter: disnake.ApplicationCommandInteraction,
                                    channel: disnake.TextChannel = commands.Param(
                                        name="channel", description="Der Kanal, in dem die Nachrichten gelöscht werden sollen."),
                                    timestamp: str = commands.Param(name="timestamp", description="Der Zeitpunkt (im Format YYYY-MM-DD HH:MM:SS) nach dem die Nachrichten gelöscht werden sollen.")):
        """Lösche alle Nachrichten in einem Kanal nach einer bestimmten Uhrzeit."""
        await self.mod_instance._delete_messages_after(inter, channel, timestamp)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Leitung")
    async def create_ticket_dropdown(self, inter: disnake.ApplicationCommandInteraction):
        """Erstellt Embeds für alle Ticket-Kategorien."""
        await self.ticket_instance._create_ticket_embed_with_dropdown(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Co Owner")
    async def create_roles_embeds(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        """Erstellt Embeds für alle Rollen."""
        await self.roleassignment_instance._create_roles_embeds(inter, channel)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Co Owner")
    async def create_nsfwrules_embeds(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        """Erstellt Embeds für alle NSFW-Regeln."""
        await self.roleassignment_instance._create_nsfwrules_embeds(inter, channel)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Co Owner")
    async def create_embed(self, inter: disnake.ApplicationCommandInteraction, message_type: str, channel: disnake.TextChannel):
        """Erstellt ein Embed für eine bestimmte Nachricht."""
        await self.roleassignment_instance._create_embed(inter, message_type, channel)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Co Owner")
    async def create_seelsorge_embed(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        """Erstellt ein Embed für die Seelsorge."""
        await self.roleassignment_instance._create_seelsorge_embed(inter, channel)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Co Owner")
    async def create_rules_embed(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        """Erstellt ein Embed für die Seelsorge."""
        await self.roleassignment_instance._create_rules_embed(inter, channel)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def beichte(self, inter: disnake.ApplicationCommandInteraction, message: str):
        """Sendet eine Beichte in den Beichtkanal."""
        await self.roleassignment_instance._beichte(inter, message)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def voicerename(self, inter: disnake.ApplicationCommandInteraction, name: str):
        """Ändert den Namen des Sprachkanals."""
        await self.voice_instance._voicerename(inter, name)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def voicerename(self, inter: disnake.ApplicationCommandInteraction, name: str):
        """Ändert den Namen des Sprachkanals."""
        await self.voice_instance._voicerename(inter, name)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def setlimit(self, inter: disnake.ApplicationCommandInteraction, limit: int):
        """Ändert das Limit des Sprachkanals."""
        await self.voice_instance._setlimit(inter, limit)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def voicekick(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Kickt einen Benutzer aus dem Sprachkanal."""
        await self.voice_instance._voicekick(inter, member)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def voiceblock(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Blockiert einen Benutzer im Sprachkanal."""
        await self.voice_instance._voiceblock(inter, member)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def voiceunblock(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Entblockiert einen Benutzer im Sprachkanal."""
        await self.voice_instance._voiceunblock(inter, member)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def deletechannel(self, inter: disnake.ApplicationCommandInteraction):
        """Löscht den Sprachkanal."""
        await self.voice_instance._deletechannel(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def hide(self, inter: disnake.ApplicationCommandInteraction):
        """Versteckt den Sprachkanal."""
        await self.voice_instance._hide(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def unhide(self, inter: disnake.ApplicationCommandInteraction):
        """Macht den Sprachkanal sichtbar."""
        await self.voice_instance._unhide(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def lock(self, inter: disnake.ApplicationCommandInteraction):
        """Sperrt den Sprachkanal."""
        await self.voice_instance._lock(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def unlock(self, inter: disnake.ApplicationCommandInteraction):
        """Entsperrt den Sprachkanal."""
        await self.voice_instance._unlock(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def permit(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Erlaubt einem Benutzer den Sprachkanal zu betreten."""
        await self.voice_instance._permit(inter, member)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def claim(self, inter: disnake.ApplicationCommandInteraction):
        """Fordert den Sprachkanal an."""
        await self.voice_instance._claim(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def transfer(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Überträgt den Sprachkanal an einen anderen Benutzer."""
        await self.voice_instance._transfer(inter, member)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def save(self, inter: disnake.ApplicationCommandInteraction):
        """Speichert den Sprachkanal."""
        await self.voice_instance._save(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def joinrequest(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.VoiceChannel):
        """Sendet eine Anfrage, um den Sprachkanal zu betreten."""
        await self.voice_instance._joinrequest(inter, channel)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def draw_giveaway(self, inter: disnake.ApplicationCommandInteraction, giveaway_id: int):
        """Zieht einen Gewinner für ein Gewinnspiel."""
        await self.giveaway_instance._draw_giveaway(inter, giveaway_id)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Administrator")
    async def create_giveaway(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel,
        title: str,
        description: str,
        prize: str,
        level_based: bool,
        allowed_roles: Optional[str] = None,
        excluded_roles: Optional[str] = None
    ):
        """Erstellt ein Gewinnspiel."""
        await self.giveaway_instance._create_giveaway(inter, channel, title, description, prize, level_based, allowed_roles, excluded_roles)

        # Replace with your guild ID

    @commands.slash_command(guild_ids=[854698446996766730])
    async def set_activste_user_color(self, inter: disnake.ApplicationCommandInteraction, color: str = commands.Param(name="color", description="Hier brauchst du einen Farbcode. (Bsp.: #ff0000)")):
        """Manually change the color of a specific role."""
        await inter.response.defer()
        if self.rolemanager.get_role(inter.guild.id, int(os.getenv("MOSTACTIVEUSER_ROLE_ID"))) in inter.user.roles:
            await self.level_instance._change_role_color(1342437571531116634, color, inter.guild)
        else:
            await inter.edit_original_response(content="Nur die Person mit der Rolle darf sie auch ändern.")
        await inter.edit_original_response(content=f"Changed color of role with ID {1342437571531116634} to {color}.")

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Leitung")
    async def subtract_xp_from_levels(self, inter: disnake.ApplicationCommandInteraction, subtractxp: int):
        """Subtracts XP from all users."""
        await self.level_instance._subtract_xp_from_levels(inter, subtractxp)

    @commands.slash_command(guild_ids=[854698446996766730], name="friend_add")
    async def friend_add(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        """Schicket eine Freundschaftsanfrage an einen Benutzer."""
        await self.friend_instance._friend_add(inter, user)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def friend_remove(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        """Entfernt einen Benutzer aus deiner Freundesliste."""
        await self.friend_instance._friend_remove(inter, user)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def friendlist(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User = None):
        """Zeigt dir deine Freundesliste an."""
        await self.friend_instance._friend_list(inter, user)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def friendrequests(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt dir alle Freundschaftsanfragen an."""
        await self.friend_instance._show_friend_requests(inter)    

    @commands.slash_command(guild_ids=[854698446996766730])
    async def privacy_settings(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt dir deine Datenschutzeinstellungen an."""
        await self.userprofile_instance._privacy_settings(inter)         

    @commands.slash_command(guild_ids=[854698446996766730])
    async def block(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        """Blockiert einen Benutzer."""
        await self.userprofile_instance._block(inter, user)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def unblock(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        """Blockiert einen Benutzer."""
        await self.userprofile_instance._unblock(inter, user)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def blocklist(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt dir deine Blockliste an."""
        await self.userprofile_instance._blocklist(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def set_introduction(self, inter: disnake.ApplicationCommandInteraction):
        """Setzt deine Vorstellung."""
        await self.userprofile_instance._set_introduction(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def get_introduction(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User = None):
        """Zeigt dir die Vorstellung eines Benutzers an."""
        await self.userprofile_instance._get_introduction(inter, user)
    
    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    @rolehierarchy.check_permissions("Leitung")
    async def commands_embed(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        """Zeigt dir alle Befehle an."""
        await self.roleassignment_instance._commands_embed(inter, channel)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def my_answers(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt dir deine Antworten an."""
        await self.cupid_instance._my_answers(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def edit_answer(self, inter: disnake.ApplicationCommandInteraction, 
                          question_id: int = commands.Param(name="frage_id", description="Die ID der Frage, die du beantworten möchtest."),
                          value: str = commands.Param(choices=["Eher ja", "Neutral", "Eher nein"])):
        """Ändert deine Antwort auf eine Frage für den Dating Bot."""
        await self.cupid_instance._edit_answer(inter, question_id, value)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def match_users(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Zeigt dir deine Top Matches an."""
        await self.cupid_instance._match_users(inter, member)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def set_parcipitation(self, inter: disnake.ApplicationCommandInteraction, value: str = commands.Param(choices=["Ja/Aktiviert", "Nein/Deaktiviert"])):
        """Setzt deine Teilnahme am Dating-System."""
        await self.cupid_instance._set_user_participation(inter, value)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def delete_answers(self, inter: disnake.ApplicationCommandInteraction):
        """Löscht deine Antworten auf alle Fragen für den Dating Bot."""
        await self.cupid_instance._delete_answers(inter, inter.guild)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def create_intro(self, inter: disnake.ApplicationCommandInteraction):
        """Erstellt eine Vorstellung."""
        await self.userprofile_instance._create_intro(inter)

    @commands.slash_command(guild_ids=[854698446996766730], default_member_permissions=disnake.Permissions(view_audit_log=True))
    async def check_birthday(self, inter: disnake.ApplicationCommandInteraction):
        """Ändert deine Vorstellung."""
        await self.globalfile._check_birthday(inter.guild)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def show_intro(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User = None):
        """Zeigt dir die Vorstellung eines Benutzers an."""
        if user is None:
            user = inter.user
        await self.userprofile_instance._show_intro(inter, user)

def setupCommands(bot: commands.Bot, rolemamaner: RoleManager):
    bot.add_cog(MyCommands(bot, rolemamaner))
