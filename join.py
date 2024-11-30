import disnake
from disnake.ext import commands
import logging
import sqlite3
from DBConnection import DatabaseConnection
from globalfile import Globalfile
import pyperclip

class Join(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger("Join")
        formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.globalfile = Globalfile(bot)
        self.db = DatabaseConnection()
   
    @commands.Cog.listener()
    async def on_member_update(self, before: disnake.Member, after: disnake.Member):
        if before.pending and not after.pending:            
            try:
                frischling_id = 854698446996766731
                info_id = 1065696216060547092
                hobbies_id = 1065696208103952465
                games_id = 1065696207416082435
                other_id = 1065701427361611857
                verify_id = 1066793314482913391

                guild = after.guild

                frischling = disnake.utils.get(guild.roles, id=frischling_id)
                info = disnake.utils.get(guild.roles, id=info_id)
                hobbies = disnake.utils.get(guild.roles, id=hobbies_id)
                games = disnake.utils.get(guild.roles, id=games_id)
                other = disnake.utils.get(guild.roles, id=other_id)
                verify = disnake.utils.get(guild.roles, id=verify_id)

                await after.add_roles(frischling, info, hobbies, games, other, verify)
                embed = disnake.Embed(title=f"Herzlich Willkommen!", color=0x6495ED)
                embed.set_author(name="Aincrad", icon_url=guild.icon.url)
                embed.description = (
                    f"Ein wildes {before.mention} ist aufgetaucht, willkommen bei uns auf **Aincrad!**\n"
                    f"In <#1039167130190491709> kannst du dir deine eigenen Rollen vergeben.\n"
                    f"In <#1039167960012554260> kannst du dich nach Möglichkeit vorstellen damit die anderen wissen wer du bist."
                )
                embed.set_image(url="https://media1.tenor.com/m/7-CNilpY-l8AAAAd/link-start-sao.gif")
                channel = guild.get_channel(854698447247769630)

                # Füge den neuen Benutzer zur USER-Tabelle hinzu
                cursor = self.db.connection.cursor()
                cursor.execute("SELECT ID FROM USER WHERE DISCORDID = ?", (str(after.id),))
                result = cursor.fetchone()

                if not result:
                    cursor.execute("INSERT INTO USER (DISCORDID, USERNAME) VALUES (?, ?)", (str(after.id), after.name))
                    self.db.connection.commit()
                    self.logger.info(f"Neuer Benutzer {after.name} (ID: {after.id}) zur USER-Tabelle hinzugefügt.")
                else:
                    self.logger.info(f"Benutzer {after.name} (ID: {after.id}) existiert bereits in der USER-Tabelle.")      

                guild = before.guild
                mod_embed = disnake.Embed(title="Neuer Benutzer Beigetreten", color=0xFF0000)
                mod_embed.add_field(name="Benutzername", value=before.name, inline=True)
                mod_embed.add_field(name="Benutzer ID", value=before.id, inline=True)
                mod_embed.add_field(name="Erwähnung", value=before.mention, inline=True)

                class CopyMentionButton(disnake.ui.Button):                
                    def __init__(self, mention):
                        super().__init__(label="Erwähnung kopieren", style=disnake.ButtonStyle.primary)
                        self.mention = mention
                        self.callback = self.on_click

                    async def on_click(self, interaction: disnake.Interaction):
                        pyperclip.copy(self.mention)
                        await interaction.response.send_message(f"`{self.mention}` wurde in die Zwischenablage kopiert!", ephemeral=True)

                view = disnake.ui.View(timeout=None)  # Setze die Lebensdauer der View auf unbegrenzt
                view.add_item(CopyMentionButton(before.mention))

                mod_channel = guild.get_channel(854698447113027594)  # Ersetze durch die ID des Moderatoren-Kanals
                guild.fetch_members()
                await channel.send(embed=embed)                      
                await mod_channel.send(embed=mod_embed, view=view)

                embed = disnake.Embed(
                    title="Willkommen auf unserem Server!",
                    description=f"Hallo {after.mention}, wir freuen uns, dich bei uns begrüßen zu dürfen!",
                    color=0x117A65 # Grün
                )
                embed.set_author(name="Aincrad", icon_url=after.guild.icon.url)
                embed.set_thumbnail(url=after.avatar.url)
                embed.add_field(
                    name="📜 Regeln",
                    value="Bitte lies dir unsere [Serverregeln](https://discord.com/channels/854698446996766730/854698447113027598) durch.",
                    inline=False
                )
                embed.add_field(
                    name="📢 Ankündigungen",
                    value="Bleibe auf dem Laufenden mit unseren [Ankündigungen](https://discord.com/channels/854698446996766730/854698447113027595).",
                    inline=False
                )
                embed.add_field(
                    name="🥳 Events",
                    value="Sei bei unseren regelmäßigen [Events](https://discord.com/channels/854698446996766730/1068984187115282512) dabei!.",
                    inline=False
                )                
                embed.add_field(
                    name="💬 Allgemeiner Chat",
                    value="Tritt unserem [allgemeinen Chat](https://discord.com/channels/854698446996766730/854698447247769630) bei und sag Hallo!",
                    inline=False
                )
                embed.add_field(
                    name="🎮 Spiele",
                    value="Diskutiere über deine Lieblingsspiele in unserem [Spiele-Channel](https://discord.com/channels/854698446996766730/1066715518276481054).",
                    inline=False
                )
                embed.set_image(url="https://media.giphy.com/media/b29IZK1dP4aWs/giphy.gif")
                embed.set_footer(text="Wir wünschen dir viel Spaß auf unserem Server!")

                await after.send(embed=embed)
                # Führe hier weitere Aktionen aus, z.B. Rolle hinzufügen oder Datenbank aktualisieren  
            except Exception as e:
                self.logger.critical(f"Fehler beim Hinzufügen der Rollen: {e}")          

def setupJoin(bot):
    bot.add_cog(Join(bot))
