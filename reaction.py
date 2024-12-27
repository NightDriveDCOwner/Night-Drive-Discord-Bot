import disnake
import asyncio
from globalfile import Globalfile
from collections import namedtuple
import disnake.message
import disnake.audit_logs
from disnake.ext import commands
from datetime import datetime, timedelta, timedelta, timezone
from moderation import Moderation
import logging
from DBConnection import DatabaseConnection
import os

class Reaction(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_data = {}
        self.TimerMustReseted = True      
        self.globalfile_instance = Globalfile(bot)   
        self.moderation = Moderation(bot)    
        self.logger = logging.getLogger("Reaction")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper() 
        self.logger.setLevel(logging_level)    
        self.globalfile = Globalfile(bot)        
        self.db = DatabaseConnection()

        # Überprüfen, ob der Handler bereits hinzugefügt wurde
        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        try:
            if message.guild is not None:
                botrolle = message.guild.get_role(854698446996766738)
                member = await self.globalfile.get_member_from_user(message.author, message.guild.id)
                if member and (message.content != "" or len(message.attachments) > 0):
                    if message.channel.id != 1208770898832658493 and message.channel.id != 1219347644640530553:
                        if botrolle not in member.roles:                                
                            avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                            current_datetime = self.globalfile.get_current_time()
                            await self.moderation.check_message_for_badwords(message)
                            self.logger.info(f"Nachricht von Server {message.guild.name} erhalten: Channel: {message.channel.name}, Username: {member.name}, Userid: {member.id}, Content: {message.content}")                
                            embed = disnake.Embed(title=f"Message send in <#{message.channel.id}>!", color=0x4169E1)                                                                
                            embed.set_author(name=member.name, icon_url=avatar_url)               
                            embed.add_field(name="Message:", value=message.content, inline=True)              
                            embed.set_footer(text=f"ID: {member.id} - heute um {current_datetime.strftime('%H:%M:%S')} Uhr \nMessage-ID: {message.id}")
                            if message.attachments:
                                embed.set_image(url=message.attachments[0].url)
            
                            channel = message.guild.get_channel(1208770898832658493)
                            await channel.send(embed=embed)
        except Exception as e:
            self.logger.critical(f"Fehler aufgetreten [on_message]: {e}") 

    @commands.Cog.listener()
    async def on_message_delete(self, message: disnake.Message):      
        if message.guild is not None:        
            botrolle = message.guild.get_role(854698446996766738)                     
            member = await self.globalfile.get_member_from_user(message.author, message.guild.id)
            if member and message.channel.id != 1208770898832658493 and message.channel.id != 1219347644640530553: 
                if botrolle not in member.roles:                               
                    try:
                        User = await self.globalfile_instance.admin_did_something(disnake.AuditLogAction.message_delete, message.guild, member)
                        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url

                        current_datetime = self.globalfile.get_current_time()
                        
                        self.logger.info(f"Nachricht von Server {message.guild.name} deleted: Channel: {message.channel.name}. Username: {member.name}, Userid: {member.id}, Content: {message.content}, Message deleted by: {User.username}, User ID: {str(User.userid)}")                                  
                        embed = disnake.Embed(title=f"Message deleted in <#{message.channel.id}>!", color=0xFF0000)                                                 
                        embed.set_author(name=member.name, icon_url=avatar_url)               
                        embed.add_field(name="Message:", value=message.content, inline=False)              
                        embed.add_field(name="Deleted by:", value=f"{User.username} - {str(User.userid)}", inline=False)
                        embed.set_footer(text=f"ID: {member.id} - heute um {current_datetime.strftime('%H:%M:%S')} Uhr \nMessage-ID: {message.id}")

                        if User.username == member.name:
                            channel = message.guild.get_channel(1208770898832658493)
                        else:
                            channel = message.guild.get_channel(1221018527289577582)


                        # Ermitteln der USERID des Admins, der die Nachricht gelöscht hat
                        cursor = self.db.connection.cursor()
                        cursor.execute("SELECT ID FROM USER WHERE DISCORDID = ?", (User.userid,))
                        admin_user_id = cursor.fetchone()
                        if admin_user_id:
                            admin_user_id = admin_user_id[0]

                        # Aktualisieren der Nachricht in der Datenbank mit DELETED_BY
                        cursor.execute("UPDATE MESSAGE SET DELETED_BY = ? WHERE MESSAGEID = ? AND CHANNELID = ?", (admin_user_id, message.id, message.channel.id))
                        self.db.connection.commit()
                        await channel.send(embed=embed)                        
                    except Exception as e:
                        self.logger.critical(f"Fehler aufgetreten [on_message_delete]: {e}")  

    @commands.Cog.listener()
    async def on_message_edit(self, before: disnake.Message, after: disnake.Message):
        try:
            if before.guild is not None:
                botrolle = before.guild.get_role(854698446996766738)              
                member = await self.globalfile.get_member_from_user(before.author, before.guild.id)
                if member and before.channel.id != 1208770898832658493 and before.channel.id != 1219347644640530553 and botrolle not in member.roles:                                              
                    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                    current_datetime = self.globalfile.get_current_time()

                    self.logger.info(f"Nachricht von Server {before.guild.name} edited: Channel {after.channel.name}, Username: {member.name}, Userid: {member.id}, Content before: {before.content}, Content after: {after.content}")
                    embed = disnake.Embed(title=f"Message edited in <#{after.channel.id}>!", color=0xFFA500)
                    embed.set_author(name=member.name, icon_url=avatar_url)               
                    embed.add_field(name="Message before:", value=before.content, inline=False)              
                    embed.add_field(name="Message after:", value=after.content, inline=False)              
                    embed.set_footer(text=f"ID: {member.id} - heute um {current_datetime.strftime('%H:%M:%S')} Uhr \nMessage-ID: {before.id}")
                    if before.attachments:
                        embed.set_image(url=before.attachments[0].url)

                    channel = before.guild.get_channel(1208770898832658493)

                    # Ermitteln der MESSAGE_BEFORE-ID
                    cursor = self.db.connection.cursor()
                    cursor.execute("SELECT ID FROM MESSAGE WHERE MESSAGEID = ? AND CHANNELID = ?", (before.id, before.channel.id))
                    message_before_id = cursor.fetchone()
                    if message_before_id:
                        message_before_id = message_before_id[0]
                    
                    userrecord = self.globalfile.get_user_record(discordid=member.id)
                    # Speichern der bearbeiteten Nachricht in der Datenbank
                    current_datetime = self.globalfile.get_current_time().strftime('%Y-%m-%d %H:%M:%S')
                    image_paths = [attachment.url for attachment in after.attachments]
                    if len(image_paths) != 0:
                        image_path_fields = ", " + ', '.join([f"IMAGEPATH{i+1}" for i in range(len(image_paths))])
                        image_path_values = ", " + ', '.join(['?' for _ in range(len(image_paths))])
                    else:
                        image_path_fields = ""
                        image_path_values = ""
                    query = f"INSERT INTO MESSAGE (CONTENT, USERID, CHANNELID, MESSAGEID, MESSAGE_BEFORE, INSERT_DATE{image_path_fields}) VALUES (?, ?, ?, ?, ?, ?{image_path_values})"
                    cursor.execute(query, (after.content, userrecord['ID'], after.channel.id, after.id, message_before_id, current_datetime, *image_paths))
                    self.db.connection.commit()
                    await channel.send(embed=embed)                    
        except Exception as e:
            self.logger.critical(f"Fehler aufgetreten [on_message_edit]: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before: disnake.Member, after: disnake.Member):
        try:
            # Überprüfen, ob sich die Rollen des Mitglieds geändert haben
            if before.roles != after.roles:
                added_roles = [role for role in after.roles if role not in before.roles]
                removed_roles = [role for role in before.roles if role not in after.roles]

                for role in added_roles:
                    self.logger.info(f"Rolle hinzugefügt: {role.name} für {after.name} ({after.id})")

                for role in removed_roles:
                    self.logger.info(f"Rolle entfernt: {role.name} von {after.name} ({after.id})")

                current_datetime = self.globalfile.get_current_time()
                log_channel_id = 1221018527289577582
                log_channel = self.bot.get_channel(log_channel_id)
                if log_channel:
                    if added_roles or removed_roles:
                        embed = disnake.Embed(title="Rollenaktualisierung", color=0x4169E1)
                        avatar_url = after.avatar.url if after.avatar else after.default_avatar.url
                        embed.set_author(name=after.name, icon_url=avatar_url)
                        embed.add_field(name="Mitglied", value=after.mention, inline=False)
                        if added_roles:                        
                            embed.add_field(name="Hinzugefügte Rollen", value=", ".join([role.mention for role in added_roles]), inline=False)
                        if removed_roles:
                            embed.add_field(name="Entfernte Rollen", value=", ".join([role.mention for role in removed_roles]), inline=False)                        
                        embed.set_footer(text=f"ID: {before.id} - heute um {current_datetime.strftime('%H:%M:%S')} Uhr")
                        await log_channel.send(embed=embed)

        except Exception as e:
            self.logger.critical(f"Fehler aufgetreten [on_member_update]: {e}")     

    @commands.Cog.listener()
    async def on_member_remove(self, member: disnake.Member):
        try:
            current_datetime = self.globalfile.get_current_time()
            log_channel_id = 854698447113027594  # Replace with your log channel ID
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel:
                embed = disnake.Embed(title="Mitglied hat den Server verlassen", color=0xFF0000)
                avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                embed.set_author(name=member.name, icon_url=avatar_url)
                embed.add_field(name="Mitglied", value=member.mention, inline=False)
                embed.set_footer(text=f"ID: {member.id} - heute um {current_datetime.strftime('%H:%M:%S')} Uhr")
                await log_channel.send(embed=embed)

        except Exception as e:
            self.logger.critical(f"Fehler aufgetreten [on_member_remove]: {e}")

    

def setupReaction(bot):
    bot.add_cog(Reaction(bot))
