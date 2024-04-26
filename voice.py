import disnake
from disnake.ext import commands
from datetime import datetime, timedelta, timedelta

class VoiceLogging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Überprüfen, ob der Benutzer einen Voice-Channel betritt
        embed = None
        avatar_url = member.avatar.url
        if avatar_url is None:
            avatar_url = member.default_avatar.url        

        guild = member.guild  # Zugriff auf die Guild (Server) des Mitglieds
        channel = guild.get_channel(1219347644640530553)            
        
        current_datetime = datetime.now()

        if before.channel is None and after.channel is not None:
            print(f"{member.name} hat den Voice-Channel {after.channel.name} betreten.")
            embed = disnake.Embed(title=f"User entered voice channel <#{after.channel.id}>!", color=0x4169E1)                                                                
            embed.set_author(name=member.name, icon_url=avatar_url)                           
            embed.set_footer(text=f"ID: {member.id} - heute um {(current_datetime + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr")            
        
        # Überprüfen, ob der Benutzer einen Voice-Channel verlässt
        elif before.channel is not None and after.channel is None:
            print(f"{member.name} hat den Voice-Channel {before.channel.name} verlassen.")
            embed = disnake.Embed(title=f"User leaved voice channel <#{before.channel.id}>!", color=0xFF0000)                                                                
            embed.set_author(name=member.name, icon_url=avatar_url)                          
            embed.set_footer(text=f"ID: {member.id} - heute um {(current_datetime + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr")           

        # Überprüfen, ob der Benutzer seine Lautstärke ändert
        elif before.deaf != after.deaf or before.mute != after.mute:
            if after.deaf:
                print(f"{member.name} was generally muted.")
                embed = disnake.Embed(title=f"User was generally muted in <#{after.channel.id}>!", color=0xFFA500)                                                                
                embed.set_author(name=member.name, icon_url=avatar_url)                          
                embed.set_footer(text=f"ID: {member.id} - heute um {(current_datetime + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr")                
            elif after.mute:
                print(f"{member.name} microphone was muted.")
                embed = disnake.Embed(title=f"Users microphone was muted in <#{after.channel.id}>!", color=0xFFA500)                                                                
                embed.set_author(name=member.name, icon_url=avatar_url)                          
                embed.set_footer(text=f"ID: {member.id} - heute um {(current_datetime + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr")                   
            else:
                print(f"{member.name} no longer muted.")
                embed = disnake.Embed(title=f"User no longer muted <#{after.channel.id}>!", color=0x006400)                                                                
                embed.set_author(name=member.name, icon_url=avatar_url)                          
                embed.set_footer(text=f"ID: {member.id} - heute um {(current_datetime + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr")   
        
        elif before.channel is not None and after.channel is not None and before.channel is not after.channel:            
            print(f"{member.name} hat den Voice-Channel {before.channel.name} verlassen und den Voice Channel {after.channel.name} betreten.")
            embed = disnake.Embed(title=f"User leaved voice channel <#{before.channel.id}> and entered voice channel <#{after.channel.id}>!", color=0x4169E1)                                                                
            embed.set_author(name=member.name, icon_url=avatar_url)                          
            embed.set_footer(text=f"ID: {member.id} - heute um {(current_datetime + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr")

        if embed is not None:
            await channel.send(embed=embed)                                               

def setupVoice(bot):
    bot.add_cog(VoiceLogging(bot))
