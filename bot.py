import asyncio
import os

import dotenv
from pyrogram import Client, filters
from pyrogram.types import BotCommand, Message
from pyrogram.types.payments import input_stars_transaction

from server import run_server
from utils.connect_to_mongo import connect_to_mongo
from utils.errors import CredentialsError
from utils.get_balance_status import get_balance_status

run_server()
dotenv.load_dotenv()


API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

DB_URI = os.getenv("DB_URI")

LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
INSTRUCTIONS_MESSAGE_ID = int(os.getenv("INSTRUCTIONS_MESSAGE_ID", 2))
MASTER_ID = int(os.getenv("MASTER_ID", ""))

DETECTOR_COOLDOWN_INTERVAL = int(os.getenv("DETECTOR_COOLDOWN_INTERVAL", 10))
DEFAULT_MINIMUM_REPORT_AMOUNT = float(os.getenv("DEFAULT_MINIMUM_REPORT_AMOUNT", ".5"))

client = Client(name="BinBalBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
USERS_STATUSES = {}

db_client = connect_to_mongo(DB_URI)


async def main():
    await client.start()
    await client.send_message(MASTER_ID, "I am up!")
    await client.set_bot_commands(
        [
            BotCommand("start", "Start the bot"),
            BotCommand("balance", "Get current balance"),
            BotCommand("link", "Link your binance account"),
            BotCommand("settings", "Edit bot settings"),
        ]
    )

    @client.on_message(filters.command("start"))
    async def start_handler(client, message):
        user = message.from_user
        user_in_db = db_client.binbal.users.find_one({"_id": user.id})

        if not user_in_db:
            db_client.binbal.users.insert_one(
                {
                    "_id": user.id,
                    "api_key": None,
                    "api_secret": None,
                    "do_not_report": False,
                    "minimum_report_amount": DEFAULT_MINIMUM_REPORT_AMOUNT,
                }
            )
            return await message.reply(
                f"Hello {user.first_name}!, Welcome To Binance Balance Bot!\n"
                "With me you can:\n"
                "1. Check your binance balance without leaving telegram just with a single command!\n\n"
                "2. Get notified at anytime your recive or made a transfer!\n."
                "No need to check your binance every now and then unless you want to donate for my developer hehe.\n\n"
                "To link your binance account send /link and follow the instructions please.\n\n"
                "<b>NOTE: The bot doesn't need more than the 'Enable Reading' permission, THERE IS NOTHING CAN GO WRONG WITH YOUR FUNDS:)</b>"
            )

        if not user_in_db["api_secret"] or not user_in_db["api_secret"]:
            return await message.reply(
                f"Hey {user.first_name}!, How are you doing?\n"
                "Please /link your binance account to be able to use the bot!."
            )

        try:
            get_balance_status(user_in_db["api_key"], user_in_db["api_secret"])
        except CredentialsError:
            return await message.reply(
                f"Hey {user.first_name}!, it looks like your API credentials are no longer working :(\n"
                "please relink your account with /link to continue to be able to use the bot!"
            )
        except Exception as e:
            await log(e)

        await message.reply(
            f"Hey {user.first_name}!\n"
            "Everything seems fine! 💯, I hope you are finding me userfull :)\n"
            f"[My father](tg://user?id={MASTER_ID}) wants feedbacks about my work, please tell him I was a good boy hehe."
        )

    @client.on_message(filters.command("balance"))
    async def balance_handler(client, message):
        user_id = message.from_user.id
        user_in_db = db_client.binbal.users.find_one({"_id": user_id})

        if not user_in_db:
            return await message.reply("Please start the bot first.")

        if not user_in_db["api_key"] or not user_in_db["api_secret"]:
            return await message.reply(
                "You have to /link your binance account to be able to use this command!"
            )

        try:
            current_status = get_balance_status(
                user_in_db["api_key"], user_in_db["api_secret"]
            )
        except CredentialsError:
            return await message.reply(
                "It looks like your binance api credentials are no longer working :("
                "please re /link your accuont to continue to be able to use the bot!."
            )
        except Exception as e:
            await log(e)
            await message.reply(
                "Sorry The bot is temporaly unavailable, we will try to solve this issue as soon as possible."
            )

        report_text = "\n".join(
            [f"{key}: {value}$" for key, value in current_status.items()]
        )
        await message.reply(
            "<u><b>Your wallets current statuses</b></u>:\n\n" + report_text
        )

    @client.on_message(filters.command("link"))
    async def link_handler(client, message: Message):
        if message.chat.id != message.from_user.id:
            return await message.reply("Broo, not here in front of every one, come DM.")

        instructions_message = await client.get_messages(
            LOG_CHANNEL_ID, INSTRUCTIONS_MESSAGE_ID
        )
        await instructions_message.copy(message.from_user.id)

        while True:
            api_key_message = await message.ask(
                "Please send the <b>API Key</b> or send /cancel to cancel."
            )

            if api_key_message.text == "/cancel":
                return await message.reply("Cancelled")

            elif api_key_message.text:
                break
            else:
                await api_key_message.reply("Please Enter a Valid API Key")

        while True:
            api_secret_message = await message.ask(
                "Please send the <b>Secret Key</b> or send /cancel to cancel."
            )

            if api_key_message.text == "/cancel":
                return await message.reply("Cancelled")

            elif api_secret_message.text:
                break
            else:
                await api_key_message.reply("Please Enter a Valid Secret Key")

        try:
            get_balance_status(api_key_message.text, api_secret_message.text)
        except CredentialsError:
            await api_secret_message.reply(
                "Invalid API Key or Secret please ensure they are correct and try again."
            )
        except Exception as e:
            await log(e)

        else:
            await api_secret_message.reply(
                "Binance account linked succeuflly! ✅\n"
                "you can use /balance to check your balance.\n"
                "I will notify you when your balance change!, you can stop this by /stop_balance_change_notifications or from settings!"
            )

            db_client.binbal.users.update_one(
                {"_id": message.from_user.id},
                {
                    "$set": {
                        "api_key": api_key_message.text,
                        "api_secret": api_secret_message.text,
                        "do_not_report": False,
                    }
                },
            )

    @client.on_message(filters.private & filters.command("settings"))
    async def settings_handler(client, message):
        user = message.from_user
        user_in_db = db_client.binbal.users.find_one({"_id": user.id})

        if not user_in_db:
            await message.reply("Please Start the bot first")

        current_settings = (
            "<u><b>Bot Settings</b></u>:\n\n"
            + "Balance Change Notifications: "
            + ("On ✅\n" if not user_in_db["do_not_report"] else "Off ❌\n")
            + (
                "/stop_balance_change_notifications"
                if not user_in_db["do_not_report"]
                else "/turn_on_balance_change_notifications"
            )
            + (
                f"\n\nMinimum Balance Change to notify: {user_in_db['minimum_report_amount']}$\n /set_minimum_change_notifications"
                if not user_in_db["do_not_report"]
                else ""
            )
        )
        await message.reply(current_settings)

    @client.on_message(
        filters.private & filters.command("stop_balance_change_notifications")
    )
    async def stop_notif_handler(client, message):
        db_client.binbal.users.update_one(
            {"_id": message.from_user.id}, {"$set": {"do_not_report": True}}
        )
        await message.reply(
            "You will not be notified for your account balance changes."
        )

    @client.on_message(
        filters.private & filters.command("turn_on_balance_change_notifications")
    )
    async def turn_on_notif_handler(client, message):
        user_in_db = db_client.binbal.users.find_one({"_id": message.from_user.id})
        if not user_in_db:
            await message.reply("Please Start the bot first")

        if not user_in_db["api_key"] or not user_in_db["api_secret"]:
            db_client.binbal.users.update_one(
                {"_id": message.from_user.id}, {"$set": {"do_not_report": False}}
            )
            await message.reply(
                "You will recive notifications about your balance changes, but only after you /link your binance account :)"
            )

        try:
            current_status = get_balance_status(
                user_in_db["api_key"], user_in_db["api_secret"]
            )
        except CredentialsError:
            await message.reply(
                "It looks like your binance credentials are no longer valid, please re /link your binance account to be able to continue to use the bot"
            )
        except Exception as e:
            await log(e)

        else:
            USERS_STATUSES[user_in_db["_id"]] = current_status
            db_client.binbal.users.update_one(
                {"_id": message.from_user.id}, {"$set": {"do_not_report": False}}
            )
            await message.reply(
                "You will be notified for your account balance changes."
            )

    @client.on_message(
        filters.private & filters.command("set_minimum_change_notifications")
    )
    async def set_minimum_change_notification_handler(client, message):
        while True:
            new_min_message = await message.ask(
                "What is the new minimum balance change to notify you about?\n"
                "(Setting a low limit may cause unnecessary notifications)\n\n"
                "You can send integers or decimals like 1 or .5\n"
                "to cancel send /cancel"
            )
            if new_min_message.text == "/cancel":
                return await message.reply("Cancelled")
            try:
                float(new_min_message.text)
            except ValueError:
                await message.reply(
                    "Please send a valid integer or decimal number (e.g 1 or .5) or /cancel"
                )
                continue
            else:
                db_client.binbal.users.update_one(
                    {"_id": message.from_user.id},
                    {"$set": {"minimum_report_amount": float(new_min_message.text)}},
                )
                await message.reply(
                    f"You will be notified whith changes in your balance at of at least {new_min_message.text}$"
                )
                return await settings_handler(client, new_min_message)

    async def changes_detecter(client):
        while True:
            await asyncio.sleep(DETECTOR_COOLDOWN_INTERVAL)
            users = db_client.binbal.users.find({})

            for user in users:
                if (
                    not user["api_key"]
                    or not user["api_secret"]
                    or user["do_not_report"]
                ):
                    continue

                try:
                    user_current_state = get_balance_status(
                        user["api_key"], user["api_secret"]
                    )
                except CredentialsError as e:
                    await client.send_message(
                        user["_id"],
                        "Hey!, It looks like your binance API credentials stop working :(\n"
                        "Fix them by relinking your account (/link) to be able to use the bot or recive notifications!",
                    )
                    db_client.binbal.users.update_one(
                        {"_id": user["_id"]}, {"$set": {"do_not_report": True}}
                    )
                    continue
                except Exception as e:
                    await log(e)

                if user["_id"] not in USERS_STATUSES:
                    USERS_STATUSES[user["_id"]] = user_current_state
                    continue

                user_last_state = USERS_STATUSES[user["_id"]]
                user_diffs = {
                    "_id": user["_id"],
                    "new_wallet_added": [],
                    "old_wallet_removed": [],
                    "wallet_changed": [],
                }

                for wallet in user_current_state:
                    if wallet not in user_last_state:
                        user_diffs["new_wallet_added"].append(
                            {"wallet": wallet, "balance": user_current_state[wallet]}
                        )

                    elif (
                        abs(user_current_state[wallet] - user_last_state[wallet])
                        >= user["minimum_report_amount"]
                    ):
                        user_diffs["wallet_changed"].append(
                            {
                                "wallet": wallet,
                                "was": user_last_state[wallet],
                                "now": user_current_state[wallet],
                            }
                        )

                for wallet in user_last_state:
                    if wallet not in user_current_state:
                        user_diffs["old_wallet_removed"].append(
                            {"wallet": wallet, "balance": user_last_state[wallet]}
                        )

                to_report = (
                    user_diffs["new_wallet_added"]
                    or user_diffs["old_wallet_removed"]
                    or user_diffs["wallet_changed"]
                )

                if to_report:
                    await send_report(client, user_diffs)
                    USERS_STATUSES[user["_id"]] = user_current_state

    async def send_report(client, user_diffs):
        report_text = "<u><b>Changes In your account Balance</b></u>:\n\n"

        if user_diffs["new_wallet_added"]:
            report_text += "<u><b>New Wallets Added:</b></u>\n\n"
            for wallet in user_diffs["new_wallet_added"]:
                report_text += (
                    f"Wallet: {wallet['wallet']}\n" f"Balance: {wallet['balance']}$\n\n"
                )

        if user_diffs["old_wallet_removed"]:
            report_text += "\n<u><b>Old Wallets Removed:</b></u>\n\n"
            for wallet in user_diffs["old_wallet_removed"]:
                report_text += (
                    f"Wallet: {wallet['wallet']}\n" f"Balance: {wallet['balance']}$\n\n"
                )

        if user_diffs["wallet_changed"]:
            report_text += "\n<u><b>Wallets Balance Changed:</b></u>\n\n"
            for change in user_diffs["wallet_changed"]:
                report_text += (
                    f"Wallet: {change['wallet']}\n"
                    f"Balance: {'+' if change['now']>change['was'] else ''}{round(change['now']-change['was'], 2)}$\n\n"
                )
        await client.send_message(user_diffs["_id"], report_text)

    asyncio.create_task(changes_detecter(client))

    async def log(text):
        await client.send_message(LOG_CHANNEL_ID, text)

    print("Bot is running.")
    while True:
        await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
