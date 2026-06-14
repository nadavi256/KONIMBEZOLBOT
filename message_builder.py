import random

# Opening hooks - emotional/FOMO driven
HOOKS = [
    "🔥 **מוצר שאתם חייבים לראות לפני שנגמר!**",
    "💥 **מחיר כזה לא יחזור – קחו עכשיו!**",
    "⚡ **הדיל שכולם מדברים עליו היום!**",
    "🤑 **אחרי שתראו את המחיר תתחרטו שלא הזמנתם מוקדם יותר!**",
    "😱 **לא מאמינים שמוצר כזה עולה כל כך מעט!**",
    "🚨 **עצרו הכל! הדיל הזה שווה כל שקל!**",
    "💸 **מה שהכסף שלכם יכול לקנות כאן – מדהים!**",
    "🛒 **זה לא מוצר, זה השקעה חכמה!**",
    "👀 **ראינו ולא האמנו – ואתם?**",
    "✨ **המוצר שכולם רוצים, עכשיו במחיר שהגיוני לחלוטין!**",
]

# CTA variants
CTAS = [
    "👇 **לחצו לרכישה מיידית באלי אקספרס:**",
    "🛍️ **לחצו לדיל המלא עם כל הפרטים:**",
    "⬇️ **הזמינו עכשיו לפני שייגמרו:**",
    "🔗 **לרכישה מהירה – לחצו כאן:**",
    "🏃 **מהרו! הזמינו ישר מאלי אקספרס:**",
    "💳 **לרכישה ישירה ובטוחה:**",
]

CATEGORY_EMOJIS = {
    "גאדג'ט חייב": "🔧",
    "אופנה וסטייל": "👗",
    "מטבח": "🍳",
    "לרכב": "🚗",
    "ספורט": "💪",
    "בית וגן": "🏠",
    "שעונים ותכשיטים": "⌚",
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


def build_message(product: dict, index: int, total: int) -> str:
    """Build a compelling Hebrew marketing message for a product."""
    hook = random.choice(HOOKS)
    cta = random.choice(CTAS)
    urgency = random.choice(URGENCY_LINES)
    cat_emoji = CATEGORY_EMOJIS.get(product.get("category", ""), "⭐")

    name = product.get("name", "מוצר מיוחד")
    description = product.get("description", "")
    price = product.get("price", "")
    category = product.get("category", "מוצר מומלץ")

    lines = [
        hook,
        "",
        f"{cat_emoji} **{name}**",
    ]

    if price and price not in ("₪0", "0", "לא צוין"):
        lines.append(f"💰 **מחיר:** {price}")

    if description:
        # Trim to 150 chars
        short_desc = description[:150].rsplit(" ", 1)[0] + "..." if len(description) > 150 else description
        lines.append(f"\n📝 {short_desc}")

    lines.append(f"\n{urgency}")
    lines.append("")
    lines.append(cta)
    lines.append(product["aliexpress_link"])
    lines.append("")
    lines.append(f"📌 קטגוריה: {category}")
    lines.append(f"_{index}/{total}_")

    return "\n".join(lines)


def build_daily_header(count: int) -> str:
    greetings = [
        "🌅 **בוקר טוב ישראל!**\nמוכנים לדילים הכי שווים של היום? 🔥",
        "☀️ **יום חדש, דילים חדשים!**\nאספנו עבורכם את המוצרים הכי מבוקשים! 💥",
        "🛍️ **רשימת הקניות היומית שלכם כבר כאן!**\nמחירים שלא תאמינו שקיימים! 🤑",
        "💫 **האלגוריתם עבד קשה בלילה!**\nוהנה הדילים הכי חמים שמצאנו לכם! 🔥",
    ]
    greeting = random.choice(greetings)
    return (
        f"{greeting}\n\n"
        f"👇 היום אנחנו מגישים לכם **{count} מוצרים** שכדאי לכם לראות!\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )


def build_daily_footer() -> str:
    footers = [
        "🔔 **רוצים עוד דילים?**\nהצטרפו לקהילה שלנו ואל תפספסו כלום!\n\n💬 שתפו חברים שאוהבים לחסוך! ❤️",
        "💡 **טיפ יומי:** תמיד בדקו את ביקורות הקונים לפני רכישה!\n\n🔔 שתפו את הפוסט לחברים שאוהבים דילים! 🙌",
        "✅ **כל המוצרים נבחרו ידנית על ידי הצוות שלנו!**\n\n❤️ אהבתם? שתפו וחסכו ביחד!",
    ]
    return random.choice(footers)
