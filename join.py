import disnake
from disnake.ext import commands
import logging
from dbconnection import DatabaseConnection
from globalfile import Globalfile
import pyperclip
import openai
import os
from datetime import timedelta, timedelta
import asyncio
from dotenv import load_dotenv, set_key
import platform
import requests
import random
from exceptionhandler import exception_handler


class Join(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger("Join")
        self.globalfile = Globalfile(bot)
        self.db = DatabaseConnection()
        self.invites_before_join = {}
        self.stats_channels = {}             
        
        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)         

    async def get_random_anime_gif(self):
        api_key = os.getenv("TENOR_API_KEY")  # Abrufen des API-Schlüssels aus der .env-Datei
        if not api_key:
            self.logger.error("TENOR_API_KEY ist nicht gesetzt.")
            return "https://media.giphy.com/media/b29IZK1dP4aWs/giphy.gif"

        search_term = "welcome anime wave girl"
        limit = 80  # Setze das Limit auf 20, um mehrere GIFs zu erhalten
        ckey = "my_test_app"  # set the client_key for the integration and use the same value for all API calls

        params = {
            "q": search_term,
            "key": api_key,
            "limit": limit,
            "client_key": ckey,
            "media_filter": "gif"
        }

        banned_gifs = [
        "https://media.giphy.com/media/b29IZK1dP4aWs/giphy.gif",
        "https://media.tenor.com/4KNFp4i5COoAAAAC/evil-iruma-kun-show-his-power-evil-iruma-kun.gif",
        "https://media.tenor.com/NZiiD__VWjoAAAAC/shikanoko-nokonoko-koshitantan-my-deer-friend-nokotan.gif",
        "https://media.tenor.com/t0w6bxOvDX8AAAAC/konosuba-aqua.gif",
        "https://media.tenor.com/kwelUfsbLdYAAAAC/welcome-anime-anime-welcome.gif",
        "https://media.tenor.com/rmhI_IqGmVIAAAAC/anime-wave.gif"
        # Füge hier weitere gesperrte GIF-URLs hinzu
        ]

        # get the top GIFs for the search term
        r = requests.get(
            f"https://tenor.googleapis.com/v2/search", params=params)

        if r.status_code == 200:
            # load the GIFs using the urls for the smaller GIF sizes
            data = r.json()
            gifs = data['results']
            
            # Filter GIFs by aspect ratio 16:9
            filtered_gifs = [
                gif for gif in gifs
                if 'gif' in gif['media_formats'] and
                1.7 <= gif['media_formats']['gif']['dims'][0] / gif['media_formats']['gif']['dims'][1] <= 1.8 and
                gif['media_formats']['gif']['url'] not in banned_gifs
            ]
            
            if filtered_gifs:
                random_gif = random.choice(filtered_gifs)
                return random_gif['media_formats']['gif']['url']
            else:
                self.logger.error("Keine GIFs mit dem Seitenverhältnis 16:9 gefunden.")
        elif r.status_code == 401:
            self.logger.error("401 Unauthorized: Überprüfen Sie Ihren API-Schlüssel.")
        else:
            self.logger.error(f"Fehler bei der Anfrage: {r.status_code}")
     
    @exception_handler
    @commands.Cog.listener()
    async def on_ready(self):
        self.new_member_ping = self.bot.guilds[0].get_role(1339347572506234890)  # Ersetze dies durch die tatsächliche ID der "Neuer Benutzer"-Rolle
        self.underage_role = self.bot.guilds[0].get_role(1300559732905607269)  # Ersetze dies durch die tatsächliche ID der
        def count_total_lines(directory):
            total_lines = 0
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.endswith('.py'):
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            total_lines += sum(1 for _ in f)
            return total_lines

        self.invites_before_join = await self.get_guild_invites()
        self.bot.add_view(await self.create_copy_mention_view()) 
        await self.bot.change_presence(activity=disnake.Activity(type=disnake.ActivityType.watching, name="über die Spieler"))      
        await self.create_stats_category()
        await self.update_stats()
        total_lines = count_total_lines(os.getcwd())
        self.logger.info(f"Total lines of code: {total_lines}")
        if self.bot.guilds:
            guild = self.bot.guilds[0]

        # Überprüfen Sie alle Mitglieder beim Start des Bots
        for guild in self.bot.guilds:
            for member in guild.members:
                if not await self.is_member_in_user_table(member.id):
                    await self.check_member_update(member)
                    await self.process_member_join(member)
                else:
                    cursor = self.db.connection.cursor()
                    cursor.execute("SELECT LEAVED FROM USER WHERE DISCORDID = ?", (str(member.id),))
                    leaved_status = cursor.fetchone()
                    if leaved_status and leaved_status[0] == 1:
                        await self.check_member_update(member)
                        await self.process_member_join(member)

    @exception_handler
    async def _random_anime_gif(self, inter: disnake.ApplicationCommandInteraction):
        """Sendet ein zufälliges Anime-Willkommens-GIF."""
        await inter.response.defer()
        gif_url = await self.get_random_anime_gif()
        embed = disnake.Embed(
            title="Hier ist dein zufälliges Anime-Willkommens-GIF!",
            color=0x6495ED
        )
        embed.set_image(url=gif_url)
        await inter.followup.send(embed=embed)

    @exception_handler
    async def set_leaved_for_non_members(self):
        cursor = self.db.connection.cursor()
        cursor.execute("SELECT DISCORDID FROM USER WHERE LEAVED = 0")
        all_users = cursor.fetchall()
        all_user_ids = {user[0] for user in all_users}

        current_member_ids = {str(member.id) for guild in self.bot.guilds for member in guild.members}

        non_member_ids = all_user_ids - current_member_ids

        for user_id in non_member_ids:
            cursor.execute("UPDATE USER SET LEAVED = 1 WHERE DISCORDID = ?", (user_id,))
        
        self.db.connection.commit()

    @exception_handler
    async def is_member_in_user_table(self, member_id: int) -> bool:
        cursor = self.db.connection.cursor()
        cursor.execute("SELECT 1 FROM USER WHERE DISCORDID = ?", (str(member_id),))
        return cursor.fetchone() is not None          

    @exception_handler
    async def get_guild_invites(self):
        invites = {}
        for guild in self.bot.guilds:
            guild_invites = await guild.invites()
            invites[guild.id] = {invite.code: invite for invite in guild_invites}
        return invites

    @exception_handler    
    async def create_copy_mention_view(self):
        view = disnake.ui.View(timeout=None)  # Setze die Lebensdauer der View auf unbegrenzt
        view.add_item(CopyMentionButton())
        return view

    @exception_handler
    async def generate_welcome_message(self, user: disnake.Member) -> str:
        context = f"Dies ist ein Community-Discord-Server-Bot namens Cupid für den Server '{user.guild.name}'. Der Bot interagiert freundlich und kumpelhaft mit den Benutzern."
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": context},
                    {"role": "user", "content": f"Erstelle eine Willkommensnachricht für {user.name} mit einem Wortspiel der mit dem Benutzernamen zu tun hat wenn es möglich ist. Bitte mache dieses Wortspiel nicht zu cringe. Bitte erwähne ebenfalls den Servername fett geschrieben. Bitte gebe die Willkommensnachricht selbst direkt zurück."}
                ],
                max_tokens=80
            )
            message = response.choices[0].message['content'].strip()
            return message
        except Exception as e:
            self.logger.error(f"Fehler bei der Anfrage an OpenAI: {e}")
            return f"Willkommen {user.name}! Schön, dass du da bist!"          

    @exception_handler
    @commands.Cog.listener()
    async def on_member_update(self, before: disnake.Member, after: disnake.Member):
        if before.pending and not after.pending:
            await self.check_member_update(after)
        elif self.underage_role in after.roles:
            await self.check_account_age_and_ban(after)
        else:
            booster_role_id = 1062833612485054504  # Ersetze dies durch die tatsächliche ID der "Server Booster"-Rolle  # Ersetze dies durch die tatsächliche ID der "Zweiter Account"-Rolle
            before_roles = set(before.roles)
            after_roles = set(after.roles)

            if disnake.utils.get(after.roles, id=booster_role_id) and not disnake.utils.get(before.roles, id=booster_role_id):
                await self.send_booster_thank_you_message(after) 

    @exception_handler
    async def check_member_update(self, member: disnake.Member):
        try:           
            frischling_id = 854698446996766731
            info_id = 1065696216060547092
            hobbies_id = 1065696208103952465
            games_id = 1065696207416082435
            other_id = 1065701427361611857

            guild = member.guild

            frischling = disnake.utils.get(guild.roles, id=frischling_id)
            info = disnake.utils.get(guild.roles, id=info_id)
            hobbies = disnake.utils.get(guild.roles, id=hobbies_id)
            games = disnake.utils.get(guild.roles, id=games_id)
            other = disnake.utils.get(guild.roles, id=other_id)

            gif_urls = [
            "https://media.tenor.com/SPkUmWsvnGIAAAAC/sumi-sakurasawa-rent-a-girlfriend.gif",
            "https://media.tenor.com/6CHontNt1mIAAAAC/otterpaka-jujutsu-kaisen.gif",
            "https://media.tenor.com/aSEjob2tK08AAAAC/youre-welcome-you-are-welcome.gif",
            "https://media.tenor.com/idC5CxU2_1gAAAAC/anon-chihaya-bang-dream-it%E2%80%99s-mygo.gif",
            "https://media.tenor.com/VGvT1NOxOrIAAAAC/the-greatest-demon-lord-is-reborn-as-a-typical-nobody-ginny.gif",
            "https://media.tenor.com/xsICn9T81LcAAAAC/roy-leops.gif",
            "https://media.tenor.com/l7vlJJZpwxYAAAAC/anime-girl.gif",
            "https://media.tenor.com/39qeokHcO4sAAAAC/anime-girl.gif",
            "https://media.tenor.com/zp4x__IgSpYAAAAC/nagomi-yui-pam-pam.gif",
            "https://media.tenor.com/vNapCUP0d3oAAAAC/pjsk-pjsk-anime.gif"
            "https://media.tenor.com/9aXyxmnYW7oAAAAC/my-dress-up-darling-sono-bisque-doll-wa-koi-wo-suru.gif"
            # Füge hier weitere GIF-URLs hinzu
            ]

            await member.add_roles(frischling, info, hobbies, games, other)
            embed = disnake.Embed(title=f"Herzlich Willkommen!", color=0x6495ED)
            embed.set_author(name=guild.name, icon_url=guild.icon.url)            
            embed.set_footer(text="✨Wir hoffen, dass du dich bei uns wohlfühlst!✨")
            embed.set_image(url=random.choice(gif_urls))
            embed.description = (
                f"{await self.generate_welcome_message(member)}\n"
                f"> - In <#1039167130190491709> kannst du dir deine eigenen Rollen vergeben.\n"
                f"> - In <#1039167960012554260> kannst du dich vorstellen.\n"
                f"> - In <#1329189129740882033> kannst du mit dem Dating Bot interargieren.\n"
                f"> - In <#854698447113027598> findet du die Regeln und das Levelsystem .\n"                
                f"> - Mit dem Befehl `/me` kannst du dein eigenes Profil abrufen."
            )            
            channel = guild.get_channel(854698447247769630)  

            guild = member.guild
            mod_embed = disnake.Embed(title="Neuer Benutzer Beigetreten", color=0x00FF00)
            mod_embed.add_field(name="Benutzername", value=member.name, inline=True)
            mod_embed.add_field(name="Benutzer ID", value=member.id, inline=True)
            mod_embed.add_field(name="Erwähnung", value=member.mention, inline=True)

            view = disnake.ui.View(timeout=None)
            view.add_item(CopyMentionButton())

            mod_channel = guild.get_channel(854698447113027594)
            guild.fetch_members()
            await channel.send(f"||{member.mention}{self.new_member_ping.mention}||", embed=embed)
            await mod_channel.send(embed=mod_embed, view=view)

            embed = disnake.Embed(
                title="Willkommen auf unserem Server!",
                description=f"Hallo {member.mention}, wir freuen uns, dich bei uns begrüßen zu dürfen!",
                color=0x117A65
            )
            embed.set_author(name=self.bot.user.name, icon_url=member.guild.icon.url)
            embed.set_thumbnail(url=member.avatar.url)
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
            embed.add_field(
                name="💕 Dating Bot",
                value="Nehme an unserm [Dating Bot](https://discord.com/channels/854698446996766730/1329189129740882033) teil und finde deinen Traumpartner.",
                inline=False
            )
            embed.set_image(url="https://media.giphy.com/media/b29IZK1dP4aWs/giphy.gif")
            embed.set_footer(text="Wir wünschen dir viel Spaß auf unserem Server!")

            userrecord = await self.globalfile.get_user_record(discordid=member.id)
            if userrecord:
                user_id = userrecord['ID']
                cursor = self.db.connection.cursor()
                cursor.execute("SELECT 1 FROM EXPERIENCE WHERE USERID = ?", (user_id,))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO EXPERIENCE (USERID, MESSAGE, VOICE, LEVEL, INVITE) VALUES (?, 0, 0, 1, 0)", (user_id,))
                    self.db.connection.commit()

            await member.send(embed=embed)
        except Exception as e:
            self.logger.critical(f"Fehler beim Hinzufügen der Rollen: {e}")                                                          

    @exception_handler
    async def process_member_join(self, member: disnake.Member):
        self.logger.info(f"{member.name} (ID: {member.id}) joined Server {member.guild.name}.")
        cursor = self.db.connection.cursor()
        cursor.execute("SELECT ID FROM USER WHERE DISCORDID = ?", (str(member.id),))
        result = cursor.fetchone()

        if not result:
            cursor.execute("INSERT INTO USER (DISCORDID, USERNAME) VALUES (?, ?)", (str(member.id), member.name))
            self.db.connection.commit()
            self.logger.info(f"Neuer Benutzer {member.name} (ID: {member.id}) zur USER-Tabelle hinzugefügt.")
        else:
            cursor.execute("UPDATE USER SET LEAVED = 0 WHERE DISCORDID = ?", (str(member.id),))
            self.db.connection.commit()
            self.logger.info(f"Benutzer {member.name} (ID: {member.id}) existiert bereits in der USER-Tabelle.")          

        invites_after_join = await member.guild.invites()
        for invite in invites_after_join:
            if invite.code in self.invites_before_join[member.guild.id] and invite.uses > self.invites_before_join[member.guild.id][invite.code].uses:
                inviter_id = invite.inviter.id
                current_date = (await self.globalfile.get_current_time()).strftime('%Y-%m-%d')

                # Hole die interne Benutzer-ID des Einladers
                inviter_record = await self.globalfile.get_user_record(discordid=str(inviter_id))
                if not inviter_record:
                    self.logger.error(f"Einlader {invite.inviter.name} (ID: {inviter_id}) nicht in der USER-Tabelle gefunden.")
                    return

                inviter_user_id = inviter_record['ID']

                cursor = self.db.connection.cursor()
                cursor.execute("SELECT COUNT(*) FROM INVITE_XP WHERE USERID = ? AND DATE = ?", (inviter_user_id, current_date))
                result = cursor.fetchone()

                if result[0] == 0:
                    cursor.execute("INSERT INTO INVITE_XP (USERID, DATE, COUNT) VALUES (?, ?, ?)", (inviter_user_id, current_date, 1))
                else:
                    cursor.execute("UPDATE INVITE_XP SET COUNT = COUNT + 1 WHERE USERID = ? AND DATE = ?", (inviter_user_id, current_date))

                # Aktualisiere das INVITEID-Feld in der USER-Tabelle
                cursor.execute("SELECT ID FROM INVITE_XP WHERE USERID = ? AND DATE = ?", (inviter_user_id, current_date))
                invite_id = cursor.fetchone()[0]
                cursor.execute("UPDATE USER SET INVITEID  = ? WHERE DISCORDID = ?", (invite_id, str(member.id)))
                load_dotenv(dotenv_path="envs/settings.env", override=True)
                factor = int(os.getenv("INVITEXP_FACTOR", 50))
                # Aktualisiere INVITEXP in der EXPERIENCE Tabelle
                
                cursor.execute("SELECT SECONDACC_USERID FROM USER WHERE ID = ?", (inviter_user_id,))
                secondacc_userid = cursor.fetchone()[0]
                if secondacc_userid is None:
                    # Aktualisiere INVITEXP in der EXPERIENCE Tabelle
                    cursor.execute("UPDATE EXPERIENCE SET INVITE = INVITE + ? WHERE USERID = ?", (factor * 60, inviter_user_id))

                self.db.connection.commit()
                self.logger.info(f"Einladung von {invite.inviter.name} (ID: {inviter_id}) wurde angenommen. INVITE_XP aktualisiert und USER-Tabelle aktualisiert.")
                break

        self.invites_before_join[member.guild.id] = {invite.code: invite for invite in invites_after_join}
        tmp = await self.check_account_age_and_ban(member)
        if tmp == False:
            await self.update_stats()

    @exception_handler
    @commands.Cog.listener()           
    async def on_member_join(self, member: disnake.Member):
        await self.process_member_join(member)

    @exception_handler        
    async def check_account_age_and_ban(self, member: disnake.Member):
        min_account_age_days = int(os.getenv("MIN_ACCOUNT_AGE_DAYS", 30))
        account_age = ((await self.globalfile.get_current_time()) - member.created_at).days

        if account_age < min_account_age_days:
            # Sende ein Embed an den Benutzer
            embed = disnake.Embed(
                title="Account zu jung",
                description=f"Dein Account muss mindestens {min_account_age_days} Tage alt sein, um diesem Server beizutreten. Dein Account ist derzeit nur {account_age} Tage alt.",
                color=disnake.Color.red()
            )
            try:
                await asyncio.sleep(1)  # Add a delay to avoid rate limit issues
                await member.send(embed=embed)
            except disnake.Forbidden:
                self.logger.warning(f"Konnte keine Nachricht an {member.name} ({member.id}) senden. Möglicherweise hat der Benutzer DMs deaktiviert.")
            except disnake.HTTPException as e:
                self.logger.error(f"Fehler beim Senden der Nachricht an {member.name} ({member.id}): {e}")
            
            # Ban den Benutzer für einen Tag
            duration_seconds = 24 * 60 * 60  # 1 Tag in Sekunden
            ban_end_time = (await self.globalfile.get_current_time()) + timedelta(seconds=duration_seconds)
            ban_end_timestamp = int(ban_end_time.timestamp())
            ban_end_formatted = ban_end_time.strftime('%Y-%m-%d %H:%M:%S')

            try:
                await member.ban(reason=f"Account is younger than {min_account_age_days} days.")
                self.logger.info(f"Benutzer {member.name} (ID: {member.id}) wurde für einen Tag gebannt, da der Account nur {account_age} Tage alt ist.")
                
                # Speichere den Ban in der Datenbank
                cursor = self.db.connection.cursor()
                cursor.execute(
                    "INSERT INTO BAN (USERID, REASON, BANNEDTO, DELETED_DAYS) VALUES (?, ?, ?, ?)",
                    (member.id, f"Account is younger than {min_account_age_days} days.", ban_end_timestamp, 1)
                )
                self.db.connection.commit()
                return True
            except disnake.Forbidden:
                self.logger.error(f"Ich habe keine Berechtigung, {member.mention} zu bannen.")
            except disnake.HTTPException as e:
                self.logger.error(f"Ein Fehler ist aufgetreten: {e}")          
        else:
            return False     

    @exception_handler
    @commands.Cog.listener()
    async def on_member_remove(self, member: disnake.Member):
        await self.update_stats()

    @exception_handler
    @commands.Cog.listener()
    async def on_guild_update(self, before: disnake.Guild, after: disnake.Guild):
        await self.update_stats()

    @exception_handler
    async def send_booster_thank_you_message(self, member: disnake.Member):
        embed = disnake.Embed(
            title="Vielen Dank fürs Boosten!",
            description=(
                f"Hallo {member.mention},\n\n"
                "vielen Dank, dass du unseren Server boostest! Dein Support hilft uns, diesen Server noch besser zu machen.\n\n"
                "Ich, Tatzu, der Owner von Date Night, möchte mich im Namen des gesamten Teams herzlich bei dir bedanken. "
                "Du bist ein wertvoller Teil dieses großartigen Projekts.\n\n"
                "Falls du Fragen oder Anliegen hast, zögere nicht, dich jederzeit an unser Team zu wenden. "
                "Wir sind immer für dich da!\n\n"
                "Schau doch auch mal in unserem [Farben-Channel](https://discord.com/channels/854698446996766730/1108774868801048576) vorbei!"
            ),
            color=0xFF69B4
        )
        embed.set_author(name=self.bot.user.name, icon_url=member.guild.icon.url)
        embed.set_thumbnail(url=member.avatar.url)
        embed.set_image(url="https://media1.tenor.com/m/CNHBs2BUJy0AAAAC/discord-pjsekai.gif")
        embed.set_footer(text="Wir schätzen deine Unterstützung sehr!")

        try:
            await member.send(embed=embed)
            self.logger.info(f"Booster-Dankesnachricht an {member.name} (ID: {member.id}) gesendet.")
        except Exception as e:
            self.logger.error(f"Fehler beim Senden der Booster-Dankesnachricht: {e}")

    @exception_handler
    async def create_stats_category(self):
        for guild in self.bot.guilds:
            category = disnake.utils.get(guild.categories, name="⏤ Serverstatistiken")
            if not category:
                category = await guild.create_category("⏤ Serverstatistiken")

            # Verschiebe die Kategorie an die oberste Position
            await category.edit(position=0)

            channels = {
                "Mitglieder": None,
                "Bots": None,
                "Boosts": None
            }

            for channel_name in channels.keys():
                channel = next((ch for ch in guild.channels if ch.name.startswith(channel_name)), None)
                if not channel:
                    channel = await guild.create_voice_channel(channel_name, category=category)
                channels[channel_name] = channel

                # Überprüfen und Berechtigungen anpassen
                everyone_role = guild.default_role
                overwrites = channel.overwrites_for(everyone_role)
                if overwrites.connect is not False:
                    overwrites.connect = False
                    await channel.set_permissions(everyone_role, overwrite=overwrites)

            self.stats_channels[guild.id] = channels

    @exception_handler
    async def update_stats(self):
        for guild in self.bot.guilds:
            if guild.id in self.stats_channels:
                member_count = sum(1 for member in guild.members if not member.bot)
                bot_count = sum(1 for member in guild.members if member.bot)
                boost_count = guild.premium_subscription_count

                await self.stats_channels[guild.id]["Mitglieder"].edit(name=f"Mitglieder: {member_count}")
                await self.stats_channels[guild.id]["Bots"].edit(name=f"Bots: {bot_count}")
                await self.stats_channels[guild.id]["Boosts"].edit(name=f"Boosts: {boost_count}")      

    @exception_handler
    @commands.Cog.listener()
    async def on_member_remove(self, member: disnake.Member):
        try:
            current_datetime = (await self.globalfile.get_current_time())
            log_channel_id = 854698447113027594  # Replace with your log channel ID
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel:
                embed = disnake.Embed(title="Mitglied hat den Server verlassen", color=0xFF0000)
                avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
                embed.set_author(name=member.name, icon_url=avatar_url)
                embed.add_field(name="Mitglied", value=member.mention, inline=False)
                embed.set_footer(text=f"ID: {member.id} - heute um {current_datetime.strftime('%H:%M:%S')} Uhr")
                await log_channel.send(embed=embed)
            
            # Setze das Feld LEAVED in der USER-Tabelle auf 1
            cursor = self.db.connection.cursor()
            cursor.execute("UPDATE USER SET LEAVED = 1 WHERE DISCORDID = ?", (str(member.id),))
            self.db.connection.commit()

            user_record = await self.globalfile.get_user_record(discordid=member.id)
            await self.globalfile.delete_user_data(user_record['ID'])
        except Exception as e:
            self.logger.critical(f"Fehler aufgetreten [on_member_remove]: {e}")

class CopyMentionButton(disnake.ui.Button):                
    def __init__(self):
        super().__init__(label="Erwähnung kopieren", style=disnake.ButtonStyle.primary, custom_id="copy_mention_button")
        self.callback = self.on_click

    async def on_click(self, interaction: disnake.Interaction):
        embed = interaction.message.embeds[0]
        user_id = embed.fields[1].value  # Annahme: Die User ID ist das zweite Feld im Embed
        mention = f"<@{user_id}>"
        try:
            pyperclip.copy(mention)
            await interaction.response.send_message(f"`{mention}` wurde in die Zwischenablage kopiert!", ephemeral=True)
        except pyperclip.PyperclipException as e:
            if platform.system() == "Linux":
                await interaction.response.send_message(
                    "Fehler: Pyperclip konnte keinen Copy/Paste-Mechanismus für dein System finden. "
                    "Bitte installiere `xclip` oder `xsel` und versuche es erneut.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Fehler: Pyperclip konnte keinen Copy/Paste-Mechanismus für dein System finden.",
                    ephemeral=True
                )                  

def setupJoin(bot):
    bot.add_cog(Join(bot))