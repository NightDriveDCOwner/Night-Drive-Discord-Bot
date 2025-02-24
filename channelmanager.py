import disnake
import logging
import os
from disnake.ext import commands

class ChannelManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channel_cache = {}
        self.logger = logging.getLogger("ChannelManager")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)

        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    async def cache_channels(self):
        for guild in self.bot.guilds:
            self.channel_cache[guild.id] = {}
            for channel in guild.channels:
                self.channel_cache[guild.id][channel.id] = channel

    def get_channel_name(self, guild_id: int, channel_id: int) -> str:
        channel = self.channel_cache.get(guild_id, {}).get(channel_id, None)
        return channel.name if channel else None

    def get_channel_id(self, guild_id: int, channel_name: str) -> int:
        for channel_id, channel in self.channel_cache.get(guild_id, {}).items():
            if channel.name == channel_name:
                return channel_id
        return None

    def get_channel(self, guild_id: int, channel_id: int) -> disnake.abc.GuildChannel:
        return self.channel_cache.get(guild_id, {}).get(channel_id, None)

    def get_channel_by_name(self, guild_id: int, channel_name: str) -> disnake.abc.GuildChannel:
        for channel in self.channel_cache.get(guild_id, {}).values():
            if channel.name == channel_name:
                return channel
        return None