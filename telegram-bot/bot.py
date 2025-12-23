import json
import os
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# ⚙️ აქ ჩასვი შენი BotFather-ის TOKEN
# BOT_TOKEN = "8375308624:AAHy3qHw4Au0F1HpHODx4mufhJ3M_jTe5CQ"  # ← აქ ჩასვი შენი ნამდვილი ტოკენი
BOT_TOKEN = os.environ["BOT_TOKEN"]
# ⚙️ აქ ჩასვი შენი პირადი Telegram user ID (admin)
ADMIN_ID = 8201387380  # შეცვალე შენზე

# დახურული ჯგუფის ლინკი (invite link)
GROUP_LINK = "https://t.me/+rCNHBtic_rJhYmIy" 
# GROUP_LINK = "https://t.me/+by5kgyP5JPAwYmEy"  # ← აქ ჩაწერე შენი რეალური ჯგუფის ლინკი

# გამომწერთა სიის ფაილი
SUBSCRIBERS_FILE = "subscribers.json"

# სუბსქრიფშენების ფაილი
SUBSCRIPTIONS_FILE = "subscriptions.json"

# გადასახადის პარამეტრები
BASE_PRICE = 11      # ძირითადი ღირებულება (მაგ. 10 ლარი თვეში)
TAX_RATE = 0       # 18% VAT


# ==================== Utility: გამომწერები ====================

def load_subscribers():
    """ჩატვირთავს subscribers.json ფაილს და საჭირო হলে დაანორმალებს სტრუქტურას."""
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []

    with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []

    # ნორმალიზაცია: თუ ძველი ფორმატია (უბრალო int-ები), გადავიყვანოთ dict-ებად
    normalized = []
    changed = False

    for item in data:
        if isinstance(item, int):
            normalized.append({
                "id": item,
                "username": None,
                "first_name": None,
                "last_name": None,
            })
            changed = True
        elif isinstance(item, dict):
            if "id" in item:
                normalized.append(item)
            else:
                changed = True
        else:
            changed = True

    if changed:
        save_subscribers(normalized)

    return normalized


def save_subscribers(subscribers):
    """შეინახავს subscribers.json ფაილში."""
    with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
        json.dump(subscribers, f, ensure_ascii=False, indent=2)


def calc_price_with_tax(base_price: float, tax_rate: float) -> float:
    """გადახდის სრული თანხის დათვლა (ფასი + გადასახადი)."""
    return base_price * (1 + tax_rate)


# ==================== Utility: სუბსქრიფშენები ====================

def load_subscriptions():
    """ჩატვირთავს subscriptions.json-ს (user_id → paid_until)."""
    if not os.path.exists(SUBSCRIPTIONS_FILE):
        return {}
    with open(SUBSCRIPTIONS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_subscriptions(data):
    """შეინახავს subscriptions.json-ში."""
    with open(SUBSCRIPTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def set_subscription(chat_id: int, days: int = 30):
    """
    ადმინი რომ დაადასტურებს გადახდას, ამ ფუნქციას ვიყენებთ.
    chat_id-ს ვანიჭებთ days დღით აქტიურ გამოწერას.
    """
    subs = load_subscriptions()
    now = datetime.utcnow()
    paid_until = now + timedelta(days=days)

    subs[str(chat_id)] = {
        "paid_until": paid_until.isoformat()
    }

    save_subscriptions(subs)


def has_active_subscription(chat_id: int) -> bool:
    """
    ამოწმებს, აქვს თუ არა მომხმარებელს აქტიური სუბსქრიფშენი (ვადა არ გაუვლია).
    """
    subs = load_subscriptions()
    info = subs.get(str(chat_id))
    if not info:
        return False
    try:
        paid_until = datetime.fromisoformat(info["paid_until"])
    except Exception:
        return False

    return datetime.utcnow() < paid_until


def get_subscription_info(chat_id: int) -> str:
    """
    აბრუნებს ტექსტურ ინფოს, როდემდე აქვს აქტიური სუბსქრიფშენი.
    """
    subs = load_subscriptions()
    info = subs.get(str(chat_id))
    if not info:
        return "შენ აქტიური Shen Space გამოწერა არ გაქვს."

    try:
        paid_until = datetime.fromisoformat(info["paid_until"])
    except Exception:
        return "აქტიური სუბსქრიფშენის მონაცემი დაზიანებულია. დაუკავშირდი ადმინს."

    if datetime.utcnow() >= paid_until:
        return "შენი Shen Space გამოწერის ვადა დასრულებულია."

    return f"შენი Shen Space გამოწერა აქტიურია აქამდე: {paid_until.strftime('%Y-%m-%d %H:%M UTC')} 🌙"


# ==================== Command handler-ები ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    subscribers = load_subscribers()
    exists = any(sub.get("id") == chat.id for sub in subscribers)

    if not exists:
        subscribers.append({
            "id": chat.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
        })
        save_subscribers(subscribers)
text = (
    "გამარჯობა 🌟\n\n"
    "თუ გაინტერესებს ასტროლოგია, ტარო, ალქიმია, ტრანზიტების ანალიზი — ეს მხოლოდ მცირე ჩამონათვალია. "
    "ჩვენს დახურულ არხზე შენ გელოდება ცოდნა, რომელიც საჯაროდ არ ზიარდება. "
    "ექსკლუზიური ვიდეოები და ყოველდღიური პროგნოზები, რომლებიც შენს რეალობას შეცვლის.\n\n"
    "გამოიყენე /subscribe\n"
    "ფასის გასაგებად გამოიყენე /price.\n"
)
    else:
        text = (
            "კიდევ ერთხელ მოგესალმები! ✨\n"
            "შენ უკვე გამოწერილი გაქვს პრემიუმ სივრცე.\n"
            "ფასის გასაგებად გამოიყენე /price,\n"
            "გასაუქმებლად /unsubscribe.\n"
        )

    await context.bot.send_message(chat_id=chat.id, text=text)


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    subscribers = load_subscribers()

    existing = None
    for sub in subscribers:
        if sub.get("id") == chat.id:
            existing = sub
            break

    if existing is None:
        subscribers.append({
            "id": chat.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
        })
        save_subscribers(subscribers)
        text = "შენ წარმატებით გამოიწერე Shen Space განახლებები ✅"
    else:
        existing["username"] = user.username
        existing["first_name"] = user.first_name
        existing["last_name"] = user.last_name
        save_subscribers(subscribers)
        text = " თუ გსურს გქონდეს წვდომა პრემიუმ კონტენტზე, აუცილებელია გამოგვიგზავნო ქვითარი სადაც ჩანს რომ შესრულდა გადახდა. გთხოვთ გადახდის დანიშნულებაში მიუთითოთ თქვენი - telegram Username\n"

    await context.bot.send_message(chat_id=chat.id, text=text)

    total = calc_price_with_tax(BASE_PRICE, TAX_RATE)
    tax_amount = total - BASE_PRICE

    price_text = (
        "💳 *Shen Space - თვიური გამოწერა*\n\n"
        f"საბაზო ფასი: {BASE_PRICE:.2f} ₾\n"
        # f"გადასახადი ({int(TAX_RATE * 100)}%): {tax_amount:.2f} ₾\n"
        # f"საბოლოო თანხა: *{total:.2f} ₾*\n\n"
        "ამ თანხით მიიღებ 1 თვიან წვდომას Shen Space-ის დახურულ სივრცესთან 🌙\n"
        "აირჩიე გადახდის მეთოდი:"
    )

    keyboard = [
        [
            InlineKeyboardButton("🏦 ბანკის გადარიცხვა", callback_data="pay_bank"),
        ],
        [
            InlineKeyboardButton("⏳ მოგვიანებით გადავიხდი", callback_data="pay_later"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat.id,
        text=price_text,
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subscribers = load_subscribers()

    new_list = [sub for sub in subscribers if sub.get("id") != chat_id]

    if len(new_list) < len(subscribers):
        save_subscribers(new_list)
        text = "Shen Space-ის გამოწერა წარმატებით გაუქმდა ❌"
    else:
        text = "შენი chat ID გამოწერილთა სიაში არ იყო."

    await context.bot.send_message(chat_id=chat_id, text=text)


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total = calc_price_with_tax(BASE_PRICE, TAX_RATE)
    tax_amount = total - BASE_PRICE

    text = (
        "💳 *Shen Space გამოწერის ფასი*\n\n"
        f"საბაზო ფასი: {BASE_PRICE:.2f} ₾\n"
        # f"გადასახადი ({int(TAX_RATE * 100)}%): {tax_amount:.2f} ₾\n"
        # f"საბოლოო თანხა: *{total:.2f} ₾*\n\n"
        "ამ თანხით მიიღებ 1 თვიან წვდომას Shen Space-ის დახურულ სივრცესთან.\n"
        "თუ დაინტერესდი დააკლიკე \n"
        "/subscribe\n"
    )

    await update.message.reply_text(text, parse_mode="Markdown")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("ამ ბრძანების გამოყენება მხოლოდ ადმინს შეუძლია.")
        return

    if not context.args:
        await update.message.reply_text("გამოიყენე: /broadcast ტექსტი-შეტყობინება")
        return

    message_text = " ".join(context.args)
    subscribers = load_subscribers()

    success = 0
    for sub in subscribers:
        chat_id = sub.get("id")
        if chat_id is None:
            continue
        try:
            await context.bot.send_message(chat_id=chat_id, text=message_text)
            success += 1
        except Exception as e:
            print(f"ვერ გავაგზავნე {chat_id}-ზე: {e}")

    await update.message.reply_text(f"შეტყობინება გაიგზავნა {success} გამომწერთან ✅")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "გამარჯობა! ეს არის Shen Space subscribe-based ბოტი 🇬🇪\n\n"
        "ბრძანებები:\n"
        "/start - დაწყება და ავტომატური გამოწერა\n"
        "/subscribe - ხელახლა გამოწერა + გადახდის ვარიანტები\n"
        "/unsubscribe - გამოწერის გაუქმება\n"
        "/price - ფასის + გადასახადის ნახვა\n"
        "/premium - დახურული Shen Space სივრცე (მხოლოდ აქტიური სუბსქრიფშენით)\n"
        "/status - გაიგე, აქტიურია თუ არა შენი სუბსქრიფშენი\n"
        "/help - დახმარება\n\n"
        "ადმინისთვის:\n"
        "/broadcast ტექსტი - masse მიმართვა ყველა გამომწერთან\n"
        "/approve USER_ID - მომხმარებლის 1 თვიანი Shen Space სუბსქრიფშენის აქტივაცია."
    )
    await update.message.reply_text(text)


# ==================== PREMIUM & ADMIN Command-ები ====================

async def premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not has_active_subscription(chat_id):
        await update.message.reply_text(
            " ამ სექციაზე წვდომა მხოლოდ აქტიური Shen Space გამოწერის მქონეებისთვის არის 🌙\n"
            "გამოიყენე /price და /subscribe, გადაიხადე და შემდეგ გადახდის ქვითრის მიხედვით ადმინი გაგიაქტიურებს ხელმოწერას."
        )
        return

    await update.message.reply_text(
        "🌌 კეთილი იყოს შენი დაბრუნება Shen Space-ის დახურულ სივრცეში.\n"
        "აქ შეგიძლია მიიღო დღევანდელი გზავნილი, მედიტაცია, მინიშნებები და სხვა პრივილეგირებული კონტენტი."
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    info = get_subscription_info(chat_id)
    await update.message.reply_text(info)


async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("ამ ბრძანების გამოყენება მხოლოდ ადმინს შეუძლია.")
        return

    if not context.args:
        await update.message.reply_text("გამოიყენე: /approve USER_ID (მაგ: /approve 123456789)")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("USER_ID უნდა იყოს რიცხვი.")
        return

    set_subscription(target_id, days=30)

    await update.message.reply_text(
        f"OK ✅ მომხმარებელს {target_id} მიენიჭა 30 დღიანი Shen Space გამოწერა."
    )

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="🌟 შენი Shen Space გამოწერა აქტიურად არის 30 დღით. კეთილი იყოს შენი შემოსვლა დახურულ სივრცეში!"
        )
    except Exception as e:
        print(f"ვერ გავუგზავნეთ შეტყობინება {target_id}-ზე:", e)


# ==================== გადახდის ღილაკების callback ====================

async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id

    if query.data == "pay_bank":
        total = calc_price_with_tax(BASE_PRICE, TAX_RATE)
        tax_amount = total - BASE_PRICE

        text = (
            "🏦 *ბანკით გადარიცხვა*\n\n"
            f"საბაზო ფასი: {BASE_PRICE:.2f} ₾\n"
            f"გადასახადი ({int(TAX_RATE * 100)}%): {tax_amount:.2f} ₾\n"
            f"საბოლოო თანხა გადასახადით: *{total:.2f} ₾*\n\n"
            "მიმღები: ეკატერინე სარიჯაშვილი\n"
            "დანიშნულება: telegram Username\n\n"
            "გადახდის შემდეგ *აუცილებლად* ჩაგვიგდოთ *ფოტო* ან *სქრინშოტი* *(PDF ფაილი არ გამოდგება)* 🌟\n"
            "შემდეგ ადმინი გადაამოწმებს და საბოლოოდ გაგაქტიურებს პრემიუმ კონტენტზე წვდომას."
        )

        # ავღნიშნოთ, რომ ამ იუზერისგან ველოდებით ქვითრის ფოტოს
        context.user_data["waiting_for_receipt"] = True

        await query.edit_message_text(text=text, parse_mode="Markdown")

        # --- თიბისი ბანკი ---
        await context.bot.send_message(chat_id=chat_id, text="თიბისი ბანკი")
        await context.bot.send_message(chat_id=chat_id, text="GE46TB7576145064300089")  # TBC ანგარიში

        # --- საქართველოს ბანკი ---
        await context.bot.send_message(chat_id=chat_id, text="საქართველოს ბანკი")
        await context.bot.send_message(chat_id=chat_id, text="GE50BG0000000609711161")  # BOG ანგარიში

    elif query.data == "pay_later":
        text = (
            "კარგი 🌙\n"
            "შეგიძლია გადაიხადო მოგვიანებით. როცა მზად იქნები, გამოიყენე /price და /subscribe."
        )
        await query.edit_message_text(text=text)


# ==================== ქვითრის ფოტოს დამუშავება ====================

from telegram.constants import ParseMode

async def handle_receipt_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    იძახება, როცა იუზერი აგზავნის ფოტოს.
    თუ ამ იუზერისთვის მონიშნულია waiting_for_receipt,
    ვთვლით, რომ ეს არის გადახდის ქვითარი.
    """
    chat_id = update.effective_chat.id
    user = update.effective_user

    # თუ ამ იუზერისთვის არ ველოდებით ქვითარს, არაფერს ვაკეთებთ
    if not context.user_data.get("waiting_for_receipt"):
        return

    # ერთხელ რომ დაამუშავოს, მოვხსნათ ფლაგი
    context.user_data["waiting_for_receipt"] = False

    if not update.message or not update.message.photo:
        return

    # 👉 1) ფოტო არ ვიღებთ file_id-ით, პირდაპირ ვფორვარდებთ მთელ მესიჯს
    await context.bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=chat_id,
        message_id=update.message.message_id,
    )

    # 👉 2) ცალკე ტექსტური მესიჯი ადმინს /approve ბრძანებით
    caption = (
        "📥 ახალი გადახდის ქვითარი Shen Space-ისთვის\n\n"
        f"User ID: `{chat_id}`\n"
        f"Username: @{user.username if user.username else '—'}\n"
        f"სახელი: {user.full_name}\n\n"
        f"დადასტურებისას შეგიძლია გამოიყენო:\n"
        f"/approve {chat_id}"
    )

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=caption,
        parse_mode=ParseMode.MARKDOWN,
    )

    # 👉 3) პასუხი მომხმარებელს + ჯგუფის ლინკი
    await update.message.reply_text(
        "გადახდის ქვითaრი მიღებულია 🌟\n"
        "შეგიძლია უკვე შემოხვიდე Shen Space-ის დახურულ ჯგუფში:\n"
        f"{GROUP_LINK}\n\n"
        "ადმინი გადაამოწმებს ჩარიცხვას და საბოლოოდ დაამტკიცებს შენს წევრობას."
    )


# ==================== main ====================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("premium", premium))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("approve", approve))

    # Callback ღილაკების დამუშავება
    app.add_handler(CallbackQueryHandler(payment_callback))

    # ქვითრის ფოტოს ჰენდლერი
    app.add_handler(MessageHandler(filters.PHOTO, handle_receipt_photo))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()




