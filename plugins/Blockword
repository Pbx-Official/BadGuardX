from html import escape
import re  # <-- Import regex module

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus as CMS
from pyrogram.types import CallbackQuery, Message

from config import OWNER_ID
from Bad import app
from Bad.logging import LOGGERR

from Bad.database.blacklist_db import Blacklist
from Bad.database.kbhelpersdb import ikb
from Bad.database.permissionsdb import adminsOnly


# Show all blacklisted words
@app.on_message(filters.command("blacklist"))
@adminsOnly("can_restrict_members")
async def view_blacklist(_, m: Message):
    db = Blacklist(m.chat.id)
    blacklisted = db.get_blacklists()

    if not blacklisted:
        return await m.reply_text(f"No blacklisted words in <b>{m.chat.title}</b>.")

    words = "\n".join(f" • <code>{escape(w)}</code>" for w in blacklisted)
    await m.reply_text(f"Blacklisted words in <b>{m.chat.title}</b>:\n\n{words}")


# Add blacklist words
@app.on_message(filters.command("addblacklist"))
@adminsOnly("can_restrict_members")
async def add_blacklist(_, m: Message):
    db = Blacklist(m.chat.id)
    if len(m.text.split()) < 2:
        return await m.reply_text("Usage: /addblacklist <word1> <word2> ...")

    new_words = m.text.split(None, 1)[1].lower().split()
    existing = db.get_blacklists()

    added = [w for w in new_words if w not in existing]
    skipped = [w for w in new_words if w in existing]

    for word in added:
        db.add_blacklist(word)

    msg = f"✅ Added: {', '.join(f'<code>{w}</code>' for w in added)}"
    if skipped:
        msg += f"\n⚠️ Already exists: {', '.join(f'<code>{w}</code>' for w in skipped)}"

    LOGGERR.info(f"{m.from_user.id} added blacklists: {added}")
    await m.reply_text(msg)
    await m.stop_propagation()


# Remove blacklist words
@app.on_message(filters.command(["rmblacklist", "unblacklist"]))
@adminsOnly("can_restrict_members")
async def rm_blacklist(_, m: Message):
    db = Blacklist(m.chat.id)
    if len(m.text.split()) < 2:
        return await m.reply_text("Usage: /rmblacklist <word1> <word2> ...")

    remove_words = m.text.split(None, 1)[1].lower().split()
    existing = db.get_blacklists()

    removed = [w for w in remove_words if w in existing]
    not_found = [w for w in remove_words if w not in existing]

    for word in removed:
        db.remove_blacklist(word)

    msg = f"❌ Removed: {', '.join(f'<code>{w}</code>' for w in removed)}"
    if not_found:
        msg += f"\n⚠️ Not found: {', '.join(f'<code>{w}</code>' for w in not_found)}"

    LOGGERR.info(f"{m.from_user.id} removed blacklists: {removed}")
    await m.reply_text(msg)
    await m.stop_propagation()


# Set or get blacklist action
@app.on_message(filters.command(["blaction", "blacklistaction", "blacklistmode"]))
@adminsOnly("can_restrict_members")
async def set_blacklist_action(_, m: Message):
    db = Blacklist(m.chat.id)
    args = m.text.split()

    valid = ("ban", "kick", "mute", "warn", "none")

    if len(args) == 2:
        action = args[1].lower()
        if action not in valid:
            return await m.reply_text(
                f"Invalid action!\nChoose from: {', '.join(f'<code>{v}</code>' for v in valid)}"
            )
        db.set_action(action)
        LOGGERR.info(f"{m.from_user.id} set blacklist action to {action}")
        return await m.reply_text(f"✅ Action set to: <b>{action}</b>")

    current = db.get_action()
    await m.reply_text(
        f"The current blacklist action is: <b>{current}</b>\n"
        "All blacklist actions auto-delete the message."
    )


# Set or get blacklist reason
@app.on_message(filters.command("blreason"))
@adminsOnly("can_restrict_members")
async def blacklist_reason(_, m: Message):
    db = Blacklist(m.chat.id)
    args = m.text.split(None, 1)

    if len(args) == 1:
        reason = db.get_reason()
        return await m.reply_text(f"Current reason: <code>{reason}</code>")

    reason = args[1]
    db.set_reason(reason)
    await m.reply_text(f"Updated blacklist reason:\n<code>{reason}</code>")


# Owner-only: Confirm remove all blacklists
@app.on_message(filters.command("rmallblacklist") & OWNER_ID)
async def confirm_clear_all(_, m: Message):
    db = Blacklist(m.chat.id)
    if not db.get_blacklists():
        return await m.reply_text("No blacklisted words to remove.")

    await m.reply_text(
        "⚠️ Are you sure you want to remove all blacklists?",
        reply_markup=ikb([[("✅ Confirm", "rm_allblacklist"), ("❌ Cancel", "close_admin")]])
    )


# Callback: Confirm delete all
@app.on_callback_query(filters.regex("^rm_allblacklist$"))
async def callback_rm_all(_, q: CallbackQuery):
    user = q.from_user
    status = (await q.message.chat.get_member(user.id)).status

    if status != CMS.OWNER:
        return await q.answer("Only group owner can do this!", show_alert=True)

    db = Blacklist(q.message.chat.id)
    db.rm_all_blacklist()
    LOGGERR.info(f"{user.id} cleared all blacklists")
    await q.message.delete()
    await q.answer("✅ All blacklists removed!", show_alert=True)


# Text filter: Check for blacklisted words and take action
@app.on_message(filters.text)
async def filter_blacklisted_text(_, m: Message):
    db = Blacklist(m.chat.id)
    words = db.get_blacklists()
    action = db.get_action()

    if not words or m.from_user is None:
        return

    text = m.text.lower()
    # Join all words as regex pattern for word boundary match
    pattern = r'\b(' + '|'.join(re.escape(word) for word in words) + r')\b'
    if re.search(pattern, text):
        await m.delete()
        user = m.from_user.id

        if action == "ban":
            await app.kick_chat_member(m.chat.id, user)
        elif action == "kick":
            await app.kick_chat_member(m.chat.id, user)
            await app.unban_chat_member(m.chat.id, user)
        elif action == "mute":
            await app.restrict_chat_member(m.chat.id, user, permissions=False)
        elif action == "warn":
            reason = db.get_reason()
            await m.reply_text(f"⚠️ Warning!\nBlacklisted word used.\nReason: {reason}")

        return
