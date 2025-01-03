import disnake
from disnake.ext import commands
import sqlite3
import logging
import os
from typing import Union
import emoji

class RoleAssignment(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("RoleAssignment")
        logging_level = os.getenv("LOGGING_LEVEL", "INFO").upper()
        self.logger.setLevel(logging_level)
        self.db = sqlite3.connect('nightdrive')
        self.cursor = self.db.cursor()

        if not self.logger.handlers:
            formatter = logging.Formatter('[%(asctime)s - %(name)s - %(levelname)s]: %(message)s')
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.setup_database()

    def setup_database(self):
        # Add columns for embed values if they don't exist
        embed_columns = ["TITLE", "DESCRIPTION", "FOOTER", "COLORCODE"]
        for column in embed_columns:
            self.cursor.execute(f"PRAGMA table_info(UNIQUE_MESSAGE)")
            columns = [info[1] for info in self.cursor.fetchall()]
            if column not in columns:
                self.cursor.execute(f"ALTER TABLE UNIQUE_MESSAGE ADD COLUMN {column} TEXT")

        # Add columns for role IDs and emojis if they don't exist
        for i in range(1, 31):
            role_column = f"ROLE_ID_{i}"
            emoji_column = f"EMOJI_{i}"
            self.cursor.execute(f"PRAGMA table_info(UNIQUE_MESSAGE)")
            columns = [info[1] for info in self.cursor.fetchall()]
            if role_column not in columns:
                self.cursor.execute(f"ALTER TABLE UNIQUE_MESSAGE ADD COLUMN {role_column} INTEGER")
            if emoji_column not in columns:
                self.cursor.execute(f"ALTER TABLE UNIQUE_MESSAGE ADD COLUMN {emoji_column} TEXT")

        self.db.commit()

    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info("RoleAssignment Cog is ready.")

    async def create_embed_message(self, channel: disnake.TextChannel, message_type: str):
        self.cursor.execute("SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGETYPE = ?", (message_type,))
        result = self.cursor.fetchone()

        if not result:
            self.logger.error(f"No data found for message type: {message_type}")
            return
        description = result[4].replace('\\n', '\n')
        description = f"{description}\n\n"  # Assuming DESCRIPTION is the second column
        roles_found = False
        for i in range(1, 31):
            role_id = result[7 + (i - 1) * 2]  # Adjust the index based on your table structure
            emoji = result[8 + (i - 1) * 2]  # Adjust the index based on your table structure
            if role_id and emoji:
                role = channel.guild.get_role(role_id)
                if role:
                    roles_found = True
                    emojifetched = self.get_emoji_by_name(channel.guild, emoji)
                    if emojifetched is None or emojifetched.name is None or emojifetched.name == "":
                        description += f":{emoji}: = {role.name}\n"
                    try:
                        if emojifetched.id is not None and emojifetched.id != "":
                            description += f"<:{emojifetched.name}:{emojifetched.id}> = {role.name}\n"
                        else:
                            description += f":{emojifetched.name}: = {role.name}\n"
                    except Exception as e:
                        self.logger.error(f"Error adding role ({emoji}) to description: {e}")

        embed = disnake.Embed(
            title=result[3],  # Assuming TITLE is the first column
            description=f"{description}",
            color=0x00008B
        )
        if result[5] != "" and result[5] is not None:
            embed.set_footer(text=result[5])  # Assuming FOOTER is the fifth column

        message = await channel.send(embed=embed)

        if roles_found:
            for i in range(1, 31):
                role_id = result[7 + (i - 1) * 2]  # Adjust the index based on your table structure
                emoji = result[8 + (i - 1) * 2]  # Adjust the index based on your table structure
                if role_id and emoji:
                    try:
                        emojifetched = self.get_emoji_by_name(channel.guild, emoji)
                        if emojifetched.id is not None:
                            await message.add_reaction(emojifetched)
                        else:                                                        
                            emojifetched = self.get_manual_emoji(emoji)
                            await message.add_reaction(emojifetched)
                    except Exception as e:
                        self.logger.error(f"Error adding reaction ({emoji}) to message: {e}")

        self.cursor.execute("UPDATE UNIQUE_MESSAGE SET MESSAGEID = ? WHERE MESSAGETYPE = ?", (message.id, message_type))
        self.db.commit()  
        
    def get_emoji_by_name(self, guild: disnake.Guild, emoji_name: str) -> Union[disnake.Emoji, disnake.PartialEmoji, None]:
        # Check custom emojis in the guild
        for emoji in guild.emojis:
            if emoji.name == emoji_name:
                return emoji

        # Check general Discord emojis
        try:
            return disnake.PartialEmoji(name=emoji_name)
        except ValueError:
            return None
                
    @commands.slash_command(guild_ids=[854698446996766730])
    async def create_embed(self, inter: disnake.ApplicationCommandInteraction, message_type: str, channel: disnake.TextChannel):
        await inter.response.defer(ephemeral=True)
        await self.create_embed_message(channel, message_type)
        await inter.edit_original_response(content="Embed message created.")
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: disnake.RawReactionActionEvent):
        if payload.member.bot:
            return

        self.cursor.execute("SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGEID = ?", (payload.message_id,))
        result = self.cursor.fetchone()

        if not result:
            return

        guild : disnake.Guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        
        
        for i in range(1, 31):
            role_id = result[7 + (i - 1) * 2]
            emoji = result[8 + (i - 1) * 2]
            if role_id and emoji:
                emojifetched: disnake.Emoji = None
                emojifetched = self.get_emoji_by_name(guild, emoji)
                if emojifetched and str(emojifetched) == str(payload.emoji):
                    role = guild.get_role(role_id)
                    if role:
                        await guild.get_member(payload.user_id).add_roles(role)
                        self.logger.info(f"Assigned role {role.name} to {payload.member.name} for reacting with {emoji}")
                        break    
                    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: disnake.RawReactionActionEvent):
        if payload.user_id == None:
            return

        self.cursor.execute("SELECT * FROM UNIQUE_MESSAGE WHERE MESSAGEID = ?", (payload.message_id,))
        result = self.cursor.fetchone()

        if not result:
            return

        guild: disnake.Guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        for i in range(1, 31):
            role_id = result[7 + (i - 1) * 2]
            emoji = result[8 + (i - 1) * 2]
            if role_id and emoji:
                emojifetched: disnake.Emoji = None
                emojifetched = self.get_emoji_by_name(guild, emoji)
                if emojifetched and str(emojifetched) == str(payload.emoji):
                    role = guild.get_role(role_id)
                    if role:
                        await guild.get_member(payload.user_id).remove_roles(role)
                        member: disnake.Member = guild.get_member(payload.user_id)
                        self.logger.info(f"Removed role {role.name} from {member.name} for removing reaction {emoji}")
                        break                    

    def get_manual_emoji(self, emoji_name: str) -> disnake.Emoji:
        emoji_dict = {
            "newspaper": "📰",
            "sparkler": "🎇",
            "sparkles": "✨",
            "microphone2": "🎙️",
            "night_with_stars": "🌃",
            "bell": "🔔",
            "no_bell": "🔕",
            "question": "❓",
            "zero": "0️⃣",
            "one": "1️⃣",
            "two": "2️⃣",
            "three": "3️⃣",
            "four": "4️⃣",
            "five": "5️⃣",
            "six": "6️⃣",
            "seven": "7️⃣",
            "eight": "8️⃣",
            "nine": "9️⃣",
            "circle": "⚪",
            "blue_circle": "🔵",
            "red_circle": "🔴",
            "black_circle": "⚫",
            "white_circle": "⚪",
            "purple_circle": "🟣",
            "green_circle": "🟢",
            "yellow_circle": "🟡",
            "brown_circle": "🟤",
            "orange_circle": "🟠",
            "pink_circle": "🟣",
            "large_blue_circle": "🔵",
            "gun": "🔫",
            "space_invader": "👾",
            "crossed_swords": "⚔️",
            "knife": "🔪",
            "pick": "⛏️",
            "smile": "😊",
            "heart": "❤️",
            "thumbs_up": "👍",
            "fire": "🔥",
            "star": "⭐",
            "check_mark": "✔️",
            "cross_mark": "❌",
            "clap": "👏",
            "wave": "👋",
            "rocket": "🚀",
            "sun": "☀️",
            "moon": "🌙",
            "cloud": "☁️",
            "snowflake": "❄️",
            "zap": "⚡",
            "umbrella": "☔",
            "coffee": "☕",
            "soccer": "⚽",
            "basketball": "🏀",
            "football": "🏈",
            "baseball": "⚾",
            "tennis": "🎾",
            "volleyball": "🏐",
            "rugby": "🏉",
            "golf": "⛳",
            "trophy": "🏆",
            "medal": "🏅",
            "crown": "👑",
            "gem": "💎",
            "money_bag": "💰",
            "dollar": "💵",
            "yen": "💴",
            "euro": "💶",
            "pound": "💷",
            "credit_card": "💳",
            "shopping_cart": "🛒",
            "gift": "🎁",
            "balloon": "🎈",
            "party_popper": "🎉",
            "confetti_ball": "🎊",
            "tada": "🎉",
            "sparkles": "✨",
            "boom": "💥",
            "collision": "💥",
            "dizzy": "💫",
            "speech_balloon": "💬",
            "thought_balloon": "💭",
            "zzz": "💤",
            "wave": "👋",
            "raised_hand": "✋",
            "ok_hand": "👌",
            "victory_hand": "✌️",
            "crossed_fingers": "🤞",
            "love_you_gesture": "🤟",
            "call_me_hand": "🤙",
            "backhand_index_pointing_left": "👈",
            "backhand_index_pointing_right": "👉",
            "backhand_index_pointing_up": "👆",
            "backhand_index_pointing_down": "👇",
            "index_pointing_up": "☝️",
            "raised_fist": "✊",
            "oncoming_fist": "👊",
            "left_facing_fist": "🤛",
            "right_facing_fist": "🤜",
            "clapping_hands": "👏",
            "raising_hands": "🙌",
            "open_hands": "👐",
            "palms_up_together": "🤲",
            "handshake": "🤝",
            "folded_hands": "🙏",
            "writing_hand": "✍️",
            "nail_polish": "💅",
            "selfie": "🤳",
            "muscle": "💪",
            "mechanical_arm": "🦾",
            "mechanical_leg": "🦿",
            "leg": "🦵",
            "foot": "🦶",
            "ear": "👂",
            "ear_with_hearing_aid": "🦻",
            "nose": "👃",
            "brain": "🧠",
            "anatomical_heart": "🫀",
            "lungs": "🫁",
            "tooth": "🦷",
            "bone": "🦴",
            "eyes": "👀",
            "eye": "👁️",
            "tongue": "👅",
            "mouth": "👄",
            "baby": "👶",
            "child": "🧒",
            "boy": "👦",
            "girl": "👧",
            "person": "🧑",
            "man": "👨",
            "woman": "👩",
            "older_person": "🧓",
            "old_man": "👴",
            "old_woman": "👵",
            "person_frowning": "🙍",
            "person_pouting": "🙎",
            "person_gesturing_no": "🙅",
            "person_gesturing_ok": "🙆",
            "person_tipping_hand": "💁",
            "person_raising_hand": "🙋",
            "deaf_person": "🧏",
            "person_bowing": "🙇",
            "person_facepalming": "🤦",
            "person_shrugging": "🤷",
            "health_worker": "🧑‍⚕️",
            "student": "🧑‍🎓",
            "teacher": "🧑‍🏫",
            "judge": "🧑‍⚖️",
            "farmer": "🧑‍🌾",
            "cook": "🧑‍🍳",
            "mechanic": "🧑‍🔧",
            "factory_worker": "🧑‍🏭",
            "office_worker": "🧑‍💼",
            "scientist": "🧑‍🔬",
            "technologist": "🧑‍💻",
            "singer": "🧑‍🎤",
            "artist": "🧑‍🎨",
            "pilot": "🧑‍✈️",
            "astronaut": "🧑‍🚀",
            "firefighter": "🧑‍🚒",
            "police_officer": "👮",
            "detective": "🕵️",
            "guard": "💂",
            "ninja": "🥷",
            "construction_worker": "👷",
            "prince": "🤴",
            "princess": "👸",
            "person_wearing_turban": "👳",
            "person_with_skullcap": "👲",
            "woman_with_headscarf": "🧕",
            "person_in_tuxedo": "🤵",
            "person_with_veil": "👰",
            "pregnant_woman": "🤰",
            "breast_feeding": "🤱",
            "woman_feeding_baby": "👩‍🍼",
            "man_feeding_baby": "👨‍🍼",
            "person_feeding_baby": "🧑‍🍼",
            "angel": "👼",
            "santa_claus": "🎅",
            "mrs_claus": "🤶",
            "mx_claus": "🧑‍🎄",
            "superhero": "🦸",
            "supervillain": "🦹",
            "mage": "🧙",
            "fairy": "🧚",
            "vampire": "🧛",
            "merperson": "🧜",
            "elf": "🧝",
            "genie": "🧞",
            "zombie": "🧟",
            "person_getting_massage": "💆",
            "person_getting_haircut": "💇",
            "person_walking": "🚶",
            "person_standing": "🧍",
            "person_kneeling": "🧎",
            "person_with_probing_cane": "🧑‍🦯",
            "person_in_motorized_wheelchair": "🧑‍🦼",
            "person_in_manual_wheelchair": "🧑‍🦽",
            "person_running": "🏃",
            "woman_dancing": "💃",
            "man_dancing": "🕺",
            "person_in_suit_levitating": "🕴️",
            "people_with_bunny_ears": "👯",
            "person_in_steamy_room": "🧖",
            "person_climbing": "🧗",
            "person_fencing": "🤺",
            "horse_racing": "🏇",
            "skier": "⛷️",
            "snowboarder": "🏂",
            "person_golfing": "🏌️",
            "person_surfing": "🏄",
            "person_rowing_boat": "🚣",
            "person_swimming": "🏊",
            "person_bouncing_ball": "⛹️",
            "person_lifting_weights": "🏋️",
            "person_biking": "🚴",
            "person_mountain_biking": "🚵",
            "person_cartwheeling": "🤸",
            "people_wrestling": "🤼",
            "person_playing_water_polo": "🤽",
            "person_playing_handball": "🤾",
            "person_juggling": "🤹",
            "person_in_lotus_position": "🧘",
            "person_taking_bath": "🛀",
            "person_in_bed": "🛌",
            "people_holding_hands": "🧑‍🤝‍🧑",
            "women_holding_hands": "👭",
            "woman_and_man_holding_hands": "👫",
            "men_holding_hands": "👬",
            "kiss": "💏",
            "couple_with_heart": "💑",
            "family": "👪",
            "speaking_head": "🗣️",
            "bust_in_silhouette": "👤",
            "busts_in_silhouette": "👥",
            "footprints": "👣",
            "monkey_face": "🐵",
            "monkey": "🐒",
            "gorilla": "🦍",
            "orangutan": "🦧",
            "dog_face": "🐶",
            "dog": "🐕",
            "guide_dog": "🦮",
            "service_dog": "🐕‍🦺",
            "poodle": "🐩",
            "wolf": "🐺",
            "fox": "🦊",
            "raccoon": "🦝",
            "cat_face": "🐱",
            "cat": "🐈",
            "black_cat": "🐈‍⬛",
            "lion": "🦁",
            "tiger_face": "🐯",
            "tiger": "🐅",
            "leopard": "🐆",
            "horse_face": "🐴",
            "horse": "🐎",
            "unicorn": "🦄",
            "zebra": "🦓",
            "deer": "🦌",
            "bison": "🦬",
            "cow_face": "🐮",
            "ox": "🐂",
            "water_buffalo": "🐃",
            "cow": "🐄",
            "pig_face": "🐷",
            "pig": "🐖",
            "boar": "🐗",
            "pig_nose": "🐽",
            "ram": "🐏",
            "ewe": "🐑",
            "goat": "🐐",
            "camel": "🐪",
            "two_hump_camel": "🐫",
            "llama": "🦙",
            "giraffe": "🦒",
            "elephant": "🐘",
            "mammoth": "🦣",
            "rhinoceros": "🦏",
            "hippopotamus": "🦛",
            "mouse_face": "🐭",
            "mouse": "🐁",
            "rat": "🐀",
            "hamster": "🐹",
            "rabbit_face": "🐰",
            "rabbit": "🐇",
            "chipmunk": "🐿️",
            "beaver": "🦫",
            "hedgehog": "🦔",
            "bat": "🦇",
            "bear": "🐻",
            "polar_bear": "🐻‍❄️",
            "koala": "🐨",
            "panda": "🐼",
            "sloth": "🦥",
            "otter": "🦦",
            "skunk": "🦨",
            "kangaroo": "🦘",
            "badger": "🦡",
            "paw_prints": "🐾",
            "turkey": "🦃",
            "chicken": "🐔",
            "rooster": "🐓",
            "hatching_chick": "🐣",
            "baby_chick": "🐤",
            "front_facing_baby_chick": "🐥",
            "bird": "🐦",
            "penguin": "🐧",
            "dove": "🕊️",
            "eagle": "🦅",
            "duck": "🦆",
            "swan": "🦢",
            "owl": "🦉",
            "dodo": "🦤",
            "feather": "🪶",
            "flamingo": "🦩",
            "peacock": "🦚",
            "parrot": "🦜",
            "frog": "🐸",
            "crocodile": "🐊",
            "turtle": "🐢",
            "lizard": "🦎",
            "snake": "🐍",
            "dragon_face": "🐲",
            "dragon": "🐉",
            "sauropod": "🦕",
            "t_rex": "🦖",
            "spouting_whale": "🐳",
            "whale": "🐋",
            "dolphin": "🐬",
            "seal": "🦭",
            "fish": "🐟",
            "tropical_fish": "🐠",
            "blowfish": "🐡",
            "shark": "🦈",
            "octopus": "🐙",
            "spiral_shell": "🐚",
            "snail": "🐌",
            "butterfly": "🦋",
            "bug": "🐛",
            "ant": "🐜",
            "honeybee": "🐝",
            "beetle": "🪲",
            "lady_beetle": "🐞",
            "cricket": "🦗",
            "cockroach": "🪳",
            "spider": "🕷️",
            "spider_web": "🕸️",
            "scorpion": "🦂",
            "mosquito": "🦟",
            "fly": "🪰",
            "worm": "🪱",
            "microbe": "🦠",
            "bouquet": "💐",
            "cherry_blossom": "🌸",
            "white_flower": "💮",
            "rosette": "🏵️",
            "rose": "🌹",
            "wilted_flower": "🥀",
            "hibiscus": "🌺",
            "sunflower": "🌻",
            "blossom": "🌼",
            "tulip": "🌷",
            "seedling": "🌱",
            "potted_plant": "🪴",
            "evergreen_tree": "🌲",
            "deciduous_tree": "🌳",
            "palm_tree": "🌴",
            "cactus": "🌵",
            "sheaf_of_rice": "🌾",
            "herb": "🌿",
            "shamrock": "☘️",
            "four_leaf_clover": "🍀",
            "maple_leaf": "🍁",
            "fallen_leaf": "🍂",
            "leaf_fluttering_in_wind": "🍃",
            "grapes": "🍇",
            "melon": "🍈",
            "watermelon": "🍉",
            "tangerine": "🍊",
            "lemon": "🍋",
            "banana": "🍌",
            "pineapple": "🍍",
            "mango": "🥭",
            "red_apple": "🍎",
            "green_apple": "🍏",
            "pear": "🍐",
            "peach": "🍑",
            "cherries": "🍒",
            "strawberry": "🍓",
            "blueberries": "🫐",
            "kiwi_fruit": "🥝",
            "tomato": "🍅",
            "olive": "🫒",
            "coconut": "🥥",
            "avocado": "🥑",
            "eggplant": "🍆",
            "potato": "🥔",
            "carrot": "🥕",
            "ear_of_corn": "🌽",
            "hot_pepper": "🌶️",
            "bell_pepper": "🫑",
            "cucumber": "🥒",
            "leafy_green": "🥬",
            "broccoli": "🥦",
            "garlic": "🧄",
            "onion": "🧅",
            "mushroom": "🍄",
            "peanuts": "🥜",
            "chestnut": "🌰",
            "bread": "🍞",
            "croissant": "🥐",
            "baguette_bread": "🥖",
            "flatbread": "🫓",
            "pretzel": "🥨",
            "bagel": "🥯",
            "pancakes": "🥞",
            "waffle": "🧇",
            "cheese_wedge": "🧀",
            "meat_on_bone": "🍖",
            "poultry_leg": "🍗",
            "cut_of_meat": "🥩",
            "bacon": "🥓",
            "face_with_tears_of_joy": "😂",
            "smiling_face_with_heart_eyes": "😍",
            "face_with_rolling_eyes": "🙄",
            "face_with_medical_mask": "😷",
            "face_with_thermometer": "🤒",
            "face_with_head_bandage": "🤕",
            "nauseated_face": "🤢",
            "sneezing_face": "🤧",
            "hot_face": "🥵",
            "cold_face": "🥶",
            "woozy_face": "🥴",
            "partying_face": "🥳",
            "smiling_face_with_tear": "🥲",
            "disguised_face": "🥸",
            "pinched_fingers": "🤌",
            "anatomical_heart": "🫀",
            "lungs": "🫁",
            "people_hugging": "🫂",
            "blueberries": "🫐",
            "bell_pepper": "🫑",
            "olive": "🫒",
            "flatbread": "🫓",
            "tamale": "🫔",
            "fondue": "🫕",
            "teapot": "🫖",
            "bubble_tea": "🧋",
            "beaver": "🦫",
            "polar_bear": "🐻‍❄️",
            "feather": "🪶",
            "seal": "🦭",
            "beetle": "🪲",
            "cockroach": "🪳",
            "fly": "🪰",
            "worm": "🪱",
            "rock": "🪨",
            "wood": "🪵",
            "hut": "🛖",
            "pickup_truck": "🛻",
            "roller_skate": "🛼",
            "magic_wand": "🪄",
            "piñata": "🪅",
            "nesting_dolls": "🪆",
            "coin": "🪙",
            "boomerang": "🪃",
            "carpentry_saw": "🪚",
            "screwdriver": "🪛",
            "hook": "🪝",
            "ladder": "🪜",
            "mirror": "🪞",
            "window": "🪟",
            "plunger": "🪠",
            "sewing_needle": "🪡",
            "knots": "🪢",
            "bucket": "🪣",
            "mouse_trap": "🪤",
            "toothbrush": "🪥",
            "headstone": "🪦",
            "placard": "🪧",
            "transgender_flag": "🏳️‍⚧️",
            "transgender_symbol": "⚧️",
            "up": "⬆️",
        }
        return emoji_dict.get(emoji_name, None)


def setupRoleAssignment(bot):
    bot.add_cog(RoleAssignment(bot))