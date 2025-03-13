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
from dbconnection import DatabaseConnectionManager
from datetime import timedelta
from channelmanager import ChannelManager
from dotenv import load_dotenv

class RoleAssignment(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
        self.bot = bot
        self.logger = logging.getLogger("RoleAssignment")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.globalfile : Globalfile = self.bot.get_cog('Globalfile')
        self.role_hierarchy = rolehierarchy()
        self.team_roles = []
        self.rolemanager = rolemanager
        self.channelmanager = channelmanager

        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

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
        self.logger.info(
            f"Roles Embeds created by {inter.user.name} ({inter.user.id}).")

    @exception_handler
    @commands.Cog.listener()
    async def on_ready(self):                                        
        self.logger.info("RoleAssignment Cog is ready.")

    @exception_handler
    async def create_embed_message(self, channel: disnake.TextChannel, message_type: str):
        cursor = await DatabaseConnectionManager.execute_sql_statement(channel.guild.id, channel.guild.name, "SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (message_type,))
        result = (await cursor.fetchone())
        role_count = sum(1 for i in range(1, 31) if result[7 + (i - 1) * 2])
        if not result:
            self.logger.error(
                f"No data found for message type: {message_type}")
            return
        description = result[4].replace('\\n', '\n')
        # Assuming DESCRIPTION is the second column
        description = f"{description}\n\n"
        roles_found = False
        options = []
        for i in range(1, 31):
            # Adjust the index based on your table structure
            role_id = result[7 + (i - 1) * 2]
            # Adjust the index based on your table structure
            emoji = result[8 + (i - 1) * 2]
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
                            emojifetched = await self.globalfile.get_emoji_by_name(emoji, channel.guild)
                            if hasattr(emojifetched, 'id') and emojifetched.id is not None:
                                description += f"<:{emojifetched.name}:{emojifetched.id}> = {role.name}\n"
                            elif hasattr(emojifetched, 'name') and emojifetched.name is not None and message_type == "COLOR":
                                description += f"{emojifetched} = <@&{role.id}>\n"
                        except Exception as e:
                            self.logger.error(
                                f"Error adding role ({emoji}) to description: {e}")
                    options.append(SelectOption(label=role.name,
                                   value=str(role_id), emoji=emojifetched))

        embed = disnake.Embed(
            title=result[3],  # Assuming TITLE is the first column
            description=f"{description}",
            color=0x00008B
        )
        if result[5] != "" and result[5] is not None:
            # Assuming FOOTER is the fifth column
            embed.set_footer(text=result[5])

        message = await channel.send(embed=embed)

        if message_type in ["COLOR", "PERSONALITY", "ORIGIN", "DIRECT_MESSAGE"] and roles_found:
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

        cursor = await DatabaseConnectionManager.execute_sql_statement(channel.guild.id, channel.guild.name, "UPDATE UNIQUE_MESSAGE SET MESSAGEID = ? WHERE MESSAGETYPE = ?", (message.id, message_type))

    @exception_handler
    async def create_embed_wo_reaction(self, message_type: str, channel: disnake.TextChannel):
        cursor = await DatabaseConnectionManager.execute_sql_statement(channel.guild.id, channel.guild.name, "SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (message_type,))
        result = (await cursor.fetchone())

        if not result:
            self.logger.error(
                f"No data found for message type: {message_type}")
            return

        description = result[4].replace('\\n', '\n')
        description_lines = description.split('\n')
        formatted_description = "\n".join([f"- {line}" if line.strip()[:2] in [
                                          f"{chr(97 + i)})" for i in range(26)] else line for line in description_lines])

        embed = disnake.Embed(
            title=result[3],  # Assuming TITLE is the first column
            description=formatted_description,
            color=0x00008B
        )
        if result[5] != "" and result[5] is not None:
            # Assuming FOOTER is the fifth column
            embed.set_footer(text=result[5])

        message = await channel.send(embed=embed)

        if message_type == "NSFWRULES9":
            role_button = Button(
                label="Regeln akzeptieren", style=disnake.ButtonStyle.green, custom_id="toggle_nsfwrule_button")
            view = View()
            view.add_item(role_button)
            await message.edit(view=view)

    @exception_handler
    async def _create_rules_embed(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await inter.response.defer()

        cursor = await DatabaseConnectionManager.execute_sql_statement(channel.guild.id, channel.guild.name, "SELECT DESCRIPTION FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", ("RULES1",))
        result = (await cursor.fetchone())
        if result:
            rules1_description = result[0].replace('\\n', '\n')
        # Create the initial embed
        start_embed = disnake.Embed(
            title="Willkommmen auf Date Night 18+",
            description=rules1_description,
            color=0x00008B
        )
        start_embed.set_author(
            name=channel.guild.name, icon_url=channel.guild.icon.url if channel.guild.icon else channel.guild.icon.url)
        start_embed.add_field(
            name="**Invite Link**", value=f"https://discord.gg/datenight \n\nStand der Regeln und Infos: <t:{int(disnake.utils.utcnow().timestamp())}:R>*", inline=False)
        start_embed.set_footer(text="")
        start_message = await channel.send(embed=start_embed)

        # Create the dropdown options for rules
        message_types = [f"RULES{i}" for i in range(2, 10)]
        options = []
        for message_type in message_types:
            cursor = await DatabaseConnectionManager.execute_sql_statement(channel.guild.id, channel.guild.name, "SELECT TITLE FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (message_type,))
            result = (await cursor.fetchone())
            if result:
                options.append(SelectOption(
                    label=result[0], value=message_type, default=False))

        # Create the dropdown menu for rules
        rules_select = Select(
            placeholder="📝Wähle eine Regel...",
            options=options,
            custom_id="rules_select"
        )

        # Create the dropdown options for server information
        info_options = [
            SelectOption(label="Levelsystem", emoji="💠" , value="LEVEL", default=False),
            SelectOption(label="Warnsystem", emoji="⚠️", value="WARNSYSTEM", default=False),
            # Add more options as needed
        ]

        # Create the dropdown menu for server information
        info_select = Select(
            placeholder="📢Wähle eine Information...",
            options=info_options,
            custom_id="info_select"
        )

        self_roles_button = Button(label="Self Roles", style=disnake.ButtonStyle.link,url="https://discord.com/channels/854698446996766730/1039167130190491709")

        server_team_button = Button(label="Serverteam", style=disnake.ButtonStyle.primary, custom_id="server_team_button")
        
        server_stats_button = Button(label="Server Statistiken", style=disnake.ButtonStyle.green, custom_id="server_stats_button")

        # Create the view and add items
        view = View()
        view.add_item(self_roles_button)
        view.add_item(rules_select)
        view.add_item(info_select)        
        # Add the server team button to the view
        view.add_item(server_team_button)
        view.add_item(server_stats_button)

        await start_message.edit(view=view)

        await inter.edit_original_response(content="Das Regel-Embed wurde erstellt.")

    @exception_handler
    async def server_team_button_callback(self, interaction: disnake.Interaction):
        # Fetch team members from the database
        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "SELECT USERID, ROLE FROM TEAM_MEMBERS WHERE TEAM_ROLE = 1")
        team_members_data = await cursor.fetchall()
        team_members = []
        for user_id, role_name in team_members_data:
            user_record = await self.globalfile.get_user_record(guild=interaction.guild, user_id=user_id)
            if user_record:
                discord_id = user_record['DISCORDID']
                member = interaction.guild.get_member(int(discord_id))
                if member:
                    role_id = self.rolemanager.get_role_id(interaction.guild.id,role_name)
                    role = interaction.guild.get_role(role_id) if role_id else None
                    role_mention = role.mention if role else f"<@&{role_id}>"
                    team_members.append(
                        (role_name, f"{member.mention} - {role_mention}"))

        # Sort team members by role hierarchy
        team_members.sort(
            key=lambda x: self.role_hierarchy.role_hierarchy.index(x[0]))

        # Extract sorted team member mentions
        sorted_team_members = [member for _, member in team_members]

        team_roles = [self.rolemanager.get_role(interaction.guild.id, role_id) for role_id in self.role_hierarchy.role_hierarchy if self.rolemanager.get_role(interaction.guild.id, role_id)]
        team_roles_mentions = ", ".join(
            [role.mention for role in team_roles if role])

        team_channel = self.channelmanager.get_channel(interaction.guild.id, int(os.getenv("TEAM_CHANNEL_ID")))        
        team_embed = disnake.Embed(
            title="Serverteam",
            description="Hier sind die Mitglieder des Serverteams:",
            color=0x00008B
        )
        team_embed.set_author(
            name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else interaction.guild.icon.url)
        team_embed.add_field(name="Teammitglieder", value="\n".join(
            sorted_team_members), inline=False)
        team_embed.add_field(
            name="Vorstellungen", value=f"Die Vorstellungen der Teammitglieder findest du im {team_channel.mention} Channel.", inline=False)
        team_embed.set_footer(
            text="Du kannst jederzeit die Teamrolle pingen, wenn du Hilfe benötigst.")

        await interaction.response.send_message(embed=team_embed, ephemeral=True)

    @exception_handler
    async def server_stats_button_callback(self, interaction: disnake.Interaction):
        self.logger.info(f"Server Stats button pressed by {interaction.user.name}.")
        guild_id = interaction.guild.id

        # Get current time
        current_time = await self.globalfile.get_current_time()

        # Define time periods
        start_of_day = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_week = start_of_day - timedelta(days=start_of_day.weekday())
        start_of_month = start_of_day.replace(day=1)
        start_of_year = start_of_day.replace(month=1, day=1)

        # Fetch message counts
        async def fetch_message_count(start_date):
            cursor = await DatabaseConnectionManager.execute_sql_statement(
                guild_id, interaction.guild.name,
                "SELECT COUNT(*) FROM MESSAGE WHERE INSERT_DATE >= ?", (start_date,)
            )
            result = await cursor.fetchone()
            return result[0] if result else 0

        messages_today = await fetch_message_count(start_of_day)
        messages_this_week = await fetch_message_count(start_of_week)
        messages_this_month = await fetch_message_count(start_of_month)
        messages_this_year = await fetch_message_count(start_of_year)

        # Fetch join and leave counts
        async def fetch_user_count(start_date, condition):
            cursor = await DatabaseConnectionManager.execute_sql_statement(
                guild_id, interaction.guild.name,
                f"SELECT COUNT(*) FROM USER WHERE {condition} >= ?", (start_date,)
            )
            result = await cursor.fetchone()
            return result[0] if result else 0

        joined_today = await fetch_user_count(start_of_day, "JOINED_DATE")
        joined_this_week = await fetch_user_count(start_of_week, "JOINED_DATE")
        joined_this_month = await fetch_user_count(start_of_month, "JOINED_DATE")
        joined_this_year = await fetch_user_count(start_of_year, "JOINED_DATE")

        left_today = await fetch_user_count(start_of_day, "LEAVED_DATE")
        left_this_week = await fetch_user_count(start_of_week, "LEAVED_DATE")
        left_this_month = await fetch_user_count(start_of_month, "LEAVED_DATE")
        left_this_year = await fetch_user_count(start_of_year, "LEAVED_DATE")

        # Fetch voice activity counts
        async def fetch_voice_activity_count(start_date):
            # Convert start_date to date only
            start_date = start_date.date()
            cursor = await DatabaseConnectionManager.execute_sql_statement(
                guild_id, interaction.guild.name,
                "SELECT SUM(VOICE) FROM VOICE_XP WHERE DATE >= ?", (start_date,)
            )
            result = await cursor.fetchone()
            return result[0] if result else 0
        
        async def format_voice_activity(minutes):
            if minutes >= 60:
                hours = minutes // 60
                remaining_minutes = minutes % 60
                return f"{int(hours)} Stunden {remaining_minutes} Minuten" if remaining_minutes > 0 else f"{hours} Stunden"
            return f"{minutes} Minuten"

        voice_activity_today = await fetch_voice_activity_count(start_of_day)
        voice_activity_this_week = await fetch_voice_activity_count(start_of_week)
        voice_activity_this_month = await fetch_voice_activity_count(start_of_month)
        voice_activity_this_year = await fetch_voice_activity_count(start_of_year)

        if voice_activity_today is None:
            voice_activity_today = 0
        if voice_activity_this_week is None:
            voice_activity_this_week = 0
        if voice_activity_this_month is None:
            voice_activity_this_month = 0
        if voice_activity_this_year is None:
            voice_activity_this_year = 0

        # Create embed
        embed = disnake.Embed(
            title="📊 Server Statistiken",
            color=0x00008B,
            timestamp=current_time,
            description="Hier sind die Statistiken für den Server."
        )
        embed.set_author(name=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else interaction.guild.icon.url)

        embed.add_field(name="📅 **Heute**", value=f"Nachrichten: {messages_today}\nVoice-Aktivität: {await format_voice_activity(int(voice_activity_today)//2)}\nBeigetreten: {joined_today}\nVerlassen: {left_today}", inline=False)
        embed.add_field(name="📅 **Diese Woche**", value=f"Nachrichten: {messages_this_week}\nVoice-Aktivität: {await format_voice_activity(int(voice_activity_this_week)//2)}\nBeigetreten: {joined_this_week}\nVerlassen: {left_this_week}", inline=False)
        embed.add_field(name="📅 **Dieser Monat**", value=f"Nachrichten: {messages_this_month}\nVoice-Aktivität: {await format_voice_activity(int(voice_activity_this_month)//2)}\nBeigetreten: {joined_this_month}\nVerlassen: {left_this_month}", inline=False)
        embed.add_field(name="📅 **Dieses Jahr**", value=f"Nachrichten: {messages_this_year}\nVoice-Aktivität: {await format_voice_activity(int(voice_activity_this_year)//2)}\nBeigetreten: {joined_this_year}\nVerlassen: {left_this_year}", inline=False)

        embed.set_footer(text="Server Statistiken")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @exception_handler
    async def _create_nsfwrules_embeds(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        await inter.response.defer()

        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT DESCRIPTION FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", ("NSFWRULES1",))
        result = (await cursor.fetchone())
        if result:
            nsfwrules1_description = result[0].replace('\\n', '\n')

        # Create the initial embed
        start_embed = disnake.Embed(
            title="NSFW Regeln",
            description=nsfwrules1_description,
            color=0x00008B
        )
        start_embed.set_author(
            name=inter.guild.name, icon_url=inter.guild.icon.url if inter.guild.icon else inter.guild.icon.url)
        start_embed.add_field(name="**Wichtige Informationen**",
                              value=f"Bitte lese alle Regeln sorgfältig durch.\n\nStand der Regeln und Infos: <t:{int(disnake.utils.utcnow().timestamp())}:R>*", inline=False)
        start_embed.set_footer(text="")
        start_message = await channel.send(embed=start_embed)

        # Create the dropdown options for nsfw rules
        message_types = [f"NSFWRULES{i}" for i in range(2, 10)]
        options = []
        for message_type in message_types:
            cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT TITLE FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (message_type,))
            result = (await cursor.fetchone())
            if result:
                options.append(SelectOption(
                    label=result[0], value=message_type))

        # Create the dropdown menu for nsfw rules
        nsfwrules_select = Select(
            placeholder="Wähle eine Regel...",
            options=options,
            custom_id="nsfwrules_select"
        )

        # Create the button for NSFW role
        nsfw_role_button = Button(
            label="Regeln akzeptieren", style=disnake.ButtonStyle.green, custom_id="toggle_nsfwrule_button")

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
            selected_role_ids = [
                int(role_id) for role_id in inter.values] if inter.values else []

            # Check if more than one role is selected
            if len(selected_role_ids) > 1:
                if not inter.response.is_done():
                    await inter.response.send_message("Bitte wähle bei dieser Kategorie nur eine Rolle aus.", ephemeral=True)
                return

            selected_roles = [inter.guild.get_role(
                role_id) for role_id in selected_role_ids]

            # Check if the user already has roles from the select menu
            user_roles = inter.author.roles
            role_ids = [option.value for option in inter.component.options]
            existing_roles = [
                role for role in user_roles if str(role.id) in role_ids]

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
            selected_role_ids = [
                int(role_id) for role_id in inter.values] if inter.values else []

            selected_roles = [inter.guild.get_role(
                role_id) for role_id in selected_role_ids]

            # Check if the user already has roles from the select menu
            user_roles = inter.author.roles
            role_ids = [option.value for option in inter.component.options]
            existing_roles = [
                role for role in user_roles if str(role.id) in role_ids]

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
            cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (selected_rule,))
            result = (await cursor.fetchone())

            if result:
                description = result[4].replace('\\n', '\n')
                embed = disnake.Embed(
                    title=result[3],  # Assuming TITLE is the first column
                    description=description,
                    color=0x00008B
                )
                if result[5] != "" and result[5] is not None:
                    # Assuming FOOTER is the fifth column
                    embed.set_footer(text=result[5])

                await inter.send(embed=embed, ephemeral=True)
            else:
                await inter.send("Keine Daten für die ausgewählte Regel gefunden.", ephemeral=True)
        elif inter.component.custom_id == "info_select":
            await inter.response.defer(ephemeral=True)
            selected_info = inter.values[0]

            if selected_info == "LEVEL":
                # Fetch and send the level embed
                cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", ("LEVEL",))
                result = (await cursor.fetchone())

                if result:
                    description = result[4].replace('\\n', '\n')
                    embed = disnake.Embed(
                        title=result[3],  # Assuming TITLE is the first column
                        description=description,
                        color=0x00008B
                    )
                    if result[5] != "" and result[5] is not None:
                        # Assuming FOOTER is the fifth column
                        embed.set_footer(text=result[5])

                    await inter.send(embed=embed, ephemeral=True)
                else:
                    await inter.send("Keine Daten für die ausgewählte Information gefunden.", ephemeral=True)
            if selected_info == "WARNSYSTEM":
                # Fetch and send the warn embed
                cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", ("WARNSYSTEM",))
                result = (await cursor.fetchone())

                if result:
                    description = result[4].replace('\\n', '\n')
                    embed = disnake.Embed(
                        title=result[3],  # Assuming TITLE is the first column
                        description=description,
                        color=0x00008B
                    )
                    if result[5] != "" and result[5] is not None:
                        # Assuming FOOTER is the fifth column
                        embed.set_footer(text=result[5])

                    await inter.send(embed=embed, ephemeral=True)
                else:
                    await inter.send("Keine Daten für die ausgewählte Information gefunden.", ephemeral=True)
        elif inter.component.custom_id == "nsfwrules_select":
            await inter.response.defer(ephemeral=True)
            selected_rule = inter.values[0]
            cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (selected_rule,))
            result = (await cursor.fetchone())

            if result:
                description = result[4].replace('\\n', '\n')
                embed = disnake.Embed(
                    title=result[3],  # Assuming TITLE is the first column
                    description=description,
                    color=0x00008B
                )
                if result[5] != "" and result[5] is not None:
                    # Assuming FOOTER is the fifth column
                    embed.set_footer(text=result[5])

                await inter.send(embed=embed, ephemeral=True)
            else:
                await inter.send("Keine Daten für die ausgewählte Regel gefunden.", ephemeral=True)
        if inter.component.custom_id == "rules_select" or inter.component.custom_id == "info_select":
            options = [SelectOption(label=option.label, value=option.value, default=False) for option in inter.component.options]
            
            # Define info_options separately with the correct values
            info_options = [
                SelectOption(label="Levelsystem", emoji="💠", value="LEVEL", default=False),
                SelectOption(label="Warnsystem", emoji="⚠️", value="WARNSYSTEM", default=False),
                # Add more options as needed
            ]

            message_types = [f"RULES{i}" for i in range(2, 10)]
            options = []
            for message_type in message_types:
                cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT TITLE FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (message_type,))
                result = (await cursor.fetchone())
                if result:
                    options.append(SelectOption(
                        label=result[0], value=message_type, default=False))
                                        
            self_roles_button = Button(label="Self Roles", style=disnake.ButtonStyle.link,url="https://discord.com/channels/854698446996766730/1039167130190491709")
            
            server_team_button = Button(label="Serverteam", style=disnake.ButtonStyle.primary, custom_id="server_team_button")
            
            server_stats_button = Button(label="Server Statistiken", style=disnake.ButtonStyle.green, custom_id="server_stats_button")
            
            await inter.edit_original_response(view=View().add_item(self_roles_button).add_item(server_team_button).add_item(server_stats_button)
            .add_item(Select(
                placeholder="📝Wähle eine Regel...",
                options=options,
                custom_id="rules_select"                
            ),
            ).add_item(Select(
                placeholder="📢Wähle eine Information...",
                options=info_options,
                custom_id="info_select"
            )))

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
            elif custom_id == "server_stats_button":
                await self.server_stats_button_callback(interaction)                

    @exception_handler
    async def nsfwrules_button_callback(self, interaction: disnake.Interaction):
        nsfwrole = self.rolemanager.get_role(interaction.guild.id, int(os.getenv("MSFW_ROLE_ID")))
        if nsfwrole in interaction.user.roles:
            await interaction.user.remove_roles(nsfwrole)
            await interaction.response.send_message("Die Rolle wurde entfernt und du hast die Regeln nicht mehr akzeptiert. Das gilt nicht rückwirkend.", ephemeral=True)
        else:
            await interaction.user.add_roles(nsfwrole)
            await interaction.response.send_message("Die Rolle wurde hinzugefügt und du hast die regeln akzeptiert.", ephemeral=True)

    @exception_handler
    async def seelsorge_button_callback(self, interaction: disnake.Interaction):
        seelsorge_role = self.rolemanager.get_role(interaction.guild.id, int(os.getenv("SEELSORGE_ROLE_ID")))    
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

        guild: disnake.Guild = self.bot.get_guild(payload.guild_id)           
        cursor = await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, "SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGEID = ?", (payload.message_id,))
        result = (await cursor.fetchone())

        if not result:
            return
             
        if not guild:
            return

        for i in range(1, 31):
            role_id = result[7 + (i - 1) * 2]
            emoji = result[8 + (i - 1) * 2]
            if role_id and emoji:
                emojifetched: disnake.Emoji = None
                emojifetched = await self.globalfile.get_emoji_by_name(emoji, guild=guild)
                if emojifetched.id is None:
                    emojifetched = await self.globalfile.get_manual_emoji(emoji)
                if emojifetched and str(emojifetched) == str(payload.emoji):
                    role = guild.get_role(role_id)
                    if role:
                        await guild.get_member(payload.user_id).add_roles(role)
                        self.logger.info(
                            f"Assigned role {role.name} to {payload.member.name} for reacting with {emoji}")
                        break

    @exception_handler
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: disnake.RawReactionActionEvent):
        if payload.user_id == None:
            return
        
        guild: disnake.Guild = self.bot.get_guild(payload.guild_id)
        cursor = await DatabaseConnectionManager.execute_sql_statement(guild.id, guild.name, "SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGEID = ?", (payload.message_id,))
        result = (await cursor.fetchone())

        if not result:
            return

        if not guild:
            return

        for i in range(1, 31):
            role_id = result[7 + (i - 1) * 2]
            emoji = result[8 + (i - 1) * 2]
            if role_id and emoji:
                emojifetched: disnake.Emoji = None
                emojifetched = await self.globalfile.get_emoji_by_name(emoji, guild=guild)
                if emojifetched.id is None:
                    emojifetched = await self.globalfile.get_manual_emoji(emoji)
                if emojifetched and str(emojifetched) == str(payload.emoji):
                    role = guild.get_role(role_id)
                    if role:
                        await guild.get_member(payload.user_id).remove_roles(role)
                        member: disnake.Member = guild.get_member(
                            payload.user_id)
                        self.logger.info(
                            f"Removed role {role.name} from {member.name} for removing reaction {emoji}")
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
        seelsorge_embed.set_author(
            name=inter.guild.name, icon_url=inter.guild.icon.url if inter.guild.icon else inter.guild.icon.url)

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

        seelsorge_embed.add_field(
            name="Beichte", value=beichte_description, inline=False)
        seelsorge_embed.add_field(
            name="Unter den folgenden Telefonnummern können Betroffene zusätzliche Hilfe finden:", value=nummern_description, inline=False)
        seelsorge_embed.description = seelsorge_description
        seelsorge_message = await channel.send(embed=seelsorge_embed)

        # Button hinzufügen
        role_button = Button(label="Regeln akzeptieren",
                             style=disnake.ButtonStyle.green, custom_id="toggle_seelsorge_button")
        view = View()
        view.add_item(role_button)
        await seelsorge_message.edit(view=view)

        await inter.response.send_message("Seelsorge und Beichte Embeds wurden erstellt.", ephemeral=True)

        # Datenbankeintrag erstellen
        await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "INSERT INTO UNIQUE_MESSAGE (MESSAGETYPE, MESSAGEID, TITLE, DESCRIPTION, FOOTER) VALUES (?, ?, ?, ?, ?)",
                                                              ("SEELSORGE", seelsorge_message.id, "Seelsorge Channel", seelsorge_description, ""))

    @exception_handler
    async def _beichte(self, inter: disnake.ApplicationCommandInteraction, message: str):
        beichte_channel : disnake.TextChannel = self.channelmanager.get_channel(inter.guild, int(os.getenv("BEICHTE_CHANNEL_ID")))  
        if not beichte_channel:
            user_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
            await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "INSERT INTO BEICHTEN (USERID, MESSAGE) VALUES (?, ?)", (user_record['ID'], message))

            await inter.response.send_message("Deine Beichte wurde gespeichert und ggfs. für das Team zugänglich.", ephemeral=True)
            await beichte_channel.send(f"Neue Beichte: {message}")
        else:
            await inter.response.send_message("Der Beichte-Channel wurde nicht gefunden bzw noch nicht gesetzt.", ephemeral=True)
            await self.logger.error("Beichte-Channel nicht gefunden.")

    @exception_handler
    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.id != self.bot.user.id:
            load_dotenv(dotenv_path="envs/settings.env", override=True)        
            seelsorge_channel = self.channelmanager.get_channel(message.guild.id, int(os.getenv("SEELSORGE_CHANNEL_ID")))
            if message.channel.id == seelsorge_channel:
                thread: disnake.Thread = await message.channel.create_thread(
                    name=f"{message.author.name}'s Self Reveal",
                    message=message,
                    auto_archive_duration=1440
                )
                await thread.send(f"{message.author.mention} hat diesen Thread eröffnet.")

    @exception_handler
    @commands.Cog.listener()
    async def on_thread_update(self, before: disnake.Thread, after: disnake.Thread):
        seelsorge_channel = self.channelmanager.get_channel(after.guild.id, int(os.getenv("SEELSORGE_CHANNEL_ID")))
        if after.parent_id == seelsorge_channel and after.archived and not after.locked:
            await after.delete()

    @exception_handler
    async def _commands_embed(self, inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
        embed = disnake.Embed(
            title="Verfügbare Befehle",
            description=(
                "Hier findest du alle Befehle die du benutzen kannst.\n" 
                "Bitte verwende den Channel <#1345763534482575503> zum ausführen der Commands.\n\n" 
                "**Allgemeine Befehle**\n"
                "- `/info` - Zeigt technische Informationen über den Bot und den Server an.\n"
                "- `/server` - Zeigt Informationen über den Server an.\n"
                "- `/me` - Zeigt Informationen über deinen Benutzer an.\n"
                "- `/user_profile` - Zeigt Informationen über einen anderen Benutzer an.\n"
                "- `/set_birthday` - Damit kannst du dein Geburtstag setzen.\n"
                "- `/privacy_settings` - Damit stellst du ein wer welche Informationen über dein Profil sehen kann.\n\n"
                "**Cupid Bot Befehle**\n"
                "- `/my_anwers` - Zeigt die Antworten welche du bei dem Dating Bot gegeben hast.\n"
                "- `/edit_answer` - Damit kannst du die Antwort einer Frage bearbeiten.\n"
                "- `/match_users` - Dort findest du eine Detailierte Ausgabe der Fragenanalyse mit dem angegeben User.\n\n"
                "**Level Befehle**\n"
                "- `/top_users` - Zeigt die aktuelle Top Platzierung an. (<#1066777274759786578>)\n\n"                
                "**Freundschafts Befehle**\n"
                "- `/friend_add` - Sendet eine Freundschaftsanfrage an einen Benutzer.\n"
                "- `/friend_remove` - Entfernt einen Benutzer aus deiner Freundesliste.\n"
                "- `/friend_list` - Zeigt deine Freundesliste an.\n"
                "- `/show_friend_requests` - Zeigt alle ausstehenden Freundschaftsanfragen an.\n\n"
                "**Block Befehle**\n"
                "- `/block` - Blockiert einen Benutzer.\n"
                "- `/unblock` - Entblockiert einen Benutzer.\n"
                "- `/blocklist` - Zeigt die Liste der blockierten Benutzer an.\n\n"
                "**Vorstellungs Befehle**\n"
                "- `/set_introduction` - Setzt deine Vorstellung.\n"
                "- `/get_introduction` - Zeigt die Vorstellung eines Benutzers an.\n\n"
                "**Voice Commands**\n"
                "- Diese findest du ausgesondert in <#1338259151184330833>.\n"
            ),
            color=disnake.Color.blue()
        )
        embed.set_author(
            name=inter.guild.name, icon_url=inter.guild.icon.url if inter.guild.icon else inter.guild.icon.url)
        await channel.send(embed=embed)
        await inter.response.send_message("Das Befehls-Embed wurde erstellt.", ephemeral=True)

def setupRoleAssignment(bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
    bot.add_cog(RoleAssignment(bot, rolemanager, channelmanager))
