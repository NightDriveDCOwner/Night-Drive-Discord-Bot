import disnake
from disnake.ext import commands
import logging

class Join(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger("Main")
        formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s - %(message)s]:')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    @commands.Cog.listener()
    async def on_member_join(self, member: disnake.member):
        try:
            frischling_id = 854698446996766731
            info_id = 1065696216060547092
            hobbies_id = 1065696208103952465
            games_id = 1065696207416082435
            other_id = 1065701427361611857
            verify_id = 1066793314482913391

            guild = member.guild

            frischling = disnake.utils.get(guild.roles, id=frischling_id)
            info = disnake.utils.get(guild.roles, id=info_id)
            hobbies = disnake.utils.get(guild.roles, id=hobbies_id)
            games = disnake.utils.get(guild.roles, id=games_id)
            other = disnake.utils.get(guild.roles, id=other_id)
            verify = disnake.utils.get(guild.roles, id=verify_id)

            await member.add_roles(frischling, info, hobbies, games, other, verify)
        except Exception as e:
            self.logger.critical(f"Fehler beim Hinzufügen der Rollen: {e}")

def setupJoin(bot):
    bot.add_cog(Join(bot))
