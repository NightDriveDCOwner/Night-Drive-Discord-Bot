import discord
from discord.ext import commands

class Reaction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is not None:
            if message.channel.id != 1208770898832658493 and message.content:
                print(f"Nachricht von Server {message.guild.name} erhalten: Username: {message.author.name}, Userid: {message.author.id}, Content: {message.content}")
                
                embed = discord.Embed(title="Message send!", color=0x4169E1)
                embed.set_author(name=message.author.name, icon_url=message.author.avatar_url)
                embed.add_field(name="Message:", value=message.content, inline=True)
                embed.set_footer(text=f"ID: {message.author.id} - heute um {message.created_at.strftime('%H:%M:%S')} Uhr")

                channel = message.guild.get_channel(1208770898832658493)
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        pass

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        pass

def setup(bot):
    bot.add_cog(Reaction(bot))