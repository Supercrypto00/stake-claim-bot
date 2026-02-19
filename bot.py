import os
import asyncio
import sqlite3
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")  # ton token Telegram
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # ton ID Telegram

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)

# ================= DATABASE =================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS claims (
    user_id INTEGER PRIMARY KEY,
    stake_username TEXT,
    network TEXT,
    wallet TEXT,
    status TEXT
)
""")
conn.commit()

# ================= STATES =================
ASK_USERNAME, ASK_NETWORK, ASK_WALLET = range(3)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    cursor.execute("SELECT * FROM claims WHERE user_id=?", (user_id,))
    exists = cursor.fetchone()
    if exists:
        await update.message.reply_text("⚠️ Tu as déjà une demande en cours.")
        return ConversationHandler.END

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Réclamer mes 20€", callback_data="claim")]
    ])

    await update.message.reply_text(
        "🎁 Bienvenue ! Clique ci-dessous pour commencer la réclamation.",
        reply_markup=keyboard
    )

# ================= BUTTON CALLBACK =================
async def claim_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📝 Envoie ton pseudo Stake :")
    return ASK_USERNAME

# ================= ASK USERNAME =================
async def ask_network(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["stake_username"] = update.message.text

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Solana", callback_data="SOL"),
            InlineKeyboardButton("ETH", callback_data="ETH"),
            InlineKeyboardButton("BTC", callback_data="BTC"),
        ]
    ])
    await update.message.reply_text(
        "💳 Choisis le réseau de ton wallet :",
        reply_markup=keyboard
    )
    return ASK_NETWORK

# ================= ASK NETWORK =================
async def ask_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["network"] = query.data
    await query.message.reply_text(
        f"📩 Envoie ton adresse {context.user_data['network']} :",
        reply_markup=None
    )
    return ASK_WALLET

# ================= SAVE CLAIM =================
async def save_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    wallet = update.message.text
    data = context.user_data

    cursor.execute(
        "INSERT INTO claims VALUES (?, ?, ?, ?, ?)",
        (
            user_id,
            data["stake_username"],
            data["network"],
            wallet,
            "pending"
        )
    )
    conn.commit()

    msg = await update.message.reply_text("🔍 Vérification du wallet...")

    steps = [
        "🔍 Recherche du wallet...",
        "🧠 Analyse...",
        "📡 Vérification...",
        "✅ Wallet valide."
    ]
    for step in steps:
        await asyncio.sleep(1.2)
        await msg.edit_text(step)

    await update.message.reply_text(
        "✅ **Votre demande a bien été envoyée.**\n\n"
        "💸 Vos fonds seront envoyés sous **24 heures** si aucun problème n’a été détecté.\n\n"
        "⚠️ Problèmes possibles :\n"
        "• Double compte\n"
        "• Wager insuffisant\n"
        "• Wallet invalide\n"
        "• Activité suspecte"
    )

    # Notif admin
    await context.bot.send_message(
        ADMIN_ID,
        f"🆕 Nouvelle demande :\n"
        f"👤 User: {data['stake_username']}\n"
        f"🌐 Network: {data['network']}\n"
        f"💳 Wallet: {wallet}"
    )

    return ConversationHandler.END

# ================= ADMIN PANEL =================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    cursor.execute("SELECT COUNT(*) FROM claims")
    total = cursor.fetchone()[0]
    await update.message.reply_text(f"📊 Total demandes : {total}")

# ================= CANCEL =================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Opération annulée.")
    return ConversationHandler.END

# ================= MAIN =================
def main():
    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(claim_button, pattern="claim")],
        states={
            ASK_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_network)],
            ASK_NETWORK: [CallbackQueryHandler(ask_wallet)],
            ASK_WALLET: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_claim)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(conv_handler)

    app.run_polling()

if __name__ == "__main__":
    main()
