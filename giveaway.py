import disnake
from disnake.ext import commands
import sqlite3
import logging
from typing import Optional
import random
from dbconnection import DatabaseConnection
from globalfile import Globalfile


class Giveaway(commands.Cog):
    def __init__(self, bot: commands.Bot, role_manager):
        self.bot = bot
        self.role_manager = role_manager
        self.logger = logging.getLogger("Giveaway")
        self.db: sqlite3.Connection = DatabaseConnection()
        self.cursor = self.db.connection.cursor()
        self.setup_database()
        self.globalfile_cog : Globalfile = self.bot.get_cog("Globalfile")

        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def setup_database(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS GIVEAWAY (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                CHANNELID INTEGER NOT NULL,
                TITLE TEXT NOT NULL,
                DESCRIPTION TEXT NOT NULL,
                PRIZE TEXT NOT NULL,
                LEVEL_BASED BOOLEAN NOT NULL,
                ALLOWED_ROLES TEXT,
                EXCLUDED_ROLES TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS GIVEAWAY_ENTRIES (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                GIVEAWAY_ID INTEGER NOT NULL,
                USERID INTEGER NOT NULL,
                FOREIGN KEY (GIVEAWAY_ID) REFERENCES GIVEAWAY(ID)
            )
        """)
        self.db.connection.commit()
    
    async def _create_giveaway(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel,
        title: str,
        description: str,
        prize: str,
        level_based: bool,
        allowed_roles: Optional[str] = None,
        excluded_roles: Optional[str] = None
    ):
        if allowed_roles and excluded_roles:
            await inter.response.send_message("Du kannst nicht sowohl allowed_roles als auch excluded_roles angeben.", ephemeral=True)
            return

        self.cursor.execute("""
            INSERT INTO GIVEAWAY (CHANNELID, TITLE, DESCRIPTION, PRIZE, LEVEL_BASED, ALLOWED_ROLES, EXCLUDED_ROLES)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (channel.id, title, description, prize, level_based, allowed_roles, excluded_roles))
        self.db.connection.commit()
        self.logger.debug(f"Created giveaway in channel {channel.id}")


        giveaway_id = self.cursor.lastrowid

        embed = disnake.Embed(
            title=title,
            description=description,
            color=disnake.Color.blue()
        )
        embed.add_field(name="Preis", value=prize, inline=False)
        embed.set_footer(text="Klicke auf den Button unten, um am Gewinnspiel teilzunehmen! | ID: " + str(giveaway_id))

        view = GiveawayView(giveaway_id, self.cursor)
        message = await channel.send(embed=embed, view=view)

        await inter.response.send_message(f"Gewinnspiel erstellt in {channel.mention}", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: disnake.Interaction):
        if interaction.type == disnake.InteractionType.component:
            custom_id = interaction.data.get("custom_id")
            if custom_id.startswith("enter_giveaway_"):
                try:
                    giveaway_id = int(custom_id.split("_")[-1])
                    await self.enter_giveaway(interaction, giveaway_id)
                except ValueError:
                    self.logger.error(f"Invalid custom_id format: {custom_id}")
                    await interaction.response.send_message("Ungültige Interaktion.", ephemeral=True)

    async def enter_giveaway(self, interaction: disnake.MessageInteraction, giveaway_id: int):
        cursor = self.cursor

        cursor.execute("SELECT * FROM GIVEAWAY WHERE ID = ?", (giveaway_id,))
        giveaway = cursor.fetchone()

        if giveaway is None:
            await interaction.response.send_message("Gewinnspiel nicht gefunden.", ephemeral=True)
            return

        allowed_roles = giveaway[6]
        excluded_roles = giveaway[7]

        if allowed_roles:
            allowed_roles = allowed_roles.split(',')
            allowed_roles = [int(role_id) for role_id in allowed_roles]
            if not any(role.id in allowed_roles for role in interaction.user.roles):
                await interaction.response.send_message("Du hast keine Berechtigung, an diesem Gewinnspiel teilzunehmen.", ephemeral=True)
                return

        if excluded_roles:
            excluded_roles = excluded_roles.split(',')
            excluded_roles = [int(role_id) for role_id in excluded_roles]
            if any(role.id in excluded_roles for role in interaction.user.roles):
                await interaction.response.send_message("Du darfst nicht an diesem Gewinnspiel teilnehmen.", ephemeral=True)
                return

        user_record = await self.globalfile_cog.get_user_record(discordid=interaction.user.id)
        if not user_record:
            await interaction.response.send_message("Benutzer nicht gefunden.", ephemeral=True)
            return
        user_id = user_record["ID"]
        cursor.execute("SELECT * FROM GIVEAWAY_ENTRIES WHERE GIVEAWAY_ID = ? AND USERID = ?", (giveaway_id, user_id))
        entry = cursor.fetchone()

        if entry:
            await interaction.response.send_message("Du hast bereits an diesem Gewinnspiel teilgenommen.", ephemeral=True)
            return

        cursor.execute("INSERT INTO GIVEAWAY_ENTRIES (GIVEAWAY_ID, USERID) VALUES (?, ?)", (giveaway_id, user_id))
        self.db.connection.commit()

        view = GiveawayView(giveaway_id, self.cursor)
        view.update_button_label()
        await interaction.message.edit(view=view)

        await interaction.response.send_message("Du hast erfolgreich am Gewinnspiel teilgenommen!", ephemeral=True)

    def get_entry_count(self, giveaway_id: int) -> int:
        self.cursor.execute("SELECT COUNT(*) FROM GIVEAWAY_ENTRIES WHERE GIVEAWAY_ID = ?", (giveaway_id,))
        count = self.cursor.fetchone()[0]
        return count
    
    async def _draw_giveaway(self, inter: disnake.ApplicationCommandInteraction, giveaway_id: int):
        await inter.response.defer()
        self.cursor.execute("SELECT * FROM GIVEAWAY WHERE ID = ?", (giveaway_id,))
        giveaway = self.cursor.fetchone()

        if not giveaway:
            await inter.response.send_message("Gewinnspiel nicht gefunden.", ephemeral=True)
            return

        level_based = giveaway[5]

        self.cursor.execute("SELECT USERID FROM GIVEAWAY_ENTRIES WHERE GIVEAWAY_ID = ?", (giveaway_id,))
        entries = self.cursor.fetchall()

        if not entries:
            await inter.response.send_message("Keine Teilnehmer für dieses Gewinnspiel.", ephemeral=True)
            return

        user_chances = []
        for entry in entries:
            user_id = entry[0]
            user_record = await self.globalfile_cog.get_user_record(user_id=user_id)
            if not user_record:
                continue

            if level_based:
                self.cursor.execute("SELECT LEVEL FROM EXPERIENCE WHERE USERID = ?", (user_id,))
                user_level = self.cursor.fetchone()
                if user_level:
                    level = user_level[0]
                    chance = 1 + (level * 0.01)
                else:
                    chance = 1
            else:
                chance = 1
            user_chances.extend([user_id] * int(chance * 100))

        if not user_chances:
            await inter.response.send_message("Keine gültigen Teilnehmer für dieses Gewinnspiel.", ephemeral=True)
            return

        winner_id = random.choice(user_chances)
        user_record = await self.globalfile_cog.get_user_record(user_id=winner_id)
        winner = await self.bot.fetch_user(user_record["DISCORDID"])

        embed = disnake.Embed(
            title="Gewinnspiel Gewinner",
            description=f"Herzlichen Glückwunsch {winner.mention}! Du hast das Gewinnspiel gewonnen!",
            color=disnake.Color.green()
        )
        embed.add_field(name="Preis", value=giveaway[4], inline=False)
        embed.set_footer(text="Vielen Dank an alle Teilnehmer!")

        await inter.edit_original_response(embed=embed)

class GiveawayView(disnake.ui.View):
    def __init__(self, giveaway_id: int, cursor):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.cursor = cursor
        self.update_button_label()

    def update_button_label(self):
        self.cursor.execute("SELECT COUNT(*) FROM GIVEAWAY_ENTRIES WHERE GIVEAWAY_ID = ?", (self.giveaway_id,))
        count = self.cursor.fetchone()[0]
        self.children[0].label = f"Am Gewinnspiel teilnehmen ({count})"
        self.children[0].custom_id = f"enter_giveaway_{self.giveaway_id}"

    @disnake.ui.button(label="Am Gewinnspiel teilnehmen", style=disnake.ButtonStyle.green, custom_id="enter_giveaway_button")
    async def enter_giveaway(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        button.custom_id = f"enter_giveaway_{self.giveaway_id}"

def setupGiveaway(bot: commands.Bot, role_manager):
    bot.add_cog(Giveaway(bot, role_manager))