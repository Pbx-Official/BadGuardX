from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ChatPermissions
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from Bad import application  # Assuming this is your main application instance
from Bad.core.mongo import mongodb
from telegram.error import Forbidden, BadRequest

antiflood_collection = mongodb.antiflood_settings
DEFAULT_FLOOD_ACTION = "tmute"

app_instance = application  # Use the imported application instance

async def get_chat_flood_settings(chat_id):
    settings = await antiflood_collection.find_one({"chat_id": chat_id})
    if not settings:
        return {
            "flood_limit": 0,
            "flood_timer": 0,
            "flood_action": DEFAULT_FLOOD_ACTION,
            "delete_flood": False
        }
    return {
        "flood_limit": settings.get("flood_limit", 0),
        "flood_timer": settings.get("flood_timer", 0),
        "flood_action": settings.get("flood_action", DEFAULT_FLOOD_ACTION),
        "delete_flood": settings.get("delete_flood", False)
    }

def update_chat_flood_settings(chat_id, update_data):
    antiflood_collection.update_one({"chat_id": chat_id}, {"$set": update_data}, upsert=True)

async def check_admin_rights(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    chat = update.effective_chat
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ("administrator", "creator"):
            return True
    except (Forbidden, BadRequest):
        pass
    await update.message.reply_text("**You are not an admin.**")
    return False

async def get_flood_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin_rights(update, context):
        return
    chat_id = update.effective_chat.id
    settings = await get_chat_flood_settings(chat_id)
    await update.message.reply_text(
        f"Flood Limit: {settings['flood_limit']}\n"
        f"Flood Timer: {settings['flood_timer']} seconds\n"
        f"Flood Action: {settings['flood_action']}\n"
        f"Delete Flood Messages: {settings['delete_flood']}"
    )

async def set_flood_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin_rights(update, context):
        return
    chat_id = update.effective_chat.id
    command_args = context.args

    if not command_args:
        await update.message.reply_text("Please provide a flood limit or 'off'.")
        return

    flood_limit = command_args[0].lower()

    if flood_limit in ["off", "no", "0"]:
        update_chat_flood_settings(chat_id, {"flood_limit": 0})
        await update.message.reply_text("Antiflood has been disabled.")
    else:
        try:
            flood_limit = int(flood_limit)
            update_chat_flood_settings(chat_id, {"flood_limit": flood_limit})
            await update.message.reply_text(f"Flood limit set to {flood_limit} consecutive messages.")
        except ValueError:
            await update.message.reply_text("Invalid flood limit. Please provide a valid number or 'off'.")

async def set_flood_timer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin_rights(update, context):
        return
    chat_id = update.effective_chat.id
    command_args = context.args

    if not command_args or command_args[0].lower() in ["off", "no"]:
        update_chat_flood_settings(chat_id, {"flood_timer": 0})
        await update.message.reply_text("Timed antiflood has been disabled.")
        return

    if len(command_args) != 2:
        await update.message.reply_text("Please provide both message count and duration in seconds.")
        return

    try:
        count = int(command_args[0])
        duration = int(command_args[1].replace('s', ''))
        update_chat_flood_settings(chat_id, {"flood_timer": duration, "flood_limit": count})
        await update.message.reply_text(f"Flood timer set to {count} messages in {duration} seconds.")
    except ValueError:
        await update.message.reply_text("Invalid timer settings. Please provide valid numbers.")

async def set_flood_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin_rights(update, context):
        return
    chat_id = update.effective_chat.id
    command_args = context.args

    if not command_args:
        await update.message.reply_text("Please provide a valid action (ban/mute/kick/tban/tmute).")
        return

    action = command_args[0].lower()
    if action not in ["ban", "mute", "kick", "tban", "tmute"]:
        await update.message.reply_text("Invalid action. Choose from ban/mute/kick/tban/tmute.")
        return

    update_chat_flood_settings(chat_id, {"flood_action": action})
    await update.message.reply_text(f"Flood action set to {action}.")

async def set_flood_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin_rights(update, context):
        return
    chat_id = update.effective_chat.id
    command_args = context.args

    if not command_args or command_args[0].lower() not in ["yes", "no", "on", "off"]:
        await update.message.reply_text("Please choose either 'yes' or 'no'.")
        return

    delete_flood = command_args[0].lower() in ["yes", "on"]
    update_chat_flood_settings(chat_id, {"delete_flood": delete_flood})
    await update.message.reply_text(f"Delete flood messages set to {delete_flood}.")

flood_count = {}

async def flood_detector(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        message = update.message

        # Skip if not a group chat
        if update.effective_chat.type not in ("group", "supergroup"):
            return

        settings = await get_chat_flood_settings(chat_id)
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in ("administrator", "creator"):
            return

        if settings['flood_limit'] == 0:
            return

        if chat_id not in flood_count:
            flood_count[chat_id] = {}

        user_flood_data = flood_count[chat_id].get(user_id, {"count": 0, "first_message_time": datetime.now()})
        flood_timer = settings.get('flood_timer', 0)

        if (datetime.now() - user_flood_data['first_message_time']).seconds > flood_timer:
            user_flood_data = {"count": 1, "first_message_time": datetime.now()}
        else:
            user_flood_data['count'] += 1

        flood_count[chat_id][user_id] = user_flood_data

        if user_flood_data['count'] > settings['flood_limit']:
            action = settings['flood_action']
            await take_flood_action(context, message, action)

            if settings['delete_flood']:
                try:
                    await message.delete()
                except (Forbidden, BadRequest):
                    pass

    except Exception as e:
        print(f"An error occurred in flood_detector: {e}")

async def take_flood_action(context: ContextTypes.DEFAULT_TYPE, message, action):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_first_name = message.from_user.first_name

    buttons = None

    try:
        if action == "ban":
            await context.bot.ban_chat_member(chat_id, user_id)
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Unban", callback_data=f"unban:{user_id}")]]
            )
        elif action == "mute":
            await context.bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False))
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Unmute", callback_data=f"unmute:{user_id}")]]
            )
        elif action == "kick":
            await context.bot.ban_chat_member(chat_id, user_id)
            await context.bot.unban_chat_member(chat_id, user_id)
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("View Profile", url=f"tg://user?id={user_id}")]]
            )
        elif action == "tban":
            until_date = datetime.now() + timedelta(minutes=1)
            await context.bot.ban_chat_member(chat_id, user_id, until_date=until_date)
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Unban", callback_data=f"unban:{user_id}")]]
            )
        elif action == "tmute":
            until_date = datetime.now() + timedelta(minutes=1)
            await context.bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False), until_date=until_date)
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Unmute", callback_data=f"unmute:{user_id}")]]
            )

        await message.reply_text(
            f"**User {user_first_name} was {action}ed for flooding.**",
            reply_markup=buttons,
            parse_mode="Markdown"
        )

    except (Forbidden, BadRequest):
        pass

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat.id
    user_id = query.from_user.id

    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if not member.can_restrict_members:
            await query.answer(
                "You don't have enough permissions to perform this action\n"
                "Permission needed: can_restrict_members",
                show_alert=True
            )
            return
    except (Forbidden, BadRequest):
        await query.answer("You are not a participant in this chat.", show_alert=True)
        return

    data = query.data
    if data.startswith("unban:"):
        target_user_id = int(data.split(":")[1])
        try:
            await context.bot.unban_chat_member(chat_id, target_user_id)
            await query.answer("User unbanned!", show_alert=True)
            await query.message.delete()
        except (Forbidden, BadRequest):
            await query.answer("Failed to unban user, maybe they are an admin.", show_alert=True)

    elif data.startswith("unmute:"):
        target_user_id = int(data.split(":")[1])
        try:
            await context.bot.restrict_chat_member(chat_id, target_user_id, permissions=ChatPermissions(can_send_messages=True))
            await query.answer("User unmuted!", show_alert=True)
            await query.message.delete()
        except (Forbidden, BadRequest):
            await query.answer("Failed to unmute user, maybe they are an admin.", show_alert=True)

def main():
    app_instance.add_handler(CommandHandler("flood", get_flood_settings))
    app_instance.add_handler(CommandHandler("setflood", set_flood_limit))
    app_instance.add_handler(CommandHandler("setfloodtimer", set_flood_timer))
    app_instance.add_handler(CommandHandler("floodmode", set_flood_mode))
    app_instance.add_handler(CommandHandler("clearflood", set_flood_clear))
    app_instance.add_handler(MessageHandler(filters.ChatType.GROUPS, flood_detector))
    app_instance.add_handler(CallbackQueryHandler(callback_handler))

if __name__ == "__main__":
    main()

__MODULE__ = "Antiflood"
__HELP__ = """**Antiflood**

Admin commands:
- /flood: Get the current antiflood settings
- /setflood <number/off/no>: Set the number of consecutive messages to trigger antiflood. Set to '0', 'off', or 'no' to disable.
- /setfloodtimer <count> <duration>: Set the number of messages and time required for timed antiflood to take action on a user. Set to just 'off' or 'no' to disable.
- /floodmode <action type>: Choose which action to take on a user who has been flooding. Possible actions: ban/mute/kick/tban/tmute
- /clearflood <yes/no/on/off>: Whether to delete the messages that triggered the flood.

Examples:
- Set antiflood to trigger after 7 messages:
-> /setflood 7

- Disable antiflood:
-> /setflood off

- Set timed antiflood to trigger after 10 messages in 30 seconds:
-> /setfloodtimer 10 30s

- Disable timed antiflood:
-> /setfloodtimer off

- Set the antiflood action to mute:
-> /floodmode mute
"""
