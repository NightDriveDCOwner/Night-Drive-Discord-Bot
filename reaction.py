import discord
import asyncio
from discord.audit_logs import AuditLogEntry
from discord.ext import commands
from datetime import datetime, timedelta

class Reaction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_data = {} # Initialisieren der user_data Liste
        self.reset_timer() # Starten des Timers zum Löschen der user_data Liste nach 6 Minuten

    def reset_timer(self):
        # Löschen der user_data Liste nach 6 Minuten
        asyncio.create_task(self.clear_user_data_after_6_minutes())

    async def clear_user_data_after_6_minutes(self):
        await asyncio.sleep(6 * 60) # Warten von 6 Minuten
        self.user_data.clear() # Löschen der user_data Li
        self.reset_timer() # Starten des Timers erneut

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is not None:
            if message.channel.id != 1208770898832658493 and message.content:
                print(f"Nachricht von Server {message.guild.name} erhalten: Username: {message.author.name}, Userid: {message.author.id}, Content: {message.content}")
                
                embed = discord.Embed(title="Message send!", color=0x4169E1)
                avatar_url = message.author.avatar.url               
                if avatar_url is None:
                    avatar_url = message.author.default_avatar.url                                 
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
                    async for entry in message.guild.audit_logs(limit=5, action=discord.AuditLogAction.message_delete, after=datetime.now() - timedelta(minutes=65)):                    
                        two_minutes_ago = str(datetime.now() - timedelta(minutes=60,seconds=-35))                                   
                        EntryTime = str(entry.created_at)
                        if entry.user_id in self.user_data:
                            if entry.extra.count > self.user_data[entry.user_id]:
                                self.user_data[entry.user_id] = entry.extra.count
                                DeletedbyAdmin = True
                                break
                            else:
                                DeletedbyAdmin = False
                        else:
                            if entry.extra.count > 0 and entry.extra.count is not None:
                                self.user_data[entry.user_id] = entry.extra.count
                                DeletedbyAdmin = True
                                print(f"Der {entry.user} wurde zur Liste hinzugefügt.")
                                break
                            else:
                                DeletedbyAdmin = False                                

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
                    
                    print(f"Nachricht von Server {message.guild.name} deleted : Username: {message.author.name}, Userid: {message.author.id}, Content: {message.content}, Message deleted by: {deleted_by_name}, User ID: {str(deleted_by_id)}")                                  
                    embed = discord.Embed(title="Message deleted!", color=0xFF0000)                                                 
                    embed.set_author(name=message.author.name, icon_url=avatar_url)               
                    embed.add_field(name="Message:", value=message.content, inline=False)              
                    embed.add_field(name="Deleted by:", value=f"{deleted_by_name} - {str(deleted_by_id)}", inline=False)
                    embed.set_footer(text=f"ID: {message.author.id} - heute um {message.created_at.strftime('%H:%M:%S')} Uhr")

                    channel = message.guild.get_channel(1208770898832658493)
                    await channel.send(embed=embed)
        except discord.HTTPException as e:
            print(f"Error fetching audit logs: {e}")                

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.guild is not None:
            if before.channel.id != 1208770898832658493 and before.content:
                print(f"Nachricht von Server {before.guild.name} edited: Username: {before.author.name}, Userid: {before.author.id}, Content before: {before.content}, Content after: {after.content}")
                
                embed = discord.Embed(title="Message edited!", color=0xFFA500)
                avatar_url = before.author.avatar.url               
                if avatar_url is None:
                    avatar_url = before.author.default_avatar.url                                 
                embed.set_author(name=before.author.name, icon_url=avatar_url)               
                embed.add_field(name="Message before:", value=before.content, inline=False)              
                embed.add_field(name="Message after:", value=after.content, inline=False)              
                embed.set_footer(text=f"ID: {before.author.id} - heute um {before.created_at.strftime('%H:%M:%S')} Uhr")

                channel = before.guild.get_channel(1208770898832658493)
                await channel.send(embed=embed)

def setup(bot):
    bot.add_cog(Reaction(bot))
