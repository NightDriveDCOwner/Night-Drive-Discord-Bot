import disnake
from disnake.ui import Button, View
from dbconnection import DatabaseConnectionManager
from channelmanager import ChannelManager
from rolehierarchy import rolehierarchy
from globalfile import Globalfile
import datetime
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
import uuid
from dotenv import load_dotenv
import asyncio


class Friend(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
        self.bot = bot
        self.logger = logging.getLogger("Friend")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.globalfile: Globalfile = self.bot.get_cog('Globalfile')
        self.rolemanager : RoleManager = rolemanager
        self.channelmanager : ChannelManager = channelmanager

        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    @exception_handler
    async def on_ready(self):
        load_dotenv(dotenv_path="envs/settings.env", override=True)
        self.botchannel = self.channelmanager.get_channel(self.bot.guilds[0].id, int(os.getenv("BOT_CHANNEL_ID")))
        self.team_role = self.rolemanager.get_role(self.bot.guilds[0].id, int(os.getenv("TEAM_ROLE")))
        self.logger.info("Friend Cog is ready.")                
         
    @exception_handler
    async def _friend_add(self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member):
        if inter.channel == self.botchannel:
            if inter.user.id == user.id:
                await inter.response.send_message("Du kannst dich nicht selbst hinzufügen.", ephemeral=True)
                return
            user_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
            friend_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=user.id)
            cursor = await DatabaseConnectionManager.execute_sql_statement(
                inter.guild.id, 
                inter.guild.name, 
                """SELECT * FROM FRIEND WHERE (USERID = ? AND FRIENDID = ?) OR (USERID = ? AND FRIENDID = ?)""", 
                (user_record['ID'], friend_record['ID'], friend_record['ID'], user_record['ID']))
            
            if (await cursor.fetchone()):
                await inter.response.send_message("Du bist bereits mit dieser Person befreundet.", ephemeral=True)
                return

            request_id = str(uuid.uuid4())
            current_datetime = (await self.globalfile.get_current_time()).strftime("%Y-%m-%d %H:%M:%S")      
            await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, """
                INSERT INTO FRIEND (USERID, FRIENDID, REQUESTID, INSERT_DATE, STATUS)
                VALUES (?, ?, ?, ?, ?)
            """, (int(user_record['ID']), int(friend_record['ID']), request_id, current_datetime, "pending"))
            
            embed = disnake.Embed(
                title="Freundschaftsanfrage",
                description=f"{inter.user.mention} hat dir eine Freundschaftsanfrage geschickt. Möchtest du sie annehmen?",
                color=disnake.Color.green()
            )
            embed.set_footer(text=f"Anfrage-ID: {request_id}")

            accept_button = Button(label="Annehmen", style=disnake.ButtonStyle.green, custom_id=f"accept_friend_request_{request_id}")
            decline_button = Button(label="Ablehnen", style=disnake.ButtonStyle.red, custom_id=f"decline_friend_request_{request_id}")

            view = View()
            view.add_item(accept_button)
            view.add_item(decline_button)

            message = await inter.response.send_message(content=f"||{user.mention}||", embed=embed, view=view)
            self.logger.info(f"{inter.user.name}#{inter.user.discriminator} hat {user.name}#{user.discriminator} eine Freundschaftsanfrage geschickt.")

            await asyncio.sleep(180)  # 3 Minuten warten
            message = await inter.original_message()
            if message.components:
                embed.description = f"Es wurde nicht auf die Freundschaftsanfrage reagiert. Du kannst sie über `/friendrequests` erneut anzeigen lassen."
                await inter.edit_original_message(embed=embed, view=None)
                try:
                    await user.send(f"{inter.user.mention} hat dir eine Freundschaftsanfrage geschickt. Du kannst sie über `/friendrequests` anzeigen und annehmen lassen. (Anfrage-ID: {request_id})")
                except disnake.Forbidden:
                    self.logger.warning(f"Could not send a friend request message to {user.name}#{user.discriminator}.")
        else:
            await inter.response.send_message(f"Du kannst nur Freundschaftsanfragen in {self.botchannel.mention} senden.", ephemeral=True)

    async def _friend_remove(self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member):
        user_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
        friend_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=user.id)
        cursor = await DatabaseConnectionManager.execute_sql_statement(
            inter.guild.id, 
            inter.guild.name, 
            """SELECT * FROM FRIEND WHERE (USERID = ? AND FRIENDID = ?) OR (USERID = ? AND FRIENDID = ?)""", 
            (user_record['ID'], friend_record['ID'], friend_record['ID'], user_record['ID']))
        
        if not (await cursor.fetchone()):
            await inter.response.send_message("Du bist nicht mit dieser Person befreundet.", ephemeral=True)
            return

        await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, """
            DELETE FROM FRIEND WHERE (USERID = ? AND FRIENDID = ?) OR (USERID = ? AND FRIENDID = ?)
        """, (user_record['ID'], friend_record['ID'], friend_record['ID'], user_record['ID']))
        
        self.logger.info(f"{inter.user.name}#{inter.user.discriminator} hat {user.name}#{user.discriminator} aus seiner Freundesliste entfernt.")
        await inter.response.send_message(f"{user.mention} wurde aus deiner Freundesliste entfernt.", ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: disnake.Interaction):
        custom_id = interaction.data.get('custom_id', None)
        if custom_id and custom_id.startswith("accept_friend_request_"):
            request_id = custom_id.split("_")[-1]
            await self.accept_friend_request(interaction, request_id)
        elif custom_id and custom_id.startswith("decline_friend_request_"):
            request_id = custom_id.split("_")[-1]
            await self.decline_friend_request(interaction, request_id)
        elif custom_id and custom_id.startswith("accept_friendrequests_"):
            parts = custom_id.split("_")
            request_id = parts[-2]
            await self.accept_friend_request(interaction, request_id)
            await asyncio.sleep(1)
            index = int(parts[-1])
            await self._navigate_friend_requests(interaction, 0, index)
        elif custom_id and custom_id.startswith("decline_friendrequests_"):
            parts = custom_id.split("_")
            request_id = parts[-2]
            await self.decline_friend_request(interaction, request_id)
            await asyncio.sleep(1)
            index = int(parts[-1])
            await self._navigate_friend_requests(interaction, 0, index)
        elif custom_id and custom_id.startswith("prev_request_"):
            index = int(custom_id.split("_")[-1])
            await self._navigate_friend_requests(interaction, -1, index)
        elif custom_id and custom_id.startswith("next_request_"):
            index = int(custom_id.split("_")[-1])
            await self._navigate_friend_requests(interaction, 1, index)

    async def _navigate_friend_requests(self, interaction: disnake.MessageInteraction, direction: int, index: int):
        user_record = await self.globalfile.get_user_record(guild=interaction.guild, discordid=interaction.user.id)
        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, """
            SELECT REQUESTID, USERID FROM FRIEND WHERE FRIENDID = ? AND STATUS = 'pending'
        """, (int(user_record['ID']),))        
        requests = await cursor.fetchall()

        current_index = index
        new_index = current_index + direction
        await self.update_message(requests, interaction, new_index)
        
    @exception_handler
    async def accept_friend_request(self, interaction: disnake.MessageInteraction, request_id: str):        
        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, """
            SELECT FRIENDID FROM FRIEND WHERE REQUESTID = ? AND STATUS = 'pending'""",
            (request_id,))
    
        user_id = (await cursor.fetchone())[0]
        user_record = await self.globalfile.get_user_record(guild=interaction.guild, user_id=user_id)
        if interaction.user.id != int(user_record['DISCORDID']):
            await interaction.response.send_message("Du kannst nur deine eigenen Freundschaftsanfragen annehmen.", ephemeral=True)    
            return

        await interaction.response.defer()
        current_datetime = (await self.globalfile.get_current_time()).strftime("%Y-%m-%d %H:%M:%S")
        await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, """
            UPDATE FRIEND SET STATUS = 'accepted', FRIEND_DATE = ? WHERE REQUESTID = ?
        """, (current_datetime, request_id))
        
        embed = disnake.Embed(
            title="Freundschaftsanfrage",
            description=f"Die Freundschaftsanfrage an {interaction.user.mention} wurde angenommen.✅",
            color=disnake.Color.green()
        )
        
        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, """SELECT USERID FROM FRIEND WHERE REQUESTID = ?""", (request_id,))
        user_id = (await cursor.fetchone())[0]
        user_record = await self.globalfile.get_user_record(guild=interaction.guild, user_id=user_id)
        user = await interaction.guild.fetch_member(int(user_record['DISCORDID']))
        if interaction.message.flags.ephemeral:
            await interaction.edit_original_response(content=None,embed=embed, view=None)
        else:
            await interaction.message.edit(content=f"||{user.mention}||",embed=embed, view=None)
        self.logger.info(f"{interaction.user.name}#{interaction.user.discriminator} hat die Freundschaftsanfrage von {user.name}#{user.discriminator} angenommen.")

    async def decline_friend_request(self, interaction: disnake.MessageInteraction, request_id: str):        
        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, """
            SELECT FRIENDID FROM FRIEND WHERE REQUESTID = ? AND STATUS = 'pending'""",
            (request_id,))
    
        user_id = (await cursor.fetchone())[0]
        user_record = await self.globalfile.get_user_record(guild=interaction.guild, user_id=user_id)
        if interaction.user.id != int(user_record['DISCORDID']):
            await interaction.response.send_message(content="Du kannst nur deine eigenen Freundschaftsanfragen ablehnen.", ephemeral=True)
            return
        
        await interaction.response.defer()
        await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, 
                                                              """UPDATE FRIEND SET STATUS = 'declined' WHERE REQUESTID = ?""", (request_id,))
        
        embed = disnake.Embed(
            title="Freundschaftsanfrage",
            description="Die Freundschaftsanfrage wurde abgelehnt.❌",
            color=disnake.Color.red()
        )

        cursor = await DatabaseConnectionManager.execute_sql_statement(interaction.guild.id, interaction.guild.name, "SELECT USERID FROM FRIEND WHERE REQUESTID = ?", (request_id,))
        user_id = (await cursor.fetchone())[0]
        user_record = await self.globalfile.get_user_record(guild=interaction.guild, user_id=user_id)
        user = await interaction.guild.fetch_member(int(user_record['DISCORDID']))
        if interaction.message.flags.ephemeral:
            await interaction.edit_original_response(content=None,embed=embed, view=None)
        else:
            await interaction.message.edit(content=f"||{user.mention}||",embed=embed, view=None)
        self.logger.info(f"{interaction.user.name}#{interaction.user.discriminator} hat die Freundschaftsanfrage von {user.name}#{user.discriminator} abgelehnt.")

    @exception_handler    
    async def _friend_list(self, inter: disnake.ApplicationCommandInteraction, user: disnake.User = None):
        user_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
        if user is not None:
            if user.id != inter.user.id:                
                user_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=user.id)
                privacy_settings = await self.globalfile.get_user_privacy_settings(user.id, inter.guild)

                # Überprüfe, ob der anfragende Benutzer mit dem Zielbenutzer befreundet ist
                tmp_user = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
                is_friend = await self.globalfile.are_user_friends(user_record["ID"], tmp_user['ID'], inter.guild)
                is_blocked = await self.globalfile.is_user_blocked(user_record["ID"], tmp_user["ID"], inter.guild)

                def can_view(setting: str) -> bool:
                    if self.team_role in inter.user.roles:
                        return True                        

                    return (
                        privacy_settings.get(setting, 'nobody') == 'everyone' or
                        (privacy_settings.get(setting, 'nobody') == 'friends' and is_friend) or
                        (privacy_settings.get(setting, 'nobody') == 'blocked' and not is_blocked)
                    )

                if not can_view('friendlist'):
                    await inter.response.send_message("Du hast keine Berechtigung, die Freundesliste dieses Benutzers zu sehen.", ephemeral=True)
                    return            
        else:
            user = inter.user

        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, """
            SELECT FRIENDID, FRIEND_DATE FROM FRIEND WHERE USERID = ? AND STATUS = 'accepted'
        """, (user_record['ID'],))
        
        friends = await cursor.fetchall()
        
        if not friends:
            await inter.response.send_message("Dieser Benutzer hat noch keine Freunde hinzugefügt.", ephemeral=True)
            return
        
        friend_mentions = []
        for friend in friends:
            friend_record = await self.globalfile.get_user_record(guild=inter.guild, user_id=friend[0])
            friend_user = await inter.guild.fetch_member(friend_record['DISCORDID'])
            if friend_user:
                friend_date = datetime.strptime(friend[1], "%Y-%m-%d %H:%M:%S")
                friend_mentions.append(f"{friend_user.mention} <t:{int(friend_date.timestamp())}:R>")

        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, """
            SELECT USERID, FRIEND_DATE FROM FRIEND WHERE FRIENDID = ? AND STATUS = 'accepted'
        """, (user_record['ID'],))      

        friends = await cursor.fetchall()          
        
        for friend in friends:
            friend_record = await self.globalfile.get_user_record(guild=inter.guild, user_id=friend[0])
            friend_user = await inter.guild.fetch_member(friend_record['DISCORDID'])
            if friend_user:
                friend_date = datetime.strptime(friend[1], "%Y-%m-%d %H:%M:%S")
                friend_mentions.append(f"{friend_user.mention} <t:{int(friend_date.timestamp())}:R>")   

        embed = disnake.Embed(
            title=f"Freundesliste von {user.name}",
            description="\n".join(friend_mentions),
            color=disnake.Color.blue()
        )
        self.logger.info(f"{inter.user.name}#{inter.user.discriminator} hat die Freundesliste von {user.name}#{user.discriminator} angezeigt.")
        await inter.response.send_message(embed=embed, ephemeral=True)

    async def update_message(self, requests, inter: disnake.MessageInteraction, index):        
        if not inter.response.is_done():
            await inter.response.defer(ephemeral=True)  # Defer the interaction to give more time

        if not requests:
            try:
                if inter.message:
                    embed = disnake.Embed(
                    title="Freundschaftsanfrage",
                    description=f"{inter.user.mention}, es gibt keine ausstehenden Freundschaftsanfragen.",
                    color=disnake.Color.green()
                    )
                    await inter.edit_original_response(embed=embed)
                    return
            except Exception as e:
                await inter.message.delete()
                await inter.followup.send(content="Du hast keine ausstehenden Freundschaftsanfragen.", ephemeral=True)
        
        request_id, user_id = requests[index]
        user_record = await self.globalfile.get_user_record(guild=inter.guild, user_id=user_id)
        user = await inter.guild.fetch_member(int(user_record['DISCORDID']))
        embed = disnake.Embed(
            title=f"Freundschaftsanfrage [{index + 1}/{len(requests)}]",
            description=f"{user.mention} hat dir eine Freundschaftsanfrage geschickt.\nMöchtest du sie annehmen?",
            color=disnake.Color.green()
        )
        embed.set_footer(text=f"Anfrage-ID: {request_id}")

        view = View()
        if index > 0:
            view.add_item(Button(label="Zurück", style=disnake.ButtonStyle.grey, custom_id=f"prev_request_{index}"))
        view.add_item(Button(label="Annehmen", style=disnake.ButtonStyle.green, custom_id=f"accept_friendrequests_{request_id}_{index}"))
        view.add_item(Button(label="Ablehnen", style=disnake.ButtonStyle.red, custom_id=f"decline_friendrequests_{request_id}_{index}"))
        if index < len(requests) - 1:
            view.add_item(Button(label="Weiter", style=disnake.ButtonStyle.grey, custom_id=f"next_request_{index}"))

        try:
            if inter.message:
                await inter.edit_original_response(embed=embed, view=view)
        except Exception as e:
            await inter.followup.send(embed=embed, view=view, ephemeral=True)

    @exception_handler
    async def _show_friend_requests(self, inter: disnake.ApplicationCommandInteraction):
        user_record = await self.globalfile.get_user_record(guild=inter.guild, discordid=inter.user.id)
        cursor = await DatabaseConnectionManager.execute_sql_statement(inter.guild.id, inter.guild.name, """
            SELECT REQUESTID, USERID FROM FRIEND WHERE FRIENDID = ? AND STATUS = 'pending'
        """, (int(user_record['ID']),))
        
        requests = await cursor.fetchall()
        
        if not requests:
            await inter.response.send_message("Du hast keine ausstehenden Freundschaftsanfragen.", ephemeral=True)
            return

        current_index = 0

        await self.update_message(requests, inter, current_index)

def setupFriend(bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
    bot.add_cog(Friend(bot, rolemanager, channelmanager))
