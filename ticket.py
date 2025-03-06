import disnake
from disnake.ext import commands
from dbconnection import DatabaseConnectionManager
from rolehierarchy import rolehierarchy
from globalfile import Globalfile
from datetime import datetime
import logging
import os
import sqlite3
from typing import Union
from exceptionhandler import exception_handler
from rolemanager import RoleManager
import disnake
from disnake.ext import commands
from disnake import SelectOption
from disnake.ui import Select, View


class Ticket(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager: RoleManager):
        self.bot = bot
        self.logger = logging.getLogger("Ticket")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.globalfile: Globalfile = self.bot.get_cog('Globalfile')
        self.guild: disnake.Guild = None
        self.support_channel = None  # Hinzugefügt
        self.verify_channel = None  # Hinzugefügt
        self.rolemanager = rolemanager

        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    @commands.Cog.listener()
    async def on_ready(self):
        self.support_channel = self.bot.guilds[0].get_channel(
            1061446191088418888)
        self.verify_channel = self.bot.guilds[0].get_channel(
            1323005558730657812)
        self.team_role = self.rolemanager.get_role(
            self.bot.guilds[0].id, 1235534762609872899)
        guild = await self.bot.fetch_guild(854698446996766730)
        self.bot.add_view(await self.create_bewerbung_view(guild))
        self.bot.add_view(await self.create_ticket_view(guild))
        self.bot.add_view(await self.create_admin_ticket_view(guild))
        self.bot.add_view(await self.create_verify_ticket_view(guild))
        self.logger.info("Ticket Cog is ready.")

    @exception_handler
    async def fetch_channel_messages(self, channel: disnake.TextChannel):
        messages = []
        async for message in channel.history(limit=None):
            messages.append(message)
        return messages

    @exception_handler
    async def save_html_to_file(self, html_content, file_path):
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(html_content)

    @exception_handler
    async def export_chat(self, channel: disnake.TextChannel):
        messages = await self.fetch_channel_messages(channel)
        html_content = await self.format_messages_to_html(messages)
        file_path = os.path.join(
            os.getcwd(), f"{channel.name}_chat_history.html")
        await self.save_html_to_file(html_content, file_path)

        self.logger.info(f"Chat history has been exported to {file_path}")

    async def format_messages_to_html(self, messages):
        html_content = """
        <html>
        <head>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    background-color: #36393f;
                    color: #dcddde;
                    padding: 20px;
                }
                .message {
                    border-bottom: 1px solid #2f3136;
                    padding: 10px;
                    margin-bottom: 10px;
                }
                .message .author {
                    font-weight: bold;
                    color: #7289da;
                }
                .message .timestamp {
                    font-size: 0.75em;
                    color: #72767d;
                    margin-left: 10px;
                }
                .message .content {
                    margin-top: 5px;
                }
            </style>
        </head>
        <body>
        """

        for message in messages:
            timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S')
            html_content += f"""
            <div class="message">
                <div class="author">{message.author.display_name}<span class="timestamp">{timestamp}</span></div>
                <div class="content">{message.content}</div>
            </div>
            """

        html_content += """
        </body>
        </html>
        """
        return html_content

    @exception_handler
    async def save_html_to_file(self, html_content, file_path):
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(html_content)


    async def create_bewerbung_view(self, guild: disnake.Guild):
        bewerbung_button = disnake.ui.Button(
            label="Öffne ein Bewerbungs Ticket!", 
            emoji=await self.globalfile.get_manual_emoji("incoming_envelope"), 
            style=disnake.ButtonStyle.blurple, custom_id="bewerbung_button")
        bewerbung_view = disnake.ui.View(timeout=None)
        bewerbung_view.add_item(bewerbung_button)
        return bewerbung_view

    async def create_admin_ticket_view(self, guild: disnake.Guild):
        emoji = await self.globalfile.get_emoji_by_name(emoji_name="owner", guild=guild)
        admin_ticket_button = disnake.ui.Button(
            label="Öffne ein Admin Ticket!", emoji=emoji, style=disnake.ButtonStyle.blurple, custom_id="admin_ticket_button")
        admin_ticket_view = disnake.ui.View(timeout=None)
        admin_ticket_view.add_item(admin_ticket_button)
        return admin_ticket_view
    
    async def create_ticket_view(self, guild: disnake.Guild):
        emoji = await self.globalfile.get_emoji_by_name(emoji_name="blackhammerids", guild=guild)
        ticket_button = disnake.ui.Button(
            label=f"Öffne ein Support Ticket!", emoji=emoji, style=disnake.ButtonStyle.blurple, custom_id="ticket_button")
        ticket_view = disnake.ui.View(timeout=None)
        ticket_view.add_item(ticket_button)
        return ticket_view

    async def create_verify_ticket_view(self, guild: disnake.Guild):
        emoji = await self.globalfile.get_emoji_by_name(emoji_name="verified", guild=guild)
        verify_ticket_button = disnake.ui.Button(
            label="Verify Ticket erstellen!", emoji=emoji, style=disnake.ButtonStyle.green, custom_id="verify_ticket_button")
        verify_ticket_view = disnake.ui.View(timeout=None)
        verify_ticket_view.add_item(verify_ticket_button)
        return verify_ticket_view

    @exception_handler
    @commands.Cog.listener()
    async def on_interaction(self, interaction: disnake.Interaction):
        if interaction.type == disnake.InteractionType.component:
            custom_id = interaction.data.get("custom_id")                        
            if custom_id == "verify_ticket_button":
                await self.verify_ticket_button_callback(interaction)
            elif custom_id.startswith("claim_button_"):
                ticket_id = int(custom_id.split("_")[-1])
                await self.claim_ticket(interaction, ticket_id, interaction.user.id)
            elif custom_id.startswith("close_button_"):
                ticket_id = int(custom_id.split("_")[-1])
                await self.close_ticket(interaction, ticket_id)
            elif custom_id == "ticket_select":
                selected_value = interaction.data.get("values")[0]
                if selected_value == "bewerbung":
                    await self.create_ticket_channel(interaction, "Bewerbung")
                elif selected_value == "admin":
                    await self.create_ticket_channel(interaction, "Admin Ticket")
                elif selected_value == "support":
                    await self.create_ticket_channel(interaction, "Support Ticket")
            elif custom_id == "delete_channel_button":
                if self.team_role in interaction.user.roles:
                    await interaction.channel.delete()
                else:
                    await interaction.response.send_message("Du hast nicht die erforderlichen Berechtigungen, um diesen Kanal zu löschen.", ephemeral=True)

    @exception_handler
    async def check_and_update_message(self, channel: disnake.TextChannel, embed, message_type, button_view):
        cursor = await DatabaseConnectionManager.execute_sql_statement(channel.guild.id, channel.guild.name, "SELECT MESSAGEID FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (message_type,))
        result = (await cursor.fetchone())

        if result:
            message_id = result[0]
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
            except disnake.NotFound:
                pass

            # Aktualisiere die MESSAGEID in der Datenbank
            message = await channel.send(embed=embed, view=button_view)
            cursor = await DatabaseConnectionManager.execute_sql_statement(channel.guild.id, channel.guild.name, "UPDATE UNIQUE_MESSAGE SET MESSAGEID = ? WHERE MESSAGETYPE = ?", (message.id, message_type))
        else:
            # Füge einen neuen Eintrag in die Datenbank ein
            message = await channel.send(embed=embed, view=button_view)
            await DatabaseConnectionManager.execute_sql_statement(channel.guild.id, channel.guild.name, "INSERT INTO UNIQUE_MESSAGE (MESSAGETYPE, MESSAGEID) VALUES (?, ?)", (message_type, message.id))

    @exception_handler
    async def create_ticket_channel(self, interaction: disnake.Interaction, ticket_type: str):
        guild = interaction.guild
        # Replace with your category ID
        category = guild.get_channel(854698446996766739)

        if not isinstance(category, disnake.CategoryChannel):
            await interaction.response.send_message("Die angegebene Kategorie-ID ist ungültig. Bitte überprüfen Sie die Kategorie-ID.", ephemeral=True)
            return

        # Calculate the next Ticket ID
        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "SELECT MAX(ID) FROM Ticket")
        max_id = (await cursor.fetchone())[0]
        next_id = (max_id + 1) if max_id is not None else 1

        channel_name = f"{ticket_type.lower()}-{next_id}"

        # Fetch roles
        leitung_role = disnake.utils.get(guild.roles, name="Leitung")
        team_role = disnake.utils.get(guild.roles, name="Team")

        # Define permissions
        overwrites = {
            guild.default_role: disnake.PermissionOverwrite(read_messages=False),
            interaction.user: disnake.PermissionOverwrite(
                read_messages=True, send_messages=True)
        }

        if ticket_type.lower() == "admin ticket" and leitung_role:
            overwrites[leitung_role] = disnake.PermissionOverwrite(
                read_messages=True, send_messages=True)
        elif ticket_type.lower() == "ticket" and team_role:
            overwrites[team_role] = disnake.PermissionOverwrite(
                read_messages=True, send_messages=True)

        # Create the new channel
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        if ticket_channel != None:
            self.logger.info(
                f"Ticket channel {ticket_channel.name} created successfully.")
        else:
            self.logger.error(
                f"Failed to create ticket channel {channel_name}.")
            await interaction.response.send_message("Fehler beim Erstellen des Ticketkanals. Bitte versuchen Sie es erneut.", ephemeral=True)
            return

        # Insert the new entry into the database
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "INSERT INTO Ticket (ID, TICKETTYPE, USERID, CREATED_AT) VALUES (?, ?, ?, ?)", (next_id, ticket_type, interaction.user.id, created_at))

        # Create the Claim button
        claim_button = disnake.ui.Button(
            label="Claim", style=disnake.ButtonStyle.green, custom_id=f"claim_button_{next_id}")

        # Create the Close button
        close_button = disnake.ui.Button(
            label="Close", style=disnake.ButtonStyle.red, custom_id=f"close_button_{next_id}")

        claim_view = disnake.ui.View(timeout=None)
        claim_view.add_item(claim_button)
        claim_view.add_item(close_button)

        current_time = await self.globalfile.get_current_time()
        timestamp = int(current_time.timestamp())

        if ticket_type.lower() == "verify ticket":
            content = ("vielen Dank, dass du dich auf Date Night verifizieren möchtest.\n\n"
                       "Bitte schicke uns ein Bild von dir mit einem Zettel, auf dem dein Discord-Tag und das aktuelle Datum geschrieben sind. "
                       "Anschließend erhälst du die <@&1066793314482913391> Rolle, als Bestätigung deiner Identität.\n\n"
                       "Bitte beachte, dass wir deine Daten nur für die Verifizierung verwenden und sie nicht an Dritte weitergeben. Das Ticket wie auch das Bild werden nach der Verifizierung gelöscht. "
                       "Wenn du Fragen zur Verifizierung hast, kannst du sie gerne hier im Ticket stellen.\n"
                       f"Ticket wurde erstellt am: <t:{timestamp}:R>\n\nViele Grüße\nDas Date Night Team"
                       )
        else:
            content = ("vielen Dank, dass du dich an uns gewendet hast. Wir sind da um dir zu helfen.\n\n"
                       "Bitte schildere uns dein Anliegen so detailliert wie möglich, damit wir dir schnell und effektiv helfen können.\n\n"
                       "Dazu könntest du uns folgende Informationen geben:\n"
                       "- Was ist dein Anliegen?\n"
                       "- Seit wann besteht das Problem?/Wann ist es aufgetreten?\n\n"
                       f"Ticket wurde erstellt am: <t:{timestamp}:R>\n\nViele Grüße\nDas Date Night Team"
                       )
        # Create the embed for the message
        ticket_embed = disnake.Embed(
            title="Neues Ticket",
            description=f"Hey {interaction.user.mention},\n\n {content}",
            color=0x98f5ff
        )
        # Send the message in the new channel
        ticket_embed.set_thumbnail(url=interaction.user.avatar.url)
        ticket_embed.set_footer(text=f"Ticket ID: {next_id}")
        ticket_embed.set_author(name=guild.name, icon_url=guild.icon.url)
        await ticket_channel.send(embed=ticket_embed, view=claim_view)
        await interaction.response.send_message(f"Dein Ticket wurde erfolgreich erstellt. {ticket_channel.mention}", ephemeral=True)

    @exception_handler
    async def claim_ticket(self, interaction: disnake.Interaction, ticket_id: int, user_id: int):
        role_hierarchy = rolehierarchy()
        if not role_hierarchy.has_role_or_higher(interaction.author, "Supporter"):
            await interaction.response.send_message("Du hast nicht die erforderlichen Berechtigungen, um dieses Ticket zu claimen.", ephemeral=True)
            return

        # Überprüfe, ob das Ticket bereits zugewiesen wurde
        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "SELECT ASSIGNED FROM Ticket WHERE ID = ?", (ticket_id,))
        assigned = (await cursor.fetchone())[0]
        if assigned:
            assigned_user = await self.bot.fetch_user(assigned)
            await interaction.response.send_message(f"Dieses Ticket wurde bereits {assigned_user.mention} zugewiesen.", ephemeral=True)
            self.logger.debug(f"Ticket {ticket_id} wurde bereits zugewiesen.")
            return

        # Aktualisiere das Ticket in der Datenbank
        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "UPDATE Ticket SET ASSIGNED = ? WHERE ID = ?", (interaction.author.id, ticket_id))

        await interaction.response.send_message(f"Dieses Ticket wurde dem Teammitglied {interaction.author.mention} zugewiesen.")
        self.logger.info(
            f"Ticket {ticket_id} wurde erfolgreich dem Teammitglied {interaction.author.name} zugewiesen.")

    @exception_handler
    async def close_ticket(self, interaction: disnake.Interaction, ticket_id: int):
        # Setze das Ticket in der Datenbank auf "DONE"
        await interaction.response.defer()
        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "UPDATE TICKET SET DONE = 1 WHERE ID = ?", (ticket_id,))

        await self.export_chat(interaction.channel)

        # Schließe den Kanal nicht sofort, sondern sende ein Embed mit einem Button zum endgültigen Löschen
        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "SELECT USERID, TICKETTYPE, CREATED_AT, ASSIGNED FROM Ticket WHERE ID = ?", (ticket_id,))
        ticket_info = (await cursor.fetchone())
        user_id, ticket_type, created_at, assigned_id = ticket_info
        user = await self.bot.fetch_user(user_id)

        # Entferne Schreibrechte des Benutzers
        team_role_id = 1235534762609872899
        bot_role_id = 854698446996766738

        team_role = disnake.utils.get(interaction.guild.roles, id=team_role_id)
        bot_role = disnake.utils.get(interaction.guild.roles, id=bot_role_id)

        for member in interaction.channel.members:
            if team_role not in member.roles and bot_role not in member.roles:
                await interaction.channel.set_permissions(member, send_messages=False, read_messages=True)

        # Verschiebe den Kanal in eine andere Kategorie
        archive_category = disnake.utils.get(
            interaction.guild.categories, id=1336437509487460523)
        await interaction.channel.edit(category=archive_category)

        # Sende eine DM an den Benutzer, der das Ticket erstellt hat
        try:
            await user.send(f"Dein Ticket mit der ID {ticket_id} wurde geschlossen.")
        except Exception as e:
            self.logger.error(f"Error sending DM to {user.name}: {e}")
        await interaction.followup.send(f"{user.mention}, das Ticket wurde geschlossen.")
        self.logger.info(f"Ticket {ticket_id} wurde erfolgreich geschlossen.")

        # Sende ein Embed in einen bestimmten Channel
        log_channel = self.bot.get_channel(1061456790279168141)
        # Ersetze durch die ID des gewünschten Kanals
        test_channel = self.bot.get_channel(1233796714721317014)
        assigned_user = await self.bot.fetch_user(assigned_id) if assigned_id else None
        embed = disnake.Embed(
            title="Ticket geschlossen",
            description=f"Ticket ID: {ticket_id}\nTicket Typ: {ticket_type}\nErstellt von: {user.mention}\nErstellt am: {created_at}\nZugewiesen an: {assigned_user.mention if assigned_user else 'Nicht zugewiesen'}",
            color=disnake.Color.red()
        )
        embed.set_footer(text=f"Geschlossen von: {interaction.user.name}")

        file_path = os.path.join(
            os.getcwd(), "ticketlogs", f"{interaction.channel.name}_chat_history.html")
        file = disnake.File(
            file_path, filename=f"{interaction.channel.name}_chat_history.html")

        # Sende die Datei zuerst
        file_message = await test_channel.send(file=file)

        # Hole die URL der hochgeladenen Datei
        file_url = file_message.attachments[0].url

        # Sende das Embed und die Schaltfläche
        view = disnake.ui.View()
        view.add_item(disnake.ui.Button(
            label="Chatverlauf herunterladen", style=disnake.ButtonStyle.link, url=file_url))
        await log_channel.send(embed=embed, view=view)

        # Sende ein Embed in den Ticket-Kanal mit einem Button zum endgültigen Löschen
        delete_embed = disnake.Embed(
            title="Ticket geschlossen",
            description="Dieses Ticket wurde geschlossen. Klicke auf den Button unten, um den Kanal endgültig zu löschen.",
            color=disnake.Color.red()
        )
        delete_view = disnake.ui.View()
        delete_view.add_item(disnake.ui.Button(
            label="Kanal löschen", style=disnake.ButtonStyle.danger, custom_id="delete_channel_button"))
        await interaction.channel.send(embed=delete_embed, view=delete_view)

    @exception_handler
    async def export_chat(self, channel: disnake.TextChannel):
        messages = await self.fetch_channel_messages(channel)
        html_content = await self.format_messages_to_html(messages)
        directory = os.path.join(os.getcwd(), "ticketlogs")
        os.makedirs(directory, exist_ok=True)
        file_path = os.path.join(
            directory, f"{channel.name}_chat_history.html")
        await self.save_html_to_file(html_content, file_path)

        self.logger.info(f"Chat history has been exported to {file_path}")

    @exception_handler
    async def bewerbung_button_callback(self, interaction: disnake.Interaction):
        await self.create_ticket_channel(interaction, "Bewerbung")

    @exception_handler
    async def ticket_button_callback(self, interaction: disnake.Interaction):
        await self.create_ticket_channel(interaction, "Ticket")

    @exception_handler
    async def admin_ticket_button_callback(self, interaction: disnake.Interaction):
        await self.create_ticket_channel(interaction, "Admin Ticket")

    @exception_handler
    async def verify_ticket_button_callback(self, interaction: disnake.Interaction):
        await self.create_ticket_channel(interaction, "Verify Ticket")

    @exception_handler
    async def _create_ticket_embed_with_dropdown(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer()

        # Embed erstellen
        ticket_embed = disnake.Embed(            
            title="Ticket Auswahl",
            description=(
                "Wähle eine der folgenden Ticket-Arten aus:\n\n"
                "**Bewerbung Ticket**\n"
                "Erstelle ein Bewerbungsticket, wenn du dich als Supporter oder Entwickler bewerben möchtest. "
                "Supporter-Rollen können ebenfalls Aufgaben wie Eventplanung und Promotion umfassen. "
                "Entwickler-Rollen beinhalten die Arbeit an Projekten und technischen Aufgaben.\n\n"
                "**Admin Ticket**\n"
                "Erstelle ein Admin-Ticket, wenn du administrative Anliegen hast oder ein Teammitglied melden möchtest. "
                "Dieses Ticket ist für Themen, welche die Aufmerksamkeit des Administrations-Teams erfordern.\n\n"
                "**Support Ticket**\n"
                "Hier kannst du ein Support-Ticket öffnen, wenn du allgemeine Fragen hast oder einen Spieler melden möchtest. "
                "Diese Art der Tickets sind für die generelle Unterstützung der User, welche die Aufmerksamkeit des Support-Teams erfordern."
            ),
            color=0x0080FF
        )
        ticket_embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar.url)

        # Dropdown-Optionen erstellen
        options = [
            SelectOption(label="Support Ticket", description="Erstelle ein Support-Ticket", emoji=await self.globalfile.get_emoji_by_name(emoji_name="blurpleban", guild=inter.guild) , value="support"),
            SelectOption(label="Admin Ticket", description="Erstelle ein Admin-Ticket", emoji=await self.globalfile.get_emoji_by_name(emoji_name="reportmessage", guild=inter.guild) , value="admin"),
            SelectOption(label="Bewerbung Ticket", description="Erstelle ein Bewerbungsticket", emoji=await self.globalfile.get_emoji_by_name(emoji_name="member", guild=inter.guild) , value="bewerbung")            
        ]

        # Dropdown-Menü erstellen
        select = Select(
            placeholder="Wähle eine Ticket-Art...",
            options=options,
            custom_id="ticket_select"
        )

        # View erstellen und Dropdown-Menü hinzufügen
        view = View()
        view.add_item(select)

        # Embed und View senden
        await inter.edit_original_response(embed=ticket_embed, view=view)

def setupTicket(bot: commands.Bot, rolemanager: RoleManager):
    bot.add_cog(Ticket(bot, rolemanager))
