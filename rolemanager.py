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
            for role in guild.roles:
                self.role_cache[role.id] = role
        self.logger.debug(f"Role cache initialized: {self.role_cache}")

    def get_role_name(self, role_id: int) -> str:
        role = self.role_cache.get(role_id, None)
        role_name = role.name if role else None
        self.logger.debug(f"Retrieved role name for ID {role_id}: {role_name}")
        return role_name

    def get_role_id(self, role_name: str) -> int:
        for role_id, role in self.role_cache.items():
            if role.name == role_name:
                return role_id
        return None

    def get_role(self, role_id: int) -> disnake.Role:
        role = self.role_cache.get(role_id, None)
        self.logger.debug(f"Retrieved role for ID {role_id}: {role}")
        return role

    def get_role_by_name(self, role_name: str) -> disnake.Role:
        for role in self.role_cache.values():
            if role.name == role_name:
                return role
        return None