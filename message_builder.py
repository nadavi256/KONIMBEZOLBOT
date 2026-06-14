import random
import html

HOOKS = [
    "🔥 <b>מוצר שאתם חייבים לראות לפני שנגמר!</b>",
    "💥 <b>מחיר כזה לא יחזור – קחו עכשיו!</b>",
    "⚡ <b>הדיל שכולם מדברים עליו היום!</b>",
    "🤑 <b>אחרי שתראו את המחיר תתחרטו שלא הזמנתם מוקדם יותר!</b>",
    "😱 <b>לא מאמינים שמוצר כזה עולה כל כך מעט!</b>",
    "🚨 <b>עצרו הכל! הדיל הזה שווה כל שקל!</b>",
    "💸 <b>מה שהכסף שלכם יכול לקנות כאן – מדהים!</b>",
    "🛒 <b>זה לא מוצר, זה השקעה חכמה!</b>",
    "👀 <b>ראינו ולא האמנו – ואתם?</b>",
    "✨ <b>המוצר שכולם רוצים, עכשיו במחיר שהגיוני לחלוטין!</b>",
]

CTAS = [
    "👇 <b>לחצו לרכישה מיידית באלי אקספרס:</b>",
    "🛍️ <b>לחצו לדיל המלא עם כל הפרטים:</b>",
    "⬇️ <b>הזמינו עכשיו לפני שייגמרו:</b>",
    "🔗 <b>לרכישה מהירה – לחצו כאן:</b>",
    "🏃 <b>מהרו! הזמינו ישר מאלי אקספרס:</b>",
    "💳 <b>לרכישה ישירה ובטוחה:</b>",
]

CATEGORY_EMOJIS = {
    "אופנה וסטייל": "👗",
    "מוצרי מטבח": "🍳",
    "מוצרים לרכב": "🚗",
    "ספורט וכושר": "💪",
    "בית וגן": "🏠",
    "שעונים ותכשיטים": "⌚",
    "גאדג'טים": "🔧",
    "מוצר מומלץ": "⭐",
}

URGENCY_LINES = [
    "⏰ מלאי מוגבל – אל תחכו!",
    "📦 משלוח מהיר לישראל!",
    "🔥 ביקוש גבוה – המחיר יכול לעלות בכל רגע!",
    "✅ אלפי לקוחות מרוצים ברחבי העולם!",
    "🌍 משלוח בינלאומי עם הגנת קונה מלאה!",
    "💯 איכות מוכחת במחיר שלא תמצאו בישראל!",
    "🎁 מתנה מושלמת שתרשים כל אחד!",
    "⭐ דירוג 4.8+ מאלפי קונים!",
]


def _e(text: str) -> str:
    """Escape text for Telegram HTML parse mode."""
    return html.escape(str(text))


def build_message(product: dict, index: int, total: int) -> str:
    hook = random.choice(HOOKS)
    cta = random.choice(CTAS)
    urgency = random.choice(URGENCY_LINES)
    cat_emoji = CATEGORY_EMOJIS.get(product.get("category", ""), "⭐")

    name = _e(product.get("name", "מוצר מיוחד"))
    description = product.get("description", "")
    price = product.get("price", "")
    category = _e(product.get("category", "מוצר מומלץ"))
    link = product["aliexpress_link"]

    lines = [
        hook,
        "",
        f"{cat_emoji} <b>{name}</b>",
    ]

    if price and price not in ("₪0", "0", "לא צוין"):
        lines.append(f"💰 <b>מחיר:</b> {_e(price)}")

    if description:
        short = description[:160].rsplit(" ", 1)[0] + "..." if len(description) > 160 else description
        lines.append(f"\n📝 {_e(short)}")

    lines.append(f"\n{urgency}")
    lines.append("")
    lines.append(cta)
    lines.append(f'<a href="{link}">לחץ כאן לרכישה באלי אקספרס</a>')
    lines.append("")
    lines.append(f"📌 קטגוריה: {category}")
    lines.append(f"<i>{index}/{total}</i>")

    return "\n".join(lines)


def build_daily_header(count: int) -> str:
    greetings = [
        "🌅 <b>בוקר טוב ישראל!</b>\nמוכנים לדילים הכי שווים של היום? 🔥",
        "☀️ <b>יום חדש, דילים חדשים!</b>\nאספנו עבורכם את המוצרים הכי מבוקשים! 💥",
        "🛍️ <b>רשימת הקניות שלכם כבר כאן!</b>\nמחירים שלא תאמינו שקיימים! 🤑",
        "💫 <b>האלגוריתם עבד קשה!</b>\nהנה הדילים הכי חמים שמצאנו לכם! 🔥",
    ]
    greeting = random.choice(greetings)
    return f"{greeting}\n\n👇 הגיעו <b>{count} מוצרים</b> שכדאי לכם לראות!\n━━━━━━━━━━━━━━━━━━━━"


def build_daily_footer() -> str:
    footers = [
        "🔔 <b>רוצים עוד דילים?</b>\nהצטרפו לקהילה שלנו ואל תפספסו כלום!\n\n💬 שתפו חברים שאוהבים לחסוך! ❤️",
        "💡 <b>טיפ יומי:</b> תמיד בדקו את ביקורות הקונים לפני רכישה!\n\n🔔 שתפו את הפוסט לחברים שאוהבים דילים! 🙌",
        "✅ <b>כל המוצרים נבחרו ידנית על ידי הצוות שלנו!</b>\n\n❤️ אהבתם? שתפו וחסכו ביחד!",
    ]
    return random.choice(footers)
