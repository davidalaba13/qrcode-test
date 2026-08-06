import httpx
import random
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.error import BadRequest, Forbidden

BOT_TOKEN = "8722702041:AAGb-qbUeunORGIk6Tsla3ajx9H7Vwqmv80"

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

# Escrow addresses mapped by network
ESCROW_ADDRESSES = {
    "TRC-20": "TD4WyBPqkSfSi4M1vZyvZ8ZquELbRdXRst",
    "BEP-20": "0x0198Cb1c13AF5988c937eF1ffe7fa376E6Ca465E"
}

# In-memory dictionaries to store active trades and users
TRADES = {}
USER_DATABASE = {}  # Maps username -> chat_id
USER_DATABASE_FILE = "users.json"


def load_user_database():
    """Učitava korisnike iz JSON fajla pri pokretanju bota."""
    global USER_DATABASE
    if os.path.exists(USER_DATABASE_FILE):
        try:
            with open(USER_DATABASE_FILE, "r") as f:
                USER_DATABASE = json.load(f)
        except Exception as e:
            print(f"Greška pri učitavanju baze korisnika: {e}")
            USER_DATABASE = {}


def save_user_database():
    """Čuva korisnike u JSON fajl."""
    try:
        with open(USER_DATABASE_FILE, "w") as f:
            json.dump(USER_DATABASE, f)
    except Exception as e:
        print(f"Greška pri čuvanju baze korisnika: {e}")


async def check_if_user_exists(username: str) -> bool:
    """
    Proverava da li username postoji na Telegramu.
    Umesto fragment.com, proveravamo direktno t.me/username jer fragment
    sadrži samo NFT imena i blokira botove (Cloudflare).
    """
    clean_username = username.lstrip('@')
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"https://t.me/{clean_username}", timeout=5.0)

            if "tgme_page_title" in response.text:
                return True
            return False
    except Exception as e:
        print(f"Greška pri proveri username-a: {e}")
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Register the user automatically when they start the bot
    user = update.effective_user
    if user and user.username:
        USER_DATABASE[user.username.lower()] = update.effective_chat.id
        save_user_database()

    # Check if the bot was started via a deep link (e.g. trade proposal)
    if context.args and context.args[0].startswith("trade_"):
        trade_id = context.args[0][6:]
        trade = TRADES.get(trade_id)
        
        if trade:
            initiator = trade["initiator"]
            target = trade["target"]
            
            # If this is a public trade link, the person clicking it becomes the target!
            if target == "None":
                target = f"@{user.username}" if user.username else "[vaš_username]"
                trade["target"] = target
                trade["target_chat_id"] = update.effective_chat.id
                TRADES[trade_id] = trade # Save updated trade

            amount = trade["amount"]
            rsd_amount = trade["rsd_amount"]
            network = trade["network"]
            pay_amount = trade["pay_amount"]
            trade_type = trade["type"]
            
            # 1st message
            text1 = f"Korisnik {initiator} vam predlaže trgovinu:"
            await update.message.reply_text(text1)
            
            # 2nd message logic based on whether initiator is buying or selling
            title = "Kupovina" if trade_type == "buy" else "Prodaja"
            
            if trade_type == "buy":
                # Initiator is buying USDT, so target is selling (Prodavac)
                text2 = (
                    f"🔵 {title} USDT {network}\n"
                    f"👤 Prodavac: {target} (vi)\n"
                    f"👤 Kupac: {initiator} (kupuje {amount} USDT {network})\n"
                    f"💰 Dobićete: {rsd_amount:g} RSD\n"
                    f"💸 Platićete: {pay_amount} USDT {network}\n"
                    f"ℹ️ Gas fee: {SERVICE_FEE} USDT (zadržava se od USDT za pokrivanje troškova mreže)\n\n"
                    f"⏰ Ponuda važi 30 minuta"
                )
            else:
                # Initiator is selling USDT, so target is buying (Kupac)
                text2 = (
                    f"🔵 {title} USDT {network}\n"
                    f"👤 Prodavac: {initiator}\n"
                    f"👤 Kupac: {target} (vi) (kupuje {amount} USDT {network})\n"
                    f"💰 Dobićete: {amount} USDT {network}\n"
                    f"💸 Platićete: {rsd_amount:g} RSD\n"
                    f"ℹ️ Gas fee: {SERVICE_FEE} USDT (zadržava se od USDT za pokrivanje troškova mreže)\n\n"
                    f"⏰ Ponuda važi 30 minuta"
                )
            
            # Attach the Accept/Reject buttons to the message
            target_keyboard = [
                [InlineKeyboardButton("Prihvatiti trgovinu", callback_data=f"accept_trade_{trade_id}")],
                [InlineKeyboardButton("Otkazati trgovinu", callback_data=f"reject_trade_{trade_id}")],
            ]
            await update.message.reply_text(
                text2,
                reply_markup=InlineKeyboardMarkup(target_keyboard)
            )
            return

    # Default welcome flow if no deep link or trade not found
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


async def submit_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Komanda /submit_exchange prikazuje meni za prijavu uspešne razmene."""
    await show_report_successful_trade(update, context)


async def show_network_selection(query, context: ContextTypes.DEFAULT_TYPE):
    """Shows the TRC-20 / BEP-20 picker (used both from 'buy' and 'Promeniti iznos')."""
    context.user_data.pop("awaiting_amount", None)
    context.user_data.pop("awaiting_rsd_amount", None)
    context.user_data.pop("network", None)
    context.user_data.pop("amount", None)

    keyboard = [
        [InlineKeyboardButton("🔴 TRON (TRC-20)", callback_data="network_tron")],
        [InlineKeyboardButton("🟡 BSC (BEP-20)", callback_data="network_bsc")],
    ]

    await query.message.reply_text(
        "💱 Odaberite mrežu za razmenu:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def ask_amount(update_or_query, context: ContextTypes.DEFAULT_TYPE, network_label: str, network_key: str):
    """Puts the user into 'awaiting amount' state and asks for it."""
    context.user_data["awaiting_amount"] = True
    context.user_data["network"] = network_key  # "TRC-20" or "BEP-20"
    
    trade_type = context.user_data.get("trade_type", "buy")
    if trade_type == "buy":
        text = f"Koliko USDT {network_label} želite da kupite?"
    else:
        text = f"Koliko USDT {network_label} prodajete? ( koliko tačno stiže na escrow )"

    await update_or_query.message.reply_text(text)


async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: int):
    """Shows the buy/pay/receive/fee summary with Nastaviti / Promeniti iznos buttons."""
    network = context.user_data.get("network", "")
    pay_amount = amount + SERVICE_FEE
    trade_type = context.user_data.get("trade_type", "buy")

    if trade_type == "buy":
        text = (
            f"Vi kupujete: {amount} USDT\n"
            f"Prodavac šalje: {pay_amount} USDT\n"
            f"Vi dobijate: {amount} USDT\n"
            f"Servisni zbor: {SERVICE_FEE} USDT*\n\n"
            f"*plaćanje naknade mreže za transfer USDT na vašu adresu"
        )
    else:
        text = (
            f"Prodajete: {amount} USDT\n"
            f"Kupac će dobiti: {amount} USDT\n"
            f"Servisna taksa: {SERVICE_FEE} USDT*\n\n"
            f"*plaćanje naknade mreže za transfer USDT kupcu"
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


async def show_additional_options(query, context: ContextTypes.DEFAULT_TYPE):
    """Prikazuje meni sa dodatnim opcijama."""
    keyboard = [
        [InlineKeyboardButton("📝 Prijavi uspešnu razmenu", callback_data="report_successful_trade")],
        [InlineKeyboardButton("🔍 Pronađi proverenog partnera za razmenu", callback_data="find_verified_partner")],
        [InlineKeyboardButton("❓ Kako funkcioniše razmena", callback_data="how_it_works")],
        [InlineKeyboardButton("⬅️ Nazad", callback_data="back_to_main")],
    ]

    await query.message.reply_text(
        "📋 Dodatne opcije tether.rs",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_location_selection(query, context: ContextTypes.DEFAULT_TYPE):
    """Prikazuje meni za izbor lokacije pri pronalaženju partnera."""
    keyboard = [
        [InlineKeyboardButton("📍 Beograd", callback_data="location_beograd")],
        [InlineKeyboardButton("📍 Novi sad", callback_data="location_novi_sad")],
        [InlineKeyboardButton("📍 Niš", callback_data="location_nis")],
        [InlineKeyboardButton("📍 Kragujevac", callback_data="location_kragujevac")],
        [InlineKeyboardButton("💳 ONLINE - Uplata na Račun:", callback_data="location_online")],
        [InlineKeyboardButton("⬅️ Nazad", callback_data="back_to_options")],
    ]

    await query.message.reply_text(
        "Odakle ste?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_report_successful_trade(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    """Prikazuje tekst i dugmad za prijavu uspešne razmene van bota."""
    text = (
        "📋 Zahtev za prijavljivanje uspešne razmene\n\n"
        "Ako ste izvršili direktnu razmenu USDT sa drugim korisnikom van našeg bota, "
        "možete podneti zahtev da se ova transakcija uračuna u vaš rejting na sajtu.\n\n"
        "Ovo će povećati:\n"
        "✅ Broj završenih transakcija\n"
        "✅ Količinu razmenjenog USDT-a\n"
        "✅ Rejting na sajtu\n\n"
        "🔐 Autorizacija\n"
        "Da biste podneli zahtev za uračunavanje razmene u vaš rejting, potrebno je da se autorizujete putem email-a.\n\n"
        "Ako još nemate nalog na tether.rs, prvo se registrujte na sajtu."
    )

    keyboard = [
        [InlineKeyboardButton("Nastaviti", callback_data="continue_report")],
        [InlineKeyboardButton("🌐 Registrujte se na sajtu", url="https://tether.rs/")],
    ]

    await update_or_query.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True  # Sprečava pojavljivanje velikog preview-a linka ispod poruke
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(cache_time=0)

    if query.data == "buy":
        context.user_data["trade_type"] = "buy"
        await show_network_selection(query, context)

    elif query.data == "sell":
        context.user_data["trade_type"] = "sell"
        await show_network_selection(query, context)

    elif query.data == "options":
        await show_additional_options(query, context)

    elif query.data == "back_to_main":
        # Briše ceo "Dodatne opcije" meni
        await query.message.delete()

    elif query.data == "report_successful_trade":
        await show_report_successful_trade(query, context)

    elif query.data == "continue_report":
        # Bot traži email adresu od korisnika
        context.user_data["awaiting_email_for_report"] = True
        keyboard = [
            [InlineKeyboardButton("Otkaži", callback_data="cancel_email_report")]
        ]
        await query.message.reply_text(
            "📧 Unesite vaš email\n\n"
            "Navedite email adresu sa kojom ste registrovani na tether.rs",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "cancel_email_report":
        context.user_data["awaiting_email_for_report"] = False
        keyboard = [
            [InlineKeyboardButton("🟢 Kupovina USDT za RSD", callback_data="buy")],
            [InlineKeyboardButton("🔵 Prodaja USDT za RSD", callback_data="sell")],
            [InlineKeyboardButton("📋 Dodatne opcije", callback_data="options")],
        ]
        await query.message.reply_text(
            "Akcija otkazana",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "find_verified_partner":
        await show_location_selection(query, context)

    elif query.data == "back_to_options":
        # Vraća korisnika na "Dodatne opcije"
        await query.message.delete()
        await show_additional_options(query, context)

    elif query.data == "location_beograd":
        keyboard = [
            [InlineKeyboardButton("⬅️ Nazad", callback_data="back_to_locations")]
        ]
        await query.message.reply_text(
            "Ovo su nam provereni partneri u Beogradu: @whatnow92 @jvnklzc @Sajci @milanfirma",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "location_novi_sad":
        keyboard = [
            [InlineKeyboardButton("⬅️ Nazad", callback_data="back_to_locations")]
        ]
        await query.message.reply_text(
            "Kontaktirajte naseg partnera u Novom Sadu @JohnZony",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "location_nis":
        keyboard = [
            [InlineKeyboardButton("⬅️ Nazad", callback_data="back_to_locations")]
        ]
        await query.message.reply_text(
            "Kontaktirajte naseg partnera u Nisu @OtkupKriptovaluta",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "location_kragujevac":
        keyboard = [
            [InlineKeyboardButton("⬅️ Nazad", callback_data="back_to_locations")]
        ]
        await query.message.reply_text(
            "Kontaktirajte naseg partnera u Kragujevcu @acikus",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "location_online":
        keyboard = [
            [InlineKeyboardButton("⬅️ Nazad", callback_data="back_to_locations")]
        ]
        await query.message.reply_text(
            "Za uplate na račun fizičkog lica kao i za uplate na račun firme iz Srbije ili inostranstva kontaktirajte nas direktno @TetherSrb ; u poruci navedite iznos i na koji tip računa želite primiti uplatu.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "back_to_locations":
        # Briše tu poruku, a originalni meni sa gradovima ostaje jer je već poslat iznad
        await query.message.delete()

    elif query.data == "how_it_works":
        how_it_works_text = (
            "➡️ Postavljanje objave\n"
            "Svaki registrovani korisnik može postaviti objavu veoma brzo i jednostavno. Objava se može postaviti sa "
            "naslovne stranice (Tab \"Objavi ponudu/potražnju\") ili isti taj Tab na stranici Moj nalog i objave.\n"
            "Prvo birate da li kupujete ili prodajete Tether, nakon čega unosite iznos, birate Layer i proviziju. U polje Total "
            "automatski se prikazuje ukupan iznos koji nudite odnosno očekujete.\n"
            "Polje Lokacije predstavlja jedno ili više mesta gde želite da izvršite razmenu i automatski je popunjeno "
            "podatkom koji ste uneli pri registraciji, ali umesto toga možete uneti i druge lokacije koje će važiti samo za tu "
            "Vašu objavu. Te lokacije ne moraju da predstavljaju Vašu stvarnu lokaciju odnosno grad odakle ste, već "
            "predstavlja jedno ili više mesta koja Vam odgovaraju za razmenu.\n"
            "Na kraju birate vreme do kada će objava biti aktivna na sajtu (7, 14 ili 30 dana). Ukoliko do isteka odabranog "
            "vremena ne produžite trajanje objave, ona će biti automatski obrisana.\n\n"
            "➡️ Izmena i brisanje objave\n"
            "Uvek možete promeniti sve vezano za Vašu objavu: Iznos, Layer, proviziju, lokacije ili produžiti vreme trajanja. "
            "To radite na stranici Moj nalog i objave, u Tab-u MOJE OBJAVE, klikom na ikonu zelene olovčice u koloni "
            "AKCIJE.\n"
            "Ukoliko objava nije više aktuelna, možete je obrisati klikom na trash ikonu u istoj koloni.\n\n"
            "➡️ Kontakt između članova\n"
            "Ukoliko ste zainteresovani za neku objavu, iniciraćete prepisku sa članom koji je postavio objavu klikom na "
            "dugme PORUKA iz tabele na naslovnoj stranici. Unesite poruku i izaberite da li će biti prikazan Vaš nickname ili "
            "ne i nakon slanja bićete automatski preusmereni na stranicu Prepiske.\n"
            "Na toj stranici će biti prikazane sve Vaše prepiske. Član koji je postavio objavu biće mailom obavešten da ima "
            "novu poruku, a Vi ćete moći da vidite da li je poruka pročitana u vidu plave dvostuke check ikone u donjem "
            "desnom uglu Vaše poruke. Takođe, i Vi ćete biti mailom obavešteni kada dobijete odgovor.\n"
            "Daljom prepiskom dogovorite sve detalje razmene: mesto, vreme i sve ostalo po potrebi. Taj deo je prepušten "
            "na volju Vama i Vašem sagovorniku.\n\n"
            "➡️ Razmena\n"
            "Prodavac Tethera kupcu prebacuje dogovorenu svotu, a kupac isplaćuje prodavca u dogovrenoj valuti na ruke "
            "ili na neki drugi unapred dogovoren način."
        )
        keyboard = [
            [InlineKeyboardButton("⬅️ Nazad", callback_data="back_to_options")]
        ]
        await query.message.reply_text(
            how_it_works_text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

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

    # --- LOGIKA ZA @username ---

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
        await query.message.delete()
        await show_ad_creation_menu(query, context)

    elif query.data == "ad_public_link":
        target_user = "None"
        initiator_username = update.effective_user.username
        initiator_str = f"@{initiator_username}" if initiator_username else "[vaš_username]"
        
        amount = context.user_data.get("amount", 0)
        rsd_amount = context.user_data.get("rsd_amount", 0)
        network = context.user_data.get("network", "TRC-20")
        pay_amount = amount + SERVICE_FEE
        trade_type = context.user_data.get("trade_type", "buy")

        trade_id = f"D{random.randint(10000, 99999)}"
        context.user_data["trade_id"] = trade_id

        TRADES[trade_id] = {
            "initiator": initiator_str,
            "initiator_chat_id": update.effective_chat.id,
            "target": target_user,
            "target_chat_id": None,
            "amount": amount,
            "rsd_amount": rsd_amount,
            "network": network,
            "pay_amount": pay_amount,
            "type": trade_type
        }

        text1 = (
            "✅ Trgovina je kreirana!\n\n"
            "Podelite ovaj link sa kupcem (važi 30 minuta):\n"
            f"<code>https://t.me/tether_srb_bot?start=trade_{trade_id}</code>\n\n"
            "Bilo koji korisnik može da klikne na link i prihvati vašu ponudu. Dobićete obaveštenje čim se neko odazove."
        )
        await query.message.reply_text(text1, parse_mode="HTML")

        if trade_type == "buy":
            text2 = (
                f"🔵 Trgovina USDT ⇄ RSD\n"
                f"👤 Prodavac: None\n"
                f"👤 Kupac: {initiator_str}\n"
                f"🔢 Broj trgovine: #{trade_id}\n\n"
                f"💰 Prodaje se: {pay_amount} USDT → {amount} USDT ({network})(nakon provizije)\n"
                f"💸 Cena: {rsd_amount:g} RSD"
            )
        else:
            text2 = (
                f"🔵 Trgovina USDT ⇄ RSD\n"
                f"👤 Prodavac: {initiator_str}\n"
                f"👤 Kupac: None\n"
                f"🔢 Broj trgovine: #{trade_id}\n\n"
                f"💰 Prodaje se: {pay_amount} USDT → {amount} USDT ({network})(nakon provizije)\n"
                f"💸 Cena: {rsd_amount:g} RSD"
            )

        keyboard = [
            [InlineKeyboardButton("Otkazati trgovinu", callback_data=f"initiator_cancel_{trade_id}")]
        ]
        await query.message.reply_text(
            text2,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "create_trade":
        target_user = context.user_data.get("target_username", "@username")
        confirm_text = (
            "Da li želite da kreirate trgovinu?\n\n"
            f"Korisnik {target_user} će dobiti obaveštenje i imaće 30 minuta da prihvati ponudu.\n\n"
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
        await query.message.delete()

    elif query.data == "cancel_trade_entirely":
        target_user = context.user_data.get("target_username", "@username")
        trade_id = context.user_data.get("trade_id", "D20705")
        text = (
            f"❌ Odbijanje trgovine #{trade_id}\n\n"
            f"Navedite razlog odbijanja ponude od {target_user}\n\n"
            "ℹ️ Prodavac će videti izabrani razlog."
        )
        keyboard = [
            [InlineKeyboardButton("🔴 Više nije aktuelno", callback_data="reject_reason_1")],
            [InlineKeyboardButton("💸 Ne odgovaraju uslovi", callback_data="reject_reason_2")],
            [InlineKeyboardButton("⏰ Ne odgovara vreme", callback_data="reject_reason_3")],
            [InlineKeyboardButton("🔒 Nedovoljno poverenja", callback_data="reject_reason_4")],
            [InlineKeyboardButton("❓ Drugi razlog", callback_data="reject_reason_5")],
        ]
        await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data in ["reject_reason_1", "reject_reason_2", "reject_reason_3", "reject_reason_4", "reject_reason_5"]:
        context.user_data.pop("amount", None)
        context.user_data.pop("rsd_amount", None)
        context.user_data.pop("target_username", None)
        context.user_data.pop("network", None)
        context.user_data.pop("trade_id", None)
        
        keyboard = [
            [InlineKeyboardButton("🟢 Kupovina USDT za RSD", callback_data="buy")],
            [InlineKeyboardButton("🔵 Prodaja USDT za RSD", callback_data="sell")],
            [InlineKeyboardButton("📋 Dodatne opcije", callback_data="options")],
        ]
        await query.message.reply_text(
            "Akcija otkazana",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # --- LOGIKA ZA PRIHVATANJE I ODBIJANJE TRGOVINE OD STRANE KLIJENTA ---
    
    elif query.data.startswith("accept_trade_"):
        trade_id = query.data.split("_")[-1]
        trade = TRADES.get(trade_id)
        if not trade:
            await query.message.reply_text("Greška: Trgovina nije pronađena ili je istekla.")
            return

        initiator = trade["initiator"]
        target = trade["target"]
        amount = trade["amount"]
        rsd_amount = trade["rsd_amount"]
        network = trade["network"]
        pay_amount = trade["pay_amount"]
        trade_type = trade["type"]
        title = "Kupovina" if trade_type == "buy" else "Prodaja"

        # 1. Send message to Client B (who just accepted)
        client_msg = f"Sačekajte potvrdu početka transakcije od {initiator}"
        await query.message.reply_text(client_msg)
        
        # 2. Send message to User A (Initiator) for final confirmation
        initiator_chat_id = trade.get("initiator_chat_id")
        if initiator_chat_id:
            if trade_type == "buy":
                seller_str = target
                buyer_str = f"{initiator} (vi)"
                gets_str = f"{amount} USDT {network}"
                pays_str = f"{rsd_amount:g} RSD"
                deposit_msg = f"• Prodavac dobija 60 minuta da unese {pay_amount} USDT na escrow račun\n"
                transfer_msg = f"• Zatim imate 120 minuta da prenesete {rsd_amount:g} RSD prodavcu\n"
                final_msg = f"• Nakon potvrde prijema RSD - poslaće vam se {amount} USDT\n"
            else:
                seller_str = f"{initiator} (vi)"
                buyer_str = target
                gets_str = f"{rsd_amount:g} RSD"
                pays_str = f"{amount} USDT {network}"
                deposit_msg = f"• Vi dobijate 60 minuta da unesete {pay_amount} USDT na escrow račun\n"
                transfer_msg = f"• Zatim kupac ima 120 minuta da vam prenese {rsd_amount:g} RSD\n"
                final_msg = f"• Nakon potvrde prijema RSD - poslaćete {amount} USDT kupcu\n"

            initiator_msg = (
                "⚠️ Potvrdite prihvatanje trgovine\n\n"
                "Da li stvarno želite da prihvatite ovu ponudu?\n\n"
                "Detalji trgovine:\n"
                f"🔵 {title} USDT {network}\n"
                f"👤 Prodavac: {seller_str}\n"
                f"👤 Kupac: {buyer_str}\n"
                f"💰 Dobićete: {gets_str}\n"
                f"💸 Platićete: {pays_str}\n\n"
                f"ℹ️ Gas fee: {SERVICE_FEE} USDT\n"
                "(zadržava se od prodavca)\n"
                f"🔢 Broj trgovine: #{trade_id}\n\n"
                "⏰ Nakon potvrde:\n"
                f"{deposit_msg}"
                f"{transfer_msg}"
                f"{final_msg}"
                "• Na svakoj etapi možete kontaktirati administratora\n\n"
                "❗ Pažnja: Nakon potvrde, trgovina može biti otkazana samo uz obostrani dogovor.\n\n"
                "Potvrditi i započeti trgovinu?"
            )
            keyboard = [
                [InlineKeyboardButton("✅ Da, prihvatam trgovinu", callback_data=f"start_trade_{trade_id}")],
                [InlineKeyboardButton("❌ Ne, otkaži", callback_data=f"initiator_cancel_accept_{trade_id}")],
            ]
            try:
                await context.bot.send_message(
                    chat_id=initiator_chat_id,
                    text=initiator_msg,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                print(f"Greška pri slanju poruke inicijatoru: {e}")

    elif query.data.startswith("start_trade_"):
        trade_id = query.data.split("_")[-1]
        trade = TRADES.get(trade_id)
        if not trade:
            await query.message.reply_text("Greška: Trgovina nije pronađena ili je istekla.")
            return

        initiator = trade["initiator"]
        target = trade["target"]
        amount = trade["amount"]
        rsd_amount = trade["rsd_amount"]
        network = trade["network"]
        pay_amount = trade["pay_amount"]
        trade_type = trade["type"]
        escrow_addr = ESCROW_ADDRESSES.get(network, "")

        if trade_type == "buy":
            # Initiator is buyer, Target is seller
            # Initiator gets waiting message
            initiator_msg = (
                "✅ Trgovina započeta!\n\n"
                "Detalji trgovine:\n"
                f"🔵 Kupovina USDT {network}\n"
                f"👤 Prodavac: {target}\n"
                f"👤 Kupac: {initiator} (vi)\n"
                f"💰 Dobićete: {amount} USDT {network}\n"
                f"💸 Platićete: {rsd_amount:g} RSD\n"
                f"🔢 Broj trgovine: #{trade_id}\n\n"
                "⏰ Trenutni status:\n"
                f"Čekamo da prodavac unese {pay_amount} USDT {network} na escrow račun\n\n"
                "Prodavac ima 60 minuta za prenos.\n\n"
                "Nakon potvrde dobićete njegove bankovne podatke za plaćanje.\n\n"
                "🔔 Obavestićemo vas o sledećem koraku"
            )
            await query.message.reply_text(
                initiator_msg,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🆘 Podrška", callback_data="support")]])
            )

            # Target gets escrow message
            target_chat_id = trade.get("target_chat_id")
            if target_chat_id:
                target_msg = (
                    f"✅ Trgovina #{trade_id} prihvaćena!\n\n"
                    "Detalji trgovine:\n"
                    f"🔵 Prodaja USDT {network}\n"
                    f"👤 Prodavac: {target} (vi)\n"
                    f"👤 Kupac: {initiator}\n"
                    f"💰 Za prenos: {pay_amount} USDT {network}\n"
                    f"({amount} + {SERVICE_FEE} provizija)\n"
                    f"💸 Dobićete: {rsd_amount:g} RSD\n\n"
                    "⏰ Sledeći korak:\n"
                    f"Unesite {pay_amount} USDT {network} na escrow račun u roku od 60 minuta\n\n"
                    "Adresa escrow računa:\n"
                    f"<code>{escrow_addr}</code>\n\n"
                    "Nakon potvrde transakcije kupac će dobiti vaše bankovne podatke."
                )
                target_keyboard = [
                    [InlineKeyboardButton("✅ Potvrditi otpremu", callback_data=f"confirm_send_{trade_id}")],
                    [InlineKeyboardButton("🆘 Podrška", callback_data="support")],
                    [InlineKeyboardButton("❌ Ne, otkaži", callback_data=f"reject_trade_{trade_id}")]
                ]
                try:
                    await context.bot.send_message(
                        chat_id=target_chat_id,
                        text=target_msg,
                        reply_markup=InlineKeyboardMarkup(target_keyboard),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"Greška pri slanju poruke klijentu: {e}")
        else:
            # Initiator is seller, Target is buyer
            # Initiator gets escrow message
            initiator_msg = (
                f"✅ Trgovina #{trade_id} prihvaćena!\n\n"
                "Detalji trgovine:\n"
                f"🔵 Prodaja USDT {network}\n"
                f"👤 Prodavac: {initiator} (vi)\n"
                f"👤 Kupac: {target}\n"
                f"💰 Za prenos: {pay_amount} USDT {network}\n"
                f"({amount} + {SERVICE_FEE} provizija)\n"
                f"💸 Dobićete: {rsd_amount:g} RSD\n\n"
                "⏰ Sledeći korak:\n"
                f"Unesite {pay_amount} USDT {network} na escrow račun u roku od 60 minuta\n\n"
                "Adresa escrow računa:\n"
                f"<code>{escrow_addr}</code>\n\n"
                "Nakon potvrde transakcije kupac će dobiti vaše bankovne podatke."
            )
            initiator_keyboard = [
                [InlineKeyboardButton("✅ Potvrditi otpremu", callback_data=f"confirm_send_{trade_id}")],
                [InlineKeyboardButton("🆘 Podrška", callback_data="support")],
                [InlineKeyboardButton("❌ Ne, otkaži", callback_data=f"reject_trade_{trade_id}")]
            ]
            await query.message.reply_text(
                initiator_msg,
                reply_markup=InlineKeyboardMarkup(initiator_keyboard),
                parse_mode="HTML"
            )

            # Target gets waiting message
            target_chat_id = trade.get("target_chat_id")
            if target_chat_id:
                target_msg = (
                    "✅ Trgovina započeta!\n\n"
                    "Detalji trgovine:\n"
                    f"🔵 Kupovina USDT {network}\n"
                    f"👤 Prodavac: {initiator}\n"
                    f"👤 Kupac: {target} (vi)\n"
                    f"💰 Dobićete: {amount} USDT {network}\n"
                    f"💸 Platićete: {rsd_amount:g} RSD\n"
                    f"🔢 Broj trgovine: #{trade_id}\n\n"
                    "⏰ Trenutni status:\n"
                    f"Čekamo da prodavac unese {pay_amount} USDT {network} na escrow račun\n\n"
                    "Prodavac ima 60 minuta za prenos.\n\n"
                    "Nakon potvrde dobićete njegove bankovne podatke za plaćanje.\n\n"
                    "🔔 Obavestićemo vas o sledećem koraku"
                )
                try:
                    await context.bot.send_message(
                        chat_id=target_chat_id,
                        text=target_msg,
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🆘 Podrška", callback_data="support")]])
                    )
                except Exception as e:
                    print(f"Greška pri slanju poruke klijentu: {e}")

    elif query.data == "support":
        await query.message.reply_text("🆘 Za sva pitanja pišite @TetherSrb")

    elif query.data.startswith("confirm_send_"):
        trade_id = query.data.split("_")[-1]
        trade = TRADES.get(trade_id)
        if not trade:
            await query.message.reply_text("Greška: Trgovina nije pronađena ili je istekla.")
            return
            
        pay_amount = trade["pay_amount"]
        
        text = (
            "🔍 Proveravamo pristizanje sredstava\n\n"
            f"Trgovina #{trade_id}  \n"
            f"💰 Očekujemo: {pay_amount} USDT na escrow račun\n\n"
            "Proveravamo blokčein da li je stiglo. To može potrajati nekoliko minuta.\n\n"
            "✅ Čim sredstva stignu, dobićete obaveštenje i trgovina će se nastaviti"
        )
        keyboard = [
            [InlineKeyboardButton("🆘 Podrška", callback_data="support")]
        ]
        await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("initiator_cancel_accept_"):
        trade_id = query.data.split("_")[-1]
        trade = TRADES.get(trade_id)
        target = trade.get("target", "@username") if trade else "@username"
        
        if target == "None":
            text = (
                f"❌ Odbijanje trgovine #{trade_id}\n\n"
                "Navedite razlog odbijanja ponude\n\n"
                "ℹ️ Prodavac će videti izabrani razlog."
            )
        else:
            text = (
                f"❌ Odbijanje trgovine #{trade_id}\n\n"
                f"Navedite razlog odbijanja ponude od {target}\n\n"
                "ℹ️ Prodavac će videti izabrani razlog."
            )
        keyboard = [
            [InlineKeyboardButton("🔴 Više nije aktuelno", callback_data=f"initiator_reject_1_{trade_id}")],
            [InlineKeyboardButton("💸 Ne odgovaraju uslovi", callback_data=f"initiator_reject_2_{trade_id}")],
            [InlineKeyboardButton("⏰ Ne odgovara vreme", callback_data=f"initiator_reject_3_{trade_id}")],
            [InlineKeyboardButton("🔒 Nedovoljno poverenja", callback_data=f"initiator_reject_4_{trade_id}")],
            [InlineKeyboardButton("❓ Drugi razlog", callback_data=f"initiator_reject_5_{trade_id}")],
        ]
        await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("reject_trade_"):
        trade_id = query.data.split("_")[-1]
        trade = TRADES.get(trade_id)
        initiator = trade["initiator"] if trade else "@username"
        
        text = (
            f"❌ Odbijanje trgovine #{trade_id}\n\n"
            f"Navedite razlog odbijanja ponude od {initiator}\n\n"
            "ℹ️ Prodavac će videti izabrani razlog."
        )
        keyboard = [
            [InlineKeyboardButton("🔴 Više nije aktuelno", callback_data=f"client_reject_1_{trade_id}")],
            [InlineKeyboardButton("💸 Ne odgovaraju uslovi", callback_data=f"client_reject_2_{trade_id}")],
            [InlineKeyboardButton("⏰ Ne odgovara vreme", callback_data=f"client_reject_3_{trade_id}")],
            [InlineKeyboardButton("🔒 Nedovoljno poverenja", callback_data=f"client_reject_4_{trade_id}")],
            [InlineKeyboardButton("❓ Drugi razlog", callback_data=f"client_reject_5_{trade_id}")],
        ]
        await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("client_reject_"):
        parts = query.data.split("_")
        reason_num = parts[2]
        trade_id = parts[3]
        
        reasons = {
            "1": "🔴 Više nije aktuelno",
            "2": "💸 Ne odgovaraju uslovi",
            "3": "⏰ Ne odgovara vreme",
            "4": "🔒 Nedovoljno poverenja",
            "5": "❓ Drugi razlog"
        }
        reason_text = reasons.get(reason_num, "Nepoznat razlog")
        
        trade = TRADES.get(trade_id)
        if not trade:
            await query.message.reply_text("Greška: Trgovina nije pronađena ili je istekla.")
            return
            
        client_username = update.effective_user.username
        client_str = f"@{client_username}" if client_username else "[vaš_username]"
        
        # 1. Send message to client
        client_msg = f"✅ Ponuda #{trade_id} je odbačena\n\nŽelite li da kreirate svoj oglas?"
        keyboard = [
            [InlineKeyboardButton("🟢 Kupovina USDT za RSD", callback_data="buy")],
            [InlineKeyboardButton("🔵 Prodaja USDT za RSD", callback_data="sell")],
            [InlineKeyboardButton("📋 Dodatne opcije", callback_data="options")],
        ]
        await query.message.reply_text(
            client_msg,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # 2. Send message to initiator
        initiator_chat_id = trade.get("initiator_chat_id")
        if initiator_chat_id:
            initiator_msg = (
                "❌ Vaša ponuda je odbačena\n\n"
                f"Korisnik {client_str} odbio je trgovinu #{trade_id}\n"
                f"Razlog: {reason_text}\n\n"
                "Oglas više nije važeći.\n\n"
                "Želite li da napravite novu trgovinu?"
            )
            try:
                await context.bot.send_message(
                    chat_id=initiator_chat_id,
                    text=initiator_msg,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                print(f"Greška pri slanju poruke inicijatoru: {e}")

    # --- LOGIKA ZA OTKAZIVANJE TRGOVINE OD STRANE INICIJATORA (REVERSE) ---

    elif query.data.startswith("initiator_cancel_"):
        trade_id = query.data.split("_")[-1]
        trade = TRADES.get(trade_id)
        target = trade.get("target", "@username") if trade else "@username"
        
        if target == "None":
            text = (
                f"❌ Odbijanje trgovine #{trade_id}\n\n"
                "Navedite razlog odbijanja ponude\n\n"
                "ℹ️ Prodavac će videti izabrani razlog."
            )
        else:
            text = (
                f"❌ Odbijanje trgovine #{trade_id}\n\n"
                f"Navedite razlog odbijanja ponude od {target}\n\n"
                "ℹ️ Prodavac će videti izabrani razlog."
            )
        keyboard = [
            [InlineKeyboardButton("🔴 Više nije aktuelno", callback_data=f"initiator_reject_1_{trade_id}")],
            [InlineKeyboardButton("💸 Ne odgovaraju uslovi", callback_data=f"initiator_reject_2_{trade_id}")],
            [InlineKeyboardButton("⏰ Ne odgovara vreme", callback_data=f"initiator_reject_3_{trade_id}")],
            [InlineKeyboardButton("🔒 Nedovoljno poverenja", callback_data=f"initiator_reject_4_{trade_id}")],
            [InlineKeyboardButton("❓ Drugi razlog", callback_data=f"initiator_reject_5_{trade_id}")],
        ]
        await query.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("initiator_reject_"):
        parts = query.data.split("_")
        reason_num = parts[2]
        trade_id = parts[3]
        
        reasons = {
            "1": "🔴 Više nije aktuelno",
            "2": "💸 Ne odgovaraju uslovi",
            "3": "⏰ Ne odgovara vreme",
            "4": "🔒 Nedovoljno poverenja",
            "5": "❓ Drugi razlog"
        }
        reason_text = reasons.get(reason_num, "Nepoznat razlog")
        
        trade = TRADES.get(trade_id)
        if not trade:
            await query.message.reply_text("Greška: Trgovina nije pronađena ili je istekla.")
            return
            
        initiator_username = update.effective_user.username
        initiator_str = f"@{initiator_username}" if initiator_username else "[vaš_username]"
        
        # 1. Send message to initiator (who is canceling)
        initiator_msg = f"✅ Ponuda #{trade_id} je odbačena\n\nŽelite li da kreirate svoj oglas?"
        keyboard = [
            [InlineKeyboardButton("🟢 Kupovina USDT za RSD", callback_data="buy")],
            [InlineKeyboardButton("🔵 Prodaja USDT za RSD", callback_data="sell")],
            [InlineKeyboardButton("📋 Dodatne opcije", callback_data="options")],
        ]
        await query.message.reply_text(
            initiator_msg,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # 2. Send message to client (target user) if it's not a public trade
        target_chat_id = trade.get("target_chat_id")
        if target_chat_id:
            target_msg = (
                "❌ Vaša ponuda je odbačena\n\n"
                f"Korisnik {initiator_str} odbio je trgovinu #{trade_id}\n"
                f"Razlog: {reason_text}\n\n"
                "Oglas više nije važeći.\n\n"
                "Želite li da napravite novu trgovinu?"
            )
            try:
                await context.bot.send_message(
                    chat_id=target_chat_id,
                    text=target_msg,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                print(f"Greška pri slanju poruke klijentu: {e}")

    elif query.data == "execute_trade":
        target_user = context.user_data.get("target_username", "@username")
        initiator_username = update.effective_user.username
        initiator_str = f"@{initiator_username}" if initiator_username else "[vaš_username]"
        
        amount = context.user_data.get("amount", 0)
        rsd_amount = context.user_data.get("rsd_amount", 0)
        network = context.user_data.get("network", "TRC-20")
        pay_amount = amount + SERVICE_FEE
        trade_type = context.user_data.get("trade_type", "buy")

        # Generate a random 5-digit trade ID
        trade_id = f"D{random.randint(10000, 99999)}"
        context.user_data["trade_id"] = trade_id
        
        # Fetch target's chat ID if they exist in DB
        target_username_clean = target_user.lstrip('@').lower()
        target_chat_id = USER_DATABASE.get(target_username_clean)

        # Save trade details so the target user can retrieve them via deep link
        TRADES[trade_id] = {
            "initiator": initiator_str,
            "initiator_chat_id": update.effective_chat.id,
            "target": target_user,
            "target_chat_id": target_chat_id,
            "amount": amount,
            "rsd_amount": rsd_amount,
            "network": network,
            "pay_amount": pay_amount,
            "type": trade_type
        }

        # 1st text to initiator
        text1 = (
            "✅ Trgovina je kreirana!\n\n"
            f"Korisnik {target_user} je dobio obaveštenje o vašoj ponudi. Ima 30 minuta da donese odluku. "
            "Dobićete obaveštenje čim se odazove na ponudu.\n\n"
            "Takođe možete da mu pošaljete ovu vezu (važi 30 minuta):\n"
            f"<code>https://t.me/tether_srb_bot?start=trade_{trade_id}</code>"
        )
        await query.message.reply_text(text1, parse_mode="HTML")

        # 2nd text to initiator
        if trade_type == "buy":
            text2 = (
                f"🔵 Trgovina USDT ⇄ RSD\n"
                f"👤 Prodavac: {target_user}\n"
                f"👤 Kupac: {initiator_str}\n"
                f"🔢 Broj trgovine: #{trade_id}\n\n"
                f"💰 Prodaje se: {pay_amount} USDT → {amount} USDT ({network})(nakon provizije)\n"
                f"💸 Cena: {rsd_amount:g} RSD"
            )
        else:
            text2 = (
                f"🔵 Trgovina USDT ⇄ RSD\n"
                f"👤 Prodavac: {initiator_str}\n"
                f"👤 Kupac: {target_user}\n"
                f"🔢 Broj trgovine: #{trade_id}\n\n"
                f"💰 Prodaje se: {pay_amount} USDT → {amount} USDT ({network})(nakon provizije)\n"
                f"💸 Cena: {rsd_amount:g} RSD"
            )

        keyboard = [
            [InlineKeyboardButton("Otkazati trgovinu", callback_data=f"initiator_cancel_{trade_id}")]
        ]
        await query.message.reply_text(
            text2,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        # --- AUTOMATSKO SLANJE PORUKE KLIJENTU (TARGET USER) ---
        if target_chat_id:
            try:
                # Send 1st message to target
                target_text1 = f"Korisnik {initiator_str} vam predlaže trgovinu:"
                await context.bot.send_message(chat_id=target_chat_id, text=target_text1)

                # Send 2nd message to target
                if trade_type == "buy":
                    target_text2 = (
                        f"🔵 Kupovina USDT {network}\n"
                        f"👤 Prodavac: {target_user} (vi)\n"
                        f"👤 Kupac: {initiator_str} (kupuje {amount} USDT {network})\n"
                        f"💰 Dobićete: {rsd_amount:g} RSD\n"
                        f"💸 Platićete: {pay_amount} USDT {network}\n"
                        f"ℹ️ Gas fee: {SERVICE_FEE} USDT (zadržava se od USDT za pokrivanje troškova mreže)\n\n"
                        f"⏰ Ponuda važi 30 minuta"
                    )
                else:
                    target_text2 = (
                        f"🔵 Prodaja USDT {network}\n"
                        f"👤 Prodavac: {initiator_str}\n"
                        f"👤 Kupac: {target_user} (vi) (kupuje {amount} USDT {network})\n"
                        f"💰 Dobićete: {amount} USDT {network}\n"
                        f"💸 Platićete: {rsd_amount:g} RSD\n"
                        f"ℹ️ Gas fee: {SERVICE_FEE} USDT (zadržava se od USDT za pokrivanje troškova mreže)\n\n"
                        f"⏰ Ponuda važi 30 minuta"
                    )
                target_keyboard = [
                    [InlineKeyboardButton("Prihvatiti trgovinu", callback_data=f"accept_trade_{trade_id}")],
                    [InlineKeyboardButton("Otkazati trgovinu", callback_data=f"reject_trade_{trade_id}")],
                ]
                await context.bot.send_message(
                    chat_id=target_chat_id, 
                    text=target_text2,
                    reply_markup=InlineKeyboardMarkup(target_keyboard)
                )
            except Exception as e:
                print(f"Greška pri automatskom slanju poruke: {e}")


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches plain-text inputs (amounts, rsd amounts, usernames, emails)."""

    # 0. Unos email adrese za prijavu razmene
    if context.user_data.get("awaiting_email_for_report"):
        email = update.message.text.strip()

        # Osnovna provera da li sadrži @ i tačku
        if "@" not in email or "." not in email:
            await update.message.reply_text(
                "⚠️ Unesite validnu email adresu (npr. korisnik@example.com)."
            )
            return

        context.user_data["awaiting_email_for_report"] = False
        context.user_data["report_email"] = email

        await update.message.reply_text(
            f"✅ Hvala! Vaša email adresa ({email}) je zabeležena.\n"
            "Nastavak procesa prijave razmene — funkcionalnost u pripremi."
        )
        return

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
            text = "@" + text

        context.user_data["awaiting_target_username"] = False

        user_exists = await check_if_user_exists(text)

        if not user_exists:
            keyboard = [
                [InlineKeyboardButton("Uneti @username ponovo", callback_data="ad_username")],
                [InlineKeyboardButton("Kreirati javni link", callback_data="ad_public_link")],
            ]
            await update.message.reply_text(
                "❕ Korisnik nije pronađen u bazi, potrebno je da pokrene bota sa /start kako bi mogao dobiti notifikaciju Pokušajte da unesete @username ponovo kad drugi korisnik bude stisnuo /start",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            context.user_data["target_username"] = text

            our_username = update.effective_user.username
            our_username_str = f"@{our_username}" if our_username else "[vaš_username]"

            usdt_amount = context.user_data.get("amount", 0)
            rsd_amount = context.user_data.get("rsd_amount", 0)
            trade_type = context.user_data.get("trade_type", "buy")

            if trade_type == "buy":
                summary_text = (
                    f"⚪ Vaš oglas je spreman. Proverite detalje pre kreiranja trgovine:\n\n "
                    f"Vi ({our_username_str}) kupujete {usdt_amount} USDT za {rsd_amount:g} RSD od korisnika {text}. "
                    f"Platićete {rsd_amount:g} RSD i dobićete {usdt_amount} USDT."
                )
            else:
                summary_text = (
                    f"⚪ Vaš oglas je spreman. Proverite detalje pre kreiranja trgovine:\n\n "
                    f"Vi ({our_username_str}) prodajete {usdt_amount} USDT za {rsd_amount:g} RSD korisniku {text}. "
                    f"Dobićete {rsd_amount:g} RSD, a on dobija {usdt_amount} USDT."
                )

            keyboard = [
                [InlineKeyboardButton("Kreirati trgovinu", callback_data="create_trade")],
                [InlineKeyboardButton("Urediti trgovinu", callback_data="back_to_ad_selection")],
                [InlineKeyboardButton("Otkazati trgovinu", callback_data="cancel_trade_entirely")],
            ]

            await update.message.reply_text(
                summary_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return


def main():
    # Load users from file on startup
    load_user_database()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("submit_exchange", submit_exchange))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()
