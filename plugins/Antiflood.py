from Bad import app
from Bad.core.mongo import mongodb
from pyrogram import filters
from pyrogram.types import Message
from datetime import datetime, timedelta
from pyrogram.types import ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserAdminInvalid
from pyrogram.enums import ChatMemberStatus
from utils.permissions import adminsOnly, member_permissions
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, ChatPermissions
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, UserAdminInvalid


antiflood_collection = mongodb.antiflood_settings
DEFAULT_FLOOD_ACTION = "tmute"

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

async def check_admin_rights(client, message: Message):
    try:
        participant = await client.get_chat_member(message.chat.id, message.from_user.id)
        if participant.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return True
    except UserNotParticipant:
        pass
    await message.reply("**You are not an admin.**")
    return False


@app.on_message(filters.command("flood"))
async def get_flood_settings(client, message: Message):
    if not await check_admin_rights(client, message):
        return
    chat_id = message.chat.id
    settings = await get_chat_flood_settings(chat_id)
    await message.reply(
        f"Flood Limit: {settings['flood_limit']}\n"
        f"Flood Timer: {settings['flood_timer']} seconds\n"
        f"Flood Action: {settings['flood_action']}\n"
        f"Delete Flood Messages: {settings['delete_flood']}"
    )

@app.on_message(filters.command("setflood"))
async def set_flood_limit(client, message: Message):
    if not await check_admin_rights(client, message):
        return
    chat_id = message.chat.id
    command_args = message.command[1:]
    
    if len(command_args) == 0:
        await message.reply("Please provide a flood limit or 'off'.")
        return
    
    flood_limit = command_args[0].lower()
    
    if flood_limit in ["off", "no", "0"]:
        update_chat_flood_settings(chat_id, {"flood_limit": 0})
        await message.reply("Antiflood has been disabled.")
    else:
        try:
            flood_limit = int(flood_limit)
            update_chat_flood_settings(chat_id, {"flood_limit": flood_limit})
            await message.reply(f"Flood limit set to {flood_limit} consecutive messages.")
        except ValueError:
            await message.reply("Invalid flood limit. Please provide a valid number or 'off'.")

@app.on_message(filters.command("setfloodtimer"))
async def set_flood_timer(client, message: Message):
    if not await check_admin_rights(client, message):
        return
    chat_id = message.chat.id
    command_args = message.command[1:]
    
    if len(command_args) == 0 or command_args[0].lower() in ["off", "no"]:
        update_chat_flood_settings(chat_id, {"flood_timer": 0})
        await message.reply("Timed antiflood has been disabled.")
        return

    if len(command_args) != 2:
        await message.reply("Please provide both message count and duration in seconds.")
        return
    
    try:
        count = int(command_args[0])
        duration = int(command_args[1].replace('s', ''))
        update_chat_flood_settings(chat_id, {"flood_timer": duration, "flood_limit": count})
        await message.reply(f"Flood timer set to {count} messages in {duration} seconds.")
    except ValueError:
        await message.reply("Invalid timer settings. Please provide a valid number.")

@app.on_message(filters.command("floodmode"))
async def set_flood_mode(client, message: Message):
    if not await check_admin_rights(client, message):
        return
    chat_id = message.chat.id
    command_args = message.command[1:]
    
    if len(command_args) == 0:
        await message.reply("Please provide a valid action (ban/mute/kick/tban/tmute).")
        return
    
    action = command_args[0].lower()
    if action not in ["ban", "mute", "kick", "tban", "tmute"]:
        await message.reply("Invalid action. Choose from ban/mute/kick/tban/tmute.")
        return
    
    update_chat_flood_settings(chat_id, {"flood_action": action})
    await message.reply(f"Flood action set to {action}.")

@app.on_message(filters.command("clearflood"))
async def set_flood_clear(client, message: Message):
    if not await check_admin_rights(client, message):
        return
    chat_id = message.chat.id
    command_args = message.command[1:]
    
    if len(command_args) == 0 or command_args[0].lower() not in ["yes", "no", "on", "off"]:
        await message.reply("Please choose either 'yes' or 'no'.")
        return
    
    delete_flood = command_args[0].lower() in ["yes", "on"]
    update_chat_flood_settings(chat_id, {"delete_flood": delete_flood})
    await message.reply(f"Delete flood messages set to {delete_flood}.")

flood_count = {}

@app.on_message(filters.group, group=31)
async def flood_detector(client, message: Message):
    try:
        chat_id = message.chat.id

        user_id = message.from_user.id
        settings = await get_chat_flood_settings(chat_id)
        participant = await client.get_chat_member(message.chat.id, message.from_user.id)
        if participant.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
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
            await take_flood_action(client, message, action)

            if settings['delete_flood']:
                await message.delete()
                
    except Exception as e:
        print(f"An error occurred in flood_detector: {e}")
async def take_flood_action(client, message, action):
    user_id = message.from_user.id
    chat_id = message.chat.id
    user_first_name = message.from_user.first_name
    user_username = message.from_user.username
    
    buttons = None  
    
    if action == "ban":
        try:
            await client.ban_chat_member(chat_id, user_id)
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Unban", callback_data=f"unban:{user_id}")]]
            )
        except UserAdminInvalid:
            return 
    elif action == "mute":
        try:
            await client.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False))
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Unmute", callback_data=f"unmute:{user_id}")]]
            )
        except UserAdminInvalid:
            return 
    elif action == "kick":
        try:
            await client.kick_chat_member(chat_id, user_id)
            await client.unban_chat_member(chat_id, user_id)
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("View Profile", url=f"tg://user?id={user_id}")]]
            )
        except UserAdminInvalid:
            return 
    elif action == "tban":
        try:
            until_date = datetime.now() + timedelta(minutes=1)
            await client.ban_chat_member(chat_id, user_id, until_date=until_date)
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Unban", callback_data=f"unban:{user_id}")]]
            )
        except UserAdminInvalid:
            return 
    elif action == "tmute":
        try:
            until_date = datetime.now() + timedelta(minutes=1)
            await client.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False), until_date=until_date)
            buttons = InlineKeyboardMarkup(
                [[InlineKeyboardButton("Unmute", callback_data=f"unmute:{user_id}")]]
            )
        except UserAdminInvalid:
            return

    await message.reply(f"**User {user_first_name} was {action}ed for flooding.**", reply_markup=buttons)



@app.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    try:
        permissions = await member_permissions(chat_id, callback_query.from_user.id)
        permission = "can_restrict_members"
        if permission not in permissions:
            return await callback_query.answer(
            "ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴇɴᴏᴜɢʜ ᴘᴇʀᴍɪssɪᴏɴs ᴛᴏ ᴘᴇʀғᴏʀᴍ ᴛʜɪs ᴀᴄᴛɪᴏɴ\n"
            + f"ᴘᴇʀᴍɪssɪᴏɴ ɴᴇᴇᴅᴇᴅ: {permission}",
            show_alert=True,
        )
    except UserNotParticipant:
        await callback_query.answer("You are not a participant in this chat.", show_alert=True)
        return

    data = callback_query.data
    chat_id = callback_query.message.chat.id
    
    if data.startswith("unban:"):
        user_id = int(data.split(":")[1])
        try:
            await client.unban_chat_member(chat_id, user_id)
            await callback_query.answer("User unbanned!", show_alert=True)
            await callback_query.message.delete()
        except UserAdminInvalid:
            await callback_query.answer("Failed to unban user, maybe they are an admin.", show_alert=True)
            
    elif data.startswith("unmute:"):
        user_id = int(data.split(":")[1])
        try:
            await client.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=True))
            await callback_query.answer("User unmuted!", show_alert=True)
            await callback_query.message.delete()
        except UserAdminInvalid:
            await callback_query.answer("Failed to unmute user, maybe they are an admin.", show_alert=True)


__MODULE__ = "ᴀɴᴛɪғʟᴏᴏᴅ"
__HELP__ = """
**<u>ᴀɴᴛɪғʟᴏᴏᴅ ꜱᴇᴛᴛɪɴɢꜱ 🚫</u>**

» `/flood` - ᴄʜᴇᴄᴋ ᴄᴜʀʀᴇɴᴛ ᴀɴᴛɪғʟᴏᴏᴅ ꜱᴛᴀᴛᴜꜱ.
» `/setflood <number/off>` - ꜱᴇᴛ ᴍᴀx ᴍꜱɢ ᴀʟʟᴏᴡᴇᴅ ʙᴇꜰᴏʀᴇ ᴛʀɪɢɢᴇʀ.
» `/setfloodtimer <count> <duration>` - ᴛɪᴍᴇᴅ ᴀɴᴛɪғʟᴏᴏᴅ ꜱᴇᴛᴛɪɴɢ.
» `/floodmode <ban/mute/kick/tban/tmute>` - ᴀᴄᴛɪᴏɴ ᴏɴ ᴀɴʏ ᴠɪᴏʟᴀᴛᴏʀ.
» `/clearflood <yes/no/on/off>` - ᴅᴇʟᴇᴛᴇ ꜰʟᴏᴏᴅ ᴍᴇꜱꜱᴀɢᴇꜱ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ.

**<u>📍ᴇxᴀᴍᴘʟᴇꜱ</u>**
» `/setflood 7` - ᴀᴄᴛɪᴠᴀᴛᴇ ᴀɴᴛɪғʟᴏᴏᴅ ᴀꜰᴛᴇʀ 7 ᴍꜱɢꜱ.
» `/setflood off` - ᴅɪꜱᴀʙʟᴇ ᴀɴᴛɪғʟᴏᴏᴅ.
» `/setfloodtimer 10 30s` - 10 ᴍꜱɢꜱ ɪɴ 30s ᴛʀɪɢɢᴇʀꜱ ᴀᴄᴛɪᴏɴ.
» `/floodmode mute` - ᴍᴜᴛᴇ ᴛʜᴇ ꜱᴘᴀᴍᴍᴇʀ.
"""
