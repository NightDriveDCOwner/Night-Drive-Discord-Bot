import disnake
from disnake.ext import commands
import sqlite3
import logging
import os
from typing import Union

class RoleAssignment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("RoleAssignment")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.db = sqlite3.connect('nightdrive')
        self.cursor = self.db.cursor()

        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.setup_database()

    def setup_database(self):
        # Add columns for embed values if they don't exist
        embed_columns = ["TITLE", "DESCRIPTION", "FOOTER", "COLORCODE"]
        for column in embed_columns:
            self.cursor.execute(f"PRAGMA table_info(UNIQUE_MESSAGE)")
            columns = [info[1] for info in self.cursor.fetchall()]
            if column not in columns:
                self.cursor.execute(f"ALTER TABLE UNIQUE_MESSAGE ADD COLUMN {column} TEXT")

        # Add columns for role IDs and emojis if they don't exist
        for i in range(1, 31):
            role_column = f"ROLE_ID_{i}"
            emoji_column = f"EMOJI_{i}"
            self.cursor.execute(f"PRAGMA table_info(UNIQUE_MESSAGE)")
            columns = [info[1] for info in self.cursor.fetchall()]
            if role_column not in columns:
                self.cursor.execute(f"ALTER TABLE UNIQUE_MESSAGE ADD COLUMN {role_column} INTEGER")
            if emoji_column not in columns:
                self.cursor.execute(f"ALTER TABLE UNIQUE_MESSAGE ADD COLUMN {emoji_column} TEXT")

        self.db.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("RoleAssignment Cog is ready.")

    async def create_embed_message(self, channel: disnake.TextChannel, message_type: str):
        self.cursor.execute("SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (message_type,))
        result = self.cursor.fetchone()

        if not result:
            self.logger.error(f"No data found for message type: {message_type}")
            return

        description = f"{result[4]}\n\n"  # Assuming DESCRIPTION is the second column
        for i in range(1, 31):
            role_id = result[7 + (i - 1) * 2]  # Adjust the index based on your table structure
            emoji = result[8 + (i - 1) * 2]  # Adjust the index based on your table structure
            if role_id and emoji:
                role = channel.guild.get_role(role_id)
                if role:
                    emojifetched: disnake.Emoji = None
                    emojifetched = self.get_emoji_by_name(channel.guild, emoji)
                    try:
                        if emojifetched.id is not None and emojifetched.id != "":
                            description += f"<:{emojifetched.name}:{emojifetched.id}> = {role.name}\n"
                        else:                            
                            description += f":{emojifetched.name}: = {role.name}\n"
                    except Exception as e:
                        self.logger.error(f"Error adding role ({emoji}) to description: {e}")

        embed = disnake.Embed(
            title=result[3],  # Assuming TITLE is the first column
            description=description,
            color=0x00008B
        )
        if result[5] != "" and result[5] is not None:
            embed.set_footer(text=result[5])  # Assuming FOOTER is the fifth column

        message = await channel.send(embed=embed)

        for i in range(1, 31):
            role_id = result[7 + (i - 1) * 2]  # Adjust the index based on your table structure
            emoji = result[8 + (i - 1) * 2]  # Adjust the index based on your table structure
            if role_id and emoji:
                try:
                    emojifetched: disnake.Emoji = None
                    emojifetched = self.get_emoji_by_name(channel.guild, emoji)
                    await message.add_reaction(emojifetched)
                except Exception as e:
                    self.logger.error(f"Error adding reaction: {e}")

        self.cursor.execute("UPDATE UNIQUE_MESSAGE SET MESSAGEID = ? WHERE MESSAGETYPE = ?", (message.id, message_type))
        self.db.commit()
        
    def get_emoji_by_name(self, guild: disnake.Guild, emoji_name: str) -> Union[disnake.Emoji, disnake.PartialEmoji, None]:
        # Check custom emojis in the guild
        for emoji in guild.emojis:
            if emoji.name == emoji_name:
                return emoji

        # Check general Discord emojis
        try:
            return disnake.PartialEmoji.from_str(emoji_name)
        except ValueError:
            return None
            
    @commands.slash_command(guild_ids=[854698446996766730])
    async def create_embed(self, inter: disnake.ApplicationCommandInteraction, message_type: str, channel: disnake.TextChannel):
        await inter.response.defer(ephemeral=True)
        await self.create_embed_message(channel, message_type)
        await inter.edit_original_response(content="Embed message created.")
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: disnake.RawReactionActionEvent):
        if payload.member.bot:
            return

        self.cursor.execute("SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGEID = ?", (payload.message_id,))
        result = self.cursor.fetchone()

        if not result:
            return

        guild : disnake.Guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        
        
        for i in range(1, 31):
            role_id = result[7 + (i - 1) * 2]
            emoji = result[8 + (i - 1) * 2]
            if role_id and emoji:
                emojifetched: disnake.Emoji = None
                emojifetched = self.get_emoji_by_name(guild, emoji)
                if emojifetched and str(emojifetched) == str(payload.emoji):
                    role = guild.get_role(role_id)
                    if role:
                        await guild.get_member(payload.user_id).add_roles(role)
                        self.logger.info(f"Assigned role {role.name} to {payload.member.name} for reacting with {emoji}")
                        break    
                    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: disnake.RawReactionActionEvent):
        if payload.user_id == None:
            return

        self.cursor.execute("SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGEID = ?", (payload.message_id,))
        result = self.cursor.fetchone()

        if not result:
            return

        guild: disnake.Guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        for i in range(1, 31):
            role_id = result[7 + (i - 1) * 2]
            emoji = result[8 + (i - 1) * 2]
            if role_id and emoji:
                emojifetched: disnake.Emoji = None
                emojifetched = self.get_emoji_by_name(guild, emoji)
                if emojifetched and str(emojifetched) == str(payload.emoji):
                    role = guild.get_role(role_id)
                    if role:
                        await guild.get_member(payload.user_id).remove_roles(role)
                        member: disnake.Member = guild.get_member(payload.user_id)
                        self.logger.info(f"Removed role {role.name} from {member.name} for removing reaction {emoji}")
                        break                    

def setupRoleAssignment(bot):
    bot.add_cog(RoleAssignment(bot))