import disnake
from disnake import ButtonStyle, Embed, ui
from disnake.ext import commands
from datetime import datetime, timedelta, timedelta, timezone
import logging
from globalfile import Globalfile
import os
import sqlite3
from dbconnection import DatabaseConnectionManager
from exceptionhandler import exception_handler
from rolemanager import RoleManager
from channelmanager import ChannelManager


class Voice(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
        self.bot = bot
        self.logger = logging.getLogger("Voice")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.globalfile: Globalfile = self.bot.get_cog("Globalfile")
        self.rolemanager = rolemanager
        self.channelmanager = channelmanager

        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler) 
        self.template_channel_id = 1338277012326055967
        self.allowed_category_id = 1069043859998396529

    @commands.Cog.listener()
    async def on_ready(self):                
        self.logger.info("Voice Cog is ready.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: disnake.Member, before: disnake.VoiceState, after: disnake.VoiceState):
        # Überprüfen, ob der Benutzer einen Voice-Channel betritt
        embed = None
        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
        guild = member.guild
        voicelog_channel: disnake.TextChannel = self.channelmanager.get_channel(member.guild.id, int(os.getenv("VOICELOG_CHANNEL_ID")))
        channel = voicelog_channel
        current_datetime = (await self.globalfile.get_current_time())

        def create_embed(title, color):
            embed = disnake.Embed(title=title, color=color)
            embed.set_author(name=member.name, icon_url=avatar_url)
            embed.set_footer(
                text=f"ID: {member.id} - heute um {current_datetime.strftime('%H:%M:%S')} Uhr")
            return embed

        current_datetime = (await self.globalfile.get_current_time())

        if before.channel and before.channel.category_id == self.allowed_category_id and len(before.channel.members) == 0 and before.channel.id != 1338277012326055967:
            self.logger.info(
                f"Der Voice-Channel {before.channel.name} ist leer und wird gelöscht.")
            cursor = await DatabaseConnectionManager.execute_sql_statement(member.guild.id, member.guild.name, "DELETE FROM CUSTOMCHANNEL WHERE CHANNELID = ?", (before.channel.id,))

            await before.channel.delete()

        if before.channel is None and after.channel is not None:
            self.logger.info(
                f"{member.name} hat den Voice-Channel {after.channel.name} betreten.")
            embed = create_embed(
                f"User entered voice channel <#{after.channel.id}>!", 0x4169E1)

        elif before.channel is not None and after.channel is None:
            User = await self.globalfile.admin_did_something(disnake.AuditLogAction.member_disconnect, member, member.guild)
            if User.username == member.name:
                self.logger.info(
                    f"{member.name} hat den Voice-Channel {before.channel.name} verlassen.")
                embed = create_embed(
                    f"User leaved voice channel <#{before.channel.id}>!", 0xFF0000)
            else:
                self.logger.info(
                    f"{member.name} wurde von {User.username}({User.userid}) aus dem Channel {before.channel.name} gekickt.")
                auditlog_channel: disnake.TextChannel = self.channelmanager.get_channel(member.guild.id, int(os.getenv("AUDITLOG_CHANNEL_ID")))
                channel = auditlog_channel
                embed = create_embed(
                    f"{member.name} was kicked from {User.username}({User.userid}) out of Channel {before.channel.name}.", 0xFF0000)

        elif before.deaf != after.deaf or before.mute != after.mute or before.self_mute != after.self_mute:
            if after.deaf:
                User = await self.globalfile.admin_did_something(disnake.AuditLogAction.member_update, member, member.guild)
                if User.username == member.name:
                    self.logger.info(f"{member.name} was generally muted.")
                    embed = create_embed(
                        f"User was generally muted in <#{after.channel.id}>!", 0xFFA500)
                else:
                    self.logger.info(
                        f"{member.name} wurde generell gemuted von {User.username}({User.userid}).")
                    auditlog_channel: disnake.TextChannel = self.channelmanager.get_channel(member.guild.id, int(os.getenv("AUDITLOG_CHANNEL_ID")))
                    channel = auditlog_channel
                    embed = create_embed(
                        f"{member.name} was generally muted from {User.username}({User.userid}).", 0xFF0000)
            elif after.mute:
                User = await self.globalfile.admin_did_something(disnake.AuditLogAction.member_update, member, member.guild)
                self.logger.info(
                    f"{member.name}'s Mikrofon wurde von {User.username}({User.userid}) stummgeschaltet.")
                auditlog_channel: disnake.TextChannel = self.channelmanager.get_channel(member.guild.id, int(os.getenv("AUDITLOG_CHANNEL_ID")))
                channel = auditlog_channel
                embed = create_embed(
                    f"{member.name} microphone was muted from {User.username}({User.userid}).", 0xFF0000)
            elif after.self_mute:
                if member.voice and member.voice.self_mute:
                    self.logger.info(f"{member.name} microphone was muted.")
                    embed = create_embed(
                        f"Users microphone was muted in <#{after.channel.id}>!", 0xFFA500)
            else:
                if before.self_mute:
                    self.logger.info(f"{member.name} no longer muted.")
                    embed = create_embed(
                        f"User no longer muted <#{after.channel.id}>!", 0x006400)
                else:
                    User = await self.globalfile.admin_did_something(disnake.AuditLogAction.member_update, member, member.guild)
                    self.logger.info(
                        f"{member.name} wurde von {User.username}({User.userid}) entmuted.")
                    auditlog_channel: disnake.TextChannel = self.channelmanager.get_channel(member.guild.id, int(os.getenv("AUDITLOG_CHANNEL_ID")))
                    channel = auditlog_channel
                    embed = create_embed(
                        f"{member.name} was unmuted from {User.username}({User.userid}).", 0xFF0000)

        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            self.logger.info(
                f"{member.name} hat den Voice-Channel {before.channel.name} verlassen und den Voice Channel {after.channel.name} betreten.")
            embed = create_embed(
                f"User leaved voice channel <#{before.channel.id}> and entered voice channel <#{after.channel.id}>!", 0x4169E1)

        if embed is not None:
            await channel.send(embed=embed)

        if after.channel and after.channel.id == self.template_channel_id:
            # Erstelle einen neuen Voice-Channel
            category = after.channel.category
            new_voice_channel = await category.create_voice_channel(
                name=f"{member.name}'s Channel",
                overwrites={
                    member.guild.default_role: disnake.PermissionOverwrite(connect=True, speak=True, view_channel=True),
                    member: disnake.PermissionOverwrite(connect=True, speak=True, view_channel=True)
                }
            )

            # Verschiebe den Benutzer in den neuen Voice-Channel
            await member.move_to(new_voice_channel)

            # Sende ein Embed in den Text-Channel
            embed = disnake.Embed(
                title="Channel Steuerung",
                description="Hier sind die Befehle, um deinen Channel zu steuern:",
                color=disnake.Color.blue()
            )

            embed.add_field(name="Channel Management", value=(
                "`/voicerename <name>` - Ändere den Namen des Channels\n"
                "`/setlimit <number>` - Setze die maximale Anzahl der Mitglieder\n"
                "`/deletechannel` - Lösche den Channel\n"
                "`/save` - Speichere den Channel/die Session\n"
            ), inline=False)

            embed.add_field(name="Mitglieder Management", value=(
                "`/voicekick <member>` - Kicke ein Mitglied aus dem Channel\n"
                "`/voiceblock <member>` - Blockiere ein Mitglied vom Channel\n"
                "`/voiceunblock <member>` - Entblockiere ein Mitglied vom Channel\n"
                "`/permit <member>` - Erlaube einem Mitglied den Channel zu betreten\n"
            ), inline=False)

            embed.add_field(name="Channel Sichtbarkeit", value=(
                "`/hide` - Verstecke den Channel\n"
                "`/unhide` - Zeige den Channel wieder\n"
                "`/lock` - Schließe den Channel\n"
                "`/unlock` - Öffne den Channel\n"
            ), inline=False)

            embed.add_field(name="Channel Besitz", value=(
                "`/claim` - Übernehme den Channel\n"
                "`/transfer <member>` - Übertrage den Channel an ein Mitglied\n"
            ), inline=False)

            embed.add_field(name="Sonstiges", value=(
                "`/joinrequest` - Fordere den Beitritt zum Channel an\n"
            ), inline=False)

            await new_voice_channel.send(embed=embed)

            user_record = await self.globalfile.get_user_record(guild=member.guild, discordid=member.id)
            await DatabaseConnectionManager.execute_sql_statement(member.guild.id, member.guild.name, "INSERT INTO CUSTOMCHANNEL (CHANNELID, CHANNELOWNERID, CREATEDAT) VALUES (?,?,?)", (new_voice_channel.id, user_record["ID"], current_datetime))

            # Blockiere bereits blockierte Benutzer vom neuen Voice-Channel
            user_record = await self.globalfile.get_user_record(guild=member.guild, discordid=member.id)
            cursor = await DatabaseConnectionManager.execute_sql_statement(member.guild.id, member.guild.name, "SELECT VALUE FROM BLOCKED_USERS WHERE USERID = ?", (user_record['ID'],))
            blocked_users = await cursor.fetchall()
            for user_id in blocked_users:
                user_record = await self.globalfile.get_user_record(guild=member.guild, user_id=user_id[0])
                guild: disnake.Guild = member.guild
                user = guild.get_member(int(user_record['DISCORDID']))
                if user:
                    await new_voice_channel.set_permissions(user, connect=False)

    @exception_handler
    async def voicecommands(self, inter: disnake.ApplicationCommandInteraction):
        """Zeige alle Voice-Channel-Befehle an."""
        embed = disnake.Embed(
            title="Voice-Channel Befehle",
            description="Hier sind die Befehle, um deinen Voice-Channel zu steuern:",
            color=disnake.Color.blue()
        )

        embed.add_field(name="Channel Management", value=(
            "`/voicerename <name>` - Ändere den Namen des Channels\n"
            "`/setlimit <number>` - Setze die maximale Anzahl der Mitglieder\n"
            "`/deletechannel` - Lösche den Channel\n"
            "`/save` - Speichere den Channel/die Session\n"
        ), inline=False)

        embed.add_field(name="Mitglieder Management", value=(
            "`/voicekick <member>` - Kicke ein Mitglied aus dem Channel\n"
            "`/voiceblock <member>` - Blockiere ein Mitglied vom Channel\n"
            "`/voiceunblock <member>` - Entblockiere ein Mitglied vom Channel\n"
            "`/permit <member>` - Erlaube einem Mitglied den Channel zu betreten\n"
        ), inline=False)

        embed.add_field(name="Channel Sichtbarkeit", value=(
            "`/hide` - Verstecke den Channel\n"
            "`/unhide` - Zeige den Channel wieder\n"
            "`/lock` - Schließe den Channel\n"
            "`/unlock` - Öffne den Channel\n"
        ), inline=False)

        embed.add_field(name="Channel Besitz", value=(
            "`/claim` - Übernehme den Channel\n"
            "`/transfer <member>` - Übertrage den Channel an ein Mitglied\n"
        ), inline=False)

        embed.add_field(name="Sonstiges", value=(
            "`/joinrequest` - Fordere den Beitritt zum Channel an\n"
        ), inline=False)

        await inter.response.send_message(embed=embed, ephemeral=False)

    @exception_handler
    async def is_channel_owner(self, user: disnake.Member, channel: disnake.VoiceChannel) -> bool:
        cursor = await DatabaseConnectionManager.execute_sql_statement(channel.guild.id, channel.guild.name, "SELECT CHANNELOWNERID FROM CUSTOMCHANNEL WHERE CHANNELID = ?", (channel.id,))
        owner_id = (await cursor.fetchone())
        if owner_id and owner_id[0] == (await self.globalfile.get_user_record(guild=channel.guild, discordid=user.id))['ID']:
            return True
        return False

    @exception_handler
    async def _voicerename(self, inter: disnake.ApplicationCommandInteraction, name: str):
        """Ändere den Namen des Voice-Channels."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                if await self.is_channel_owner(inter.author, inter.author.voice.channel):
                    await inter.author.voice.channel.edit(name=name)
                    await inter.response.send_message(f"Channel-Name geändert zu {name}", ephemeral=True)
                else:
                    await inter.response.send_message("Nur der Channel-Owner kann diesen Befehl ausführen.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _setlimit(self, inter: disnake.ApplicationCommandInteraction, limit: int):
        """Setze die maximale Anzahl der Mitglieder im Voice-Channel."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                if await self.is_channel_owner(inter.author, inter.author.voice.channel):
                    await inter.author.voice.channel.edit(user_limit=limit)
                    await inter.response.send_message(f"Mitgliederlimit gesetzt auf {limit}", ephemeral=True)
                else:
                    await inter.response.send_message("Nur der Channel-Owner kann diesen Befehl ausführen.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _voicekick(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Kicke ein Mitglied aus dem Voice-Channel."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                if await self.is_channel_owner(inter.author, inter.author.voice.channel):
                    if member.voice and member.voice.channel == inter.author.voice.channel:
                        await member.move_to(None)
                        await inter.response.send_message(f"{member.name} wurde aus dem Channel gekickt.", ephemeral=True)
                    else:
                        await inter.response.send_message(f"{member.name} ist nicht in deinem Voice-Channel.", ephemeral=True)
                else:
                    await inter.response.send_message("Nur der Channel-Owner kann diesen Befehl ausführen.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _voiceblock(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Blockiere ein Mitglied vom Voice-Channel."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                if await self.is_channel_owner(inter.author, inter.author.voice.channel):
                    await inter.author.voice.channel.set_permissions(member, connect=False)
                    userid = (await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id))['ID']
                    blocked_userid = (await self.globalfile.get_user_record(guild=inter.guild, discordid=member.id))['ID']
                    await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "INSERT OR IGNORE INTO BLOCKED_USERS (USERID,VALUE) VALUES (?,?)", (int(userid), int(blocked_userid)))

                    if member.voice and member.voice.channel == inter.author.voice.channel:
                        await member.move_to(None)
                    await inter.response.send_message(f"{member.name} wurde vom Channel blockiert.", ephemeral=True)
                else:
                    await inter.response.send_message("Nur der Channel-Owner kann diesen Befehl ausführen.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _voiceunblock(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Entblockiere ein Mitglied vom Voice-Channel."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                if await self.is_channel_owner(inter.author, inter.author.voice.channel):
                    await inter.author.voice.channel.set_permissions(member, connect=True)
                    userid = (await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id))['ID']
                    blocked_userid = (await self.globalfile.get_user_record(guild=inter.guild, discordid=member.id))['ID']
                    cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "DELETE FROM BLOCKED_USERS WHERE USERID = ? AND VALUE = ?", (int(userid), int(blocked_userid)))

                    await inter.response.send_message(f"{member.name} wurde vom Channel entblockiert.", ephemeral=True)
                else:
                    await inter.response.send_message("Nur der Channel-Owner kann diesen Befehl ausführen.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _deletechannel(self, inter: disnake.ApplicationCommandInteraction):
        """Lösche den Voice-Channel."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                if await self.is_channel_owner(inter.author, inter.author.voice.channel):
                    await inter.author.voice.channel.delete()
                    await inter.response.send_message("Channel wurde gelöscht.", ephemeral=True)
                else:
                    await inter.response.send_message("Nur der Channel-Owner kann diesen Befehl ausführen.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _hide(self, inter: disnake.ApplicationCommandInteraction):
        """Verstecke den Voice-Channel."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                if await self.is_channel_owner(inter.author, inter.author.voice.channel):
                    await inter.author.voice.channel.set_permissions(inter.guild.default_role, view_channel=False)
                    await inter.author.voice.channel.set_permissions(inter.author, view_channel=True)
                    await inter.response.send_message("Channel wurde versteckt.", ephemeral=True)
                else:
                    await inter.response.send_message("Nur der Channel-Owner kann diesen Befehl ausführen.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _unhide(self, inter: disnake.ApplicationCommandInteraction):
        """Zeige den Voice-Channel wieder."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                if await self.is_channel_owner(inter.author, inter.author.voice.channel):
                    await inter.author.voice.channel.set_permissions(inter.guild.default_role, view_channel=True)
                    await inter.response.send_message("Channel wurde wieder angezeigt.", ephemeral=True)
                else:
                    await inter.response.send_message("Nur der Channel-Owner kann diesen Befehl ausführen.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _lock(self, inter: disnake.ApplicationCommandInteraction):
        """Schließe den Voice-Channel."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                if await self.is_channel_owner(inter.author, inter.author.voice.channel):
                    await inter.author.voice.channel.set_permissions(inter.guild.default_role, connect=False)
                    await inter.response.send_message("Channel wurde geschlossen.", ephemeral=True)
                else:
                    await inter.response.send_message("Nur der Channel-Owner kann diesen Befehl ausführen.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _unlock(self, inter: disnake.ApplicationCommandInteraction):
        """Öffne den Voice-Channel."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                if await self.is_channel_owner(inter.author, inter.author.voice.channel):
                    await inter.author.voice.channel.set_permissions(inter.guild.default_role, connect=True)
                    await inter.response.send_message("Channel wurde geöffnet.", ephemeral=True)
                else:
                    await inter.response.send_message("Nur der Channel-Owner kann diesen Befehl ausführen.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _permit(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Erlaube einem Mitglied den Voice-Channel zu betreten."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                if await self.is_channel_owner(inter.author, inter.author.voice.channel):
                    await inter.author.voice.channel.set_permissions(member, connect=True)
                    await inter.response.send_message(f"{member.name} wurde der Zugang zum Channel erlaubt.", ephemeral=True)
                else:
                    await inter.response.send_message("Nur der Channel-Owner kann diesen Befehl ausführen.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _claim(self, inter: disnake.ApplicationCommandInteraction):
        """Übernehme den Voice-Channel."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT CHANNELOWNERID FROM CUSTOMCHANNEL WHERE CHANNELID = ?", (inter.author.voice.channel.id,))
                owner_id = (await cursor.fetchone())
                if owner_id:
                    channel_owner = inter.guild.get_member(int(owner_id[0]))
                    if channel_owner and channel_owner.voice and channel_owner.voice.channel == inter.author.voice.channel:
                        await inter.response.send_message("Der aktuelle Channel-Owner ist noch im Channel.", ephemeral=True)
                    else:
                        user_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
                        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "UPDATE CUSTOMCHANNEL SET CHANNELOWNERID = ? WHERE CHANNELID = ?", (user_record['ID'], inter.author.voice.channel.id))

                        await inter.response.send_message("Du hast den Channel übernommen.", ephemeral=True)
                else:
                    await inter.response.send_message("Channel-Owner konnte nicht gefunden werden.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _transfer(self, inter: disnake.ApplicationCommandInteraction, member: disnake.Member):
        """Übertrage den Voice-Channel an ein Mitglied."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT CHANNELOWNERID FROM CUSTOMCHANNEL WHERE CHANNELID = ?", (inter.author.voice.channel.id,))
                owner_id = (await cursor.fetchone())
                if owner_id and owner_id[0] == (await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id))['ID']:
                    user_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=member.id)
                    await inter.author.voice.channel.set_permissions(inter.author, view_channel=False)
                    await inter.author.voice.channel.set_permissions(member, view_channel=True)
                    cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "UPDATE CUSTOMCHANNEL SET CHANNELOWNERID = ? WHERE CHANNELID = ?", (user_record['ID'], inter.author.voice.channel.id))

                    await inter.response.send_message(f"Du hast den Channel an {member.name} übertragen.", ephemeral=True)
                else:
                    await inter.response.send_message("Nur der Channel-Owner kann diesen Befehl ausführen.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _save(self, inter: disnake.ApplicationCommandInteraction):
        """Speichere den Voice-Channel/die Session."""
        if inter.author.voice and inter.author.voice.channel:
            if inter.author.voice.channel.category_id == self.allowed_category_id:
                user_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
                await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "INSERT INTO SAVESESSIONS (USERID, CHANNELNAME, CHANNELLIMIT) VALUES (?, ?, ?)",
                                                                      (user_record['ID'], inter.author.voice.channel.name, inter.author.voice.channel.user_limit))

                await inter.response.send_message("Channel/Session wurde gespeichert.", ephemeral=True)
            else:
                await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)
        else:
            await inter.response.send_message("Du bist in keinem Voice-Channel.", ephemeral=True)

    @exception_handler
    async def _joinrequest(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.VoiceChannel):
        """Fordere den Beitritt zum Voice-Channel an."""
        if channel.category_id == self.allowed_category_id:
            cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT CHANNELOWNERID FROM CUSTOMCHANNEL WHERE CHANNELID = ?", (channel.id,))
            owner_id = (await cursor.fetchone())
            if owner_id:
                user_record = await self.globalfile.get_user_record(guild=inter.guild, userid=owner_id[0])
                channel_owner = inter.guild.get_member(
                    int(user_record['DISCORDID']))
                if channel_owner:
                    embed = Embed(
                        title="Beitrittsanfrage",
                        description=f"{inter.author.mention} möchte dem Voice-Channel {channel.mention} beitreten.",
                        color=disnake.Color.blue()
                    )
                    view = ui.View(timeout=90)  # Set the timeout to 90 seconds
                    view.add_item(ui.Button(label="Beitritt gestatten",
                                  style=ButtonStyle.green, custom_id="allow_join"))
                    view.add_item(ui.Button(label="Beitritt ablehnen",
                                  style=ButtonStyle.red, custom_id="deny_join"))

                    await inter.response.send_message(content=channel_owner.mention, embed=embed, view=view, ephemeral=True)

                    async def button_callback(interaction: disnake.MessageInteraction):
                        if interaction.user != channel_owner:
                            await interaction.response.send_message("Nur der Channel-Owner kann diese Aktion ausführen.", ephemeral=True)
                            return

                        if interaction.custom_id == "allow_join":
                            await channel.set_permissions(inter.user, connect=True)
                            await interaction.response.edit_message(content=f"{inter.user.mention} darf dem Channel beitreten.", embed=None, view=None)
                            await interaction.followup.send(f"[Hier klicken, um dem Channel beizutreten]({channel.jump_url})", ephemeral=True)
                        elif interaction.custom_id == "deny_join":
                            await interaction.response.edit_message(content="Beitrittsanfrage abgelehnt.", embed=None, view=None)

                    view.children[0].callback = button_callback
                    view.children[1].callback = button_callback

                    async def on_timeout():
                        await inter.edit_original_message(content="Die Beitrittsanfrage ist abgelaufen.", embed=None, view=None)

                    view.on_timeout = on_timeout
                else:
                    await inter.response.send_message("Channel-Owner konnte nicht gefunden werden.", ephemeral=True)
            else:
                await inter.response.send_message("Channel-Owner konnte nicht gefunden werden.", ephemeral=True)
        else:
            await inter.response.send_message("Dieser Befehl kann nur in einer bestimmten Kategorie verwendet werden.", ephemeral=True)


def setupVoice(bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
    bot.add_cog(Voice(bot, rolemanager, channelmanager))
