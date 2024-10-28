import disnake
from disnake.ext import commands
import logging
import sqlite3
from DBConnection import DatabaseConnection
from globalfile import Globalfile

class Join(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger("Join")
        formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s - %(message)s]:')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.globalfile = Globalfile(bot)
        self.db = DatabaseConnection()


    @commands.Cog.listener()
    async def on_member_join(self, member: disnake.Member):
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
            embed = disnake.Embed(title=f"Herzlich Willkommen!", color=0x6495ED)
            embed.set_author(name="Aincrad", icon_url=guild.icon.url)
            embed.description = f"Ein wildes {member.mention} ist aufgetaucht, willkommen bei uns auf **Aincrad!**\nIn <#1039167130190491709> kannst du dir deine eigenen Rollen vergeben.\nIn <#1039167960012554260> kannst du dich nach Möglichkeit vorstellen damit die anderen wissen wer du bist."
            channel = guild.get_channel(854698447247769630)
            await channel.send(embed=embed)
                        
        except Exception as e:
            self.logger.critical(f"Fehler beim Hinzufügen der Rollen: {e}")

def setupJoin(bot):
    bot.add_cog(Join(bot))
