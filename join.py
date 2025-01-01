import disnake
from disnake.ext import commands
import logging
import sqlite3
from dbconnection import DatabaseConnection
from globalfile import Globalfile
import pyperclip
import openai

class Join(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger("Join")
        self.globalfile = Globalfile(bot)
        self.db = DatabaseConnection()
        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)        

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(self.create_copy_mention_view()) 
        self.bot.description=="Hier sind die [Nutzungsbedingungen vom Cardinal System](https://cdn.discordapp.com/attachments/1061441308452999261/1323286193705713736/Nutzungsbedingungen_fur_Cardinal_System.pdf?ex=6773f5ce&is=6772a44e&hm=b0f62fca99ea05c399e380b5ee0c4c5045bbd36479535e2502b5bbba4c05f725)"
        await self.bot.change_presence(activity=disnake.Activity(type=disnake.ActivityType.watching, name="über die Spieler"))      
        self.bot.reload

    def create_copy_mention_view(self):
        view = disnake.ui.View(timeout=None)  # Setze die Lebensdauer der View auf unbegrenzt
        view.add_item(CopyMentionButton())
        return view

    async def generate_welcome_message(self, user: disnake.Member) -> str:
        context = f"Dies ist ein Community-Discord-Server-Bot namens Cardinal System für den Server '{user.guild.name}'. Der Bot interagiert freundlich und kumpelhaft mit den Benutzern. Erstelle eine herzliche Willkommensnachricht für einen neuen Benutzer namens {user.name}. Integriere einen netten Wortspruch mit dem Namen des Benutzers."
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": context},
                    {"role": "user", "content": f"Erstelle eine Willkommensnachricht für {user.name} mit einem Wortspiel im idealfall. Bitte erwähne ebenfalls den Servername fett geschrieben."}
                ],
                max_tokens=80
            )
            message = response.choices[0].message['content'].strip()
            return message
        except Exception as e:
            self.logger.error(f"Fehler bei der Anfrage an OpenAI: {e}")
            return f"Willkommen {user.name}! Schön, dass du da bist!"          

    @commands.Cog.listener()
    async def on_member_update(self, before: disnake.Member, after: disnake.Member):       
        if before.pending and not after.pending:            
            try:
                frischling_id = 854698446996766731
                info_id = 1065696216060547092
                hobbies_id = 1065696208103952465
                games_id = 1065696207416082435
                other_id = 1065701427361611857

                guild = after.guild

                frischling = disnake.utils.get(guild.roles, id=frischling_id)
                info = disnake.utils.get(guild.roles, id=info_id)
                hobbies = disnake.utils.get(guild.roles, id=hobbies_id)
                games = disnake.utils.get(guild.roles, id=games_id)
                other = disnake.utils.get(guild.roles, id=other_id)

                await after.add_roles(frischling, info, hobbies, games, other)
                embed = disnake.Embed(title=f"Herzlich Willkommen!", color=0x6495ED)
                embed.set_author(name=self.bot.user.name, icon_url=guild.icon.url)
                embed.description = (
                    f"{await self.generate_welcome_message(before)}\n"
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

                view = disnake.ui.View(timeout=None)  # Setze die Lebensdauer der View auf unbegrenzt
                view.add_item(CopyMentionButton())

                mod_channel = guild.get_channel(854698447113027594)  # Ersetze durch die ID des Moderatoren-Kanals
                guild.fetch_members()
                await channel.send(f"||{after.mention}||", embed=embed)
                await mod_channel.send(embed=mod_embed, view=view)

                embed = disnake.Embed(
                    title="Willkommen auf unserem Server!",
                    description=f"Hallo {after.mention}, wir freuen uns, dich bei uns begrüßen zu dürfen!",
                    color=0x117A65 # Grün
                )
                embed.set_author(name=self.bot.user.name, icon_url=after.guild.icon.url)
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
                
class CopyMentionButton(disnake.ui.Button):                
    def __init__(self):
        super().__init__(label="Erwähnung kopieren", style=disnake.ButtonStyle.primary, custom_id="copy_mention_button")
        self.callback = self.on_click

    async def on_click(self, interaction: disnake.Interaction):
        embed = interaction.message.embeds[0]
        user_id = embed.fields[1].value  # Annahme: Die User ID ist das zweite Feld im Embed
        mention = f"<@{user_id}>"
        pyperclip.copy(mention)
        await interaction.response.send_message(f"`{mention}` wurde in die Zwischenablage kopiert!", ephemeral=True)                         

def setupJoin(bot):
    bot.add_cog(Join(bot))