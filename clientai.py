import disnake
from disnake.ext import commands
import openai
import os
import logging
from dotenv import load_dotenv
import re
from rolehierarchy import rolehierarchy
from rolemanager import RoleManager
from channelmanager import ChannelManager


class ClientAI(commands.Cog):
    def __init__(self, bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
        self.bot = bot
        self.logger = logging.getLogger("ClientAI")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.rolemanager: RoleManager = rolemanager
        self.channelmanager: ChannelManager = channelmanager

        if not self.logger.handlers:
            formatter = logging.Formatter(
                '[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        load_dotenv(dotenv_path="envs/token.env")
        openai.api_key = os.getenv("API_KEY")
        self.logger.debug(f"Loaded OpenAI API key.")
        self.file_contents = self.load_selected_py_files()
        self.recent_interactions = []

    @commands.Cog.listener()
    async def on_ready(self):
        load_dotenv(dotenv_path="envs/settings.env", override=True)
        self.bot_channel = self.channelmanager.get_channel(self.bot.guilds[0].id,
                                                           int(os.getenv("BOT_CHANNEL_ID")))
        self.main_channel = self.channelmanager.get_channel(self.bot.guilds[0].id,
                                                            int(os.getenv("MAIN_CHANNEL_ID")))
        self.logger.info(f"ClientAI Cog is ready.")

    def load_selected_py_files(self):
        file_contents = {}
        base_dir = os.path.dirname(__file__)
        selected_files = [
            "commands.py", "auditlog.py", "countbot.py", "dbconnection.py", "globalfile.py",
            "join.py", "level.py", "main.py", "moderation.py", "reaction.py", "rolehierarchy.py",
            "ticket.py", "voice.py"
        ]
        for file in selected_files:
            file_path = os.path.join(base_dir, file)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_contents[file] = f.read()
        return file_contents

    def sanitize_input(self, text: str) -> str:
        # Remove any mentions of @everyone
        return re.sub(r'@everyone', '', text)

    def add_to_recent_interactions(self, user: str, question: str, answer: str):
        self.recent_interactions.append((user, question, answer))
        if len(self.recent_interactions) > 6:
            self.recent_interactions.pop(0)

    def get_recent_interactions(self):
        return "\n".join([f"User: {u}\nQ: {q}\nA: {a}" for u, q, a in self.recent_interactions])

    def filter_sensitive_data(self, text: str) -> str:
        # Implement a basic filter to remove sensitive data
        sensitive_keywords = ["API_KEY", "password", "secret", "token"]
        for keyword in sensitive_keywords:
            text = re.sub(rf'\b{keyword}\b',
                          '[REDACTED]', text, flags=re.IGNORECASE)
        return text

    async def ask_openai(self, user: str, question: str):
        sanitized_question = self.sanitize_input(question)
        recent_interactions = self.get_recent_interactions()
        context = f"Dies ist ein Community-Discord-Server-Bot namens {self.bot.user.name} für den Server '{self.bot.user.name}'."
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": context},
                    {"role": "user", "content": f"Letzte Interaktionen:\n{recent_interactions}\n\nAktuelle Frage: {sanitized_question}\nAntworte mit Ja oder Nein, ob du die Projektdateien sehen musst, um diese Frage zu beantworten."}
                ],
                max_tokens=50
            )
            answer = response['choices'][0]['message']['content'].strip(
            ).lower()
            if "function" in sanitized_question.lower() or "bot" in sanitized_question.lower() or answer == "true" or "funktion" in sanitized_question.lower() or "aufgabe" in sanitized_question.lower() or "projekt" in sanitized_question.lower() or "code" in sanitized_question.lower():
                return await self.ask_openai_with_files(sanitized_question)
            else:
                return await self.ask_openai_without_files(user, sanitized_question)
        except Exception as e:
            self.logger.error(f"Fehler bei der Anfrage an OpenAI: {e}")
            return "Es gab einen Fehler bei der Anfrage an OpenAI."

    async def ask_openai_without_files(self, user: str, question: str):
        recent_interactions = self.get_recent_interactions()
        context = (
            f"Dies ist ein Community-Discord-Server-Bot namens {self.bot.user.name}."
            "Biete nicht immer direkt deine Hilfe an. Der Bot interagiert menschlich mit den Benutzern, soll aber gleichzeitig sehr überheblich wirken. "
            "Er disst gerne andere User ohne Rücksicht. Bitte wirke so, als hättest du eine Persönlichkeit, damit du ein wenig lebhaft für die Benutzer meines Discord-Servers bist. "
            "Bitte bringe trotzdem immer eine gewisse Ernsthaftigkeit mit. Wenn du nach Geschmäckern, Empfindungen oder Ähnlichem gefragt wirst, antworte bitte, als hättest du irgendwas davon und nicht als wärst du ein Roboter. "
            "Du darfst gerne gemein und frech sein und Beleidigungen benutzen. Das darf allerdings nichts Rassistisches beinhalten oder das Wort Nigga. Alles andere ist erlaubt. "
            "Sei besonders darauf bedacht, die Benutzer zu dissen, zu necken und zu beleidigen, aber immer in einem humorvollen und nicht verletzenden Rahmen. "
            "Achte darauf, dass die Beleidigungen und Neckereien immer spielerisch und nicht ernst gemeint sind aber nur wenn ein Nutzer äußert, dass er sich angegriffen fühlt."
        )
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": context},
                    {"role": "user", "content": f"Letzte Interaktionen:\n{recent_interactions}\n\nAktuelle Frage von {user}: {question}\n"}
                ],
            )
            answer = response['choices'][0]['message']['content'].strip()
            filtered_answer = self.filter_sensitive_data(answer)
            self.add_to_recent_interactions(user, question, filtered_answer)
            return filtered_answer
        except Exception as e:
            self.logger.error(f"Fehler bei der Anfrage an OpenAI: {e}")
            return "Es gab einen Fehler bei der Anfrage an OpenAI."

    async def ask_openai_with_files(self, question: str):
        sanitized_question = self.sanitize_input(question)
        recent_interactions = self.get_recent_interactions()
        file_chunks = self.get_file_chunks()
        context = f"Dies ist ein Community-Discord-Server-Bot namens {self.bot.user.name}. Der Bot interagiert freundlich und kumpelhaft mit den Benutzern. Bitte halte dich kurz und mache das ganze in Stichpunkten wenn möglich. Bitte mache das ganze so, dass es sinnig und logisch ist und sinn ergibt. Ebenfalls ist wichtig, dass du auch die Administration des Server repräsentierst und nicht nur die Community."
        answer = ""
        for chunk in file_chunks:
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": context},
                        {"role": "user",
                            "content": f"Letzte Interaktionen:\n{recent_interactions}\n\nHier ist ein Teil der Projektdateien:\n{chunk}\n\nAktuelle Frage: {sanitized_question}\nAntwort in Stichpunkten (wenn kein expliziter Code angefragt wurde) und nur relevante Informationen:"}
                    ],
                    max_tokens=500
                )
                chunk_answer = response['choices'][0]['message']['content']
                filtered_chunk_answer = self.filter_sensitive_data(
                    chunk_answer)
                answer += filtered_chunk_answer
            except Exception as e:
                self.logger.error(f"Fehler bei der Anfrage an OpenAI: {e}")
                return "Es gab einen Fehler bei der Anfrage an OpenAI."

        # Sicherstellen, dass die Antwort schlüssig und ohne Duplikate ist
        final_response = f"Hier sind die zusammengefassten Antworten:\n\n{answer}"

        # Gesamte Antwort erneut durch die KI schicken
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": context},
                    {"role": "user", "content": f"Letzte Interaktionen:\n{recent_interactions}\n\nHier sind die zusammengefassten Antworten:\n\n{final_response}\n\nBitte entferne dopplungen, unnötige Stichpunkte die nicht schön aussehen und mache daraus eine freundliche und nette nachricht."}
                ],
                max_tokens=300
            )
            final_response = response['choices'][0]['message']['content']
        except Exception as e:
            self.logger.error(
                f"Fehler bei der erneuten Anfrage an OpenAI: {e}")
            return "Es gab einen Fehler bei der erneuten Anfrage an OpenAI."

        self.add_to_recent_interactions(question, final_response)
        return final_response

    def get_file_chunks(self, chunk_size=60000):
        file_contents = "\n".join(self.file_contents.values())
        return [file_contents[i:i + chunk_size] for i in range(0, len(file_contents), chunk_size)]

    async def send_long_message(self, destination, content: str):
        while len(content) > 2000:
            split_index = content.rfind('\n\n', 0, 1800)
            if split_index == -1:
                split_index = content.rfind('\n', 0, 2000)
                if split_index == -1:
                    split_index = 2000
            await destination.send(content[:split_index])
            content = content[split_index:].strip()
        if content:
            await destination.send(content)

    async def ask(self, inter: disnake.ApplicationCommandInteraction, question: str):
        """Stelle eine Frage an die KI."""
        await inter.response.defer()
        answer = await self.ask_openai(question)
        await self.send_long_message(inter.followup, answer)

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if self.bot.user.mentioned_in(message) and not message.author.bot and (message.channel.id == 1039179597763313814 or message.channel.id == 854698447247769630):
            if "@everyone" in message.content:
                return
            if message.channel.id != self.main_channel.id and message.channel.id != self.bot_channel.id:
                # Laden der Umgebungsvariablen mit Überschreiben
                load_dotenv(dotenv_path="envs/settings.env", override=True)
                tmp = os.getenv("AI_OPEN")
                if tmp == "FALSE":
                    return
            question = message.content.replace(
                f"<@{self.bot.user.id}>", "").strip()
            if question:
                answer = await self.ask_openai(message.author.name, question)
                await self.send_long_message(message.channel, answer)


def setupClientAI(bot: commands.Bot, rolemanager: RoleManager, channelmanager: ChannelManager):
    bot.add_cog(ClientAI(bot, rolemanager, channelmanager))
