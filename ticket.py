import disnake
from disnake.ext import commands
import sqlite3
import logging
from dbconnection import DatabaseConnection
from rolehierarchy import rolehierarchy
from globalfile import Globalfile
from datetime import datetime
import os

class Ticket(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger("Ticket")
        formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.db: sqlite3.Connection = DatabaseConnection()
        self.cursor: sqlite3.Cursor = self.db.connection.cursor()
        self.globalfile = Globalfile(self.bot)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS TICKET (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                TICKETTYPE TEXT,
                USERID INTEGER NOT NULL,
                DONE INTEGER DEFAULT (0) NOT NULL,
                ASSIGNED INTEGER
            )
        """)
        self.db.connection.commit()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS UNIQUE_MESSAGE (
                ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                MESSAGEID TEXT,
                MESSAGETYPE TEXT                
            )
        """)
        self.db.connection.commit()

    async def fetch_channel_messages(self, channel: disnake.TextChannel):
        messages = []
        async for message in channel.history(limit=None):
            messages.append(message)
        return messages

    def format_messages_to_html(self, messages):
        html_content = "<html><head><title>Chat History</title></head><body>"
        for message in messages:
            html_content += f"<p><strong>{message.author.name}:</strong> {message.content}</p>"
        html_content += "</body></html>"
        return html_content

    async def save_html_to_file(self, html_content, file_path):
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(html_content)

    async def export_chat(self, channel: disnake.TextChannel):
        messages = await self.fetch_channel_messages(channel)
        html_content = self.format_messages_to_html(messages)
        file_path = os.path.join(os.getcwd(), f"{channel.name}_chat_history.html")
        await self.save_html_to_file(html_content, file_path)

        self.logger.info(f"Chat history has been exported to {file_path}")

    def format_messages_to_html(self, messages):
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

    async def save_html_to_file(self, html_content, file_path):
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(html_content)        

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(self.create_bewerbung_view())
        self.bot.add_view(self.create_ticket_view())
        self.bot.add_view(self.create_admin_ticket_view())
        self.bot.add_view(self.create_verify_ticket_view())

    def create_bewerbung_view(self):
        bewerbung_button = disnake.ui.Button(label="Bewerbung erstellen", style=disnake.ButtonStyle.blurple, custom_id="bewerbung_button")
        bewerbung_view = disnake.ui.View(timeout=None)
        bewerbung_view.add_item(bewerbung_button)
        return bewerbung_view

    def create_ticket_view(self):
        ticket_button = disnake.ui.Button(label="📫 Öffne ein Ticket!", style=disnake.ButtonStyle.blurple, custom_id="ticket_button")
        ticket_view = disnake.ui.View(timeout=None)
        ticket_view.add_item(ticket_button)
        return ticket_view

    def create_admin_ticket_view(self):
        admin_ticket_button = disnake.ui.Button(label="Admin Ticket erstellen", style=disnake.ButtonStyle.blurple, custom_id="admin_ticket_button")
        admin_ticket_view = disnake.ui.View(timeout=None)
        admin_ticket_view.add_item(admin_ticket_button)
        return admin_ticket_view
    
    def create_verify_ticket_view(self):
        verify_ticket_button = disnake.ui.Button(label="Verify Ticket erstellen", style=disnake.ButtonStyle.green, custom_id="verify_ticket_button")
        verify_ticket_view = disnake.ui.View(timeout=None)
        verify_ticket_view.add_item(verify_ticket_button)
        return verify_ticket_view    
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: disnake.Interaction):
        if interaction.type == disnake.InteractionType.component:
            custom_id = interaction.data.get("custom_id")
            if custom_id == "bewerbung_button":
                await self.bewerbung_button_callback(interaction)
            elif custom_id == "ticket_button":
                await self.ticket_button_callback(interaction)
            elif custom_id == "admin_ticket_button":
                await self.admin_ticket_button_callback(interaction)
            elif custom_id == "verify_ticket_button":
                await self.verify_ticket_button_callback(interaction)                
            elif custom_id.startswith("claim_button_"):
                ticket_id = int(custom_id.split("_")[-1])
                await self.claim_ticket(interaction, ticket_id, interaction.user.id)
            elif custom_id.startswith("close_button_"):
                ticket_id = int(custom_id.split("_")[-1])
                await self.close_ticket(interaction, ticket_id)  

    async def check_and_update_message(self, channel: disnake.TextChannel, embed, message_type, button_view):
        self.cursor.execute("SELECT MESSAGEID FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (message_type,))
        result = self.cursor.fetchone()

        if result:
            message_id = result[0]
            try:
                message = await channel.fetch_message(message_id)
                await message.delete()
            except disnake.NotFound:
                pass

            # Aktualisiere die MESSAGEID in der Datenbank
            message = await channel.send(embed=embed, view=button_view)
            self.cursor.execute("UPDATE UNIQUE_MESSAGE SET MESSAGEID = ? WHERE MESSAGETYPE = ?", (message.id, message_type))
        else:
            # Füge einen neuen Eintrag in die Datenbank ein
            message = await channel.send(embed=embed, view=button_view)
            self.cursor.execute("INSERT INTO UNIQUE_MESSAGE (MESSAGETYPE, MESSAGEID) VALUES (?, ?)", (message_type, message.id))

        self.db.connection.commit()            

    async def create_ticket_channel(self, interaction: disnake.Interaction, ticket_type: str):
        guild = interaction.guild
        category = guild.get_channel(854698446996766739)  # Replace with your category ID

        if not isinstance(category, disnake.CategoryChannel):
            await interaction.response.send_message("Die angegebene Kategorie-ID ist ungültig. Bitte überprüfen Sie die Kategorie-ID.", ephemeral=True)
            return

        # Calculate the next Ticket ID
        self.cursor.execute("SELECT MAX(ID) FROM Ticket")
        max_id = self.cursor.fetchone()[0]
        next_id = (max_id + 1) if max_id is not None else 1

        channel_name = f"{ticket_type.lower()}-{next_id}"

        # Fetch roles
        leitung_role = disnake.utils.get(guild.roles, name="Leitung")
        team_role = disnake.utils.get(guild.roles, name="Team")

        # Define permissions
        overwrites = {
            guild.default_role: disnake.PermissionOverwrite(read_messages=False),
            interaction.user: disnake.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        if ticket_type.lower() == "admin ticket" and leitung_role:
            overwrites[leitung_role] = disnake.PermissionOverwrite(read_messages=True, send_messages=True)
        elif ticket_type.lower() == "ticket" and team_role:
            overwrites[team_role] = disnake.PermissionOverwrite(read_messages=True, send_messages=True)

        # Create the new channel
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        if ticket_channel != None:
            self.logger.info(f"Ticket channel {ticket_channel.name} created successfully.")
        else:
            self.logger.error(f"Failed to create ticket channel {channel_name}.")
            await interaction.response.send_message("Fehler beim Erstellen des Ticketkanals. Bitte versuchen Sie es erneut.", ephemeral=True)
            return

        # Insert the new entry into the database
        self.cursor.execute("INSERT INTO Ticket (ID, TICKETTYPE, USERID) VALUES (?, ?, ?)", (next_id, ticket_type, interaction.user.id))
        self.db.connection.commit()

        # Create the Claim button
        claim_button = disnake.ui.Button(label="Claim", style=disnake.ButtonStyle.green, custom_id=f"claim_button_{next_id}")
        
        # Create the Close button
        close_button = disnake.ui.Button(label="Close", style=disnake.ButtonStyle.red, custom_id=f"close_button_{next_id}")
        
        claim_view = disnake.ui.View(timeout=None)
        claim_view.add_item(claim_button)
        claim_view.add_item(close_button)
        
        globalfile_instance = Globalfile(self.bot)
        current_time = globalfile_instance.get_current_time()
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

    async def claim_ticket(self, interaction: disnake.Interaction, ticket_id: int, user_id: int):
        role_hierarchy = rolehierarchy()
        if not role_hierarchy.has_role_or_higher(interaction.author, "Supporter"):
            await interaction.response.send_message("Du hast nicht die erforderlichen Berechtigungen, um dieses Ticket zu claimen.", ephemeral=True)
            return

        # Überprüfe, ob das Ticket bereits zugewiesen wurde
        self.cursor.execute("SELECT ASSIGNED FROM Ticket WHERE ID = ?", (ticket_id,))
        assigned = self.cursor.fetchone()[0]
        if assigned:
            assigned_user = await self.bot.fetch_user(assigned)
            await interaction.response.send_message(f"Dieses Ticket wurde bereits {assigned_user.mention} zugewiesen.", ephemeral=True)
            self.logger.debug(f"Ticket {ticket_id} wurde bereits zugewiesen.")
            return

        # Aktualisiere das Ticket in der Datenbank
        self.cursor.execute("UPDATE Ticket SET ASSIGNED = ? WHERE ID = ?", (interaction.author.id, ticket_id))
        self.db.connection.commit()

        await interaction.response.send_message(f"Dieses Ticket wurde dem Teammitglied {interaction.author.mention} zugewiesen.")
        self.logger.info(f"Ticket {ticket_id} wurde erfolgreich dem Teammitglied {interaction.author.name} zugewiesen.")

    async def close_ticket(self, interaction: disnake.Interaction, ticket_id: int):
        # Setze das Ticket in der Datenbank auf "DONE"
        self.cursor.execute("UPDATE TICKET SET DONE = 1 WHERE ID = ?", (ticket_id,))
        self.db.connection.commit()
        await self.export_chat(interaction.channel)
        # Schließe den Kanal
        await interaction.channel.delete()

        # Sende eine DM an den Benutzer, der das Ticket erstellt hat
        self.cursor.execute("SELECT USERID FROM Ticket WHERE ID = ?", (ticket_id,))
        user_id = self.cursor.fetchone()[0]
        user = await self.bot.fetch_user(user_id)
        await user.send(f"Dein Ticket mit der ID {ticket_id} wurde geschlossen.")
        self.logger.info(f"Ticket {ticket_id} wurde erfolgreich geschlossen.")

# Define the button callbacks as separate methods
    async def bewerbung_button_callback(self, interaction: disnake.Interaction):
        await self.create_ticket_channel(interaction, "Bewerbung")

    async def ticket_button_callback(self, interaction: disnake.Interaction):
        await self.create_ticket_channel(interaction, "Ticket")

    async def admin_ticket_button_callback(self, interaction: disnake.Interaction):
        await self.create_ticket_channel(interaction, "Admin Ticket")
        
    async def verify_ticket_button_callback(self, interaction: disnake.Interaction):
        await self.create_ticket_channel(interaction, "Verify Ticket")        

    @commands.slash_command(guild_ids=[854698446996766730])
    async def create_ticket_embeds(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer(ephemeral=True)  # Defer the interaction

        channel = self.bot.get_channel(1061446191088418888)  # Ersetzen Sie YOUR_CHANNEL_ID durch die ID des Kanals
        guild = inter.guild

        # Bewerbung Embed
        bewerbung_embed = disnake.Embed(
            title="Bewerbung",
            description=(
                "Erstelle ein Bewerbungsticket, wenn du dich als Supporter oder Entwickler bewerben möchtest. "
                "Supporter-Rollen können ebenfalls Aufgaben wie Eventplanung und Promotion umfassen. "
                "Entwickler-Rollen beinhalten die Arbeit an Projekten und technischen Aufgaben. "
            ),
            color=0x0080FF
        )
        bewerbung_embed.set_author(name=self.bot.user.name, icon_url=guild.icon.url if guild.icon else None)
        bewerbung_view = self.create_bewerbung_view()

        # Ticket Embed
        ticket_embed = disnake.Embed(
            title="Ticket",
            description=(
                "Hier kannst du ein Support-Ticket öffnen, wenn du Fragen hast oder dem Team ein Anliegen schildern möchtest. "
                "Dieses Ticket ist für allgemeine Unterstützung, technische Hilfe oder andere Anliegen, die die Aufmerksamkeit des Support-Teams erfordern. "
            ),
            color=0x0080FF
        )
        ticket_embed.set_author(name=self.bot.user.name, icon_url=guild.icon.url if guild.icon else None)
        ticket_view = self.create_ticket_view()

        # Admin Ticket Embed
        admin_ticket_embed = disnake.Embed(
            title="Admin Ticket",
            description=(
                "Erstelle ein Admin-Ticket, wenn du administrative Anliegen oder Beschwerden hast. "
                "Dieses Ticket ist für Themen wie Regelverstöße, technische Probleme, oder andere "
                "wichtige Angelegenheiten, die die Aufmerksamkeit des Administrations-Teams erfordern. "
            ),
            color=0x0080FF
        )
        admin_ticket_embed.set_author(name=self.bot.user.name, icon_url=guild.icon.url if guild.icon else None)
        admin_ticket_view = self.create_admin_ticket_view()
        
        verify_ticket_embed = disnake.Embed(
            title="Verify Ticket",
            description=(
                "Erstelle ein Verify-Ticket, um dich zu verifizieren. "
                "Im Zuge des Tickets wirst du aufgefordert, persönliche Informationen anzugeben, um deine Identität zu bestätigen. "
                "Du wirst gebeten, ein Bild von dir mit einem Zettel zu senden, auf dem dein Discord-Tag und das aktuelle "
                "Datum geschrieben sind. "
                "Im Zuge des Tickets beantworten wir dir Fragen zu der Notwendigkeit der Verifizierung und der Erhebung dieser Informationen. "
            ),
            color=0x0080FF
        )        
        verify_ticket_embed.set_author(name=self.bot.user.name, icon_url=guild.icon.url if guild.icon else None)
        verify_ticket_view = self.create_verify_ticket_view()

        await self.check_and_update_message(channel, bewerbung_embed, "Bewerbung", bewerbung_view)
        await self.check_and_update_message(channel, ticket_embed, "Ticket", ticket_view)
        await self.check_and_update_message(channel, admin_ticket_embed, "Admin Ticket", admin_ticket_view)
        await self.check_and_update_message(self.bot.get_channel(1323005558730657812), verify_ticket_embed, "Verify Ticket", verify_ticket_view)        
        self.logger.info("Ticket Embeds have been created/updated.")
        await inter.edit_original_response(content="Ticket Embeds wurden erstellt/aktualisiert.")    

    

def setupTicket(bot):
    bot.add_cog(Ticket(bot))