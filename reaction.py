import disnake
import asyncio
from globalfile import Globalfile
from collections import namedtuple
import disnake.message
import disnake.audit_logs
from disnake.ext import commands
from datetime import datetime, timedelta, timezone
from moderation import Moderation
import logging
from dbconnection import DatabaseConnectionManager
import os
from cupid import Cupid
from rolemanager import RoleManager
from channelmanager import ChannelManager


class Reaction(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
        self.bot = bot
        self.user_data = {}
        self.TimerMustReseted = True
        self.globalfile: Globalfile = self.bot.get_cog('Globalfile')
        self.moderation = self.bot.get_cog("Moderation")
        self.logger = logging.getLogger("Reaction")
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

    @commands.Cog.listener()
    async def on_ready(self):        
        self.logger.info("Reaction Cog is ready.")

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        try:
            if message.guild is not None:
                member = await self.globalfile.get_member_from_user(message.author, message.guild.id)
                if member and (message.content != "" or len(message.attachments) > 0):
                    if message.channel.id != 1208770898832658493 and message.channel.id != 1219347644640530553:                                
                        botrolle: disnake.Role = self.rolemanager.get_role(message.guild.id, int(os.getenv("BOT_ROLE_ID")))
                        if botrolle not in member.roles:
                            avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                            current_datetime = (await self.globalfile.get_current_time())
                            await self.moderation.check_message_for_blacklist(message)
                            self.logger.info(
                                f"Nachricht von Server {message.guild.name} erhalten: Channel: {message.channel.name}, Username: {member.name}, Userid: {member.id}, Content: {message.content}")

                            content_chunks = [message.content[i:i+1024]
                                              for i in range(0, len(message.content), 1024)]
                            embeds = []

                            for i, chunk in enumerate(content_chunks):
                                embed = disnake.Embed(
                                    title=f"Message send in <#{message.channel.id}>!", color=0x4169E1)
                                embed.set_author(
                                    name=member.name, icon_url=avatar_url)
                                embed.add_field(
                                    name="Message:", value=chunk, inline=True)
                                embed.set_footer(
                                    text=f"ID: {member.id} - heute um {current_datetime.strftime('%H:%M:%S')} Uhr \nMessage-ID: {message.id}")
                                if i == 0 and message.attachments:
                                    embed.set_image(
                                        url=message.attachments[0].url)
                                embeds.append(embed)
                            messagelog: disnake.TextChannel = self.channelmanager.get_channel(message.guild.id, int(os.getenv("MESSAGELOG_CHANNEL_ID")))
                            for embed in embeds:
                                await messagelog.send(embed=embed)

                            self_reveal_channel: disnake.TextChannel = self.channelmanager.get_channel(message.guild.id, int(os.getenv("SELFREVEAL_CHANNEL_ID")))
                            if message.attachments and message.channel == self_reveal_channel:
                                # Check if a thread already exists for this user in the self-reveal channel
                                existing_thread = None
                                for thread in self_reveal_channel.threads:
                                    if thread.name == f"{member.name}'s Self Reveal":
                                        # Check if the last message in the thread is from the same user
                                        last_message = await thread.fetch_message(thread.last_message_id)
                                        if last_message.author.id == member.id:
                                            existing_thread = thread
                                            break

                                if not existing_thread:
                                    # Create a new thread                                    
                                    thread: disnake.Thread = await self_reveal_channel.create_thread(
                                        name=f"{member.name}'s Self Reveal",
                                        message=message,
                                        auto_archive_duration=None
                                    )
                                else:
                                    thread = existing_thread

                                # Send a message in the thread
                                embed = disnake.Embed(
                                    title="Bild Diskussion",
                                    description="Hier kannst du dich mit den anderen über das Bild unterhalten.",
                                    color=disnake.Color.blue()
                                )
                                embed.set_author(
                                    name=member.name, icon_url=avatar_url)
                                embed.set_footer(
                                    text=f"ID: {member.id} - heute um {current_datetime.strftime('%H:%M:%S')} Uhr")
                                await thread.send(embed=embed)
        except Exception as e:
            self.logger.critical(f"Fehler aufgetreten [on_message]: {e}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: disnake.Message):
        if message.guild is not None:
            member = await self.globalfile.get_member_from_user(message.author, message.guild.id)
            if member and message.channel.id != 1208770898832658493 and message.channel.id != 1219347644640530553:                        
                botrolle: disnake.Role = self.rolemanager.get_role(message.guild.id, int(os.getenv("BOT_ROLE_ID")))
                if botrolle not in member.roles:
                    try:
                        User = await self.globalfile.admin_did_something(disnake.AuditLogAction.message_delete, member, message.guild)
                        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url

                        current_datetime = (await self.globalfile.get_current_time())

                        self.logger.info(
                            f"Nachricht von Server {message.guild.name} deleted: Channel: {message.channel.name}. Username: {member.name}, Userid: {member.id}, Content: {message.content}, Message deleted by: {User.username}, User ID: {str(User.userid)}")

                        content_chunks = [message.content[i:i+1024]
                                          for i in range(0, len(message.content), 1024)]
                        embeds = []

                        for i, chunk in enumerate(content_chunks):
                            embed = disnake.Embed(
                                title=f"Message deleted in <#{message.channel.id}>!", color=0xFF0000)
                            embed.set_author(name=member.name,
                                             icon_url=avatar_url)
                            embed.add_field(name="Message:",
                                            value=chunk, inline=False)
                            if i == 0:
                                embed.add_field(
                                    name="Deleted by:", value=f"{User.username} - {str(User.userid)}", inline=False)
                            embed.set_footer(
                                text=f"ID: {member.id} - heute um {current_datetime.strftime('%H:%M:%S')} Uhr \nMessage-ID: {message.id}")
                            embeds.append(embed)

                        # Ermitteln der USERID des Admins, der die Nachricht gelöscht hat

                        cursor = await DatabaseConnectionManager.execute_sql_statement(message.guild.id, message.guild.name, "SELECT ID FROM USER WHERE DISCORDID = ?", (User.userid,))
                        admin_user_id = (await cursor.fetchone())
                        if admin_user_id:
                            admin_user_id = admin_user_id[0]

                        # Aktualisieren der Nachricht in der Datenbank mit DELETED_BY
                        cursor = await DatabaseConnectionManager.execute_sql_statement(message.guild.id, message.guild.name, "UPDATE MESSAGE SET DELETED_BY = ? WHERE MESSAGEID = ? AND CHANNELID = ?", (admin_user_id, message.id, message.channel.id))
                        messagelog: disnake.TextChannel = self.channelmanager.get_channel(message.guild.id, int(os.getenv("MESSAGELOG_CHANNEL_ID")))
                        for embed in embeds:
                            if User.username == member.name:
                                await messagelog.send(embed=embed)
                            else:
                                auditlog: disnake.TextChannel = self.channelmanager.get_channel(message.guild.id, int(os.getenv("AUDITLOG_CHANNEL_ID")))
                                await auditlog.send(embed=embed)
                    except Exception as e:
                        self.logger.critical(
                            f"Fehler aufgetreten [on_message_delete]: {e}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: disnake.Message, after: disnake.Message):
        try:
            if before.guild is not None:
                member = await self.globalfile.get_member_from_user(before.author, before.guild.id)
                botrolle: disnake.Role = self.rolemanager.get_role(after.guild.id, int(os.getenv("BOT_ROLE_ID")))
                if member and before.channel.id != 1208770898832658493 and before.channel.id != 1219347644640530553 and botrolle not in member.roles:
                    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                    current_datetime = (await self.globalfile.get_current_time())

                    self.logger.info(
                        f"Nachricht von Server {before.guild.name} edited: Channel {after.channel.name}, Username: {member.name}, Userid: {member.id}, Content before: {before.content}, Content after: {after.content}")
                    embed = disnake.Embed(
                        title=f"Message edited in <#{after.channel.id}>!", color=0xFFA500)
                    embed.set_author(name=member.name, icon_url=avatar_url)
                    embed.add_field(name="Message before:",
                                    value=before.content, inline=False)
                    embed.add_field(name="Message after:",
                                    value=after.content, inline=False)
                    embed.set_footer(
                        text=f"ID: {member.id} - heute um {current_datetime.strftime('%H:%M:%S')} Uhr \nMessage-ID: {before.id}")
                    if before.attachments:
                        embed.set_image(url=before.attachments[0].url)

                    # Ermitteln der MESSAGE_BEFORE-ID

                    cursor = await DatabaseConnectionManager.execute_sql_statement(after.guild.id, after.guild.name, "SELECT ID FROM MESSAGE WHERE MESSAGEID = ? AND CHANNELID = ?", (before.id, before.channel.id))
                    message_before_id = (await cursor.fetchone())
                    if message_before_id:
                        message_before_id = message_before_id[0]

                    userrecord = await self.globalfile.get_user_record(guild=after.guild, discordid=member.id)
                    # Speichern der bearbeiteten Nachricht in der Datenbank
                    current_datetime = (await self.globalfile.get_current_time()).strftime('%Y-%m-%d %H:%M:%S')
                    image_paths = [
                        attachment.url for attachment in after.attachments]
                    if len(image_paths) != 0:
                        image_path_fields = ", " + \
                            ', '.join(
                                [f"IMAGEPATH{i+1}" for i in range(len(image_paths))])
                        image_path_values = ", " + \
                            ', '.join(['?' for _ in range(len(image_paths))])
                    else:
                        image_path_fields = ""
                        image_path_values = ""
                    query = f"INSERT INTO MESSAGE (CONTENT, USERID, CHANNELID, MESSAGEID, MESSAGE_BEFORE, INSERT_DATE{image_path_fields}) VALUES (?, ?, ?, ?, ?, ?{image_path_values})"
                    cursor = await DatabaseConnectionManager.execute_sql_statement(after.guild.id, after.guild.name, query, (after.content, userrecord['ID'], after.channel.id, after.id, message_before_id, current_datetime, *image_paths))
                    messagelog: disnake.TextChannel = self.channelmanager.get_channel(after.guild.id, int(os.getenv("MESSAGELOG_CHANNEL_ID")))
                    await messagelog.send(embed=embed)
        except Exception as e:
            self.logger.critical(f"Fehler aufgetreten [on_message_edit]: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before: disnake.Member, after: disnake.Member):
        try:
            # Überprüfen, ob sich die Rollen des Mitglieds geändert haben
            if before.roles != after.roles:
                added_roles = [
                    role for role in after.roles if role not in before.roles]
                removed_roles = [
                    role for role in before.roles if role not in after.roles]

                for role in added_roles:
                    self.logger.info(
                        f"Rolle hinzugefügt: {role.name} für {after.name} ({after.id})")

                for role in removed_roles:
                    self.logger.info(
                        f"Rolle entfernt: {role.name} von {after.name} ({after.id})")

                current_datetime = (await self.globalfile.get_current_time())
                auditlog: disnake.TextChannel = self.channelmanager.get_channel(after.guild.id, int(os.getenv("AUDITLOG_CHANNEL_ID")))
                if auditlog:
                    if added_roles or removed_roles:
                        embed = disnake.Embed(
                            title="Rollenaktualisierung", color=0x4169E1)
                        avatar_url = after.avatar.url if after.avatar else after.default_avatar.url
                        embed.set_author(name=after.name, icon_url=avatar_url)
                        embed.add_field(name="Mitglied",
                                        value=after.mention, inline=False)
                        if added_roles:
                            embed.add_field(name="Hinzugefügte Rollen", value=", ".join(
                                [role.mention for role in added_roles]), inline=False)
                        if removed_roles:
                            embed.add_field(name="Entfernte Rollen", value=", ".join(
                                [role.mention for role in removed_roles]), inline=False)
                        embed.set_footer(
                            text=f"ID: {before.id} - heute um {current_datetime.strftime('%H:%M:%S')} Uhr")
                        await auditlog.send(embed=embed)

        except Exception as e:
            self.logger.critical(f"Fehler aufgetreten [on_member_update]: {e}")


def setupReaction(bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
    bot.add_cog(Reaction(bot, rolemanager, channelmanager))
