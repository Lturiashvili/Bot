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
import logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ⚙️ აქ ჩასვი შენი BotFather-ის TOKEN
# BOT_TOKEN = "8375308624:AAHy3qHw4Au0F1HpHODx4mufhJ3M_jTe5CQ"  # ← აქ ჩასვი შენი ნამდვილი ტოკენი
BOT_TOKEN = os.environ["BOT_TOKEN"]
# BOT_TOKEN = "8372852069:AAFyAckZM4N3pStqvQwa3zqefpC8fNOsmSA" 
# ⚙️ აქ ჩასვი შენი პირადი Telegram user ID (admin)
# ADMIN_ID = 8201387380  # შეცვალე შენზე
ADMIN_IDS = {8201387380, 8313922766}
GROUP_LINK = "https://t.me/+rCNHBtic_rJhYmIy" 
POLL_INTERVAL_DAYS = 30
# გამომწერთა სიის ფაილი
DATA_DIR = os.environ.get("DATA_DIR", "/var/data")
os.makedirs(DATA_DIR, exist_ok=True)

SUBSCRIBERS_FILE = os.path.join(DATA_DIR, "subscribers.json")
RECEIPTS_FILE = os.path.join(DATA_DIR, "receipts.json")
SUBSCRIPTIONS_FILE = os.path.join(DATA_DIR, "subscriptions.json")
POLL_RESULTS_FILE = os.path.join(DATA_DIR, "poll_results.json")


# გადასახადის პარამეტრები
BASE_PRICE = 11      # ძირითადი ღირებულება (მაგ. 10 ლარი თვეში)
TAX_RATE = 0       # 18% VAT


# ==================== Utility: გამომწერები ====================


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def load_receipts():
    if not os.path.exists(RECEIPTS_FILE):
        return {}
    with open(RECEIPTS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_receipts(data):
    with open(RECEIPTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def increment_receipt_count(chat_id: int) -> int:
    data = load_receipts()
    key = str(chat_id)
    data[key] = data.get(key, 0) + 1
    save_receipts(data)
    return data[key]

def is_subscriber(chat_id: int) -> bool:
    subscribers = load_subscribers()
    return any(sub.get("id") == chat_id for sub in subscribers)



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

def load_poll_results():
    if not os.path.exists(POLL_RESULTS_FILE):
        return {}
    with open(POLL_RESULTS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_poll_results(data):
    with open(POLL_RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_user_poll_answer(chat_id: int, key: str, value):
    data = load_poll_results()
    uid = str(chat_id)
    if uid not in data:
        data[uid] = {}
    data[uid][key] = value
    data[uid]["updated_at_utc"] = datetime.utcnow().isoformat()
    save_poll_results(data)

def save_user_poll_text(chat_id: int, key: str, text: str):
    data = load_poll_results()
    uid = str(chat_id)
    if uid not in data:
        data[uid] = {}
    data[uid][key] = text
    data[uid]["updated_at_utc"] = datetime.utcnow().isoformat()
    save_poll_results(data)

def poll_should_be_sent(chat_id: int) -> bool:
    data = load_poll_results()
    uid = str(chat_id)
    info = data.get(uid, {})
    last = info.get("last_poll_sent_utc")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except Exception:
        return True
    return datetime.utcnow() - last_dt >= timedelta(days=POLL_INTERVAL_DAYS)

def mark_poll_sent(chat_id: int):
    data = load_poll_results()
    uid = str(chat_id)
    if uid not in data:
        data[uid] = {}
    data[uid]["last_poll_sent_utc"] = datetime.utcnow().isoformat()
    save_poll_results(data)


async def send_poll_report_to_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user):
    data = load_poll_results().get(str(chat_id), {})
    q1 = data.get("q1_like_most", "—")
    q2 = data.get("q2_missing", "—")
    q3 = data.get("q3_content_type", "—")
    q4 = data.get("q4_frequency", "—")
    q5 = data.get("q5_format", "—")

    text = (
        "📊 *Shen Space Poll პასუხები*\n\n"
        f"User ID: `{chat_id}`\n"
        f"Username: @{user.username if user.username else '—'}\n"
        f"სახელი: {user.full_name}\n\n"
        f"*1) ყველაზე მეტად რა მოგწონს?*\n{q1}\n\n"
        f"*2) რა გაკლია / რას დაამატებდი?*\n{q2}\n\n"
        f"*3) რომელი კონტენტი გიზიდავს ყველაზე მეტად?*\n{q3}\n\n"
        f"*4) პოსტების სიხშირე რამდენად კომფორტულია?*\n{q4}\n\n"
        f"*5) რა ფორმატში გინდა მეტი?*\n{q5}\n"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            print(f"poll report to admin {admin_id} failed: {e!r}")


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = query.message.chat_id
    user = update.effective_user

    # --- POLL CALLBACKS ---
    if data.startswith("poll:"):
        # poll:q3:inspire
        _, q, answer = data.split(":", 2)

        # Q3 -> send Q4
        if q == "q3":
            save_user_poll_answer(chat_id, "q3_content_type", answer)
            context.user_data["poll_stage"] = 4

            pretty = {
                "inspire": "ინსპირაციული ტექსტები",
                "practical": "პრაქტიკული რჩევები",
                "education": "განათლება / ცოდნა",
                "meditation": "მედიტაციები / პრაქტიკები",
                "taro": "ტარო",
            }.get(answer, answer)

            await query.edit_message_text(text=f"✅ ჩანიშნულია: {pretty}")

            keyboard = [
                [InlineKeyboardButton("ძალიან იშვიათია", callback_data="poll:q4:rare")],
                [InlineKeyboardButton("იდეალურია", callback_data="poll:q4:ideal")],
                [InlineKeyboardButton("ძალიან ხშირად იდება", callback_data="poll:q4:too_often")],
            ]

            await context.bot.send_message(
                chat_id=chat_id,
                text="*4) რამდენად კომფორტულია შენთვის პოსტების სიხშირე?*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        # Q4 -> send Q5
        if q == "q4":
            save_user_poll_answer(chat_id, "q4_frequency", answer)
            context.user_data["poll_stage"] = 5

            pretty = {
                "rare": "ძალიან იშვიათია",
                "ideal": "იდეალურია",
                "too_often": "ძალიან ხშირად იდება",
            }.get(answer, answer)

            await query.edit_message_text(text=f"✅ ჩანიშნულია: {pretty}")

            keyboard = [
                [InlineKeyboardButton("მოკლე და სწრაფი რჩევები", callback_data="poll:q5:short")],
                [InlineKeyboardButton("სიღრმისეული სტატიები", callback_data="poll:q5:deep")],
                [InlineKeyboardButton("ვიდეო/აუდიო ახსნა", callback_data="poll:q5:audio_video")],
                [InlineKeyboardButton("ცოცხალი ჩართვები", callback_data="poll:q5:live")],
                [InlineKeyboardButton("მინი-კურსები", callback_data="poll:q5:mini_course")],
            ]
            await context.bot.send_message(
                chat_id=chat_id,
                text="*5) რა ფორმატში გინდა მეტი კონტენტის მიღება?*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        # Q5 -> finish
        if q == "q5":
            save_user_poll_answer(chat_id, "q5_format", answer)

            pretty = {
                "short": "მოკლე და სწრაფი რჩევები",
                "deep": "სიღრმისეული სტატიები",
                "audio_video": "ვიდეო/აუდიო ახსნა",
                "live": "ცოცხალი ჩართვები",
                "mini_course": "მინი-კურსები",
            }.get(answer, answer)

            await query.edit_message_text(text=f"✅ ჩანიშნულია: {pretty}\n\nმადლობა! 🙏")

            context.user_data["poll_active"] = False
            context.user_data["poll_stage"] = None

            # სურვილისამებრ: admin report
            await send_poll_report_to_admin(context, chat_id, user)
            return

        return

    # --- PAYMENT CALLBACKS (pay_bank / pay_later) ---
    await payment_callback(update, context)

async def auto_poll_job(context: ContextTypes.DEFAULT_TYPE):
    subscribers = load_subscribers()

    for sub in subscribers:
        chat_id = sub.get("id")
        if not chat_id:
            continue

        # სურვილისამებრ: მხოლოდ აქტიურებს გაუგზავნე
        if not has_active_subscription(chat_id):
            continue

        if not poll_should_be_sent(chat_id):
            continue

        # PTB JobQueue-ში user ობიექტი არ გაქვს, ამიტომ dummy
        dummy_user = type(
            "U",
            (),
            {
                "username": sub.get("username"),
                "full_name": f"{sub.get('first_name') or ''} {sub.get('last_name') or ''}".strip() or "—",
            },
        )()

        try:
            mark_poll_sent(chat_id)
            await start_poll_flow(chat_id, dummy_user, context)
        except Exception as e:
            print(f"auto poll failed for {chat_id}: {e!r}")


async def poll_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    # ✅ admin-ს ყოველთვის შეეძლოს ტესტი
    if not is_admin(user.id) and not has_active_subscription(chat_id):
        await update.effective_message.reply_text("Poll მხოლოდ აქტიური გამოწერის მქონეებისთვისაა 🌙")
        return

    if not is_admin(user.id) and not poll_should_be_sent(chat_id):
        await update.effective_message.reply_text("Poll უკვე გაიგზავნა ბოლო 30 დღეში ✅")
        return

    # ჩვეულებრივ იუზერებზე ვნიშნავთ last_poll_sent_utc-ს
    if not is_admin(user.id):
        mark_poll_sent(chat_id)

    await start_poll_flow(chat_id, user, context)



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
            "გამოსაწერად დააჭირე --> /subscribe\n"
            "ფასის გასაგებად დააჭირე --> /price.\n"
        )
    else:
        text = (
            "კიდევ ერთხელ მოგესალმები! ✨\n"
            "შენ უკვე გამოწერილი გაქვს პრემიუმ სივრცე.\n"
            "ფასის გასაგებად გამოიყენე /price,\n"
            "გასაუქმებლად /unsubscribe.\n"
        )

    await context.bot.send_message(chat_id=chat.id, text=text)


def get_poll_stage(chat_id: int) -> int:
    data = load_poll_results()
    uid = str(chat_id)
    return int(data.get(uid, {}).get("poll_stage") or 0)

def set_poll_stage(chat_id: int, stage: int):
    data = load_poll_results()
    uid = str(chat_id)
    if uid not in data:
        data[uid] = {}
    data[uid]["poll_stage"] = stage
    data[uid]["updated_at_utc"] = datetime.utcnow().isoformat()
    save_poll_results(data)

def clear_poll_stage(chat_id: int):
    set_poll_stage(chat_id, 0)



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
    # if user_id != ADMIN_ID:
    if user_id not in ADMIN_IDS:
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

async def start_poll_flow(chat_id: int, user, context: ContextTypes.DEFAULT_TYPE):
    # დავნიშნოთ, რომ poll active-ია
    context.user_data["poll_active"] = True
    context.user_data["poll_stage"] = 1

    # პირველი კითხვა (Q1) — ტექსტად
    await context.bot.send_message(
        chat_id=chat_id,
        text="*1) ყველაზე მეტად რა მოგწონს Shen Space-ში?*\nმომწერე ტექსტად 👇",
        parse_mode="Markdown",
    )

async def poll_text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text.strip()

    # თუ poll არ არის აქტიური, არ შევეხოთ
    stage = context.user_data.get("poll_stage")
    if not stage:
        return

    # Q1 ტექსტი
    if stage == 1:
        save_user_poll_text(chat_id, "q1_like_most", text)
        context.user_data["poll_stage"] = 2

        await update.message.reply_text(
            "*2) რა გაკლია ან რას დაამატებდი?*\nმომწერე ტექსტად 👇",
            parse_mode="Markdown",
        )
        return

    # Q2 ტექსტი -> გადავდივართ Q3 inline-ზე
    if stage == 2:
        save_user_poll_text(chat_id, "q2_missing", text)
        context.user_data["poll_stage"] = 3

        keyboard = [[
            InlineKeyboardButton("ინსპირაციული ტექსტები", callback_data="poll:q3:inspire"),
        ],[
            InlineKeyboardButton("პრაქტიკული რჩევები", callback_data="poll:q3:practical"),
        ],[
            InlineKeyboardButton("განათლება / ცოდნა", callback_data="poll:q3:education"),
        ],[
            InlineKeyboardButton("მედიტაციები / პრაქტიკები", callback_data="poll:q3:meditation"),
        ],[
            InlineKeyboardButton("ტარო", callback_data="poll:q3:taro"),
        ]]

        await context.bot.send_message(
            chat_id=chat_id,
            text="*3) რომელი კონტენტი გიზიდავს ყველაზე მეტად?*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return


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
    # if user_id != ADMIN_ID:
    if user_id not in ADMIN_IDS:
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

GROUP_LINK_AFTER_RECEIPT = "https://t.me/+79itfRG-edE1M2Yy"

async def handle_receipt_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if not update.message:
        return

    # message_id ფორვარდისთვის
    msg_id = update.message.message_id

    # არის თუ არა სურათი
    is_photo = bool(update.message.photo)
    is_image_doc = bool(
        update.message.document
        and (update.message.document.mime_type or "").startswith("image/")
    )

    if not is_photo and not is_image_doc:
        return

    # ქვითარს ვიღებთ თუ:
    waiting = bool(context.user_data.get("waiting_for_receipt"))
    if not waiting:
        return

    # ერთხელ მიღების შემდეგ ვხსნით ფლაგს
    context.user_data["waiting_for_receipt"] = False

    receipt_num = increment_receipt_count(chat_id)

    # 1️⃣ ფორვარდი ადმინებთან (უსაფრთხოდ)
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.forward_message(
                chat_id=admin_id,
                from_chat_id=chat_id,
                message_id=msg_id,
            )
        except Exception as e:
            print(f"Forward to admin {admin_id} failed: {e!r}")


    # 2️⃣ ტექსტური დეტალები ადმინებისთვის
    caption = (
        "📥 ახალი გადახდის ქვითარი Shen Space-ისთვის\n\n"
        f"Receipt #: *{receipt_num}*\n"
        f"User ID: `{chat_id}`\n"
        f"Username: @{user.username if user.username else '—'}\n"
        f"სახელი: {user.full_name}\n\n"
        "დადასტურებისას გამოიყენე:\n"
        f"/approve {chat_id}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=caption,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as e:
            print(f"Send text to admin {admin_id} failed: {e!r}")


    # 3️⃣ პასუხი მომხმარებელს
    await update.message.reply_text(
        "მადლობა 🙏\n"
        "გთხოვთ გადახვიდეთ ლინკზე:\n"
        f"{GROUP_LINK_AFTER_RECEIPT}\n"
        "და ადმინი დაგიდასტურებთ ❤️"
    )



    # ==================== DEBUG ====================

# async def debug_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     if not update.message:
#         return

#     m = update.message
#     print("=== DEBUG ===")
#     print("chat_id:", update.effective_chat.id)
#     print("text:", m.text)
#     print("has_photo:", bool(m.photo))
#     print("has_document:", bool(m.document))
#     if m.document:
#         print("doc mime:", m.document.mime_type)
#         print("doc file_name:", m.document.file_name)
#     print("caption:", m.caption)
#     print("==============")




# ==================== main ====================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ✅ 1) Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("premium", premium))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("poll", poll_command))

    # ✅ 2) Callback queries (poll + payment)
    # IMPORTANT: callback_router უნდა იყოს main()-ზე ზემოთ აღწერილი!
    app.add_handler(CallbackQueryHandler(callback_router))

    # ✅ 3) Receipt media (photo/image-doc)
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_receipt_media))

    # ✅ 4) Poll text answers (Q1/Q2)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, poll_text_router))

    # ✅ 5) Auto poll job (24h ერთხელ)
    # IMPORTANT: auto_poll_job უნდა იყოს main()-ზე ზემოთ აღწერილი!
    app.job_queue.run_repeating(auto_poll_job, interval=24 * 60 * 60, first=30)

    # ✅ 6) DEBUG (ყველაზე ბოლოს!)
    # დროებით ჯობია ALL არ იყოს, თორემ ყველაფერს "შეჭამს" ლოგიკურად
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.ALL, debug_all))

    print("Bot started...")
    app.run_polling()



if __name__ == "__main__":
    main()






