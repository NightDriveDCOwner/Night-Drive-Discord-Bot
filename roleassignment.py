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
from exceptionhandler import exception_handler
import rolehierarchy
from rolehierarchy import rolehierarchy
from rolemanager import RoleManager
from dbconnection import DatabaseConnection


class RoleAssignment(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager: RoleManager):
        self.bot = bot
        self.logger = logging.getLogger("RoleAssignment")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.db = sqlite3.Connection = DatabaseConnection()
        self.cursor = self.db.connection.cursor()
        self.globalfile = Globalfile(bot)  
        self.role_hierarchy = rolehierarchy()
        self.team_roles = []
        self.role_manager = rolemanager

        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS BEICHTEN (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            USERID INTEGER NOT NULL,
            MESSAGE TEXT NOT NULL
        )
        """)
        self.db.connection.commit()                                   

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

        self.db.connection.commit()

    @exception_handler        
    async def _create_roles_embeds(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
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

    @exception_handler
    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.debug("RoleAssignment is ready.")
        self.beichte_channel = self.bot.get_channel(1338586807700557965)  # Replace with your Beichte channel ID
        self.seelsorge_channel_id = 1068973683361726596
        self.nsfwrole = self.bot.guilds[0].get_role(1165704468449468547)
        self.seelsorge_role = self.bot.guilds[0].get_role(1338603963720798248)  # Replace with your Seelsorge role ID
        self.team_role = self.bot.guilds[0].get_role(1235534762609872899)  # Replace with your team role ID
        self.team_channel = self.bot.get_channel(1066798419470983269)  # Assuming team_channel_id is defined in on_ready
        self.team_roles = [self.bot.guilds[0].get_role(role_id) for role_id in self.role_hierarchy.role_hierarchy if self.bot.guilds[0].get_role(role_id)]

    @exception_handler
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
                    emojifetched = await self.globalfile.get_manual_emoji(emoji)
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
        self.db.connection.commit()

    @exception_handler
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

    @exception_handler
    async def _create_rules_embed(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await inter.response.defer()
        
        self.cursor.execute("SELECT DESCRIPTION FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", ("RULES1",))
        result = self.cursor.fetchone()
        if result:
            rules1_description = result[0].replace('\\n', '\n')
        # Create the initial embed
        start_embed = disnake.Embed(
            title="Willkommmen auf Date Night 18+",
            description=rules1_description,
            color=0x00008B
        )
        start_embed.set_author(name=self.bot.guilds[0].name, icon_url=self.bot.guilds[0].icon.url if self.bot.guilds[0].icon else self.bot.guilds[0].icon.url)
        start_embed.add_field(name="**Invite Link**", value=f"https://discord.gg/datenight \n\nStand der Regeln und Infos: <t:{int(disnake.utils.utcnow().timestamp())}:R>*", inline=False)
        start_embed.set_footer(text="")
        start_message = await channel.send(embed=start_embed)
        
        # Create the dropdown options for rules
        message_types = [f"RULES{i}" for i in range(2, 10)]
        options = []
        for message_type in message_types:
            self.cursor.execute("SELECT TITLE FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (message_type,))
            result = self.cursor.fetchone()
            if result:
                options.append(SelectOption(label=result[0], value=message_type))                
        
        # Create the dropdown menu for rules
        rules_select = Select(
            placeholder="Wähle eine Regel...",
            options=options,
            custom_id="rules_select"
        )
        
        # Create the dropdown options for server information
        info_options = [
            SelectOption(label="Levelsystem", value="LEVEL"),
            # Add more options as needed
        ]
        
        # Create the dropdown menu for server information
        info_select = Select(
            placeholder="Wähle eine Information...",
            options=info_options,
            custom_id="info_select"
        )
        
        # Create the button for self roles
        self_roles_button = Button(label="Self Roles", style=disnake.ButtonStyle.link, url="https://discord.com/channels/854698446996766730/1039167130190491709")
        
        # Create the button for server team
        server_team_button = Button(label="Serverteam", style=disnake.ButtonStyle.primary, custom_id="server_team_button")
        
        # Create the view and add items
        view = View()
        view.add_item(self_roles_button)
        view.add_item(rules_select)
        view.add_item(info_select)
        view.add_item(server_team_button)  # Add the server team button to the view
        
        await start_message.edit(view=view)
        
        await inter.edit_original_response(content="Das Regel-Embed wurde erstellt.")

    @exception_handler
    async def server_team_button_callback(self, interaction: disnake.Interaction):
        # Fetch team members from the database
        self.cursor.execute("SELECT USERID, ROLE FROM TEAM_MEMBERS WHERE TEAM_ROLE = 1")
        team_members_data = self.cursor.fetchall()

        team_members = []
        for user_id, role_name in team_members_data:
            user_record = await self.globalfile.get_user_record(user_id=user_id)
            if user_record:
                discord_id = user_record['DISCORDID']
                member = interaction.guild.get_member(int(discord_id)) 
                if member:
                    role_id = self.role_manager.get_role_id(role_name)
                    role = interaction.guild.get_role(role_id) if role_id else None
                    role_mention = role.mention if role else f"<@&{role_id}>"
                    team_members.append((role_name, f"{member.mention} - {role_mention}"))

        # Sort team members by role hierarchy
        team_members.sort(key=lambda x: self.role_hierarchy.role_hierarchy.index(x[0]))

        # Extract sorted team member mentions
        sorted_team_members = [member for _, member in team_members]

        team_roles_mentions = ", ".join([role.mention for role in self.team_roles if role])

        team_embed = disnake.Embed(
            title="Serverteam",
            description="Hier sind die Mitglieder des Serverteams:",
            color=0x00008B
        )
        team_embed.set_author(name=self.bot.guilds[0].name, icon_url=self.bot.guilds[0].icon.url if self.bot.guilds[0].icon else self.bot.guilds[0].icon.url)
        team_embed.add_field(name="Teammitglieder", value="\n".join(sorted_team_members), inline=False)
        team_embed.add_field(name="Vorstellungen", value=f"Die Vorstellungen der Teammitglieder findest du im {self.team_channel.mention} Channel.", inline=False)
        team_embed.set_footer(text="Du kannst jederzeit die Teamrolle pingen, wenn du Hilfe benötigst.")

        await interaction.response.send_message(embed=team_embed, ephemeral=True)

    @exception_handler
    async def _create_nsfwrules_embeds(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await inter.response.defer()

        self.cursor.execute("SELECT DESCRIPTION FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", ("NSFWRULES1",))
        result = self.cursor.fetchone()
        if result:
            nsfwrules1_description = result[0].replace('\\n', '\n')

        # Create the initial embed
        start_embed = disnake.Embed(
            title="NSFW Regeln",
            description=nsfwrules1_description,
            color=0x00008B
        )
        start_embed.set_author(name=self.bot.guilds[0].name, icon_url=self.bot.guilds[0].icon.url if self.bot.guilds[0].icon else self.bot.guilds[0].icon.url)
        start_embed.add_field(name="**Wichtige Informationen**", value=f"Bitte lese alle Regeln sorgfältig durch.\n\nStand der Regeln und Infos: <t:{int(disnake.utils.utcnow().timestamp())}:R>*", inline=False)
        start_embed.set_footer(text="")
        start_message = await channel.send(embed=start_embed)

        # Create the dropdown options for nsfw rules
        message_types = [f"NSFWRULES{i}" for i in range(2, 10)]
        options = []
        for message_type in message_types:
            self.cursor.execute("SELECT TITLE FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (message_type,))
            result = self.cursor.fetchone()
            if result:
                options.append(SelectOption(label=result[0], value=message_type))

        # Create the dropdown menu for nsfw rules
        nsfwrules_select = Select(
            placeholder="Wähle eine Regel...",
            options=options,
            custom_id="nsfwrules_select"
        )

        # Create the button for NSFW role
        nsfw_role_button = Button(label="Regeln akzeptieren", style=disnake.ButtonStyle.green, custom_id="toggle_nsfwrule_button")

        # Create the view and add items
        view = View()
        view.add_item(nsfw_role_button)
        view.add_item(nsfwrules_select)

        await start_message.edit(view=view)

        await inter.edit_original_response(content="Das NSFW-Regel-Embed wurde erstellt.")

    @exception_handler
    @commands.Cog.listener()
    async def on_dropdown(self, inter: disnake.MessageInteraction):        
        if inter.component.custom_id == "role_select_one":
            await inter.response.defer()
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
            await inter.response.defer()
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
        elif inter.component.custom_id == "rules_select":
            await inter.response.defer(ephemeral=True)
            selected_rule = inter.values[0]
            self.cursor.execute("SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (selected_rule,))
            result = self.cursor.fetchone()
            
            if result:
                description = result[4].replace('\\n', '\n')
                embed = disnake.Embed(
                    title=result[3],  # Assuming TITLE is the first column
                    description=description,
                    color=0x00008B
                )
                if result[5] != "" and result[5] is not None:
                    embed.set_footer(text=result[5])  # Assuming FOOTER is the fifth column
                
                await inter.send(embed=embed, ephemeral=True)
            else:
                await inter.send("Keine Daten für die ausgewählte Regel gefunden.", ephemeral=True)
        elif inter.component.custom_id == "info_select":
            await inter.response.defer(ephemeral=True)
            selected_info = inter.values[0]
            
            if selected_info == "LEVEL":
                # Fetch and send the level embed
                self.cursor.execute("SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", ("LEVEL",))
                result = self.cursor.fetchone()
                
                if result:
                    description = result[4].replace('\\n', '\n')
                    embed = disnake.Embed(
                        title=result[3],  # Assuming TITLE is the first column
                        description=description,
                        color=0x00008B
                    )
                    if result[5] != "" and result[5] is not None:
                        embed.set_footer(text=result[5])  # Assuming FOOTER is the fifth column
                    
                    await inter.send(embed=embed, ephemeral=True)
                else:
                    await inter.send("Keine Daten für die ausgewählte Information gefunden.", ephemeral=True)                   
        elif inter.component.custom_id == "nsfwrules_select":
            await inter.response.defer(ephemeral=True)
            selected_rule = inter.values[0]
            self.cursor.execute("SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (selected_rule,))
            result = self.cursor.fetchone()

            if result:
                description = result[4].replace('\\n', '\n')
                embed = disnake.Embed(
                    title=result[3],  # Assuming TITLE is the first column
                    description=description,
                    color=0x00008B
                )
                if result[5] != "" and result[5] is not None:
                    embed.set_footer(text=result[5])  # Assuming FOOTER is the fifth column

                await inter.send(embed=embed, ephemeral=True)
            else:
                await inter.send("Keine Daten für die ausgewählte Regel gefunden.", ephemeral=True)

    @exception_handler
    @commands.Cog.listener()
    async def on_interaction(self, interaction: disnake.Interaction):
        if interaction.type == disnake.InteractionType.component:
            custom_id = interaction.data.get("custom_id")
            if custom_id == "toggle_nsfwrule_button":
                await self.nsfwrules_button_callback(interaction)
            elif custom_id == "toggle_seelsorge_button":
                if not interaction.response.is_done():
                    await interaction.response.defer()
                await self.seelsorge_button_callback(interaction)
            elif custom_id == "server_team_button":
                await self.server_team_button_callback(interaction)

    @exception_handler
    async def nsfwrules_button_callback(self, interaction: disnake.Interaction):           
        if self.nsfwrole in interaction.user.roles:
            await interaction.user.remove_roles(self.nsfwrole)
            await interaction.response.send_message("Die Rolle wurde entfernt und du hast die Regeln nicht mehr akzeptiert. Das gilt nicht rückwirkend.", ephemeral=True)
        else:
            await interaction.user.add_roles(self.nsfwrole)
            await interaction.response.send_message("Die Rolle wurde hinzugefügt und du hast die regeln akzeptiert.", ephemeral=True)
                     
    @exception_handler
    async def seelsorge_button_callback(self, interaction: disnake.Interaction):
        seelsorge_role = interaction.guild.get_role(1338603963720798248)  # Replace with your Seelsorge role ID
        if seelsorge_role in interaction.user.roles:
            await interaction.user.remove_roles(seelsorge_role)
            if not interaction.response.is_done():
                await interaction.response.send_message("Die Rolle wurde entfernt.", ephemeral=True)
            else:
                await interaction.followup.send("Die Rolle wurde entfernt.", ephemeral=True)
        else:
            await interaction.user.add_roles(seelsorge_role)
            if not interaction.response.is_done():
                await interaction.response.send_message("Die Rolle wurde hinzugefügt.", ephemeral=True)
            else:
                await interaction.followup.send("Die Rolle wurde hinzugefügt.", ephemeral=True)                 

    @exception_handler                
    async def _create_embed(self, inter: disnake.ApplicationCommandInteraction, message_type: str, channel: disnake.TextChannel):
        await inter.response.defer(ephemeral=True)
        await self.create_embed_message(channel, message_type)
        await inter.edit_original_response(content="Embed message created.")
    
    @exception_handler
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
                    emojifetched = await self.globalfile.get_manual_emoji(emoji)
                if emojifetched and str(emojifetched) == str(payload.emoji):
                    role = guild.get_role(role_id)
                    if role:
                        await guild.get_member(payload.user_id).add_roles(role)
                        self.logger.info(f"Assigned role {role.name} to {payload.member.name} for reacting with {emoji}")
                        break    
           
    @exception_handler         
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
                    emojifetched = await self.globalfile.get_manual_emoji(emoji)
                if emojifetched and str(emojifetched) == str(payload.emoji):
                    role = guild.get_role(role_id)
                    if role:
                        await guild.get_member(payload.user_id).remove_roles(role)
                        member: disnake.Member = guild.get_member(payload.user_id)
                        self.logger.info(f"Removed role {role.name} from {member.name} for removing reaction {emoji}")
                        break         

    @exception_handler
    async def _create_seelsorge_embed(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        bot_user = self.bot.user
        bot_avatar_url = bot_user.avatar.url if bot_user.avatar else bot_user.default_avatar.url
        
        # Seelsorge Embed
        seelsorge_embed = disnake.Embed(
            title="Seelsorge/Beichte Channel",
            color=0x00008B
        )
        seelsorge_embed.set_author(name=self.bot.guilds[0].name, icon_url=self.bot.guilds[0].icon.url if self.bot.guilds[0].icon else self.bot.guilds[0].icon.url)
        
        seelsorge_description = (
            "**Seelsorge**\n"
            "Hier kannst du dich auskotzen und Unterstützung von anderen Mitgliedern erhalten. Wenn du eine Nachricht schickst, wird ein Thread eröffnet, den du auch wieder löschen kannst. Spätestens nach 48 Stunden wird der Thread automatisch gelöscht.\n\n"
            "**Regeln für den Seelsorge Channel:**\n"
            "- **Emotionale Validierung und Unterstützung:** Jedes Mitglied dieser Gruppe hat das Recht auf Akzeptanz und Wertschätzung seiner emotionalen Erfahrungen. Wir verpflichten uns, einander mit Empathie und Verständnis zu begegnen und die geäußerten Gefühle ernst zu nehmen.\n"
            "- **Diskretion und Wahrung der Privatsphäre:** Die Vertraulichkeit aller geteilten Informationen ist von höchster Bedeutung. Alle Mitglieder verpflichten sich, persönliche Offenbarungen, die innerhalb der Gruppe gemacht werden, nicht an Dritte weiterzugeben. Die Privatsphäre jedes Einzelnen ist unbedingt zu respektieren.\n"
            "- **Aktive Unterstützung und Ressourcenorientierung:** Wir ermutigen uns gegenseitig, unterstützende Ressourcen zu teilen, und bieten einander aktiv Zuhören und Anteilnahme an. Ziel ist es, ein Netzwerk der gegenseitigen Hilfe und des Verständnisses zu schaffen, wenn möglich.\n"
            "- **Grenzen der Laienhilfe und professionelle Unterstützung:** Es ist wichtig zu betonen, dass diese Gruppe keinen Ersatz für professionelle psychologische oder medizinische Beratung darstellt. Bei ernsthaften psychischen Problemen oder Krisensituationen sind die Mitglieder angehalten, qualifizierte Fachkräfte (z.B. Therapeuten, Ärzte, Beratungsstellen) zu konsultieren.\n"                      
        )

        nummern_description = (
            "- „Nummer gegen Kummer“ (Kinder und Jugendliche) - 116 111\n"
            "- „Nummer gegen Kummer“ (Elterntelefon) - 0800 111 0 550\n"
            "- Hilfetelefon Gewalt gegen Frauen - 08000 116 016\n"
            "- Hilfetelefon Gewalt an Männern - 0800 12 39 900\n"
            "- Telefonseelsorge - 0800 111 0 111 oder 0800 111 0 222\n"
            "- „Schwangere in Not“ - 0800 40 40 020\n"
            "- Info-Telefon Depression - 0800 334 4533\n"
            "- Hilfetelefon sexueller Missbrauch: - 0800-22 55 530\n"
            "- Hilfetelefon tatgeneigte Personen - 0800 70 22 240\n"
            "(kostenfrei und anonym)"
        )

        beichte_description = (
            "Hier kannst du anonym deine Beichten ablegen. Deine Beichte wird gespeichert und anonym im Beichte-Channel veröffentlicht."
        )        

        seelsorge_embed.add_field(name="Beichte", value=beichte_description, inline=False)
        seelsorge_embed.add_field(name="Unter den folgenden Telefonnummern können Betroffene zusätzliche Hilfe finden:", value=nummern_description, inline=False)
        seelsorge_embed.description=seelsorge_description
        seelsorge_message = await channel.send(embed=seelsorge_embed)

        # Button hinzufügen
        role_button = Button(label="Regeln akzeptieren", style=disnake.ButtonStyle.green, custom_id="toggle_seelsorge_button")
        view = View()
        view.add_item(role_button)
        await seelsorge_message.edit(view=view)        
        
        await inter.response.send_message("Seelsorge und Beichte Embeds wurden erstellt.", ephemeral=True)

        # Datenbankeintrag erstellen
        self.cursor.execute("INSERT INTO UNIQUE_MESSAGE (MESSAGETYPE, MESSAGEID, TITLE, DESCRIPTION, FOOTER) VALUES (?, ?, ?, ?, ?)",
                            ("SEELSORGE", seelsorge_message.id, "Seelsorge Channel", seelsorge_description, ""))
        self.db.connection.commit()

    @exception_handler
    async def _beichte(self, inter: disnake.ApplicationCommandInteraction, message: str):
        user_record = await self.globalfile.get_user_record(discordid=inter.user.id)
        self.cursor.execute("INSERT INTO BEICHTEN (USERID, MESSAGE) VALUES (?, ?)", (user_record['ID'], message))
        self.db.connection.commit()
        await inter.response.send_message("Deine Beichte wurde gespeichert und ggfs. für das Team zugänglich.", ephemeral=True)        
        await self.beichte_channel.send(f"Neue Beichte: {message}")

    @exception_handler
    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.id != self.bot.user.id:
            if message.channel.id == self.seelsorge_channel_id:  # Replace with your Seelsorge channel ID                        
                thread: disnake.Thread = await message.channel.create_thread(
                    name=f"{message.author.name}'s Self Reveal",
                    message=message,
                    auto_archive_duration=1440  # 48 hours
                    )  
                await thread.send(f"{message.author.mention} hat diesen Thread eröffnet.")          

    @exception_handler
    @commands.Cog.listener()
    async def on_thread_update(self, before: disnake.Thread, after: disnake.Thread):
        if after.parent_id == self.seelsorge_channel_id and after.archived and not after.locked:
            await after.delete()

def setupRoleAssignment(bot: commands.Bot, rolemanager: RoleManager):
    bot.add_cog(RoleAssignment(bot, rolemanager))