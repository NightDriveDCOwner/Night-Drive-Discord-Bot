import disnake
from disnake.ext import commands
from reaction import setupReaction
from join import setupJoin
from voice import setupVoice
from globalfile import setupGlobal
from moderation import setupModeration
import disnake
import logging

root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

logging.basicConfig(level=logging.INFO, filename="log.log", filemode="w", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')

intents = disnake.Intents.all()
bot = commands.Bot(intents=intents, command_prefix=None)

@bot.event
async def on_ready():
    logger.info("The bot is ready!")  
   
bot.load_extension("commands")
setupReaction(bot)
setupJoin(bot)
setupVoice(bot)
setupGlobal(bot)
setupModeration(bot)

bot.run("MTIwODE3NTc0ODk4MDkzNjc2NA.GGk_8k.IUe5KR-MSpolnO_I7rGtx5qsE1Tr0M9fyk7gfw")