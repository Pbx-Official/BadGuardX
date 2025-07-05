from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from Bad import application  # Assuming this is your main application instance
from config import OWNER_ID as owner_id, START_IMG_URL, SUPPORT_CHAT

app_instance = application  # Use the imported application instance

def content(update: Update) -> str | None:
    message = update.message
    if message.text is None:
        return None
    parts = message.text.split(None, 1)
    return parts[1] if len(parts) > 1 else None

async def bug(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    chat = message.chat
    user = message.from_user

    # Format chat username or ID
    chat_username = f"@{chat.username}/`{chat.id}`" if chat.username else f"Private Group/`{chat.id}`"

    bugs = content(update)
    user_id = user.id
    mention = f"[{user.first_name}](tg://user?id={user.id})"
    datetimes = datetime.utcnow().strftime("%d-%m-%Y")

    bug_report = f"""
**#BUG : ** **tg://user?id={owner_id}**

**REPORTED BY : ** **{mention}**
**USER ID : ** **{user_id}**
**CHAT : ** **{chat_username}**

**BUG : ** **{bugs}**

**EVENT STAMP : ** **{datetimes}**"""

    # Check if the command is used in a private chat
    if chat.type == "private":
        await message.reply_text("<b>» This command is only for groups.</b>")
        return

    # Check if the user is the owner
    if user_id == owner_id:
        if bugs:
            await message.reply_text(
                "<b>» Are you comedy me 🤣, you're the owner of the bot.</b>"
            )
        else:
            await message.reply_text("Chumtiya owner!")
        return

    # Handle bug reporting for non-owners
    if bugs:
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("• Close •", callback_data="close_reply")]]
        )
        await message.reply_text(
            f"<b>Bug Report: {bugs}</b>\n\n"
            "<b>» Bug successfully reported at support chat!</b>",
            reply_markup=reply_markup
        )
        
        # Send bug report to support chat
        await context.bot.send_photo(
            chat_id=SUPPORT_CHAT,
            photo=START_IMG_URL,
            caption=bug_report,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("• View Bug •", url=message.link)],
                    [InlineKeyboardButton("• Close •", callback_data="close_send_photo")]
                ]
            )
        )
    else:
        await message.reply_text("<b>» No bug to report!</b>")

async def close_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.message.delete()
    await query.answer()

async def close_send_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    chat = query.message.chat

    # Check if user has permission to delete messages
    chat_member = await context.bot.get_chat_member(chat.id, user.id)
    if not chat_member.can_delete_messages:
        await query.answer("You don't have rights to close this.", show_alert=True)
        return

    await query.message.delete()
    await query.answer()

def main():
    # Add handlers to the application
    app_instance.add_handler(CommandHandler("bug", bug))
    app_instance.add_handler(CallbackQueryHandler(close_reply, pattern="close_reply"))
    app_instance.add_handler(CallbackQueryHandler(close_send_photo, pattern="close_send_photo"))

if __name__ == "__main__":
    main()
