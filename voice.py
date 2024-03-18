import discord
from discord.ext import commands

class VoiceLogging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Überprüfen, ob der Benutzer einen Voice-Channel betritt
        if before.channel is None and after.channel is not None:
            print(f"{member.name} hat den Voice-Channel {after.channel.name} betreten.")
        
        # Überprüfen, ob der Benutzer einen Voice-Channel verlässt
        elif before.channel is not None and after.channel is None:
            print(f"{member.name} hat den Voice-Channel {before.channel.name} verlassen.")
        
        # Überprüfen, ob der Benutzer seine Lautstärke ändert
        elif before.deaf != after.deaf or before.mute != after.mute:
            if after.deaf:
                print(f"{member.name} wurde stummgeschaltet.")
            elif after.mute:
                print(f"{member.name} wurde stummgeschaltet.")
            else:
                print(f"{member.name} wurde laut.")
        


def setup(bot):
    bot.add_cog(VoiceLogging(bot))
