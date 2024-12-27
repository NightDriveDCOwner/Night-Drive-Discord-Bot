import disnake
from disnake.ext import commands
import logging
from globalfile import Globalfile
from DBConnection import DatabaseConnection
from dotenv import load_dotenv
import pytz
import os
import sqlite3
from datetime import datetime, timedelta
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
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
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
        embed = disnake.Embed(
            title=f"Audit Log: {action.name}",
            description=f"Details: {entry.reason}",
            color=disnake.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="User", value=entry.user.mention, inline=True)
        embed.add_field(name="Target", value=str(entry.target), inline=True)
        embed.add_field(name="Changes", value=str(entry.changes), inline=False)

        # Replace 'YOUR_CHANNEL_ID' with the ID of the channel where you want to send the embed
        channel = self.bot.get_channel(self.channel_id)        
        if channel:
            await channel.send(embed=embed)

    async def admin_did_something(self, action: disnake.AuditLogAction, guild: disnake.Guild, handleduser: Union[disnake.User, disnake.Member]):
        DeletedbyAdmin = False
        relevant_entries = []
        entry: disnake.AuditLogEntry
        async for entry in guild.audit_logs(limit=5, action=action):
            if action == disnake.AuditLogAction.message_delete or action == disnake.AuditLogAction.member_disconnect:
                if entry.extra.count is not None:
                    if self.TimerMustReseted:
                        self.reset_timer()
                        self.TimerMustReseted = False
                    if entry.user.id in self.user_data:
                        if entry.extra.count > self.user_data[entry.user.id]:
                            self.user_data[entry.user.id] = entry.extra.count
                            relevant_entries.append(entry)
                        else:
                            continue
                    else:
                        self.user_data[entry.user.id] = entry.extra.count
                        relevant_entries.append(entry)
                else:
                    continue
            else:
                if self.TimerMustReseted:
                    self.reset_timer()
                    self.TimerMustReseted = False
                if entry.user.id not in self.user_data:
                    self.user_data[entry.user.id] = 1
                self.user_data[entry.user.id] += 1
                relevant_entries.append(entry)

        results = []
        for entry in relevant_entries:
            if action == disnake.AuditLogAction.message_delete or action == disnake.AuditLogAction.member_disconnect or action == disnake.AuditLogAction.member_update:
                if entry in relevant_entries:
                    user = entry.user
                    username = user.name
                    userid = user.id
                else:
                    user = handleduser
                    username = handleduser.name
                    userid = handleduser.id
                results.append(self.UserRecord(user, username, userid))
        
        # Logge die Änderungen in die Datenbank
        for entry in relevant_entries:
            details = f"Action: {action.name}, Target: {entry.target}, Changes: {entry.changes}, Reason: {entry.reason}, Responsible User: {entry.user.name}"
            await self.log_audit_entry(action.name, entry.user.id, details)
            await self.send_audit_log_embed(action, entry)
        
        return results


    async def log_audit_entry(self, logtype: str, userid: int, details: str):
        """Loggt einen Audit-Eintrag in die Datenbank."""
        cursor = self.db.connection.cursor()
        cursor.execute("INSERT INTO AUDITLOG (LOGTYPE, USERID, DETAILS) VALUES (?, ?, ?)", (logtype, userid, details))
        self.db.connection.commit()

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self.admin_did_something(disnake.AuditLogAction.channel_create, channel.guild, channel.guild.me)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self.admin_did_something(disnake.AuditLogAction.channel_delete, channel.guild, channel.guild.me)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        await self.admin_did_something(disnake.AuditLogAction.channel_update, before.guild, before.guild.me)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await self.admin_did_something(disnake.AuditLogAction.ban, guild, user)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await self.admin_did_something(disnake.AuditLogAction.unban, guild, user)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        await self.admin_did_something(disnake.AuditLogAction.member_update, before.guild, before.guild.me)

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        await self.admin_did_something(disnake.AuditLogAction.guild_update, before, before.me)

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        await self.admin_did_something(disnake.AuditLogAction.invite_create, invite.guild, invite.inviter)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        await self.admin_did_something(disnake.AuditLogAction.invite_delete, invite.guild, invite.inviter)

    @commands.Cog.listener()
    async def on_webhook_update(self, webhook):
        await self.admin_did_something(disnake.AuditLogAction.webhook_update, webhook.guild, webhook.user)

    @commands.Cog.listener()
    async def on_emoji_create(self, emoji):
        await self.admin_did_something(disnake.AuditLogAction.emoji_create, emoji.guild, emoji.user)

    @commands.Cog.listener()
    async def on_emoji_delete(self, emoji):
        await self.admin_did_something(disnake.AuditLogAction.emoji_delete, emoji.guild, emoji.user)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        await self.admin_did_something(disnake.AuditLogAction.message_delete, message.guild, message.author)

    @commands.Cog.listener()
    async def on_message_bulk_delete(self, messages):
        for message in messages:
            await self.admin_did_something(disnake.AuditLogAction.message_bulk_delete, message.guild, message.author)

    @commands.Cog.listener()
    async def on_message_pin(self, message):
        await self.admin_did_something(disnake.AuditLogAction.message_pin, message.guild, message.author)

    @commands.Cog.listener()
    async def on_message_unpin(self, message):
        await self.admin_did_something(disnake.AuditLogAction.message_unpin, message.guild, message.author)

    @commands.Cog.listener()
    async def on_integration_create(self, integration):
        await self.admin_did_something(disnake.AuditLogAction.integration_create, integration.guild, integration.user)

    @commands.Cog.listener()
    async def on_integration_update(self, integration):
        await self.admin_did_something(disnake.AuditLogAction.integration_update, integration.guild, integration.user)

    @commands.Cog.listener()
    async def on_integration_delete(self, integration):
        await self.admin_did_something(disnake.AuditLogAction.integration_delete, integration.guild, integration.user)

    @commands.Cog.listener()
    async def on_stage_instance_create(self, stage_instance):
        await self.admin_did_something(disnake.AuditLogAction.stage_instance_create, stage_instance.guild, stage_instance.user)

    @commands.Cog.listener()
    async def on_stage_instance_update(self, stage_instance):
        await self.admin_did_something(disnake.AuditLogAction.stage_instance_update, stage_instance.guild, stage_instance.user)

    @commands.Cog.listener()
    async def on_stage_instance_delete(self, stage_instance):
        await self.admin_did_something(disnake.AuditLogAction.stage_instance_delete, stage_instance.guild, stage_instance.user)

    @commands.Cog.listener()
    async def on_sticker_create(self, sticker):
        await self.admin_did_something(disnake.AuditLogAction.sticker_create, sticker.guild, sticker.user)

    @commands.Cog.listener()
    async def on_sticker_update(self, sticker):
        await self.admin_did_something(disnake.AuditLogAction.sticker_update, sticker.guild, sticker.user)

    @commands.Cog.listener()
    async def on_sticker_delete(self, sticker):
        await self.admin_did_something(disnake.AuditLogAction.sticker_delete, sticker.guild, sticker.user)

    @commands.Cog.listener()
    async def on_guild_scheduled_event_create(self, event):
        await self.admin_did_something(disnake.AuditLogAction.guild_scheduled_event_create, event.guild, event.creator)

    @commands.Cog.listener()
    async def on_guild_scheduled_event_update(self, event):
        await self.admin_did_something(disnake.AuditLogAction.guild_scheduled_event_update, event.guild, event.creator)

    @commands.Cog.listener()
    async def on_guild_scheduled_event_delete(self, event):
        await self.admin_did_something(disnake.AuditLogAction.guild_scheduled_event_delete, event.guild, event.creator)

    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        await self.admin_did_something(disnake.AuditLogAction.thread_create, thread.guild, thread.owner)

    @commands.Cog.listener()
    async def on_thread_update(self, thread):
        await self.admin_did_something(disnake.AuditLogAction.thread_update, thread.guild, thread.owner)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        await self.admin_did_something(disnake.AuditLogAction.thread_delete, thread.guild, thread.owner)

    @commands.Cog.listener()
    async def on_member_prune(self, guild):
        await self.admin_did_something(disnake.AuditLogAction.member_prune, guild, guild.me)

    @commands.Cog.listener()
    async def on_member_move(self, member, before, after):
        await self.admin_did_something(disnake.AuditLogAction.member_move, member.guild, member)

    @commands.Cog.listener()
    async def on_bot_add(self, member):
        if member.bot:
            await self.admin_did_something(disnake.AuditLogAction.bot_add, member.guild, member)

    @commands.Cog.listener()
    async def on_message_bulk_delete(self, messages):
        for message in messages:
            await self.admin_did_something(disnake.AuditLogAction.message_bulk_delete, message.guild, message.author)

    @commands.Cog.listener()
    async def on_message_pin(self, message):
        await self.admin_did_something(disnake.AuditLogAction.message_pin, message.guild, message.author)

    @commands.Cog.listener()
    async def on_message_unpin(self, message):
        await self.admin_did_something(disnake.AuditLogAction.message_unpin, message.guild, message.author)        

def setupAuditLog(bot):
    bot.add_cog(AuditLog(bot))