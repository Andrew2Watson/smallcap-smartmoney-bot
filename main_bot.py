# main_bot.py
import os
import telebot
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(BOT_TOKEN)

# /start command
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "👋 Hi! Bot is alive. Send me a command.")

# /sentiment command (demo response)
@bot.message_handler(commands=['sentiment'])
def sentiment(message):
    bot.reply_to(message, "📊 Sentiment command connected! (Demo)")

# /whale command (demo response)
@bot.message_handler(commands=['whale'])
def whale(message):
    bot.reply_to(message, "🐋 Whale command connected! (Demo)")

# /retail command (demo response)
@bot.message_handler(commands=['retail'])
def retail(message):
    bot.reply_to(message, "🛍️ Retail command connected! (Demo)")

# Run the bot
if __name__ == "__main__":
    print("Bot is running on Render...")
    bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
