import disnake
from disnake.ext import commands
from datetime import datetime, timedelta, timedelta, timezone
import logging
from globalfile import Globalfile
import os

class VoiceLogging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("Voice")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper() 
        self.logger.setLevel(logging_level)
        self.globalfile = Globalfile(bot)        

        # Überprüfen, ob der Handler bereits hinzugefügt wurde
        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
 
        self.channel_limits = {
            "✨│Taverne I": 12,
            "✨│Taverne II": 6,
            "✨│Taverne III": 4,
            "✨│Taverne IV": 3,
            "✨│Taverne V": 2
        }
        self.alternative_channels = {}

    def get_next_roman_numeral(self):
        roman_numerals = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"]
        highest_numeral = "I"
        
        for channel_name in self.channel_limits.keys():
            for numeral in roman_numerals:
                if numeral in channel_name:
                    highest_numeral = numeral if roman_numerals.index(numeral) > roman_numerals.index(highest_numeral) else highest_numeral

        next_index = roman_numerals.index(highest_numeral) + 1
        if next_index < len(roman_numerals):
            return roman_numerals[next_index]
        return "I"  # Fallback if all numerals are used

    def replace_roman_numeral(self, name: str, new_numeral: str):
        roman_numerals = ["XX", "XIX", "XVIII", "XVII", "XVI", "XV", "XIV", "XIII", "XII", "XI", "X", "IX", "VIII", "VII", "VI", "V", "IV", "III", "II", "I"]
        for numeral in roman_numerals:
            if name.endswith(f" {numeral}"):
                return name.replace(f" {numeral}", f" {new_numeral}")
        return f"{name} {new_numeral}"

    async def create_alternative_channel(self, guild: disnake.Guild, base_channel: disnake.VoiceChannel, limit):
        category = base_channel.category
        next_numeral = self.get_next_roman_numeral()
        new_channel_name = self.replace_roman_numeral(base_channel.name, next_numeral)
        new_channel = await guild.create_voice_channel(new_channel_name, category=category, user_limit=limit)
        await new_channel.edit(position=guild.get_channel(1066712410376904774).position)
        self.logger.info(f"Created new channel: {new_channel_name} with limit {limit}")
        self.alternative_channels[base_channel.id] = new_channel.id
        self.channel_limits[new_channel_name] = limit  # Add new channel to channel_limits
        return new_channel

    async def delete_alternative_channel(self, guild: disnake.Guild, base_channel: disnake.VoiceChannel):
        if base_channel.id in self.alternative_channels:
            alt_channel_id = self.alternative_channels[base_channel.id]
            alt_channel = guild.get_channel(alt_channel_id)
            if alt_channel and len(alt_channel.members) == 0:
                await alt_channel.delete()
                self.logger.info(f"Deleted channel: {alt_channel.name}")
                del self.alternative_channels[base_channel.id]
                del self.channel_limits[alt_channel.name]  # Remove channel from channel_limits


    @commands.Cog.listener()
    async def on_voice_state_update(self, member: disnake.Member, before: disnake.VoiceState, after: disnake.VoiceState):
        # Überprüfen, ob der Benutzer einen Voice-Channel betritt
        embed = None
        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
        guild = member.guild
        channel = guild.get_channel(1219347644640530553)
        current_datetime = self.globalfile.get_current_time()

        def create_embed(title, color):
            embed = disnake.Embed(title=title, color=color)
            embed.set_author(name=member.name, icon_url=avatar_url)
            embed.set_footer(text=f"ID: {member.id} - heute um {current_datetime.strftime('%H:%M:%S')} Uhr")
            return embed
        
        current_datetime = self.globalfile.get_current_time()

        if before.channel is None and after.channel is not None:
            self.logger.info(f"{member.name} hat den Voice-Channel {after.channel.name} betreten.")
            embed = create_embed(f"User entered voice channel <#{after.channel.id}>!", 0x4169E1)
            
            # Check if the channel is one of the monitored channels
            if after.channel.name in self.channel_limits:
                limit = self.channel_limits[after.channel.name]
                # Check if the channel is full
                if len(after.channel.members) > 0:
                    await self.create_alternative_channel(guild, after.channel, limit)
        
        elif before.channel is not None and after.channel is None:
            User = await self.globalfile.admin_did_something(disnake.AuditLogAction.member_disconnect, member)
            if User.username == member.name:
                self.logger.info(f"{member.name} hat den Voice-Channel {before.channel.name} verlassen.")
                embed = create_embed(f"User leaved voice channel <#{before.channel.id}>!", 0xFF0000)
            else:
                self.logger.info(f"{member.name} wurde von {User.username}({User.userid}) aus dem Channel {before.channel.name} gekickt.")
                channel = guild.get_channel(1221018527289577582)
                embed = create_embed(f"{member.name} was kicked from {User.username}({User.userid}) out of Channel {before.channel.name}.", 0xFF0000)                   

        elif before.deaf != after.deaf or before.mute != after.mute or before.self_mute != after.self_mute:
            if after.deaf:
                User = await self.globalfile.admin_did_something(disnake.AuditLogAction.member_update, member.guild, member)
                if User.username == member.name:
                    self.logger.info(f"{member.name} was generally muted.")
                    embed = create_embed(f"User was generally muted in <#{after.channel.id}>!", 0xFFA500)
                else:
                    self.logger.info(f"{member.name} wurde generell gemuted von {User.username}({User.userid}).")
                    channel = guild.get_channel(1221018527289577582)
                    embed = create_embed(f"{member.name} was generally muted from {User.username}({User.userid}).", 0xFF0000)                    
            elif after.mute:                
                User = await self.globalfile.admin_did_something(disnake.AuditLogAction.member_update, member.guild, member)
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
                    User = await self.globalfile.admin_did_something(disnake.AuditLogAction.member_update, member.guild ,member)
                    self.logger.info(f"{member.name} wurde von {User.username}({User.userid}) entmuted.")
                    channel = guild.get_channel(1221018527289577582)
                    embed = create_embed(f"{member.name} was unmuted from {User.username}({User.userid}).", 0xFF0000)

        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            self.logger.info(f"{member.name} hat den Voice-Channel {before.channel.name} verlassen und den Voice Channel {after.channel.name} betreten.")
            embed = create_embed(f"User leaved voice channel <#{before.channel.id}> and entered voice channel <#{after.channel.id}>!", 0x4169E1)

        if embed is not None:
            await channel.send(embed=embed)  
        
        # Check if the before channel is empty and is an alternative channel
        if before.channel is not None and before.channel.id in self.alternative_channels and len(before.channel.members) == 0:
            await self.delete_alternative_channel(guild, before.channel)                            

def setupVoice(bot):
    bot.add_cog(VoiceLogging(bot))
