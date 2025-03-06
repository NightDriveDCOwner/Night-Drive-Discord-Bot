import disnake
from disnake.ext import commands
import sqlite3
import logging
from typing import Optional
import random
from dbconnection import DatabaseConnectionManager
from globalfile import Globalfile
from rolemanager import RoleManager


class Giveaway(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager):
        self.bot = bot
        self.rolemanager = rolemanager
        self.logger = logging.getLogger("Giveaway")
        self.globalfile_cog: Globalfile = self.bot.get_cog("Globalfile")

        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)#
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("Giveaway Cog is ready.")

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

        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, """
            INSERT INTO GIVEAWAY (CHANNELID, TITLE, DESCRIPTION, PRIZE, LEVEL_BASED, ALLOWED_ROLES, EXCLUDED_ROLES)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (channel.id, title, description, prize, level_based, allowed_roles, excluded_roles))

        self.logger.debug(f"Created giveaway in channel {channel.id}")

        giveaway_id = cursor.lastrowid

        embed = disnake.Embed(
            title=title,
            description=description,
            color=disnake.Color.blue()
        )
        embed.add_field(name="Preis", value=prize, inline=False)
        embed.set_footer(
            text="Klicke auf den Button unten, um am Gewinnspiel teilzunehmen! | ID: " + str(giveaway_id))

        view = GiveawayView(giveaway_id, inter.guild.id, inter.guild.name)
        await view.update_button_label()
        message = await channel.send(embed=embed, view=view)

        await inter.response.send_message(f"Gewinnspiel erstellt in {channel.mention}", ephemeral=True)
        self.logger.info(f"Created giveaway in channel {channel.id}")

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
        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "SELECT * FROM GIVEAWAY WHERE ID = ?", (giveaway_id,))
        giveaway = (await cursor.fetchone())

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
        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "SELECT * FROM GIVEAWAY_ENTRIES WHERE GIVEAWAY_ID = ? AND USERID = ?", (giveaway_id, user_id))
        entry = (await cursor.fetchone())

        if entry:
            await interaction.response.send_message("Du hast bereits an diesem Gewinnspiel teilgenommen.", ephemeral=True)
            return

        await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "INSERT INTO GIVEAWAY_ENTRIES (GIVEAWAY_ID, USERID) VALUES (?, ?)", (giveaway_id, user_id))

        view = GiveawayView(giveaway_id, cursor)
        view.update_button_label()
        await interaction.message.edit(view=view)

        await interaction.response.send_message("Du hast erfolgreich am Gewinnspiel teilgenommen!", ephemeral=True)

    async def _draw_giveaway(self, inter: disnake.ApplicationCommandInteraction, giveaway_id: int):
        await inter.response.defer()
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT * FROM GIVEAWAY WHERE ID = ?", (giveaway_id,))
        giveaway = (await cursor.fetchone())

        if not giveaway:
            await inter.response.send_message("Gewinnspiel nicht gefunden.", ephemeral=True)
            return

        level_based = giveaway[5]

        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT USERID FROM GIVEAWAY_ENTRIES WHERE GIVEAWAY_ID = ?", (giveaway_id,))
        entries = await cursor.fetchall()
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
                cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, "SELECT LEVEL FROM EXPERIENCE WHERE USERID = ?", (user_id,))
                user_level = (await cursor.fetchone())
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
    def __init__(self, giveaway_id: int, guild_id: int, guild_name: str):
        super().__init__(timeout=None)
        self.giveaway_id = giveaway_id
        self.guild_id = guild_id
        self.guild_name = guild_name

    async def update_button_label(self):
        cursor = await DatabaseConnectionManager.execute_sql_statement(self.guild_id, self.guild_name, "SELECT COUNT(*) FROM GIVEAWAY_ENTRIES WHERE GIVEAWAY_ID = ?", (self.giveaway_id,))
        count = (await cursor.fetchone())[0]
        self.children[0].label = f"Am Gewinnspiel teilnehmen ({count})"
        self.children[0].custom_id = f"enter_giveaway_{self.giveaway_id}"

    @disnake.ui.button(label="Am Gewinnspiel teilnehmen", style=disnake.ButtonStyle.green, custom_id="enter_giveaway_button")
    async def enter_giveaway(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        guild = interaction.guild
        button.custom_id = f"enter_giveaway_{self.giveaway_id}"
        await interaction.response.send_message(f"Button gedrückt auf Server: {guild.name}", ephemeral=True)


def setupGiveaway(bot: commands.Bot, rolemanager):
    bot.add_cog(Giveaway(bot, rolemanager))
