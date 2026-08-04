import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = "lol"

SERVICE_FEE = 2  # USDT, flat fee per WELCOME_TEXT_2
USD_TO_RSD_RATE = 108.5  # informativni kurs, uredi po potrebi

WELCOME_TEXT_1 = "..."

WELCOME_TEXT_2 = """🤖 Dobro došli na tether.rs P2P Escrow System
Vaš pouzdan posrednik za bezbednu razmenu USDT za RSD preko računa 💰

Šta mogu:
• 🔒 Garantujem bezbednost razmene kroz escrow mehanizam
• 💱 Pomažem u razmeni USDT (TRC-20/BEP-20) za RSD
• ⚡ Automatizujem ceo proces od stvaranja do završetka trgovanja
• 📊 Pratim sve etape i šaljem obaveštenja

Kako ovo funkcioniše:
1. Jedan od učesnika kreira ponuda za kupovinu ili prodaju USDT
2. Prodavac šalje USDT na escrow adresu
3. USDT ostaje na escrow adresi dok kupac ne potvrdi prispeće dinara
4. Nakon potvrde prispeća RSD - USDT se šalje kupcu

Provizija: 2 USDT ( pokriva samo troškove TRON mreže )
"""


async def check_if_user_exists(username: str) -> bool:
    """
    Proverava da li username postoji na Telegramu.
    Umesto fragment.com, proveravamo direktno t.me/username jer fragment
    sadrži samo NFT imena i blokira botove (Cloudflare).
    """
    clean_username = username.lstrip('@')
    try:
        # Šaljemo GET zahtev na Telegram preview stranicu
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://t.me/{clean_username}", timeout=5.0)
            
            # Ako korisnik ne postoji, Telegram u HTML-u vraća "tgme_page_description" 
            # sa tekstom "If you have Telegram, you can contact...".
            # Ako postoji, stranica sadrži "tgme_page_title" (ime korisnika/grupe).
            if "tgme_page_title" in response.text:
                return True
            return False
    except Exception as e:
        print(f"Greška pri proveri username-a: {e}")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT_1)

    keyboard = [
        [InlineKeyboardButton("🟢 Kupovina USDT za RSD", callback_data="buy")],
        [InlineKeyboardButton("🔵 Prodaja USDT za RSD", callback_data="sell")],
        [InlineKeyboardButton("📋 Dodatne opcije", callback_data="options")],
    ]

    await update.message.reply_text(
        WELCOME_TEXT_2,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_network_selection(query, context: ContextTypes.DEFAULT_TYPE):
    """Shows the TRC-20 / BEP-20 picker (used both from 'buy' and 'Promeniti iznos')."""
    context.user_data.pop("awaiting_amount", None)
    context.user_data.pop("awaiting_rsd_amount", None)
    context.user_data.pop("network", None)
    context.user_data.pop("amount", None)

    keyboard = [
        [InlineKeyboardButton("🔴 TRON (TRC−20)", callback_data="network_tron")],
        [InlineKeyboardButton("🟡 BSC (BEP−20)", callback_data="network_bsc")],
    ]

    await query.message.reply_text(
        "💱 Odaberite mrežu za razmenu:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def ask_amount(update_or_query, context: ContextTypes.DEFAULT_TYPE, network_label: str, network_key: str):
    """Puts the user into 'awaiting amount' state and asks for it."""
    context.user_data["awaiting_amount"] = True
    context.user_data["network"] = network_key  # "TRC-20" or "BEP-20"

    await update_or_query.message.reply_text(
        f"Koliko USDT {network_label} želite da kupite?"
    )


async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
    """Shows the buy/pay/receive/fee summary with Nastaviti / Promeniti iznos buttons."""
    network = context.user_data.get("network", "")
    pay_amount = amount + SERVICE_FEE

    text = (
        f"Vi kupujete: {amount} USDT\n"
        f"Prodavac šalje: {pay_amount} USDT\n"
        f"Vi dobijate: {amount} USDT\n"
        f"Servisni zbor: {SERVICE_FEE} USDT*\n\n"
        f"*plaćanje naknade mreže za transfer USDT na vašu adresu"
    )

    context.user_data["amount"] = amount

    keyboard = [
        [InlineKeyboardButton("Nastaviti", callback_data="confirm_continue")],
        [InlineKeyboardButton("Promeniti iznos", callback_data="confirm_change_amount")],
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_rate_and_ask_rsd(query, context: ContextTypes.DEFAULT_TYPE):
    """Sends the informativni kurs message, then separately asks for the RSD amount."""
    amount = context.user_data.get("amount", 0)
    rsd_amount = amount * USD_TO_RSD_RATE

    rate_text = (
        "💱 Informativni kurs dolara prema srpskom dinaru\n"
        f"💵 1 USD = {USD_TO_RSD_RATE:g} RSD\n"
        f"💰 {amount} USD → {rsd_amount:g} RSD\n"
        "ℹ️ Prikazani kurs je orijentacioni"
    )

    await query.message.reply_text(rate_text)
    await query.message.reply_text("Upišite željeni iznos u dinarima")

    context.user_data["awaiting_rsd_amount"] = True


async def show_rsd_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, rsd_amount: float):
    """Shows 'Platićete: X RSD' with Nastaviti / Promeniti iznos buttons."""
    text = f"Platićete: {rsd_amount:g} RSD"

    keyboard = [
        [InlineKeyboardButton("Nastaviti", callback_data="rsd_confirm_continue")],
        [InlineKeyboardButton("Promeniti iznos", callback_data="rsd_confirm_change_amount")],
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_ad_creation_menu(query, context: ContextTypes.DEFAULT_TYPE):
    """Prikazuje meni za izbor načina kreiranja oglasa."""
    keyboard = [
        [InlineKeyboardButton("Za odredjeni @username", callback_data="ad_username")],
        [InlineKeyboardButton("Kreirati javni link", callback_data="ad_public_link")],
    ]

    await query.message.reply_text(
        "Kako želite da kreirate oglas?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(cache_time=0)

    if query.data == "buy":
        await show_network_selection(query, context)

    elif query.data == "sell":
        await query.message.reply_text("Prodaja USDT za RSD")

    elif query.data == "options":
        await query.message.reply_text("Dodatne opcije")

    elif query.data == "network_tron":
        await ask_amount(query, context, "TRC-20", "TRC-20")

    elif query.data == "network_bsc":
        await ask_amount(query, context, "BEP-20", "BEP-20")

    elif query.data == "confirm_change_amount":
        await show_network_selection(query, context)

    elif query.data == "confirm_continue":
        await show_rate_and_ask_rsd(query, context)

    elif query.data == "rsd_confirm_change_amount":
        context.user_data["awaiting_rsd_amount"] = True
        await query.message.reply_text("Upišite željeni iznos u dinarima")

    elif query.data == "rsd_confirm_continue":
        await show_ad_creation_menu(query, context)

    # --- LOGIKA ZA @USERNAME ---

    elif query.data == "ad_username":
        context.user_data["awaiting_target_username"] = True
        keyboard = [
            [InlineKeyboardButton("Nazad", callback_data="back_to_ad_selection")]
        ]
        await query.message.reply_text(
            "Unesite @username od drugog učesnika razmene:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "back_to_ad_selection":
        # Briše poruku iznad i vraća na glavni meni za odabir oglasa
        await query.message.delete()
        await show_ad_creation_menu(query, context)

    elif query.data == "ad_public_link":
        await query.message.reply_text("Kreiranje javnog linka... (Demo)")

    elif query.data == "create_trade":
        target_user = context.user_data.get("target_username", "@username")
        confirm_text = (
            "Da li želite da kreirate trgovinu?\n"
            f"Korisnik {target_user} će dobiti obaveštenje i imaće 30 minuta da prihvati ponudu.\n"
            "Napomena: nakon kreiranja trgovina se neće moći menjati."
        )
        keyboard = [
            [InlineKeyboardButton("Kreirati", callback_data="execute_trade")],
            [InlineKeyboardButton("Nazad", callback_data="cancel_trade_creation")],
        ]
        await query.message.reply_text(
            confirm_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "cancel_trade_creation":
        # Briše poruku o potvrdi kreiranja trgovine (ostaje prethodna poruka sa summary-om)
        await query.message.delete()

    elif query.data == "cancel_trade_entirely":
        # Logika za "Otkazati trgovinu" - briše oglas i poništava proces
        await query.message.delete()
        # Čistimo podatke da ne ostanu u memoriji
        context.user_data.pop("amount", None)
        context.user_data.pop("rsd_amount", None)
        context.user_data.pop("target_username", None)
        context.user_data.pop("network", None)
        await query.message.reply_text("❌ Trgovina je otkazana.")

    elif query.data == "execute_trade":
        # Ovde ide logika za slanje notifikacije drugom korisniku
        await query.message.reply_text("✅ Trgovina je uspešno kreirana! (Demo)")


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches plain-text inputs (amounts, rsd amounts, and usernames)."""

    # 1. Unos količine USDT
    if context.user_data.get("awaiting_amount"):
        text = update.message.text.strip()
        if not text.lstrip("-").isdigit():
            await update.message.reply_text("Unesite ceo broj!")
            return

        amount = int(text)
        if amount < 20:
            await update.message.reply_text(
                "⚠️ Minimalni iznos transakcije je 20 USDT.\n"
                "Unesite iznos od 20 USDT ili više da biste napravili ponudu."
            )
            return

        context.user_data["awaiting_amount"] = False
        await show_confirmation(update, context, amount)
        return

    # 2. Unos RSD iznosa
    if context.user_data.get("awaiting_rsd_amount"):
        text = update.message.text.strip().replace(",", ".")
        try:
            rsd_amount = float(text)
            if rsd_amount <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "⚠️ Unesite validan broj (npr. 13000) za iznos u dinarima."
            )
            return

        context.user_data["awaiting_rsd_amount"] = False
        context.user_data["rsd_amount"] = rsd_amount
        await show_rsd_confirmation(update, context, rsd_amount)
        return

    # 3. Unos @username-a
    if context.user_data.get("awaiting_target_username"):
        text = update.message.text.strip()
        if not text.startswith("@"):
            text = "@" + text  # Dodajemo @ ako korisnik zaboravi

        context.user_data["awaiting_target_username"] = False

        # Provera da li korisnik postoji na Telegramu
        user_exists = await check_if_user_exists(text)
        
        if not user_exists:
            # Korisnik ne postoji
            keyboard = [
                [InlineKeyboardButton("Uneti @username ponovo", callback_data="ad_username")],
                [InlineKeyboardButton("Kreirati javni link", callback_data="ad_public_link")],
            ]
            await update.message.reply_text(
                "❕ Korisnik nije pronađen u bazi, potrebno je da pokrene bota sa /start kako bi mogao dobiti notifikaciju Pokušajte da unesete @username ponovo kad drugi korisnik bude stisnuo /start",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            # Korisnik postoji
            context.user_data["target_username"] = text
            
            our_username = update.effective_user.username
            our_username_str = f"@{our_username}" if our_username else "[vaš_username]"
            
            usdt_amount = context.user_data.get("amount", 0)
            rsd_amount = context.user_data.get("rsd_amount", 0)
            
            summary_text = (
                f"⚪ Vaš oglas je spreman. Proverite detalje pre kreiranja trgovine: "
                f"Vi ({our_username_str}) prodajete {rsd_amount:g} RSD za {usdt_amount} USDT korisniku {text}. "
                f"Dobićete {usdt_amount} USDT TRC-20 zbog naknade mreže."
            )
            
            # 3 dugmeta: Kreirati trgovinu, Nazad, Otkazati trgovinu
            keyboard = [
                [InlineKeyboardButton("Kreirati trgovinu", callback_data="create_trade")],
                [InlineKeyboardButton("Nazad", callback_data="back_to_ad_selection")],
                [InlineKeyboardButton("Otkazati trgovinu", callback_data="cancel_trade_entirely")],
            ]
            
            await update.message.reply_text(
                summary_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
