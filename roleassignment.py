import disnake
from disnake.ext import commands
from disnake import SelectOption
from disnake.ui import Select, View
import sqlite3
import logging
import os
from typing import Union
import emoji
from rolehierarchy import rolehierarchy
from disnake.ui import Button, View
from globalfile import Globalfile

class RoleAssignment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("RoleAssignment")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.db = sqlite3.connect('nightdrive')
        self.cursor = self.db.cursor()
        self.globalfile = Globalfile(bot)  

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
        
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co Owner")
    async def create_roles_embeds(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await inter.response.defer(ephemeral=True)
        await self.create_embed_message(channel, "ORIGIN")
        await self.create_embed_message(channel, "GAMES")
        await self.create_embed_message(channel, "PERSONALITY")
        await self.create_embed_message(channel, "RELATIONSIP_STATUS")
        await self.create_embed_message(channel, "EXTRA_ROLES")
        await self.create_embed_message(channel, "DIRECT_MESSAGE") 
        await self.create_embed_message(channel, "EXTRA_BOT")                
        await inter.edit_original_response("Die Roles Embeds wurden erstellt.")      
        self.logger.info(f"Roles Embeds created by {inter.user.name} ({inter.user.id}).")

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.debug("RoleAssignment is ready.")

    async def create_embed_message(self, channel: disnake.TextChannel, message_type: str):
        self.cursor.execute("SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (message_type,))
        result = self.cursor.fetchone()
        role_count = sum(1 for i in range(1, 31) if result[7 + (i - 1) * 2])
        if not result:
            self.logger.error(f"No data found for message type: {message_type}")
            return
        description = result[4].replace('\\n', '\n')
        description = f"{description}\n\n"  # Assuming DESCRIPTION is the second column
        roles_found = False
        options = []
        for i in range(1, 31):
            role_id = result[7 + (i - 1) * 2]  # Adjust the index based on your table structure
            emoji = result[8 + (i - 1) * 2]  # Adjust the index based on your table structure
            if role_id and emoji:
                role = channel.guild.get_role(role_id)
                if role:
                    roles_found = True
                    emojifetched: disnake.Emoji = None
                    emojifetched = self.globalfile.get_manual_emoji(emoji)
                    if emojifetched != "" and emojifetched is not None and message_type != "COLOR":
                        description += f"{emojifetched} = {role.name}\n"
                    elif emojifetched != "" and emojifetched is not None and message_type == "COLOR":
                        description += f"{emojifetched} = <@&{role.id}>\n"
                    else:
                        try:                               
                            emojifetched = self.globalfile.get_emoji_by_name(emoji)
                            if hasattr(emojifetched, 'id') and emojifetched.id is not None:
                                description += f"<:{emojifetched.name}:{emojifetched.id}> = {role.name}\n"
                            elif hasattr(emojifetched, 'name') and emojifetched.name is not None and message_type == "COLOR":
                                description += f"{emojifetched} = <@&{role.id}>\n"               
                        except Exception as e:
                            self.logger.error(f"Error adding role ({emoji}) to description: {e}")
                    options.append(SelectOption(label=role.name, value=str(role_id), emoji=emojifetched))
    
        embed = disnake.Embed(
            title=result[3],  # Assuming TITLE is the first column
            description=f"{description}",
            color=0x00008B
        )
        if result[5] != "" and result[5] is not None:
            embed.set_footer(text=result[5])  # Assuming FOOTER is the fifth column

        message = await channel.send(embed=embed)

        if message_type in ["COLOR", "PERSONALITY", "ORIGIN","DIRECT_MESSAGE"] and roles_found:
            select = Select(
                placeholder="Choose your role...",
                options=options,
                custom_id="role_select_one",
                max_values=role_count,            
                min_values=0
            )
            view = View()
            view.add_item(select)
            await message.edit(view=view)
        else:
            select = Select(
                placeholder="Choose your role...",
                options=options,
                custom_id="role_select",
                max_values=role_count,            
                min_values=0
            )
            view = View()
            view.add_item(select)
            await message.edit(view=view)            

        self.cursor.execute("UPDATE UNIQUE_MESSAGE SET MESSAGEID = ? WHERE MESSAGETYPE = ?", (message.id, message_type))
        self.db.commit()

    async def create_embed_wo_reaction(self, message_type: str, channel: disnake.TextChannel):
        self.cursor.execute("SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (message_type,))
        result = self.cursor.fetchone()

        if not result:
            self.logger.error(f"No data found for message type: {message_type}")
            return

        description = result[4].replace('\\n', '\n')
        description_lines = description.split('\n')
        formatted_description = "\n".join([f"- {line}" if line.strip()[:2] in [f"{chr(97 + i)})" for i in range(26)] else line for line in description_lines])

        embed = disnake.Embed(
            title=result[3],  # Assuming TITLE is the first column
            description=formatted_description,
            color=0x00008B
        )
        if result[5] != "" and result[5] is not None:
            embed.set_footer(text=result[5])  # Assuming FOOTER is the fifth column    

        message = await channel.send(embed=embed)
        
        if message_type == "NSFWRULES9":
            role_button = Button(label="Regeln akzeptieren", style=disnake.ButtonStyle.green, custom_id="toggle_nsfwrule_button")
            view = View()            
            view.add_item(role_button)
            await message.edit(view=view)

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co Owner")    
    async def create_rules_embeds(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await inter.response.defer()
        message_types = [f"RULES{i}" for i in range(1, 10)]
        
        for message_type in message_types:
            await self.create_embed_wo_reaction(message_type, channel)
        
        await inter.edit_original_response(content="All rule embeds have been created.")        

    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co Owner")    
    async def create_nsfwrules_embeds(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await inter.response.defer()
        message_types = [f"NSFWRULES{i}" for i in range(1, 10)]
        
        for message_type in message_types:
            await self.create_embed_wo_reaction(message_type, channel)
        
        await inter.edit_original_response(content="All nsfwrule embeds have been created.")    


    @commands.Cog.listener()
    async def on_dropdown(self, inter: disnake.MessageInteraction):
        await inter.response.defer()
        if inter.component.custom_id == "role_select_one":
            selected_role_ids = [int(role_id) for role_id in inter.values] if inter.values else []

            # Check if more than one role is selected
            if len(selected_role_ids) > 1:
                if not inter.response.is_done():
                    await inter.response.send_message("Bitte wähle bei dieser Kategorie nur eine Rolle aus.", ephemeral=True)
                return

            selected_roles = [inter.guild.get_role(role_id) for role_id in selected_role_ids]

            # Check if the user already has roles from the select menu
            user_roles = inter.author.roles
            role_ids = [option.value for option in inter.component.options]
            existing_roles = [role for role in user_roles if str(role.id) in role_ids]

            # Determine roles to add and remove
            roles_to_add = []
            roles_to_remove = []

            for role in selected_roles:
                if role not in existing_roles:
                    roles_to_add.append(role)

            for role in existing_roles:
                if role not in selected_roles:
                    roles_to_remove.append(role)

            # Add new roles
            for role in roles_to_add:
                if role:
                    await inter.author.add_roles(role)

            # Remove deselected roles
            for role in roles_to_remove:
                if role:
                    await inter.author.remove_roles(role)

        elif inter.component.custom_id == "role_select":
            selected_role_ids = [int(role_id) for role_id in inter.values] if inter.values else []

            selected_roles = [inter.guild.get_role(role_id) for role_id in selected_role_ids]

            # Check if the user already has roles from the select menu
            user_roles = inter.author.roles
            role_ids = [option.value for option in inter.component.options]
            existing_roles = [role for role in user_roles if str(role.id) in role_ids]

            # Determine roles to add and remove
            roles_to_add = []
            roles_to_remove = []

            for role in selected_roles:
                if role not in existing_roles:
                    roles_to_add.append(role)

            for role in existing_roles:
                if role not in selected_roles:
                    roles_to_remove.append(role)

            # Add new roles
            for role in roles_to_add:
                if role:
                    await inter.author.add_roles(role)

            # Remove deselected roles
            for role in roles_to_remove:
                if role:
                    await inter.author.remove_roles(role)
        
    @commands.Cog.listener()
    async def on_interaction(self, interaction: disnake.Interaction):
        if interaction.type == disnake.InteractionType.component:
            custom_id = interaction.data.get("custom_id")            
            if custom_id == "toggle_nsfwrule_button":
                interaction.response.defer()
                await self.nsfwrules_button_callback(interaction)        

    async def nsfwrules_button_callback(self, interaction: disnake.Interaction):
        role_id = 1165704468449468547  # Ersetze dies durch die ID der Rolle, die du zuweisen/entfernen möchtest
        role = interaction.guild.get_role(role_id)
        
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message("Die Rolle wurde entfernt und du hast die Regeln akzeptiert.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("Die Rolle wurde hinzugefügt.", ephemeral=True)
                     
                
    @commands.slash_command(guild_ids=[854698446996766730])
    @rolehierarchy.check_permissions("Co Owner")
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
                emojifetched = self.globalfile.get_emoji_by_name(emoji)
                if emojifetched.id is None:
                    emojifetched = self.globalfile.get_manual_emoji(emoji)
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
                emojifetched = self.globalfile.get_emoji_by_name(emoji)
                if emojifetched.id is None:
                    emojifetched = self.globalfile.get_manual_emoji(emoji)
                if emojifetched and str(emojifetched) == str(payload.emoji):
                    role = guild.get_role(role_id)
                    if role:
                        await guild.get_member(payload.user_id).remove_roles(role)
                        member: disnake.Member = guild.get_member(payload.user_id)
                        self.logger.info(f"Removed role {role.name} from {member.name} for removing reaction {emoji}")
                        break                    

def setupRoleAssignment(bot):
    bot.add_cog(RoleAssignment(bot))