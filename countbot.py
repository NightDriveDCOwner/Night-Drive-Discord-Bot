import disnake
from disnake.ext import commands
import logging
from globalfile import Globalfile
from dotenv import load_dotenv
import os
import re
from rolemanager import RoleManager
from channelmanager import ChannelManager


class Countbot(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
        self.bot = bot
        self.logger = logging.getLogger("CountingBot")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.globalfile = self.bot.get_cog('Globalfile')
        load_dotenv(dotenv_path="envs/settings.env")
        self.last_correct_number = 0
        self.last_user_id = None
        self.rolemanager: RoleManager = rolemanager
        self.channelmanager: ChannelManager = channelmanager

        # Überprüfen, ob der Handler bereits hinzugefügt wurde
        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    async def initialize_last_correct_number(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.counting_channel_id)
        async for message in channel.history(limit=100):
            if message.reactions:
                for reaction in message.reactions:
                    if reaction.emoji == "✅" and reaction.me:
                        content = message.content.strip()
                        if self.is_valid_number(content):
                            number = self.evaluate_expression(content)
                            if number is not None:
                                self.last_correct_number = number
                                self.logger.debug(
                                    f"Last correct number is {self.last_correct_number}")
                                await self.count_channel.send(
                                    content=f"Die letzte Zahl war {self.last_correct_number}.")
                                return
        self.logger.debug("No correct number found in the channel history.")

    @commands.Cog.listener()
    async def on_ready(self):
        self.counting_channel_id = int(os.getenv("COUNTINGBOT_CHANNEL_ID"))
        self.count_channel: disnake.TextChannel = self.channelmanager.get_channel(
            self.bot.guilds[0].id, self.counting_channel_id)
        self.logger.debug(
            f"Bot is ready. Monitoring channel ID: {self.counting_channel_id}")
        await self.initialize_last_correct_number()

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.bot:
            return

        if message.channel.id != self.counting_channel_id:
            return

        content = message.content.strip()
        if not self.is_valid_number(content):
            return  # Ignore non-number messages

        if message.author.id == self.last_user_id:
            await message.channel.send(f"{message.author.mention}, du darfst nicht zweimal hintereinander eine Zahl schreiben. Es beginnt wieder bei 1.")
            self.last_user_id = None
            self.last_correct_number = 0
            return

        number = self.evaluate_expression(content)
        if number == self.last_correct_number + 1:
            self.last_correct_number = number
            self.last_user_id = message.author.id
            await message.add_reaction("✅")
        else:
            await message.channel.send(f"{message.author.mention}, die Zahl ist falsch. Es beginnt wieder bei 1.")
            self.last_correct_number = 0
            self.last_user_id = None

    def is_valid_number(self, content: str) -> bool:
        # Überprüfen, ob der Inhalt eine gültige Zahl oder Berechnung ist
        return bool(re.match(r'^[\d\s\+\-\*/\(\)]+$', content))

    def evaluate_expression(self, expression: str) -> int:
        # Berechne den Wert des Ausdrucks
        try:
            return int(eval(expression, {"__builtins__": None}, {}))
        except:
            return None


def setupCountbot(bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
    bot.add_cog(Countbot(bot, rolemanager, channelmanager))
