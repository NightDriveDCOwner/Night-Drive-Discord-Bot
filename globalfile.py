import disnake, os, logging
import disnake.audit_logs
from disnake.ext import commands, tasks
from datetime import datetime, timedelta, timedelta
from collections import namedtuple
import asyncio
import time
import re
from typing import Union


class Globalfile(commands.Cog):
    _instance = None
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Globalfile, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, bot: commands.Bot):
        if not hasattr(self, 'bot'):
            self.bot = bot
            self.user_data = {}
            self.TimerMustReseted = True
            self.UserRecord = namedtuple('UserRecord', ['user','username','userid'])
            self.logger = logging.getLogger("Commands")
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def convert_duration_to_seconds(self, duration: str) -> int:
        """Konvertiere eine Zeitangabe in Sekunden."""
        seconds = 0
        matches = re.findall(r'(\d+)([smhdj])', duration)
        for match in matches:
            value, unit = match
            if unit == 's':
                seconds += int(value)
            elif unit == 'm':
                seconds += int(value) * 60
            elif unit == 'h':
                seconds += int(value) * 3600
            elif unit == 'd':
                seconds += int(value) * 86400
            elif unit == 'j':
                seconds += int(value) * 31536000 # Ein Jahr hat etwa 365 Tage
        return seconds

    @staticmethod
    async def save_image(attachment: disnake.Attachment, file_name: str):
        # Speichere das Bild mit dem neuen Dateinamen
        save_path = "proofs"
        
        # Überprüfen, ob der Ordner existiert, und falls nicht, erstellen
        if not os.path.exists(save_path):
            os.makedirs(save_path)
        
        # Speichere das Bild mit dem neuen Dateinamen
        await attachment.save(f"{save_path}/{file_name}.png")
        return f"{save_path}/{file_name}.png"
    
    @tasks.loop(seconds=60) 
    async def unban_task(self):
        """Entbanne Benutzer, deren Bannzeit abgelaufen ist."""
        current_time = time.time()
        with open('bans.txt', 'r', encoding='utf-8') as file:
            bans = file.readlines()
        to_unban = [ban.strip().split(',') for ban in bans if float(ban.strip().split(',')[1]) <= current_time]
        for member_id, _ in to_unban:
            member = await self.bot.fetch_user(int(member_id))
            guild = self.bot.get_guild(854698446996766730) # Ersetze dies durch die ID deines Servers
            await guild.unban(member)
            # Entferne den Benutzer aus der Datei
            with open('bans.txt', 'w', encoding='utf-8') as file:
                for ban in bans:
                    if ban.strip().split(',')[0] != member_id:
                        file.write(ban)
                else:
                    # Füge "Show=False" hinzu, wenn der Benutzer entbannt wird
                    file.write(ban.strip() + ", Show=False\n")

    def reset_timer(self):
        asyncio.create_task(self.clear_user_data_after_6_minutes())

    async def clear_user_data_after_6_minutes(self):
        await asyncio.sleep(6 * 60)
        self.user_data.clear()
        self.TimerMustReseted = True   

    async def admin_did_something(self, action: disnake.AuditLogAction, handleduser: Union[disnake.User, disnake.Member]):
        DeletedbyAdmin = False
        guild = self.bot.get_guild(854698446996766730)
        async for entry in guild.audit_logs(limit=5, action=action, after=datetime.now() - timedelta(minutes=5)):                                            
            if action == disnake.AuditLogAction.message_delete or action == disnake.AuditLogAction.member_disconnect:
                if entry.extra.count is not None:
                    if self.TimerMustReseted:
                        self.reset_timer()
                        self.TimerMustReseted = False
                    if entry.user.id in self.user_data:
                        if entry.extra.count > self.user_data[entry.user.id]:
                            self.user_data[entry.user.id] = entry.extra.count
                            DeletedbyAdmin = True
                            break
                        else: 
                            DeletedbyAdmin = False                        
                            break
                    else:
                        self.user_data[entry.user.id] = entry.extra.count
                        DeletedbyAdmin = True
                        break  
                else:
                    DeletedbyAdmin = False                                
                    break
            else:
                if self.TimerMustReseted:
                    self.reset_timer()
                    self.TimerMustReseted = False
                if entry.user.id not in self.user_data:
                    self.user_data[entry.user.id] = 1
                self.user_data[entry.user.id] += 1
                DeletedbyAdmin = True
                break  

        if action == disnake.AuditLogAction.message_delete or action == disnake.AuditLogAction.member_disconnect or action == disnake.AuditLogAction.member_update:
            if DeletedbyAdmin:
                user = entry.user
                username = user.name
                userid = user.id
            else:
                user = handleduser
                username = handleduser.name
                userid = handleduser.id     
        return self.UserRecord(user,username,userid)  
    
    def update_ids(caseid):
        with open('.env', 'r') as file:
            lines = file.readlines()
        with open('.env', 'w') as file:
            for line in lines:
                if line.startswith("caseid"):
                    file.write(f"caseid={caseid}\n")
                else:
                    file.write(line)

    async def delete_message_by_id(self, channel_id: int, message_id: int):
        """Löscht eine Nachricht basierend auf ihrer ID in einem bestimmten Kanal."""
        try:
            channel = self.bot.get_channel(channel_id)
            if channel:
                message = await channel.fetch_message(message_id)
                await message.delete()
                print(f"Nachricht mit der ID {message_id} wurde gelöscht.")
            else:
                print(f"Kanal mit der ID {channel_id} wurde nicht gefunden.")
        except disnake.NotFound:
            print(f"Nachricht mit der ID {message_id} wurde nicht gefunden.")
        except disnake.Forbidden:
            print("Ich habe nicht die Berechtigung, diese Nachricht zu löschen.")
        except Exception as e:
            print(f"Ein Fehler ist aufgetreten: {e}")

    async def delete_message_by_id_anywhere(self, message_id: int):
        """Versucht, eine Nachricht basierend auf ihrer ID in allen Kanälen zu finden und zu löschen."""
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                try:
                    message = await channel.fetch_message(message_id)
                    await message.delete()
                    print(f"Nachricht mit der ID {message_id} wurde gelöscht.")
                    return # Nachricht wurde gefunden und gelöscht, also abbrechen
                except disnake.NotFound:
                    pass # Nachricht nicht in diesem Kanal gefunden, also weiter suchen
                except disnake.Forbidden:
                    print("Ich habe nicht die Berechtigung, diese Nachricht zu löschen.")
                    return # Berechtigung fehlt, also abbrechen
                except Exception as e:
                    self.logger.critical(f"Ein Fehler ist aufgetreten: {e}")
                    return # Ein anderer Fehler ist aufgetreten, also abbrechen
        print(f"Nachricht mit der ID {message_id} wurde nicht gefunden.")

def setupGlobal(bot):
    bot.add_cog(Globalfile(bot))
