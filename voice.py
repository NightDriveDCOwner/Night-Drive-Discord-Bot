import disnake
from disnake.ext import commands
from datetime import datetime, timedelta
import logging
from globalfile import Globalfile

class VoiceLogging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("Voice")
        self.logger.setLevel(logging.INFO)
        self.globalfile_instance = Globalfile(bot)        

        # Überprüfen, ob der Handler bereits hinzugefügt wurde
        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
 

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: disnake.member, before: disnake.VoiceState, after: disnake.VoiceState):
        # Überprüfen, ob der Benutzer einen Voice-Channel betritt
        embed = None
        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
        guild = member.guild
        channel = guild.get_channel(1219347644640530553)
        current_datetime = datetime.now()

        def create_embed(title, color):
            embed = disnake.Embed(title=title, color=color)
            embed.set_author(name=member.name, icon_url=avatar_url)
            embed.set_footer(text=f"ID: {member.id} - heute um {(current_datetime + timedelta(hours=1)).strftime('%H:%M:%S')} Uhr")
            return embed
        
        current_datetime = datetime.now()

        if before.channel is None and after.channel is not None:
            self.logger.info(f"{member.name} hat den Voice-Channel {after.channel.name} betreten.")
            embed = create_embed(f"User entered voice channel <#{after.channel.id}>!", 0x4169E1)
        
        elif before.channel is not None and after.channel is None:
            User = await self.globalfile_instance.admin_did_something(disnake.AuditLogAction.member_disconnect, member)
            if User.username == member.name:
                self.logger.info(f"{member.name} hat den Voice-Channel {before.channel.name} verlassen.")
                embed = create_embed(f"User leaved voice channel <#{before.channel.id}>!", 0xFF0000)
            else:
                self.logger.info(f"{member.name} wurde von {User.username}({User.userid}) aus dem Channel {before.channel.name} gekickt.")
                channel = guild.get_channel(1221018527289577582)
                embed = create_embed(f"{member.name} was kicked from {User.username}({User.userid}) out of Channel {before.channel.name}.", 0xFF0000)

        elif before.deaf != after.deaf or before.mute != after.mute or before.self_mute != after.self_mute:
            if after.deaf:
                User = await self.globalfile_instance.admin_did_something(disnake.AuditLogAction.member_update, member)
                if User.username == member.name:
                    self.logger.info(f"{member.name} was generally muted.")
                    embed = create_embed(f"User was generally muted in <#{after.channel.id}>!", 0xFFA500)
                else:
                    self.logger.info(f"{member.name} wurde generell gemuted von {User.username}({User.userid}).")
                    channel = guild.get_channel(1221018527289577582)
                    embed = create_embed(f"{member.name} was generally muted from {User.username}({User.userid}).", 0xFF0000)                    
            elif after.mute:                
                User = await self.globalfile_instance.admin_did_something(disnake.AuditLogAction.member_update, member)
                self.logger.info(f"{member.name}'s Mikrofon wurde von {User.username}({User.userid}) stummgeschaltet.")
                channel = guild.get_channel(1221018527289577582)
                embed = create_embed(f"{member.name} microphone was muted from {User.username}({User.userid}).", 0xFF0000)
            elif after.self_mute:
                if member.voice and member.voice.self_mute:
                    self.logger.info(f"{member.name} microphone was muted.")
                    embed = create_embed(f"Users microphone was muted in <#{after.channel.id}>!", 0xFFA500)
            else:
                if before.self_mute:
                    self.logger.info(f"{member.name} no longer muted.")
                    embed = create_embed(f"User no longer muted <#{after.channel.id}>!", 0x006400)
                else:
                    User = await self.globalfile_instance.admin_did_something(disnake.AuditLogAction.member_update, member)
                    self.logger.info(f"{member.name} wurde von {User.username}({User.userid}) entmuted.")
                    channel = guild.get_channel(1221018527289577582)
                    embed = create_embed(f"{member.name} was unmuted from {User.username}({User.userid}).", 0xFF0000)

        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            self.logger.info(f"{member.name} hat den Voice-Channel {before.channel.name} verlassen und den Voice Channel {after.channel.name} betreten.")
            embed = create_embed(f"User leaved voice channel <#{before.channel.id}> and entered voice channel <#{after.channel.id}>!", 0x4169E1)

        if embed is not None:
            await channel.send(embed=embed)                                               

def setupVoice(bot):
    bot.add_cog(VoiceLogging(bot))
