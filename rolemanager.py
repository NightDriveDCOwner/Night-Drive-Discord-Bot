import disnake
import logging
import os
from disnake.ext import commands

class RoleManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.role_cache = {}
        self.logger = logging.getLogger("RoleManager")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)

        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    async def cache_roles(self):
        for guild in self.bot.guilds:
            self.role_cache[guild.id] = {}
            for role in guild.roles:
                self.role_cache[guild.id][role.id] = role

    def get_role_name(self, guild_id: int, role_id: int) -> str:
        role = self.role_cache.get(guild_id, {}).get(role_id, None)
        return role.name if role else None

    def get_role_id(self, guild_id: int, role_name: str) -> int:
        for role_id, role in self.role_cache.get(guild_id, {}).items():
            if role.name == role_name:
                return role_id
        return None

    def get_role(self, guild_id: int, role_id: int) -> disnake.Role:
        return self.role_cache.get(guild_id, {}).get(role_id, None)

    def get_role_by_name(self, guild_id: int, role_name: str) -> disnake.Role:
        for role in self.role_cache.get(guild_id, {}).values():
            if role.name == role_name:
                return role
        return None