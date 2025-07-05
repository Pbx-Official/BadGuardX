from html import escape
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
)

from config import OWNER_ID
from Bad import application
from Bad.logging import LOGGERR

from Bad.database.blacklist_db import Blacklist
from Bad.database.kbhelpersdb import ikb
from Bad.database.permissionsdb import adminsOnly

app_instance = application  # as per your request

# Utility: Check if user is admin with can_restrict_members
async def has_permission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
    return chat_member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]

# Show all blacklisted words
async def view_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update, context):
        return
    db = Blacklist(update.effective_chat.id)
    blacklisted = db.get_blacklists()
    if not blacklisted:
        await update.message.reply_html(f"No blacklisted words in <b>{update.effective_chat.title}</b>.")
        return
    words = "\n".join(f" • <code>{escape(w)}</code>" for w in blacklisted)
    await update.message.reply_html(f"Blacklisted words in <b>{update.effective_chat.title}</b>:\n\n{words}")

# Add blacklist words
async def add_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update, context):
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /addblacklist <word1> <word2> ...")
        return
    db = Blacklist(update.effective_chat.id)
    new_words = [w.lower() for w in context.args]
    existing = db.get_blacklists()
    added = [w for w in new_words if w not in existing]
    skipped = [w for w in new_words if w in existing]
    for word in added:
        db.add_blacklist(word)
    msg = ""
    if added:
        msg += f"✅ Added: {', '.join(f'<code>{w}</code>' for w in added)}"
    if skipped:
        msg += f"\n⚠️ Already exists: {', '.join(f'<code>{w}</code>' for w in skipped)}"
    LOGGERR.info(f"{update.effective_user.id} added blacklists: {added}")
    await update.message.reply_html(msg)

# Remove blacklist words
async def rm_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update, context):
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /rmblacklist <word1> <word2> ...")
        return
    db = Blacklist(update.effective_chat.id)
    remove_words = [w.lower() for w in context.args]
    existing = db.get_blacklists()
    removed = [w for w in remove_words if w in existing]
    not_found = [w for w in remove_words if w not in existing]
    for word in removed:
        db.remove_blacklist(word)
    msg = ""
    if removed:
        msg += f"❌ Removed: {', '.join(f'<code>{w}</code>' for w in removed)}"
    if not_found:
        msg += f"\n⚠️ Not found: {', '.join(f'<code>{w}</code>' for w in not_found)}"
    LOGGERR.info(f"{update.effective_user.id} removed blacklists: {removed}")
    await update.message.reply_html(msg)

# Set or get blacklist action
async def set_blacklist_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update, context):
        return
    db = Blacklist(update.effective_chat.id)
    valid = ("ban", "kick", "mute", "warn", "none")
    if context.args:
        action = context.args[0].lower()
        if action not in valid:
            await update.message.reply_html(
                f"Invalid action!\nChoose from: {', '.join(f'<code>{v}</code>' for v in valid)}"
            )
            return
        db.set_action(action)
        LOGGERR.info(f"{update.effective_user.id} set blacklist action to {action}")
        await update.message.reply_html(f"✅ Action set to: <b>{action}</b>")
    else:
        current = db.get_action()
        await update.message.reply_html(
            f"The current blacklist action is: <b>{current}</b>\nAll blacklist actions auto-delete the message."
        )

# Set or get blacklist reason
async def blacklist_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await has_permission(update, context):
        return
    db = Blacklist(update.effective_chat.id)
    if not context.args:
        reason = db.get_reason()
        await update.message.reply_html(f"Current reason: <code>{reason}</code>")
        return
    reason = " ".join(context.args)
    db.set_reason(reason)
    await update.message.reply_html(f"Updated blacklist reason:\n<code>{reason}</code>")

# Owner-only: Confirm remove all blacklists
async def confirm_clear_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in OWNER_ID:
        return
    db = Blacklist(update.effective_chat.id)
    if not db.get_blacklists():
        await update.message.reply_text("No blacklisted words to remove.")
        return
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data="rm_allblacklist"),
            InlineKeyboardButton("❌ Cancel", callback_data="close_admin"),
        ]
    ]
    await update.message.reply_text(
        "⚠️ Are you sure you want to remove all blacklists?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Callback: Confirm delete all
async def callback_rm_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    chat = query.message.chat
    chat_member = await context.bot.get_chat_member(chat.id, user.id)
    if chat_member.status != ChatMember.OWNER:
        await query.answer("Only group owner can do this!", show_alert=True)
        return
    db = Blacklist(chat.id)
    db.rm_all_blacklist()
    LOGGERR.info(f"{user.id} cleared all blacklists")
    await query.message.delete()
    await query.answer("✅ All blacklists removed!", show_alert=True)

# Text filter: Check for blacklisted words and take action
async def filter_blacklisted_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or update.effective_user is None:
        return
    db = Blacklist(update.effective_chat.id)
    words = db.get_blacklists()
    action = db.get_action()
    if not words:
        return
    text = update.message.text.lower()
    pattern = r'\b(' + '|'.join(re.escape(word) for word in words) + r')\b'
    if re.search(pattern, text):
        await update.message.delete()
        user_id = update.effective_user.id
        if action == "ban":
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
        elif action == "kick":
            await context.bot.ban_chat_member(update.effective_chat.id, user_id)
            await context.bot.unban_chat_member(update.effective_chat.id, user_id)
        elif action == "mute":
            await context.bot.restrict_chat_member(update.effective_chat.id, user_id, permissions={"can_send_messages": False})
        elif action == "warn":
            reason = db.get_reason()
            await update.effective_chat.send_message(
                f"⚠️ Warning!\nBlacklisted word used.\nReason: {reason}",
                reply_to_message_id=update.message.message_id
            )

# Register handlers
app_instance.add_handler(CommandHandler("blacklist", view_blacklist))
app_instance.add_handler(CommandHandler("addblacklist", add_blacklist))
app_instance.add_handler(CommandHandler(["rmblacklist", "unblacklist"], rm_blacklist))
app_instance.add_handler(CommandHandler(["blaction", "blacklistaction", "blacklistmode"], set_blacklist_action))
app_instance.add_handler(CommandHandler("blreason", blacklist_reason))
app_instance.add_handler(CommandHandler("rmallblacklist", confirm_clear_all))
app_instance.add_handler(CallbackQueryHandler(callback_rm_all, pattern="^rm_allblacklist$"))
app_instance.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), filter_blacklisted_text))


__MODULE__ = "ᴡʙʟᴀᴄᴋʟɪꜱᴛ"
__HELP__ = """
**<u>⚠️ ʙʟᴀᴄᴋʟɪꜱᴛ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ</u>**

» `/blacklist` - ꜱʜᴏᴡ ᴀʟʟ ʙʟᴀᴄᴋʟɪꜱᴛᴇᴅ ᴡᴏʀᴅꜱ ɪɴ ᴛʜᴇ ɢʀᴏᴜᴘ.
» `/addblacklist <word1> <word2>` - ᴀᴅᴅ ᴡᴏʀᴅꜱ ᴛᴏ ʙʟᴀᴄᴋʟɪꜱᴛ.
» `/rmblacklist <word1> <word2>` - ʀᴇᴍᴏᴠᴇ ᴡᴏʀᴅꜱ ꜰʀᴏᴍ ʙʟᴀᴄᴋʟɪꜱᴛ.
» `/blaction <action>` - ꜱᴇᴛ ᴀᴄᴛɪᴏɴ ᴏɴ ʙʟᴀᴄᴋʟɪꜱᴛᴇᴅ ᴡᴏʀᴅ:
   → `ban`, `kick`, `mute`, `warn`, `none`
» `/blreason <reason>` - ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ʀᴇᴀꜱᴏɴ ꜰᴏʀ ᴡᴀʀɴɪɴɢ.
» `/rmallblacklist` - ʀᴇᴍᴏᴠᴇ ᴀʟʟ ʙʟᴀᴄᴋʟɪꜱᴛᴇᴅ ᴡᴏʀᴅꜱ ᴡɪᴛʜ ᴄᴏɴꜰɪʀᴍ ʙᴜᴛᴛᴏɴ (ᴏᴡɴᴇʀ ᴏɴʟʏ).

**<u>💥 Aᴄᴛɪᴏɴs ᴡʜᴇɴ ᴀ ʙʟᴀᴄᴋʟɪꜱᴛᴇᴅ ᴡᴏʀᴅ ɪꜱ ᴜꜱᴇᴅ</u>**
• `ban` - ᴜꜱᴇʀ ᴡɪʟʟ ʙᴇ ʙᴀɴɴᴇᴅ.
• `kick` - ᴜꜱᴇʀ ᴡɪʟʟ ʙᴇ ᴋɪᴄᴋᴇᴅ.
• `mute` - ᴜꜱᴇʀ ᴡɪʟʟ ʙᴇ ᴍᴜᴛᴇᴅ.
• `warn` - ᴜꜱᴇʀ ᴡɪʟʟ ʙᴇ ᴡᴀʀɴᴇᴅ ᴡɪᴛʜ ʀᴇᴀꜱᴏɴ.
• `none` - ᴏɴʟʏ ᴅᴇʟᴇᴛᴇꜱ ᴍᴇꜱꜱᴀɢᴇ.

**<u>👑 ʀᴇǫᴜɪʀᴇᴍᴇɴᴛꜱ</u>**
• ʙᴏᴛ ᴍᴜꜱᴛ ʙᴇ ᴀɴ ᴀᴅᴍɪɴ ᴡɪᴛʜ "ᴄᴀɴ_ᴅᴇʟᴇᴛᴇ", "ᴄᴀɴ_ʀᴇꜱᴛʀɪᴄᴛ" ᴘᴇʀᴍɪꜱꜱɪᴏɴꜱ.
• ᴏɴʟʏ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴀᴅᴅ/ʀᴇᴍᴏᴠᴇ ʙʟᴀᴄᴋʟɪꜱᴛꜱ.
"""
