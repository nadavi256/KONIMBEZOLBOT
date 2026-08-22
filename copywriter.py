"""AI copywriting agent for WhatsApp deal messages.

Generates a fresh, creative, high-quality Hebrew marketing message per
product via the Claude API — replacing the fixed hook/opener template
lists in message_builder.build_whatsapp_message with real per-product
copy. Falls back to that template (see bot_whatsapp.py) whenever the API
key is missing or a call fails, so a copywriting outage never blocks a
send.
"""
import logging
import os

import anthropic

logger = logging.getLogger(__name__)

MODEL = os.environ.get("COPYWRITER_MODEL", "claude-opus-5")

_client = anthropic.Anthropic() if os.environ.get("ANTHROPIC_API_KEY") else None

SYSTEM_PROMPT = """\
את/ה קופירייטר/ית שיווקי/ת בכיר/ה בישראל, כותב/ת הודעות דילים לקבוצת \
וואטסאפ בשם "קונים בזול" — קבוצה שמפרסמת מוצרים באלי אקספרס במחירים \
נמוכים לקהל ישראלי כללי. ההודעה נקראת תוך שניות בטלפון — היא חייבת \
להיות סרוקה בעין, לא פסקת טקסט רציפה.

מבנה קבוע לכל הודעה, בדיוק בסדר הזה (שורה ריקה בין חלקים):
1. שורת כותרת: אימוג'י מתאים + שם המוצר מודגש (בין כוכביות: *שם המוצר*).
2. משפט הוק אחד-שניים בלבד, קצר וממוקד — לא פסקה. זה המקום היחיד \
   ליצירתיות בניסוח; כל שאר המבנה קבוע.
3. 2-4 שורות תכונות, כל שורה מתחילה באימוג'י ✅ ומשפט קצר אחד (לא משפט \
   מורכב, לא כמה תכונות באותה שורה).
4. אם יש דירוג בפרטי המוצר — שורה אחת: "⭐ דירוג X".
5. אם יש מחיר בפרטי המוצר — שורה אחת: "💰 מחיר: <המחיר בדיוק כפי שסופק>" \
   (אל תשני את הניסוח של המחיר עצמו, כולל אם כתוב "מ-").
6. שורה אחרונה, נפרדת: לפני הקישור מותר (לא חובה) לשים פתיח קצר וניטרלי בן
   2-4 מילים (למשל "לינק:", "קישור לרכישה:", "לצפייה והזמנה:") — לא זהה בכל
   פעם, ולא בנוסח דחוף/צעקני. אחרי הפתיח (אם יש), הקישור עצמו מדויק כפי
   שסופק, בלי לשנות בו אף תו.

כללים שאסור לשבור:
1. עברית תקינה, רהוטה וטבעית לחלוטין — בלי שגיאות כתיב, בלי תחביר מתורגם \
   מילולית מאנגלית, בלי טעויות התאמת מין/מספר.
2. משפט ההוק שונה ומקורי בכל פעם — לא אותו פתיח פעמיים ברצף. זווית טרייה \
   בכל פעם: לפעמים הבעיה שהמוצר פותר, לפעמים הרגע שבו משתמשים בו, לפעמים \
   ההפתעה שבמחיר.
3. משכנע אך לא צעקני: מקסימום 1-2 סימני קריאה בהודעה שלמה, בלי "הזדמנות \
   של פעם בחיים" ובלי ניסוחים שנשמעים כמו ספאם.
4. אימוג'ים רק איפה שהמבנה קורא להם (כותרת, תכונות, דירוג, מחיר) — לא \
   מפוזרים בתוך המשפטים.
5. אסור להמציא עובדות שלא סופקו לך (מחיר, מספרי הזמנות, דירוג, תכונות) — \
   תשתמש/י רק במה שכתוב בפרטי המוצר, ותשמיט/י שורה שלמה אם המידע חסר.
6. אל תוסיף/י כותרות משל עצמך, אל תסביר/י את עצמך, אל תחזיר/י כלום חוץ \
   מגוף ההודעה לפי המבנה שלמעלה.\
"""


def is_configured() -> bool:
    return _client is not None


def generate_whatsapp_copy(product: dict) -> str | None:
    """Return a ready-to-send WhatsApp deal message, or None if the
    copywriter is unavailable / the call fails / the result looks broken —
    callers should fall back to the template writer in that case."""
    if not _client:
        return None
    link = product.get("aliexpress_link")
    if not link:
        return None

    details = [f"שם המוצר: {product.get('name', 'מוצר')}"]
    if product.get("price"):
        details.append(f"מחיר: {product['price']}")
    if product.get("features"):
        details.append("תכונות בולטות: " + "; ".join(product["features"][:5]))
    if product.get("rating"):
        details.append(f"דירוג: {product['rating']}")
    # Deliberately not passing "orders" here: it's extracted with a regex
    # from the AliExpress page and has shown false positives (picking up
    # an unrelated "recent activity" number instead of the real lifetime
    # sold count) — still scraped and logged for the dashboard so accuracy
    # can be verified over real sends, just not stated to customers yet.
    if product.get("category"):
        details.append(f"קטגוריה: {product['category']}")

    user_prompt = (
        "כתוב/כתבי הודעת דיל אחת לקבוצת הוואטסאפ על המוצר הבא.\n\n"
        + "\n".join(details)
        + f"\n\nבסיום ההודעה, בשורה נפרדת, חובה לצרף בדיוק את הקישור הזה "
        f"בלי לשנות בו אף תו: {link}"
    )

    try:
        response = _client.messages.create(
            model=MODEL,
            max_tokens=1024,
            output_config={"effort": "medium"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIStatusError as e:
        logger.error(f"Copywriter API error: {e}")
        return None
    except anthropic.APIConnectionError as e:
        logger.error(f"Copywriter connection error: {e}")
        return None
    except Exception as e:
        logger.error(f"Copywriter unexpected error: {e}")
        return None

    text = next((b.text for b in response.content if b.type == "text"), "").strip()
    if not text or link not in text:
        logger.warning("Copywriter output missing link or empty — falling back to template")
        return None
    return text
