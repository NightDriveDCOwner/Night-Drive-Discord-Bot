import discord
import asyncio
from discord.audit_logs import AuditLogEntry
from discord.ext import commands
from datetime import datetime, timedelta

class Reaction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_data = {}
        self.TimerMustReseted = True
        self.reset_timer()

    def reset_timer(self):
        asyncio.create_task(self.clear_user_data_after_6_minutes())

    async def clear_user_data_after_6_minutes(self):
        await asyncio.sleep(6 * 60)
        self.user_data.clear()
        self.TimerMustReseted = True

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is not None:
            if message.channel.id != 1208770898832658493 and message.content:                
                
                avatar_url = message.author.avatar.url
                if avatar_url is None:
                    avatar_url = message.author.default_avatar.url

                print(f"Nachricht von Server {message.guild.name} erhalten: Channel: {message.channel.name}, Username: {message.author.name}, Userid: {message.author.id}, Content: {message.content}")                
                embed = discord.Embed(title=f"Message send in <#{message.channel.id}>!", color=0x4169E1)                                                                
                embed.set_author(name=message.author.name, icon_url=avatar_url)               
                embed.add_field(name="Message:", value=message.content, inline=True)              
                embed.set_footer(text=f"ID: {message.author.id} - heute um {message.created_at.strftime('%H:%M:%S')} Uhr")

                channel = message.guild.get_channel(1208770898832658493)
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        def add_user(user_id, number):
            self.user_data[user_id] = number                  
        try:
            if message.guild is not None and message.channel.id != 1208770898832658493 and message.content:                               
                    DeletedbyAdmin = False
                    async for entry in message.guild.audit_logs(limit=5, action=discord.AuditLogAction.message_delete, after=datetime.now() - timedelta(minutes=5)):                                            
                        if entry.extra.count is not None:
                            if self.TimerMustReseted:
                                self.reset_timer()
                                self.TimerMustReseted = False
                            if entry.user_id in self.user_data:
                                if entry.extra.count > self.user_data[entry.user_id]:
                                    self.user_data[entry.user_id] = entry.extra.count
                                    DeletedbyAdmin = True
                                    break
                                else: 
                                    DeletedbyAdmin = False                        
                                    break
                            else:
                                self.user_data[entry.user_id] = entry.extra.count
                                DeletedbyAdmin = True
                                break  
                        else:
                            DeletedbyAdmin = False                                
                            break

                    if DeletedbyAdmin:
                        deleted_by = entry.user
                        deleted_by_name = deleted_by.name
                        deleted_by_id = deleted_by.id
                    else:
                        deleted_by_name = message.author.name
                        deleted_by_id = message.author.id   

                    avatar_url = message.author.avatar.url               
                    if avatar_url is None:
                        avatar_url = message.author.default_avatar.url

                    current_datetime = datetime.now()
                    
                    print(f"Nachricht von Server {message.guild.name} deleted: Channel: {message.channel.name}. Username: {message.author.name}, Userid: {message.author.id}, Content: {message.content}, Message deleted by: {deleted_by_name}, User ID: {str(deleted_by_id)}")                                  
                    embed = discord.Embed(title=f"Message deleted in <#{message.channel.id}>!", color=0xFF0000)                                                 
                    embed.set_author(name=message.author.name, icon_url=avatar_url)               
                    embed.add_field(name="Message:", value=message.content, inline=False)              
                    embed.add_field(name="Deleted by:", value=f"{deleted_by_name} - {str(deleted_by_id)}", inline=False)
                    embed.set_footer(text=f"ID: {message.author.id} - heute um {current_datetime.time().strftime('%H:%M:%S')} Uhr")

                    channel = message.guild.get_channel(1208770898832658493)
                    await channel.send(embed=embed)
        except Exception as e:
            print(f"Error fetching audit logs: {e}")                

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.guild is not None:
            if before.channel.id != 1208770898832658493 and before.content:                          
                
                avatar_url = before.author.avatar.url               
                if avatar_url is None:
                    avatar_url = before.author.default_avatar.url                                 
                
                current_datetime = datetime.now()

                print(f"Nachricht von Server {before.guild.name} edited: Channel {after.channel.name}, Username: {before.author.name}, Userid: {before.author.id}, Content before: {before.content}, Content after: {after.content}")
                embed = discord.Embed(title=f"Message edited in <#{after.channel.id}>!", color=0xFFA500)
                embed.set_author(name=after.author.name, icon_url=avatar_url)               
                embed.add_field(name="Message before:", value=before.content, inline=False)              
                embed.add_field(name="Message after:", value=after.content, inline=False)              
                embed.set_footer(text=f"ID: {before.author.id} - heute um {current_datetime.time().strftime('%H:%M:%S')} Uhr")

                channel = before.guild.get_channel(1208770898832658493)
                await channel.send(embed=embed)

def setup(bot):
    bot.add_cog(Reaction(bot))
