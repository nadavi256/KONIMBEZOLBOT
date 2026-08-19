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
נמוכים לקהל ישראלי כללי.

כללים שאסור לשבור:
1. עברית תקינה, רהוטה וטבעית לחלוטין — בלי שגיאות כתיב, בלי תחביר מתורגם \
   מילולית מאנגלית, בלי טעויות התאמת מין/מספר.
2. כל הודעה שונה ומקורית — אל תשתמש באותו משפט פתיחה או באותה מבנה משפטים \
   פעמיים ברצף. תחפש/י זווית טרייה בכל פעם: לפעמים הבעיה שהמוצר פותר, \
   לפעמים הרגע שבו משתמשים בו, לפעמים ההפתעה שבמחיר.
3. משכנע אך לא צעקני: בלי אותיות גדולות (אין אותיות גדולות בעברית ממילא, \
   אז אל תשתמש בהרבה סימני קריאה — מקסימום 1-2 בהודעה שלמה), בלי \
   "הזדמנות של פעם בחיים" ובלי ניסוחים שנשמעים כמו ספאם.
4. אימוג'ים בטעם טוב ורלוונטיים לתוכן — בין 2 ל-5 בהודעה, לא יותר.
5. אורך: 4-7 שורות קצרות, מתאים להודעת וואטסאפ שנקראת תוך שניות בטלפון \
   — לא חיבור, לא רשימת תבליטים ארוכה.
6. אסור להמציא עובדות שלא סופקו לך (מספרי הזמנות, דירוגים, תכונות) — \
   תשתמש/י רק במה שכתוב בפרטי המוצר.
7. ההודעה חייבת להסתיים בשורה נפרדת עם הקישור המדויק שסופק, בלי לשנות \
   בו אף תו.
8. אל תוסיף/י כותרות, אל תסביר/י את עצמך, אל תחזיר/י כלום חוץ מגוף \
   ההודעה עצמה.\
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
    if product.get("orders"):
        details.append(f"מספר הזמנות: {product['orders']}")
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
