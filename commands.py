import disnake, os, re
from disnake.ext import commands, tasks
from disnake.ui import Button, View
from disnake import ApplicationCommandInteraction, User, Member, Role
import disnake.file
import re
from globalfile import Globalfile
from rolehierarchy import rolehierarchy
from dotenv import load_dotenv
import logging
import sqlite3
from dbconnection import DatabaseConnection
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


class MyCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseConnection()  # Stellen Sie sicher, dass die Datenbankverbindung initialisiert wird

        # Logger initialisieren
        self.logger = logging.getLogger("Commands")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()         
        self.logger.setLevel(logging_level)
        self.globalfile = Globalfile(bot)        
        load_dotenv(dotenv_path="envs/settings.env")
        self.last_info_message = None
        self.last_info_time = None
        self.level_cog = self.bot.get_cog('Level')
        self.tmp_instance : Tmp = self.bot.get_cog('Tmp')
        self.cupid_instance : Cupid = self.bot.get_cog('Cupid')
        self.join_instance : Join = self.bot.get_cog('Join')
        self.level_instance : Level = self.bot.get_cog('Level')
        self.mod_instance : Moderation = self.bot.get_cog('Moderation')
        self.ticket_instance : Ticket = self.bot.get_cog('Ticket')
        self.roleassignment_instance : RoleAssignment = self.bot.get_cog('RoleAssignment')
        self.voice_instance = self.bot.get_cog('Voice')
        self.globalfile_instance : Globalfile = self.bot.get_cog('Globalfile')
        self.giveaway_instance : Giveaway = self.bot.get_cog('Giveaway')

        if not self.logger.handlers:          
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
        load_dotenv(dotenv_path="envs/settings.env")
        self.settings_keys = [
            "FACTOR",
            "MESSAGE_WORTH_PER_VOICEMIN",
            "MIN_ACCOUNT_AGE_DAYS"
            # Füge hier weitere Schlüssel hinzu, die änderbar sein sollen
        ]            
        
        self.db: sqlite3.Connection = DatabaseConnection()
        self.cursor: sqlite3.Cursor = self.db.connection.cursor()                   

    def cog_unload(self):
        Globalfile.unban_task.cancel()        

    
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

    @commands.slash_command(guild_ids=[854698446996766730])
    async def list_banned_users(self, inter: disnake.ApplicationCommandInteraction):
        """Listet alle gebannten Benutzer auf und zeigt den Entbannzeitpunkt an, falls vorhanden."""
        await self.tmp_instance._list_banned_users(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Moderator")
    async def badword_add(self, inter: disnake.ApplicationCommandInteraction, word: str):
        """Füge ein Wort zur Blacklist-Liste hinzu, wenn es noch nicht existiert."""
        await self.tmp_instance._badword_add(inter, word)
            
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Moderator")
    async def badword_remove(self, inter: disnake.ApplicationCommandInteraction, word: str):
        """Entferne ein Wort von der Blacklist-Liste."""
        await self.tmp_instance._badword_remove(inter, word)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Moderator")
    async def badwords_list(self, inter: disnake.ApplicationCommandInteraction):
        """Zeige die aktuelle Blacklist-Liste."""
        await self.tmp_instance._badwords_list(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Test-Supporter")
    async def add_user_to_ticket(self, inter: disnake.ApplicationCommandInteraction, ticket_id: int, user: disnake.User):
        """Fügt einen Benutzer zu einem Ticket-Channel hinzu."""
        await self.tmp_instance._add_user_to_ticket(inter, ticket_id, user)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Test-Supporter")
    async def note_add(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, reason: str, proof: disnake.Attachment = None):
        """Erstellt eine Notiz für einen Benutzer."""
        await self.tmp_instance._note_add(inter, user, reason, proof)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Senior Supporter")
    async def note_delete(self, inter: disnake.ApplicationCommandInteraction, caseid: int):
        """Markiert eine Note als gelöscht basierend auf der Note ID."""
        await self.tmp_instance._note_delete(inter, caseid)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Test-Supporter")
    async def user_profile(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        """Zeigt das Profil eines Benutzers an, einschließlich Notizen, Warnungen und Bans."""
        await self.tmp_instance._user_profile(inter, user)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co Owner")
    async def disconnect(self, inter: disnake.ApplicationCommandInteraction):
        """Schließt alle Verbindungen des Bots und beendet den Bot-Prozess."""
        await self.tmp_instance._disconnect(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Senior Moderator")
    async def sync_users(self, inter: disnake.ApplicationCommandInteraction):
        """Synchronisiere alle Benutzer des Servers mit der Users Tabelle."""
        await self.tmp_instance._sync_users(inter)
            
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co Owner")
    async def remove_role_from_all(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        """Entfernt eine bestimmte Rolle bei allen Benutzern in der Gilde."""
        await self.tmp_instance._remove_role_from_all(inter, role)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def unban_all_users(self, inter: disnake.ApplicationCommandInteraction):
        """Entbannt alle gebannten Benutzer in der Gilde."""
        await self.tmp_instance._unban_all_users(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def warn_inactive_users(self, inter: disnake.ApplicationCommandInteraction, days: int, role: disnake.Role, channel: disnake.TextChannel):
        """Warnt alle Benutzer, die innerhalb der angegebenen Tage keine Nachrichten geschrieben haben."""
        await self.tmp_instance._warn_inactive_users(inter, days, role, channel)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co Owner")
    async def kick_inactive_users(self, inter: disnake.ApplicationCommandInteraction, months: int, execute: bool = False):
        """Kicke alle Benutzer, die innerhalb der angegebenen Monate keine Nachrichten geschrieben haben."""
        await self.tmp_instance._kick_inactive_users(inter, months, execute)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Test-Supporter")
    async def help_moderation(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt alle Moderationsbefehle an."""
        await self.tmp_instance._help_moderation(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Test-Supporter")
    async def help_user(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt alle Benutzerbefehle an."""
        await self.tmp_instance._help_user(inter)                           

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Supporter")
    async def verify_user(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User):
        """Verifiziert einen Benutzer und gibt ihm die Rolle 'Verified'."""
        await self.tmp_instance._verify_user(inter, user)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Supporter")
    async def add_image(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, image: disnake.Attachment):
        """Fügt ein Bild zu einem Benutzer hinzu."""
        await self.tmp_instance._add_image(inter, user, image)
        
    @commands.slash_command(guild_ids=[854698446996766730])
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
        await self.tmp_instance._me(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def set_setting(self, inter: disnake.ApplicationCommandInteraction, key: str, value: str):
        """Ändert einen Wert in der settings.env Datei."""
        await self.tmp_instance._set_setting(inter, key, value)
        
    @set_setting.autocomplete("key")
    async def set_setting_autocomplete(self, inter: disnake.ApplicationCommandInteraction, key: str):
        return [key for key in self.settings_keys if key.startswith(key)]    

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Supporter")
    async def send_message(self, inter: disnake.ApplicationCommandInteraction, channel : disnake.TextChannel, message: str):
        """Sendet eine Nachricht in einen angegebenen Kanal."""
        await self.tmp_instance._send_message(inter, channel, message)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Supporter")
    async def send_unofficalwarn_message(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, reason: str):
        """Sendet eine ephemere Nachricht an einen anderen Benutzer und benachrichtigt einen bestimmten Kanal."""
        await self.tmp_instance._send_unofficalwarn_message(inter, user, reason)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Supporter")
    async def add_second_account(self, inter: ApplicationCommandInteraction, second_user: User, main_user: User):
        """Fügt einem Benutzer die Zweitaccount-Rolle hinzu und aktualisiert die Datenbank."""
        await self.tmp_instance._add_second_account(inter, second_user, main_user)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Owner")
    async def reorganize_database(self, inter: ApplicationCommandInteraction):
        """Führt eine Reorganisation der Datenbank durch."""
        await self.tmp_instance._reorganize_database(inter)

    @commands.slash_command(guild_ids=[854698446996766730])    
    @rolehierarchy.check_permissions("Administrator")
    async def dating_info(self, inter: disnake.ApplicationCommandInteraction):
        """Zeigt Informationen über das Dating-System an."""
        await self.cupid_instance._dating_info(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def debug_top_matches(self, inter: disnake.ApplicationCommandInteraction):   
        """Zeigt die Top-Matches für jeden Benutzer an."""
        await self.cupid_instance._debug_top_matches(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def recalculate_invite_xp(self, inter: disnake.ApplicationCommandInteraction):
        """Berechnet die XP für Einladungen neu."""
        await self.cupid_instance._recalculate_invite_xp(inter)        

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def deletedata_for_nonexistent_user(self, inter: disnake.ApplicationCommandInteraction):
        """Löscht Daten für Benutzer, die nicht mehr existieren."""
        await self.cupid_instance._deletedata_for_nonexistent_user(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def random_anime_gif(self, inter: disnake.ApplicationCommandInteraction):        
        """Sendet ein zufälliges Anime-GIF."""
        await self.join_instance._random_anime_gif(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def update_all_users_roles(self, inter: disnake.ApplicationCommandInteraction, send_level_up_messages: bool = False):
        """Aktualisiert die Rollen aller Benutzer basierend auf ihrem Level."""
        await self.level_instance._update_all_users_roles(inter, send_level_up_messages)
    
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def calculate_message_xp(self, inter: disnake.ApplicationCommandInteraction):
        """Berechnet die XP für Nachrichten neu."""
        await self.level_instance._calculate_message_xp(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def recalculate_experience(self, inter: disnake.ApplicationCommandInteraction, send_level_up_messages: bool = False):        
        """Berechnet die XP für alle Benutzer neu."""
        await self.level_instance._recalculate_experience(inter, send_level_up_messages)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def update_levels(self, inter: disnake.ApplicationCommandInteraction):
        """Aktualisiert die Level aller Benutzer."""
        await self.level_instance._update_levels(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def top_users(self, inter: disnake.ApplicationCommandInteraction):      
        """Zeigt die Top Benutzer basierend auf ihrer XP an."""
        await self.level_instance._top_users(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def add_xp_to_levels(self, inter: disnake.ApplicationCommandInteraction, addxp: int):
        """Fügt XP zu allen Benutzern hinzu."""
        await self.level_instance._add_xp_to_levels(inter, addxp)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def add_xp_to_user(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, xp: int, reason: str):
        """Fügt einem Benutzer XP hinzu."""
        await self.level_instance._add_xp_to_user(inter, user, xp, reason)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def add_xp_to_voice_channel(self, inter: disnake.ApplicationCommandInteraction, channel_id: int, xp: int, reason: str):
        """Fügt einem Sprachkanal XP hinzu."""
        await self.level_instance._add_xp_to_voice_channel(inter, channel_id, xp, reason)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Administrator")
    async def activity_since(self, inter: disnake.ApplicationCommandInteraction, start_date: str, user: disnake.User = None):
        """Zeigt die Aktivität eines Benutzers seit einem bestimmten Datum an."""
        await self.level_instance._activity_since(inter, start_date, user)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Senior Supporter")
    async def timeout(self, inter: disnake.ApplicationCommandInteraction, 
                        member: disnake.Member, 
                        duration: str = commands.Param(name="dauer", description="Dauer des Timeouts in Sek., Min., Std., Tagen oder Jahre.(Bsp.: 0s0m0h0d0j)"),
                        reason: str = commands.Param(name="begründung", description="Grund für den Timeout", default="Kein Grund angegeben"),
                        warn: bool = commands.Param(name="warn", description="Soll eine Warnung erstellt werden?", default=False),
                        warn_level: int = commands.Param(name="warnstufe", description="Warnstufe (1-3) | Default = 1 wenn warn_level = True", default=1)):
        """Timeout einen Benutzer für eine bestimmte Dauer und optional eine Warnung erstellen."""
        await self.mod_instance._timeout(inter, member, duration, reason, warn, warn_level)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Moderator")
    async def timeout_remove(self, inter: disnake.ApplicationCommandInteraction, timeout_id: int, reason: str = commands.Param(name="begründung", description="Grund für das Entfernen des Timeouts", default="Kein Grund angegeben")):
        """Entfernt einen Timeout basierend auf der Timeout ID."""
        await self.mod_instance._timeout_remove(inter, timeout_id, reason)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Test-Supporter")
    async def warn_add(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User, reason: str, level: int = 1, proof: disnake.Attachment = None, show: str = "True"):        
        """Erstellt eine Warnung für einen Benutzer."""
        await self.mod_instance._warn_add(inter, user, reason, level, proof, show)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Moderator")
    async def warn_delete(self, inter: disnake.ApplicationCommandInteraction, caseid: int):
        """Markiert eine Warnung als gelöscht basierend auf der Warn ID."""
        await self.mod_instance._warn_delete(inter, caseid)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Supporter")                   
    async def ban(self, 
                inter: disnake.ApplicationCommandInteraction, 
                member: disnake.Member = commands.Param(name="benutzer", description="Der Benutzer, der gebannt werden soll."), 
                reason: str = commands.Param(name="begründung", description="Grund warum der Benutzer gebannt werden soll", default="Kein Grund angegeben"),
                duration: str = commands.Param(name="dauer", description="Dauer des Bans in Sek., Min., Std., Tagen oder Jahre.(Bsp.: 0s0m0h0d0j) Nichts angegeben = Dauerhaft", default="0s"),
                delete_days: int = commands.Param(name="geloeschte_nachrichten", description="Anzahl der Tage, für die Nachrichten des Benutzers gelöscht werden sollen. (0-7, Default = 0)", default=0),
                proof: disnake.Attachment = commands.Param(name="beweis", description="Ein Bild als Beweis für den Ban und zur Dokumentation", default=None)):
        """Banne einen Benutzer und speichere ein Bild als Beweis."""
        await self.mod_instance._ban(inter, member, reason, duration, delete_days, proof)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Senior Supporter")
    async def unban(self, inter: disnake.ApplicationCommandInteraction, 
                    userid: int = commands.param(name="userid", description="Hier kannst du die UserID unserer Datenbank angeben.", default=0), 
                    username: str = commands.Param(name="username", description="Hier kannst du den Benutzernamen angeben, falls die UserID nicht bekannt ist.", default=""), 
                    reason: str = commands.Param(name="begruendung", description="Bitte gebe eine Begründung für den Unban an.", default="Kein Grund angegeben")):
        """Entbanne einen Benutzer von diesem Server."""
        await self.mod_instance._unban(inter, userid, username, reason)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Supporter")
    async def kick(self, 
                inter: disnake.ApplicationCommandInteraction, 
                member: disnake.Member = commands.Param(name="benutzer", description="Der Benutzer, der gekickt werden soll."), 
                reason: str = commands.Param(name="begründung", description="Grund warum der Benutzer gekickt werden soll", default="Kein Grund angegeben"),
                proof: disnake.Attachment = commands.Param(name="beweis", description="Ein Bild als Beweis für den Kick und zur Dokumentation", default=None)):
        """Kicke einen Benutzer und speichere ein Bild als Beweis."""
        await self.mod_instance._kick(inter, member, reason, proof)

    @commands.slash_command(guild_ids=[854698446996766730])
    @commands.has_permissions(manage_messages=True)
    async def delete_messages_after(self, inter: disnake.ApplicationCommandInteraction, 
                                    channel: disnake.TextChannel = commands.Param(name="channel", description="Der Kanal, in dem die Nachrichten gelöscht werden sollen."),
                                    timestamp: str = commands.Param(name="timestamp", description="Der Zeitpunkt (im Format YYYY-MM-DD HH:MM:SS) nach dem die Nachrichten gelöscht werden sollen.")):
        """Lösche alle Nachrichten in einem Kanal nach einer bestimmten Uhrzeit."""
        await self.mod_instance._delete_messages_after(inter, channel, timestamp)

    @commands.slash_command(guild_ids=[854698446996766730])
    async def create_ticket_embeds(self, inter: disnake.ApplicationCommandInteraction):
        """Erstellt Embeds für alle Ticket-Kategorien."""
        await self.ticket_instance._create_ticket_embeds(inter)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co Owner")
    async def create_roles_embeds(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        """Erstellt Embeds für alle Rollen."""
        await self.roleassignment_instance._create_roles_embeds(inter, channel)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co Owner")    
    async def create_nsfwrules_embeds(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):        
        """Erstellt Embeds für alle NSFW-Regeln."""
        await self.roleassignment_instance._create_nsfwrules_embeds(inter, channel)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co Owner")
    async def create_embed(self, inter: disnake.ApplicationCommandInteraction, message_type: str, channel: disnake.TextChannel):
        """Erstellt ein Embed für eine bestimmte Nachricht."""
        await self.roleassignment_instance._create_embed(inter, message_type, channel)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co Owner")
    async def create_seelsorge_embed(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        """Erstellt ein Embed für die Seelsorge."""
        await self.roleassignment_instance._create_seelsorge_embed(inter, channel)

    @commands.slash_command(guild_ids=[854698446996766730])
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

    @commands.slash_command(guild_ids=[854698446996766730])
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

def setupCommands(bot: commands.Bot):
    bot.add_cog(MyCommands(bot))
