import disnake
import asyncio
from globalfile import Globalfile
from collections import namedtuple
import disnake.message
import disnake.audit_logs
from disnake.ext import commands
from datetime import datetime, timedelta, timedelta
from moderation import Moderation
import logging

class Reaction(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_data = {}
        self.TimerMustReseted = True      
        self.globalfile_instance = Globalfile(bot)   
        self.moderation = Moderation(bot)    
        self.logger = logging.getLogger("Reaction")
        formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

 

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        try:
            botrolle = message.guild.get_role(854698446996766738)
            if message.guild is not None:
                if message.content != "" or len(message.attachments) > 0:
                    if message.channel.id != 1208770898832658493 and message.channel.id != 1219347644640530553:
                        if not botrolle in message.author.roles:                                
                            avatar_url = message.author.avatar.url
                            if avatar_url is None:
                                avatar_url = message.author.default_avatar.url  

                            await self.moderation.check_message_for_badwords(message)
                            self.logger.info(f"Nachricht von Server {message.guild.name} erhalten: Channel: {message.channel.name}, Username: {message.author.name}, Userid: {message.author.id}, Content: {message.content}")                
                            embed = disnake.Embed(title=f"Message send in <#{message.channel.id}>!", color=0x4169E1)                                                                
                            embed.set_author(name=message.author.name, icon_url=avatar_url)               
                            embed.add_field(name="Message:", value=message.content, inline=True)              
                            embed.set_footer(text=f"ID: {message.author.id} - heute um {(message.created_at + timedelta(hours=2)).strftime('%H:%M:%S')} Uhr \nMessage-ID: {message.id}")
                            if message.attachments:
                                embed.set_image(url=message.attachments[0].url)
            
                            channel = message.guild.get_channel(1208770898832658493)
                            await channel.send(embed=embed)
        except Exception as e:
            self.logger.critical(f"Fehler aufgetreten: {e}")        

    @commands.Cog.listener()
    async def on_message_delete(self, message: disnake.Message):      
        botrolle = message.guild.get_role(854698446996766738)                     
        if message.guild is not None and message.channel.id != 1208770898832658493 and message.channel.id != 1219347644640530553: 
            if not botrolle in message.author.roles:                               
                try:
                    User = await self.globalfile_instance.admin_did_something(disnake.AuditLogAction.message_delete, message.author)
                    avatar_url = message.author.avatar.url               
                    if avatar_url is None:
                        avatar_url = message.author.default_avatar.url

                    current_datetime = datetime.now()
                    
                    self.logger.info(f"Nachricht von Server {message.guild.name} deleted: Channel: {message.channel.name}. Username: {message.author.name}, Userid: {message.author.id}, Content: {message.content}, Message deleted by: {User.username}, User ID: {str(User.userid)}")                                  
                    embed = disnake.Embed(title=f"Message deleted in <#{message.channel.id}>!", color=0xFF0000)                                                 
                    embed.set_author(name=message.author.name, icon_url=avatar_url)               
                    embed.add_field(name="Message:", value=message.content, inline=False)              
                    embed.add_field(name="Deleted by:", value=f"{User.username} - {str(User.userid)}", inline=False)
                    embed.set_footer(text=f"ID: {message.author.id} - heute um {(current_datetime + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr \nMessage-ID: {message.id}")

                    if User.username == message.author.name:
                        channel = message.guild.get_channel(1208770898832658493)
                    else:
                        channel = message.guild.get_channel(1221018527289577582)
                    await channel.send(embed=embed)
                except Exception as e:
                    self.logger.critical(f"Fehler aufgetreten: {e}")   

    @commands.Cog.listener()
    async def on_message_edit(self, before: disnake.Message, after: disnake.Message):
        try:
            if before.guild is not None:
                botrolle = before.guild.get_role(854698446996766738)              
                if before.channel.id != 1208770898832658493 and before.channel.id != 1219347644640530553 and not botrolle in before.author.roles:                                              
                    avatar_url = before.author.avatar.url               
                    if avatar_url is None:
                        avatar_url = before.author.default_avatar.url                                 
                    
                    current_datetime = datetime.now()

                    self.logger.info(f"Nachricht von Server {before.guild.name} edited: Channel {after.channel.name}, Username: {before.author.name}, Userid: {before.author.id}, Content before: {before.content}, Content after: {after.content}")
                    embed = disnake.Embed(title=f"Message edited in <#{after.channel.id}>!", color=0xFFA500)
                    embed.set_author(name=after.author.name, icon_url=avatar_url)               
                    embed.add_field(name="Message before:", value=before.content, inline=False)              
                    embed.add_field(name="Message after:", value=after.content, inline=False)              
                    embed.set_footer(text=f"ID: {before.author.id} - heute um {(current_datetime + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr \nMessage-ID: {before.id}")
                    if before.attachments:
                        embed.set_image(url=before.attachments[0].url)

                    channel = before.guild.get_channel(1208770898832658493)
                    await channel.send(embed=embed)
        except Exception as e:
                self.logger.critical(f"Fehler aufgetreten: {e}")

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

                current_datetime = datetime.now()
                log_channel_id = 1221018527289577582
                log_channel = self.bot.get_channel(log_channel_id)
                if log_channel:
                    if not added_roles == None and not removed_roles == None:
                        embed = disnake.Embed(title="Rollenaktualisierung", color=0x4169E1)
                    elif not added_roles == None:
                        embed = disnake.Embed(title="Member update: Rolle wurde entfernt", color=0x4169E1)
                    elif not removed_roles == None:
                        embed = disnake.Embed(title="Member update: Rolle wurde hinzugefügt", color=0x4169E1)
                    
                    avatar_url = after.avatar.url               
                    if avatar_url is None:
                        avatar_url = after.default_avatar.url  

                    embed.set_author(name=after.name, icon_url=avatar_url)
                    embed.add_field(name="Mitglied", value=after.mention, inline=False)
                    if not added_roles == None:                        
                        embed.add_field(name="Hinzugefügte Rollen", value=", ".join([role.mention for role in added_roles]), inline=False)
                    if not removed_roles == None:
                        embed.add_field(name="Entfernte Rollen", value=", ".join([role.mention for role in removed_roles]), inline=False)                        
                    embed.set_footer(text=f"ID: {before.id} - heute um {(current_datetime + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr")
                    await log_channel.send(embed=embed)

        except Exception as e:
            self.logger.critical(f"Fehler aufgetreten: {e}")    

def setupReaction(bot):
    bot.add_cog(Reaction(bot))
