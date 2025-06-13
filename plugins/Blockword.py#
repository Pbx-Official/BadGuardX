from html import escape

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus as CMS
from pyrogram.types import CallbackQuery, Message

from config import OWNER_ID
from Bad.logging import LOGGERR
from Bad import app
from Bad.database.decoratorsdb import AdminRightsCheck
from Bad.database.permissionsdb import adminsOnly

from Bad.database.blacklist_db import Blacklist
from Bad.database.kbhelpersdb import ikb


@app.on_message(filters.command(["blacklist"]))
@adminsOnly("can_restrict_members")
async def view_blacklist(_, m: Message):
    db = Blacklist(m.chat.id)

    LOGGERR.info(f"{m.from_user.id} checking blacklists in {m.chat.id}")

    chat_title = m.chat.title
    blacklists_chat = f"Current Blacklisted words in <b>{chat_title}</b>:\n\n"
    all_blacklisted = db.get_blacklists()

    if not all_blacklisted:
        await m.reply_text(
            text=f"There are no blacklisted messages in <b>{chat_title}</b>!"
        )
        return

    blacklists_chat += "\n".join(
        f" • <code>{escape(i)}</code>" for i in all_blacklisted
    )

    await m.reply_text(blacklists_chat)
    return


@app.on_message(filters.command(["addblacklist"]))
@adminsOnly("can_restrict_members")
async def add_blacklist(_, m: Message):
    db = Blacklist(m.chat.id)

    if len(m.text.split()) < 2:
        await m.reply_text(text="Please check help on how to use this this command.")
        return

    bl_words = ((m.text.split(None, 1)[1]).lower()).split()
    all_blacklisted = db.get_blacklists()
    already_added_words, rep_text = [], ""

    for bl_word in bl_words:
        if bl_word in all_blacklisted:
            already_added_words.append(bl_word)
            continue
        db.add_blacklist(bl_word)

    if already_added_words:
        rep_text = (
            ", ".join([f"<code>{i}</code>" for i in bl_words])
            + " already added in blacklist, skipped them!"
        )
    LOGGERR.info(f"{m.from_user.id} added new blacklists ({bl_words}) in {m.chat.id}")
    trigger = ", ".join(f"<code>{i}</code>" for i in bl_words)
    await m.reply_text(
        text=f"Added <code>{trigger}</code> in blacklist words!"
        + (f"\n{rep_text}" if rep_text else ""),
    )

    await m.stop_propagation()


@app.on_message(filters.command(["blreason"]))
@adminsOnly("can_restrict_members")
async def blacklistreason(_, m: Message):
    db = Blacklist(m.chat.id)

    if len(m.text.split()) == 1:
        curr = db.get_reason()
        await m.reply_text(
            f"The current reason for blacklists warn is:\n<code>{curr}</code>",
        )
    else:
        reason = m.text.split(None, 1)[1]
        db.set_reason(reason)
        await m.reply_text(
            f"Updated reason for blacklists warn is:\n<code>{reason}</code>",
        )
    return


@app.on_message(filters.command(["rmblacklist", "unblacklist"]))
@adminsOnly("can_restrict_members")
async def rm_blacklist(_, m: Message):
    db = Blacklist(m.chat.id)

    if len(m.text.split()) < 2:
        await m.reply_text(text="Please check help on how to use this this command.")
        return

    chat_bl = db.get_blacklists()
    non_found_words, rep_text = [], ""
    bl_words = ((m.text.split(None, 1)[1]).lower()).split()

    for bl_word in bl_words:
        if bl_word not in chat_bl:
            non_found_words.append(bl_word)
            continue
        db.remove_blacklist(bl_word)

    if non_found_words == bl_words:
        return await m.reply_text("Blacklists not found!")

    if non_found_words:
        rep_text = (
            "Could not find " + ", ".join(f"<code>{i}</code>" for i in non_found_words)
        ) + " in blacklisted words, skipped them."

    LOGGERR.info(f"{m.from_user.id} removed blacklists ({bl_words}) in {m.chat.id}")
    bl_words = ", ".join(f"<code>{i}</code>" for i in bl_words)
    await m.reply_text(
        text=f"Removed <b>{bl_words}</b> from blacklist words!"
        + (f"\n{rep_text}" if rep_text else ""),
    )

    await m.stop_propagation()


@app.on_message(filters.command(["blaction", "blacklistaction", "blacklistmode"]))
@adminsOnly("can_restrict_members")
async def set_bl_action(_, m: Message):
    db = Blacklist(m.chat.id)

    if len(m.text.split()) == 2:
        action = m.text.split(None, 1)[1]
        valid_actions = ("ban", "kick", "mute", "warn", "none")
        if action not in valid_actions:
            await m.reply_text(
                (
                    "Choose a valid blacklist action from "
                    + ", ".join(f"<code>{i}</code>" for i in valid_actions)
                ),
            )

            return
        db.set_action(action)
        LOGGERR.info(
            f"{m.from_user.id} set blacklist action to '{action}' in {m.chat.id}",
        )
        await m.reply_text(text=f"Set action for blacklist for this to <b>{action}</b>")
    elif len(m.text.split()) == 1:
        action = db.get_action()
        LOGGERR.info(f"{m.from_user.id} checking blacklist action in {m.chat.id}")
        await m.reply_text(
            text=f"""The current action for blacklists in this chat is <i><b>{action}</b></i>
      All blacklist modes delete the message containing blacklist word."""
        )
    else:
        await m.reply_text(text="Please check help on how to use this this command.")

    return


@app.on_message(filters.command(["rmallblacklist"]) & OWNER_ID)
async def rm_allblacklist(_, m: Message):
    db = Blacklist(m.chat.id)

    all_bls = db.get_blacklists()
    if not all_bls:
        await m.reply_text("No notes are blacklists in this chat")
        return

    await m.reply_text(
        "Are you sure you want to clear all blacklists?",
        reply_markup=ikb(
            [[("⚠️ Confirm", "rm_allblacklist"), ("❌ Cancel", "close_admin")]],
        ),
    )
    return


@app.on_callback_query(filters.regex("^rm_allblacklist$"))
async def rm_allbl_callback(_, q: CallbackQuery):
    user_id = q.from_user.id
    db = Blacklist(q.message.chat.id)
    user_status = (await q.message.chat.get_member(user_id)).status
    if user_status not in {CMS.ADMINISTRATOR, CMS.OWNER}:
        await q.answer(
            "You're not even an admin, don't try this explosive shit!",
            show_alert=True,
        )
        return
    if user_status != CMS.OWNER:
        await q.answer(
            "You're just an admin, not owner\nStay in your limits!",
            show_alert=True,
        )
        return
    db.rm_all_blacklist()
    await q.message.delete()
    LOGGERR.info(f"{user_id} removed all blacklists in {q.message.chat.id}")
    await q.answer("Cleared all Blacklists!", show_alert=True)
    return


@app.on_message(filters.text)
async def check_blacklisted_words(_, m: Message):
    db = Blacklist(m.chat.id)
    blacklisted_words = db.get_blacklists()
    action = db.get_action()

    if not blacklisted_words:
        return

    for word in blacklisted_words:
        if word in m.text.lower():
            if action == "none":
                return

            await m.delete()

            if action == "ban":
                await app.kick_chat_member(m.chat.id, m.from_user.id)
            elif action == "kick":
                await app.kick_chat_member(m.chat.id, m.from_user.id)
                await app.unban_chat_member(m.chat.id, m.from_user.id)
            elif action == "mute":
                await app.restrict_chat_member(m.chat.id, m.from_user.id, permissions=False)
            elif action == "warn":
                reason = db.get_reason()
                await m.reply_text(f"Warning! You used a blacklisted word. Reason: {reason}")

            return
