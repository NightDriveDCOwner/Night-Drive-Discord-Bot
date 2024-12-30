import disnake
from disnake.ext import commands
from reaction import setupReaction
from join import setupJoin
from voice import setupVoice
from globalfile import setupGlobal
from moderation import setupModeration
from ticket import setupTicket
from level import setupLevel
from countbot import setupCountbot
from auditlog import setupAuditLog
from clientai import setupClientAI
from commands import setupCommands
import disnake
import logging
import asyncio
import os
from dotenv import load_dotenv

class DiscordLoggingHandler(logging.Handler):
    def __init__(self, bot, user_id):
        super().__init__()
        self.bot = bot
        self.user_id = user_id            

    async def send_log_message(self, record):
        user = await self.bot.fetch_user(self.user_id)
        if user:
            embed = disnake.Embed(title="Critical Error", description=record.getMessage(), color=disnake.Color.red())
            await user.send(embed=embed)

    def emit(self, record):
        if record.levelno == logging.CRITICAL:
            asyncio.create_task(self.send_log_message(record))

root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
    
load_dotenv(dotenv_path="envs/config.env")
logging_level = os.getenv("LOGGING_LEVEL", "DEBUG").upper()
logging.basicConfig(level=logging_level, filename="log.log", filemode="w", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')

intents = disnake.Intents.all()
bot = commands.Bot(intents=intents, command_prefix=None, description= "Hier sind die [Nutzungsbedingungen vom Cardinal System](https://cdn.discordapp.com/attachments/1061441308452999261/1323286193705713736/Nutzungsbedingungen_fur_Cardinal_System.pdf?ex=6773f5ce&is=6772a44e&hm=b0f62fca99ea05c399e380b5ee0c4c5045bbd36479535e2502b5bbba4c05f725)")
bot.description = "Hier sind die [Nutzungsbedingungen vom Cardinal System](https://cdn.discordapp.com/attachments/1061441308452999261/1323286193705713736/Nutzungsbedingungen_fur_Cardinal_System.pdf?ex=6773f5ce&is=6772a44e&hm=b0f62fca99ea05c399e380b5ee0c4c5045bbd36479535e2502b5bbba4c05f725)"
bot.application_info = "Hier sind die [Nutzungsbedingungen vom Cardinal System](https://cdn.discordapp.com/attachments/1061441308452999261/1323286193705713736/Nutzungsbedingungen_fur_Cardinal_System.pdf?ex=6773f5ce&is=6772a44e&hm=b0f62fca99ea05c399e380b5ee0c4c5045bbd36479535e2502b5bbba4c05f725)"

discord_handler = DiscordLoggingHandler(bot, user_id=461969832074543105)
logger.addHandler(discord_handler)

@bot.event
async def on_ready():
    logger.info("The bot is ready!")  
   
# bot.load_extension("commands")
setupReaction(bot)
setupJoin(bot)
setupVoice(bot)
setupGlobal(bot)
setupModeration(bot)
setupTicket(bot)
setupLevel(bot)
setupCountbot(bot)
setupAuditLog(bot)
setupClientAI(bot)
setupCommands(bot)


load_dotenv(dotenv_path="envs/token.env")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(DISCORD_TOKEN)