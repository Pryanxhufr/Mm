import telebot
import threading
import requests
import os
import time

TOKEN = "7698859036:AAF1T2z2tsf1Wg8iy6-PO3L3YN5_yIXyhhY"
bot = telebot.TeleBot(TOKEN)

#BEARER_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhZGRyZXNzIjoiMHg2M2I2YjJlZTYzMjRlM2M1M2NhZjFkMjg0MWIyMTEzNGRlYjE5YWE5IiwiaXNzIjoiaHR0cHM6Ly9hcGkudW5pd2hhbGVzLmlvLyIsInN1YiI6InVzZXIiLCJwbGFuIjoiYmFzaWMiLCJiYWxhbmNlIjowLCJpYXQiOjE3MzE4NDQxNDksImV4cCI6MTczMTg1NDk0OX0.i6X9L5r-cucuo8mKIbLtzKnbHxLFdMK3NVEco1FxpJ4"

wallet_name_to_address = {
    "trojan": "9yMwSPk9mrXSN7yDHUuZurAh1sjbJsfpUqjZ7SvVtdco",
    "bonk": "ZG98FUCjb8mJ824Gbs6RsgVmr1FhXb2oNiJHa2dwmPd",
    "photon": "AVUCZyuT35YSuj4RH7fwiyPu82Djn2Hfg7y2ND2XcnZH",
    "bullx": "F4hJ3Ee3c5UuaorKAMfELBjYCjiiLH75haZTKqTywRP3"
}

# Ensure required files exist
if not os.path.exists("admin_uid.txt"):
    open("admin_uid.txt", "w").close()

# Load admin user IDs
with open("admin_uid.txt", "r") as f:
    admin_uids = f.read().splitlines()

def is_user_registered(user_id):
    try:
        with open("admin_uid.txt", "r") as file:
            registered_ids = file.read().splitlines()
            return str(user_id) in registered_ids
    except FileNotFoundError:
        return False

# Store active tasks for users
active_tasks = {}
stop_flags = {}

def get_signatures(wallet_address):
    url = "https://api.mainnet-beta.solana.com"
    headers = {"Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getSignaturesForAddress",
        "params": [
            wallet_address,
            {"limit": 100}
        ]
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        signatures_data = response.json()
        return [sig['signature'] for sig in signatures_data.get('result', [])]
    except (requests.exceptions.RequestException, KeyError):
        return []

def get_sender_for_signature(signature):
    url = f'https://api.solana.fm/v0/transfers/{signature}'
    headers = {
        'authority': 'api.solana.fm',
        'accept': 'application/json, text/plain, */*',
        'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data['result']['data'][0]['source']
    except (requests.exceptions.RequestException, KeyError, IndexError):
        return None

def get_bearer_token():
    try:
        with open('config.txt', 'r') as file:
            token = file.read().strip()
            return token
    except FileNotFoundError:
        print("Error: config.txt file not found.")
        return None

def fetch_wallet_data(source, minimum_winrate, minimum_pnl, wallet_name, chat_id):
    BEARER_TOKEN = get_bearer_token()

    headers = {
        'Accept': '*/*',
        'Authorization': f'Bearer {BEARER_TOKEN}',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
    }
    params = {
        'wallet': source,
        'skip_unrealized_pnl': 'true',
        'page': '1',
    }
    try:
        response = requests.get('https://feed-api.cielo.finance/v1/pnl/tokens', params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        winrate = round(data["data"]["winrate"], 2)
        total_traded = data["data"]["total_tokens_traded"]
        pnl = round(data["data"]["total_roi_percentage"], 2)
        print(f"winrate : {winrate}\npnl : {pnl}")

        if winrate > minimum_winrate and pnl > minimum_pnl:
            message = (
                f"⛓ Detected Wallet— {wallet_name}\n\n"
                f"`{source}`\n\n"
                f"Win Rate: {winrate}%\n"
                f"Last 7D PnL: {pnl}%\n"
                f"Tokens Traded: {total_traded}"
            )
            bot.send_message(chat_id, message, parse_mode="Markdown")
    except (requests.exceptions.RequestException, KeyError):
        pass


def process_signature(signature, minimum_winrate, minimum_pnl, wallet_name, chat_id):
    sender = get_sender_for_signature(signature)
    if sender:
        fetch_wallet_data(sender, minimum_winrate, minimum_pnl, wallet_name, chat_id)

def scan_wallet(wallet_address, minimum_winrate, minimum_pnl, wallet_name, chat_id):
    while stop_flags.get(str(chat_id), False) is False:
        signatures = get_signatures(wallet_address)
        threads = []
        for signature in signatures:
            thread = threading.Thread(target=process_signature, args=(signature, minimum_winrate, minimum_pnl, wallet_name, chat_id))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()
        
        time.sleep(5)  # Wait 5 seconds before scanning again

@bot.message_handler(commands=['scan'])
def scan_command(message):
    if str(message.chat.id) not in admin_uids:
        bot.reply_to(message, "You are not registered.")
        return

    try:
        parts = message.text.split()
        if len(parts) != 6 or parts[2] != "winrate" or parts[4] != "pnl":
            bot.reply_to(message, "Invalid command format. Use /scan {wallet_name} winrate {minimum_winrate} pnl {minimum_pnl}")
            return

        wallet_name = parts[1]
        if wallet_name not in wallet_name_to_address:
            bot.reply_to(message, "No wallet of this name.")
            return

        try:
            minimum_winrate = float(parts[3])
            minimum_pnl = float(parts[5])
        except ValueError:
            bot.reply_to(message, "Winrate and PNL must be valid numbers.")
            return

        bot.reply_to(message, "Started scanning...")

        wallet_address = wallet_name_to_address[wallet_name]

        # Start the scanning loop for this user
        stop_flags[str(message.chat.id)] = False
        active_tasks[str(message.chat.id)] = threading.Thread(target=scan_wallet, args=(wallet_address, minimum_winrate, minimum_pnl, wallet_name, message.chat.id))
        active_tasks[str(message.chat.id)].start()

    except Exception:
        bot.reply_to(message, "Invalid command format. Use /scan {wallet_name} winrate {minimum_winrate} pnl {minimum_pnl}")

@bot.message_handler(commands=['start'])
def start_command(message):
    username = message.from_user.first_name
    bot.reply_to(
        message,
        f"""**Welcome, {username}, to our Bot!**  
Your reliable assistant for Wallet Detection.

💼 **What We Offer:**  
- Target custom PnL wallets  
- Target custom win-rate wallets  
- Target minimum trades  

🔍 **How to Use Commands:**  
Use `/scan {{wallet_name}} winrate {{minimum_winrate}} pnl {{minimum_pnl}}` to get started.

💼 **Available Wallets to Scan:**  
- trojan  
- bonk  
- photon  
- bullx  

🛡️ **Your privacy and security are our top priorities.**  

Thank you for choosing our Bot, {username}!
        """,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['stop'])
def stop_command(message):
    if str(message.chat.id) in active_tasks:
        # Set the stop flag to True to stop the scan gracefully
        stop_flags[str(message.chat.id)] = True
        active_tasks[str(message.chat.id)].join()
        del active_tasks[str(message.chat.id)]
        bot.reply_to(message, "Stopped checking.")
    else:
        bot.reply_to(message, "No active scan found for your chat.")

@bot.message_handler(commands=['replace_admin_list'])
def handle_replace_admin_list(message):
    bot.reply_to(message, "Send me a TXT file to replace")

# Handle file uploads
@bot.message_handler(content_types=['document'])
def handle_document(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_name = message.document.file_name

        if file_name.endswith(".txt"):
            with open("admin_uid.txt", "wb") as file:
                file.write(downloaded_file)
            bot.reply_to(message, "Admin list has been successfully replaced!")
        else:
            bot.reply_to(message, "Please send a valid TXT file.")
    except Exception as e:
        bot.reply_to(message, "An error occurred while processing the file.")

@bot.message_handler(commands=['config'])
def handle_config(message):
    user_id = message.from_user.id
    if not is_user_registered(user_id):
        bot.reply_to(message, "You are not registered")
        return

    command_data = message.text.split(maxsplit=1)
    if len(command_data) < 2:
        bot.reply_to(message, "Please provide data to replace in config.txt")
        return

    data = command_data[1]
    try:
        with open("config.txt", "w") as file:
            file.write(data)
        bot.reply_to(message, "Config data has been successfully updated!")
    except Exception:
        bot.reply_to(message, "An error occurred while updating the config file.")



bot.polling()
