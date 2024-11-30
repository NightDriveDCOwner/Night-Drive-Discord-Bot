import disnake
from disnake.ext import commands
import sqlite3
import logging
from DBConnection import DatabaseConnection
from RoleHierarchy import RoleHierarchy

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

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(self.create_bewerbung_view())
        self.bot.add_view(self.create_ticket_view())
        self.bot.add_view(self.create_admin_ticket_view())

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

        # Create the embed for the message
        ticket_embed = disnake.Embed(
            title="Neues Ticket",
            description=f"{interaction.user.mention}, bitte beschreibe dein Anliegen so detailliert wie möglich, damit wir dir schnell und "
                "effektiv helfen können.",
            color=0x00ff00
        )        
        # Send the message in the new channel
        await ticket_channel.send(embed=ticket_embed, view=claim_view)
        await interaction.response.send_message(f"Dein Ticket wurde erfolgreich erstellt. {ticket_channel.mention}", ephemeral=True)   

    async def claim_ticket(self, interaction: disnake.Interaction, ticket_id: int, user_id: int):
        role_hierarchy = RoleHierarchy()
        if not role_hierarchy.has_role_or_higher(interaction.author, "Supporter"):
            await interaction.response.send_message("Du hast nicht die erforderlichen Berechtigungen, um dieses Ticket zu claimen.", ephemeral=True)
            return

        # Überprüfe, ob das Ticket bereits zugewiesen wurde
        self.cursor.execute("SELECT ASSIGNED FROM Ticket WHERE ID = ?", (ticket_id,))
        assigned = self.cursor.fetchone()[0]
        if assigned:
            assigned_user = await self.bot.fetch_user(assigned)
            await interaction.response.send_message(f"Dieses Ticket wurde bereits {assigned_user.mention} zugewiesen.", ephemeral=True)
            return

        # Aktualisiere das Ticket in der Datenbank
        self.cursor.execute("UPDATE Ticket SET ASSIGNED = ? WHERE ID = ?", (interaction.author.id, ticket_id))
        self.db.connection.commit()

        await interaction.response.send_message(f"Dieses Ticket wurde dem Teammitglied {interaction.author.mention} zugewiesen.")

    async def close_ticket(self, interaction: disnake.Interaction, ticket_id: int):
        # Setze das Ticket in der Datenbank auf "DONE"
        self.cursor.execute("UPDATE TICKET SET DONE = 1 WHERE ID = ?", (ticket_id,))
        self.db.connection.commit()

        # Schließe den Kanal
        await interaction.channel.delete()

        # Sende eine DM an den Benutzer, der das Ticket erstellt hat
        self.cursor.execute("SELECT USERID FROM Ticket WHERE ID = ?", (ticket_id,))
        user_id = self.cursor.fetchone()[0]
        user = await self.bot.fetch_user(user_id)
        await user.send(f"Dein Ticket mit der ID {ticket_id} wurde geschlossen.")

# Define the button callbacks as separate methods
    async def bewerbung_button_callback(self, interaction: disnake.Interaction):
        await self.create_ticket_channel(interaction, "Bewerbung")

    async def ticket_button_callback(self, interaction: disnake.Interaction):
        await self.create_ticket_channel(interaction, "Ticket")

    async def admin_ticket_button_callback(self, interaction: disnake.Interaction):
        await self.create_ticket_channel(interaction, "Admin Ticket")

    # Modify the create_ticket_embeds method to use the new callbacks
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
        bewerbung_embed.set_author(name="Aincrad", icon_url=guild.icon.url if guild.icon else None)
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
        ticket_embed.set_author(name="Aincrad", icon_url=guild.icon.url if guild.icon else None)
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
        admin_ticket_embed.set_author(name="Aincrad", icon_url=guild.icon.url if guild.icon else None)
        admin_ticket_view = self.create_admin_ticket_view()

        await self.check_and_update_message(channel, bewerbung_embed, "Bewerbung", bewerbung_view)
        await self.check_and_update_message(channel, ticket_embed, "Ticket", ticket_view)
        await self.check_and_update_message(channel, admin_ticket_embed, "Admin Ticket", admin_ticket_view)

        await inter.edit_original_response(content="Ticket Embeds wurden erstellt/aktualisiert.")

def setupTicket(bot):
    bot.add_cog(Ticket(bot))