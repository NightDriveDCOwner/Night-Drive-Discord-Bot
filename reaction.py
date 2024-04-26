import disnake
import asyncio
from globalfile import Globalfile
from collections import namedtuple
import disnake.message
import disnake.audit_logs
from disnake.ext import commands
from datetime import datetime, timedelta, timedelta
from moderation import Moderation

class Reaction(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_data = {}
        self.TimerMustReseted = True      
        self.globalfile_instance = Globalfile(bot)   
        self.moderation = Moderation(bot)     

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
                            print(f"Nachricht von Server {message.guild.name} erhalten: Channel: {message.channel.name}, Username: {message.author.name}, Userid: {message.author.id}, Content: {message.content}")                
                            embed = disnake.Embed(title=f"Message send in <#{message.channel.id}>!", color=0x4169E1)                                                                
                            embed.set_author(name=message.author.name, icon_url=avatar_url)               
                            embed.add_field(name="Message:", value=message.content, inline=True)              
                            embed.set_footer(text=f"ID: {message.author.id} - heute um {(message.created_at + timedelta(hours=2)).strftime('%H:%M:%S')} Uhr \nMessage-ID: {message.id}")
                            if message.attachments:
                                embed.set_image(url=message.attachments[0].url)
            
                            channel = message.guild.get_channel(1208770898832658493)
                            await channel.send(embed=embed)
        except Exception as e:
            print(f"Fehler aufgetreten: {e}")        

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
                    
                    print(f"Nachricht von Server {message.guild.name} deleted: Channel: {message.channel.name}. Username: {message.author.name}, Userid: {message.author.id}, Content: {message.content}, Message deleted by: {User.username}, User ID: {str(User.userid)}")                                  
                    embed = disnake.Embed(title=f"Message deleted in <#{message.channel.id}>!", color=0xFF0000)                                                 
                    embed.set_author(name=message.author.name, icon_url=avatar_url)               
                    embed.add_field(name="Message:", value=message.content, inline=False)              
                    embed.add_field(name="Deleted by:", value=f"{User.username} - {str(User.userid)}", inline=False)
                    embed.set_footer(text=f"ID: {message.author.id} - heute um {(current_datetime + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr \nMessage-ID: {message.id}")

                    channel = message.guild.get_channel(1208770898832658493)
                    await channel.send(embed=embed)
                except Exception as e:
                    print(f"Fehler aufgetreten: {e}")

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

                    print(f"Nachricht von Server {before.guild.name} edited: Channel {after.channel.name}, Username: {before.author.name}, Userid: {before.author.id}, Content before: {before.content}, Content after: {after.content}")
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
                print(f"Fehler aufgetreten: {e}")
                   
def setupReaction(bot):
    bot.add_cog(Reaction(bot))
