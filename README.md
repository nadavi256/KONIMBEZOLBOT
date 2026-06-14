# KONIMBEZOL Telegram Bot

בוט טלגרם אוטומטי שמפרסם מוצרים מאתר konimbezol.co.il לערוץ טלגרם עם הפניות ישירות לאלי אקספרס.

## הגדרה מהירה

### 1. התקנת תלויות
```bash
pip install -r requirements.txt
```

### 2. קובץ `.env`
```
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHANNEL_ID=@your_channel
SITE_URL=https://konimbezol.co.il
```

### 3. הרצה

**הרצה רגילה (שולח כל יום בשעה 09:00 ו-18:00):**
```bash
python bot.py
```

**שליחה מיידית לבדיקה:**
```bash
python bot.py send-now
```

## מה הבוט עושה

- **סקרייפ אוטומטי** של כל המוצרים מהאתר (כולל כל הקטגוריות)
- **10-12 מוצרים ביום** עם תמונות, תיאורים ולינקים ישירים לאלי אקספרס
- **הודעות שיווקיות בעברית** מושכות ומניעות לפעולה
- **ללא הפניה לאתר** – כל הלינקים הולכים ישירות לאלי אקספרס
- **לו"ז אוטומטי**: 09:00 ו-18:00 שעון ישראל
- **Retry מובנה** על שגיאות טלגרם

## פריסה על שרת

### systemd (Linux VPS)
```ini
[Unit]
Description=Konimbezol Telegram Bot
After=network.target

[Service]
WorkingDirectory=/path/to/KONIMBEZOLBOT
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Docker
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```
