import discord
from discord.ext import commands, tasks
import time
import re
import json
import os
import logging
import logging.handlers
import heapq
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.all()
intents.message_content = True
client = commands.Bot(command_prefix="/", intents=intents)
REMINDER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reminders.json")

reminders = []  # This will be a heap
user_map = {}  # This will map user IDs to discord.User objects

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)  # Create the log directory if it doesn't exist
LOG_FILE = os.path.join(LOG_DIR, "reminder_bot.log")

# Create a rotating file handler which rotates after reaching 1000 lines (assuming an average of 100 bytes per line)
handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=10000, backupCount=20)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

@client.event
async def on_ready():
    global reminders
    global user_map
    print(f"{client.user.name} bot connected!")
    reminders = load_reminders()
    load_and_start_reminders()

    for guild in client.guilds:
        for member in guild.members:
            user_map[member.id] = member

@client.tree.command(name="notify", description="Sets a reminder notification via DM")
async def notify(interaction: discord.Interaction, time_str: str, message: str):
    try:
        time_pattern = r"(\d+)\s*(days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)"
        matches = re.findall(time_pattern, time_str)

        total_seconds = 0
        for amount, unit in matches:
            amount = int(amount)
            if unit.startswith('day'):
                total_seconds += amount * 24 * 60 * 60
            elif unit.startswith('hour'):
                total_seconds += amount * 60 * 60
            elif unit.startswith('min'):
                total_seconds += amount * 60
            elif unit.startswith('sec'):
                total_seconds += amount

        if not total_seconds:
            await interaction.response.send_message("Please specify a valid time duration (e.g., 2 min 30 sec)")
            return

        timestamp = time.time() + total_seconds
        save_reminder(interaction.user.id, message, timestamp)
        await interaction.response.send_message(f"Reminder set! I'll DM you in {time_str}")

    except ValueError:
        await interaction.response.send_message("Invalid time format. Example: /notify 2 mins 30 seconds This is the message!")
        return

def load_reminders():
    if os.path.exists(REMINDER_FILE):
        with open(REMINDER_FILE, "r") as f:
            reminders_list = json.load(f)
            return [tuple(reminder) for reminder in reminders_list]
    else:
        return []

def load_and_start_reminders():
    global reminders
    reminders = load_reminders()
    heapq.heapify(reminders)
    logging.info(f"Loaded {len(reminders)} reminders from file")  # Log reminder load
    if not check_reminders.is_running():
        check_reminders.start()
        
def save_reminders(reminders):
    with open(REMINDER_FILE, "w") as f:
        json.dump(reminders, f)

def save_reminder(user_id, message, timestamp):
    heapq.heappush(reminders, (timestamp, user_id, message))
    logging.info(f"Saved reminder for {user_id} at {timestamp} with message: {message}")
    save_reminders(reminders)

@tasks.loop(seconds=1.0) 
async def check_reminders():
    logging.info("Checking reminders...")
    while reminders and reminders[0][0] <= time.time():
        _, user_id, message = heapq.heappop(reminders)
        user = user_map.get(user_id)
        if user:
            try:
                await user.send(f"Reminder: {message}")
                save_reminders(reminders)
            except Exception as e:  
                logging.error(f"Error sending reminder to {user}: {e}")

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
client.run(TOKEN)
