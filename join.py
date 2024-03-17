import discord
from discord.ext import commands

class Join(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        frischling_id = 854698446996766731
        info_id = 1065696216060547092
        hobbies_id = 1065696208103952465
        games_id = 1065696207416082435
        other_id = 1065701427361611857
        verify_id = 1066793314482913391

        guild = member.guild

        frischling = discord.utils.get(guild.roles, id=frischling_id)
        info = discord.utils.get(guild.roles, id=info_id)
        hobbies = discord.utils.get(guild.roles, id=hobbies_id)
        games = discord.utils.get(guild.roles, id=games_id)
        other = discord.utils.get(guild.roles, id=other_id)
        verify = discord.utils.get(guild.roles, id=verify_id)

        await member.add_roles(frischling, info, hobbies, games, other, verify)

        print(f"Der User {member.name} mit der ID: {member.id} hat die Rollen Frischling, Info, Hobbies, Games, Other und Verified erhalten.")

def setup(bot):
    bot.add_cog(Join(bot))