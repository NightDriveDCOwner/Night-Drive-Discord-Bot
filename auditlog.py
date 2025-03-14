import disnake
from disnake.ext import commands
import logging
from globalfile import Globalfile
from dbconnection import DatabaseConnectionManager
from dotenv import load_dotenv
import pytz
import os
import sqlite3
from datetime import datetime
from collections import namedtuple
from typing import Union
from rolemanager import RoleManager
from channelmanager import ChannelManager


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

    def __init__(self, bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
        self.bot = bot
        self.logger = logging.getLogger("AuditLog")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.rolemanager = rolemanager
        self.channelmanager = channelmanager

        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        load_dotenv(dotenv_path="envs/settings.env", override=True)

        self.user_data = {}
        self.TimerMustReseted = True
        self.UserRecord = namedtuple(
            'UserRecord', ['user', 'username', 'userid'])

    @commands.Cog.listener()
    async def on_ready(self):    
        self.logger.info("AuditLog Cog is ready.")

    async def send_audit_log_embed(self, action: disnake.AuditLogAction, entry: disnake.AuditLogEntry):
        thumbnail_url = None
        if isinstance(entry.target, disnake.User) or isinstance(entry.target, disnake.Member):
            author_name = entry.target.name
            try:
                thumbnail_url = entry.user.avatar.url
            except Exception as e:
                self.logger.error(f"Error while fetching avatar URL: {e}")
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
        if thumbnail_url is not None and thumbnail_url != "":
            embed.set_author(name=author_name, icon_url=thumbnail_url)
        else:
            embed.set_author(name=author_name)
        embed.add_field(name="Responsible User",
                        value=entry.user.mention, inline=True)
        embed.add_field(name="Action", value=action.name, inline=True)

        changes_str = ""
        key = zip(entry.changes.before.__dict__.keys())
        before = entry.changes.before if entry.changes.before is not None else "N/A"
        after = entry.changes.after if entry.changes.after is not None else "N/A"
        if action == disnake.AuditLogAction.member_update:
            changes_str += f"**{key}**:\nBefore: {before}\nAfter: {after}\n\n"
        elif action == disnake.AuditLogAction.channel_create:
            changes_str += f"**Channel Created**:\nName: {after}\n\n"
        elif action == disnake.AuditLogAction.channel_update:
            changes_str += f"**Channel {key}**:\nBefore: {before}\nAfter: {after}\n\n"
        elif action == disnake.AuditLogAction.channel_delete:
            changes_str += f"**Channel Deleted**:\nName: {before}\n\n"
        elif action == disnake.AuditLogAction.guild_update:
            changes_str += f"**Guild {key}**:\nBefore: {before}\nAfter: {after}\n\n"
        elif action == disnake.AuditLogAction.message_delete:
            changes_str += f"**Message Deleted**:\nContent: {before}\n\n"
        elif action == disnake.AuditLogAction.message_bulk_delete:
            changes_str += f"**Bulk Message Delete**:\nMessages Deleted: {before}\n\n"
        elif action == disnake.AuditLogAction.emoji_create:
            changes_str += f"**Emoji Created**:\nName: {after}\n\n"
        elif action == disnake.AuditLogAction.emoji_update:
            changes_str += f"**Emoji {key}**:\nBefore: {before}\nAfter: {after}\n\n"
        elif action == disnake.AuditLogAction.emoji_delete:
            changes_str += f"**Emoji Deleted**:\nName: {before}\n\n"
        elif action == disnake.AuditLogAction.invite_create:
            changes_str += f"**Invite Created**:\nCode: {after}\n\n"
        elif action == disnake.AuditLogAction.invite_update:
            changes_str += f"**Invite {key}**:\nBefore: {before}\nAfter: {after}\n\n"
        elif action == disnake.AuditLogAction.invite_delete:
            changes_str += f"**Invite Deleted**:\nCode: {before}\n\n"
        elif action == disnake.AuditLogAction.member_role_update:
            return
        else:
            changes_str += f"**{key}**:\nBefore: {before}\nAfter: {after}\n\n"

        embed.add_field(name="Changes", value=changes_str, inline=False)
        try:
            self.auditlog_channel : disnake.TextChannel = self.channelmanager.get_channel(entry.guild, int(os.getenv("AUDITLOG_CHANNEL_ID")))        
            if self.auditlog_channel:
                await self.auditlog_channel.send(embed=embed)
        except Exception as e:
            self.logger.error(f"Error while sending audit log embed: {e}")

    async def log_audit_entry(self, logtype: str, userid: int, details: str, guild: disnake.Guild = None):
        """Loggt einen Audit-Eintrag in die Datenbank."""
        await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, "INSERT INTO AUDITLOG (LOGTYPE, USERID, DETAILS) VALUES (?, ?, ?)", (logtype, userid, details))

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: disnake.AuditLogEntry):
        action = entry.action
        details = f"Action: {action.name}, Target: {entry.target}, Changes: {entry.changes}, Reason: {entry.reason}, Responsible User: {entry.user.name}"
        await self.log_audit_entry(action.name, entry.user.id, details, entry.guild)
        await self.send_audit_log_embed(action, entry)


def setupAuditLog(bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
    bot.add_cog(AuditLog(bot, rolemanager, channelmanager))
