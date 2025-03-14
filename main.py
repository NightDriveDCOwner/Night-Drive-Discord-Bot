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
from roleassignment import setupRoleAssignment
from cupid import setupCupid
from tmp import setupTmp
from giveaway import setupGiveaway
from friend import setupFriend
from userprofile import setupProfile
import logging
import asyncio
import os
from dotenv import load_dotenv
import requests
import time
from rolemanager import RoleManager
from channelmanager import ChannelManager
from dotenv import load_dotenv, set_key


class Startup:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.rolemanager = RoleManager(bot)
        self.channelmanager = ChannelManager(bot)

    async def on_ready(self):    
        logger.info("Bot is ready. Caching roles...")
        await self.rolemanager.cache_roles()
        await self.channelmanager.cache_channels()
        logger.info("Roles cached. Setting up extensions...")
        setupGlobal(self.bot, self.rolemanager, self.channelmanager)
        setupTicket(self.bot, self.rolemanager)
        setupModeration(self.bot, self.rolemanager, self.channelmanager)        
        setupVoice(self.bot, self.rolemanager, self.channelmanager)
        setupReaction(self.bot, self.rolemanager, self.channelmanager)
        setupLevel(self.bot, self.rolemanager, self.channelmanager)
        setupCountbot(self.bot, self.rolemanager, self.channelmanager)
        setupClientAI(self.bot, self.rolemanager, self.channelmanager)
        setupRoleAssignment(self.bot, self.rolemanager, self.channelmanager)        
        setupCupid(self.bot, self.rolemanager)
        setupTmp(self.bot, self.rolemanager)
        setupGiveaway(self.bot, self.rolemanager)
        setupFriend(self.bot, self.rolemanager, self.channelmanager)
        setupProfile(self.bot, self.rolemanager)
        setupCommands(self.bot, self.rolemanager)                
        setupAuditLog(self.bot, self.rolemanager, self.channelmanager)
        setupJoin(self.bot, self.rolemanager, self.channelmanager)        
        logger.info("All extensions set up.")

root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

load_dotenv(dotenv_path="envs/config.env")
logging_level = os.getenv("LOGGING_LEVEL", "DEBUG").upper()
logging.basicConfig(level=logging_level, filename="log.log",
                    filemode="w", format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger('disnake.http').setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')

intents = disnake.Intents.all()
bot = commands.Bot(intents=intents, command_prefix=None)

startup = Startup(bot)

@bot.event
async def on_ready():
    await startup.on_ready()
    for Cog in bot.cogs.values():
        if hasattr(Cog, 'on_ready'):
            await Cog.on_ready()

def check_rate_limits(token):
    headers = {
        "Authorization": f"Bot {token}"
    }
    retry_attempts = 0
    while True:
        response = requests.get(
            "https://discord.com/api/v9/gateway/bot", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print("Rate Limit Information:")
            print(f"Total: {data['session_start_limit']['total']}")
            print(f"Remaining: {data['session_start_limit']['remaining']}")
            print(
                f"Reset After: {data['session_start_limit']['reset_after']} ms")
            print(
                f"Max Concurrency: {data['session_start_limit']['max_concurrency']}")
            return data['session_start_limit']['remaining'] > 2
        elif response.status_code == 429:
            print("Error 429: Too Many Requests. You have exceeded the rate limit.")
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                print(f"Retry after: {retry_after} seconds")
                retry_attempts += 2
                time.sleep((int(retry_after) + 10)*retry_attempts)
        else:
            print(
                f"Failed to get rate limit information: {response.status_code}")
            return False

async def main():
    load_dotenv(dotenv_path="envs/token.env")
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

    if check_rate_limits(DISCORD_TOKEN):
        logger.info("Starting bot...")
        await bot.start(DISCORD_TOKEN)
    else:
        print("Rate limit exceeded or not enough remaining requests. Bot will not start.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
