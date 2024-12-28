import disnake
from disnake.ext import commands
import logging
from globalfile import Globalfile
from DBConnection import DatabaseConnection
from dotenv import load_dotenv
import pytz
import os
import sqlite3
from datetime import datetime
from collections import namedtuple
from typing import Union

class AuditLog(commands.Cog):
    # Audit Log Action Types
    GUILD_UPDATE = disnake.AuditLogAction.guild_update
    CHANNEL_CREATE = disnake.AuditLogAction.channel_create
    CHANNEL_UPDATE = disnake.AuditLogAction.channel_update
    CHANNEL_DELETE = disnake.AuditLogAction.channel_delete
    OVERWRITE_CREATE = disnake.AuditLogAction.overwrite_create
    OVERWRITE_UPDATE = disnake.AuditLogAction.overwrite_update
    OVERWRITE_DELETE = disnake.AuditLogAction.overwrite_delete
    KICK = disnake.AuditLogAction.kick
    MEMBER_PRUNE = disnake.AuditLogAction.member_prune
    BAN = disnake.AuditLogAction.ban
    UNBAN = disnake.AuditLogAction.unban
    MEMBER_UPDATE = disnake.AuditLogAction.member_update
    MEMBER_ROLE_UPDATE = disnake.AuditLogAction.member_role_update
    MEMBER_MOVE = disnake.AuditLogAction.member_move
    MEMBER_DISCONNECT = disnake.AuditLogAction.member_disconnect
    BOT_ADD = disnake.AuditLogAction.bot_add
    ROLE_CREATE = disnake.AuditLogAction.role_create
    ROLE_UPDATE = disnake.AuditLogAction.role_update
    ROLE_DELETE = disnake.AuditLogAction.role_delete
    INVITE_CREATE = disnake.AuditLogAction.invite_create
    INVITE_UPDATE = disnake.AuditLogAction.invite_update
    INVITE_DELETE = disnake.AuditLogAction.invite_delete
    WEBHOOK_CREATE = disnake.AuditLogAction.webhook_create
    WEBHOOK_UPDATE = disnake.AuditLogAction.webhook_update
    WEBHOOK_DELETE = disnake.AuditLogAction.webhook_delete
    EMOJI_CREATE = disnake.AuditLogAction.emoji_create
    EMOJI_UPDATE = disnake.AuditLogAction.emoji_update
    EMOJI_DELETE = disnake.AuditLogAction.emoji_delete
    MESSAGE_DELETE = disnake.AuditLogAction.message_delete
    MESSAGE_BULK_DELETE = disnake.AuditLogAction.message_bulk_delete
    MESSAGE_PIN = disnake.AuditLogAction.message_pin
    MESSAGE_UNPIN = disnake.AuditLogAction.message_unpin
    INTEGRATION_CREATE = disnake.AuditLogAction.integration_create
    INTEGRATION_UPDATE = disnake.AuditLogAction.integration_update
    INTEGRATION_DELETE = disnake.AuditLogAction.integration_delete
    STAGE_INSTANCE_CREATE = disnake.AuditLogAction.stage_instance_create
    STAGE_INSTANCE_UPDATE = disnake.AuditLogAction.stage_instance_update
    STAGE_INSTANCE_DELETE = disnake.AuditLogAction.stage_instance_delete
    STICKER_CREATE = disnake.AuditLogAction.sticker_create
    STICKER_UPDATE = disnake.AuditLogAction.sticker_update
    STICKER_DELETE = disnake.AuditLogAction.sticker_delete
    GUILD_SCHEDULED_EVENT_CREATE = disnake.AuditLogAction.guild_scheduled_event_create
    GUILD_SCHEDULED_EVENT_UPDATE = disnake.AuditLogAction.guild_scheduled_event_update
    GUILD_SCHEDULED_EVENT_DELETE = disnake.AuditLogAction.guild_scheduled_event_delete
    THREAD_CREATE = disnake.AuditLogAction.thread_create
    THREAD_UPDATE = disnake.AuditLogAction.thread_update
    THREAD_DELETE = disnake.AuditLogAction.thread_delete

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("AuditLog")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper() 
        self.logger.setLevel(logging_level)

        # Überprüfen, ob der Handler bereits hinzugefügt wurde
        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levellevel)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
        self.db: sqlite3.Connection = DatabaseConnection()
        self.cursor: sqlite3.Cursor = self.db.connection.cursor()

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS AUDITLOG (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                LOGTYPE TEXT,
                USERID TEXT NOT NULL,
                DETAILS TEXT
            )
        """)
        self.db.connection.commit()
        load_dotenv(dotenv_path="settings.env")
        self.channel_id = os.getenv("AUDITLOG_CHANNEL_ID")
        print(f"Loaded channel ID: {self.channel_id}")  # Debug-Ausgabe

        self.user_data = {}
        self.TimerMustReseted = True
        self.UserRecord = namedtuple('UserRecord', ['user', 'username', 'userid'])

    def get_current_time(self):
        """Gibt die aktuelle Zeit in der deutschen Zeitzone zurück."""
        german_timezone = pytz.timezone('Europe/Berlin')
        return datetime.now(german_timezone)

    def reset_timer(self):
        """Setzt den Timer zurück."""
        self.user_data.clear()
        self.TimerMustReseted = True

    async def send_audit_log_embed(self, action: disnake.AuditLogAction, entry: disnake.AuditLogEntry):
        if isinstance(entry.target, disnake.User) or isinstance(entry.target, disnake.Member):
            author_name = entry.target.name
            thumbnail_url = entry.user.avatar.url
        elif isinstance(entry.target, disnake.Guild):
            author_name = entry.guild.name
            thumbnail_url = entry.guild.icon.url
        else:
            author_name = entry.guild.name
            thumbnail_url = entry.guild.icon.url

        embed = disnake.Embed(
            description=f"Details: {entry.reason}",
            color=disnake.Color.blue(),
            timestamp=datetime.utcnow()
        )

        embed.set_author(name=author_name, icon_url=thumbnail_url)
        embed.add_field(name="Responsible User", value=entry.user.mention, inline=True)
        embed.add_field(name="Action", value=action.name, inline=True)
        embed.add_field(name="Changes", value=str(entry.changes), inline=False)

        channel = entry.guild.get_channel(int(self.channel_id))        
        if channel:
            await channel.send(embed=embed)
        else:
            self.logger.error(f"Channel with ID {self.channel_id} not found.")

    async def log_audit_entry(self, logtype: str, userid: int, details: str):
        """Loggt einen Audit-Eintrag in die Datenbank."""
        cursor = self.db.connection.cursor()
        cursor.execute("INSERT INTO AUDITLOG (LOGTYPE, USERID, DETAILS) VALUES (?, ?, ?)", (logtype, userid, details))
        self.db.connection.commit()

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: disnake.AuditLogEntry):
        action = entry.action
        details = f"Action: {action.name}, Target: {entry.target}, Changes: {entry.changes}, Reason: {entry.reason}, Responsible User: {entry.user.name}"
        await self.log_audit_entry(action.name, entry.user.id, details)
        await self.send_audit_log_embed(action, entry)

def setupAuditLog(bot):
    bot.add_cog(AuditLog(bot))