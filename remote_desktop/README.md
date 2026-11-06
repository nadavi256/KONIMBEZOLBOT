# תמיכה מרחוק – חלופה ל-AnyDesk / TeamViewer (Windows)

## איך זה עובד
- **הלקוח** מוריד את `RemoteSupport.exe` ופותח אותו. מופיעים **מזהה** ו**סיסמה**, והוא מקריא אותם לך.
- **אתה** פותח את `RemoteControl.exe`, מקליד את המזהה והסיסמה ומתחבר.
- הלקוח מאשר את החיבור ורואה כל הזמן שהמחשב בשליטה. הוא יכול לנתק בכל רגע.

אין התקנה ואין פקודות. שני הקבצים נבנים אוטומטית ב-GitHub.

## הגדרה חד-פעמית (כ-5 דקות)
המחשבים צריכים "נקודת מפגש" באינטרנט, כלומר שרת. מקימים אותו פעם אחת, בחינם, ב-Render:

1. נכנסים ל-https://render.com ונרשמים עם חשבון ה-GitHub.
2. בוחרים **New → Blueprint** ואת הריפו `KONIMBEZOLBOT`, ולוחצים **Apply**.
3. אחרי כמה דקות מתקבלת כתובת, למשל `https://remote-support-xxxx.onrender.com`.
4. כותבים את הכתובת בקובץ `remote_desktop/config.json`:
   ```json
   { "server_url": "https://remote-support-xxxx.onrender.com" }
   ```
   GitHub בונה מחדש את שני הקבצים, עם הכתובת בפנים, ומפרסם אותם להורדה.

## קישורים
- דף הבית (מבקש סיסמה לפני ההורדה): `https://remote-support-j2e3.onrender.com`

## סיסמה לאתר (`SITE_PASSWORD`)
הדף הציבורי מוגן בסיסמה, כדי שמי שלוחץ על הקישור באתר לא יוכל להוריד את התוכנות.

ב-Render, בשירות `remote-support`, מגדירים משתנה סביבה:

- שם: `SITE_PASSWORD`
- ערך: הסיסמה שבחרתם. היא נשמרת רק בהגדרות של Render, לא בקוד ולא ב-`render.yaml`. רווחים בתחילת הערך ובסופו מוסרים.

בלי הערך הזה (או אם הוא ריק) דף הבית, דף הצופה (`/viewer`) וההורדות נשארים סגורים. `/health` ממשיך להחזיר 200, ותוכנות שכבר מותקנות ממשיכות להירשם דרך `/ws/host` בלי הסיסמה הזו.

אחרי סיסמה נכונה הדפדפן נשאר מחובר (עוגייה חתומה). כפתורי ההורדה פונים לשרת עצמו: `/download/support` ללקוח ו-`/download/control` לטכנאי.

`SITE_PASSWORD` היא לא סיסמת החיבור שהלקוח מקריא, והיא לא `ACCESS_KEY` שתוכנת הלקוח שולחת בזמן הרשמה.

קבצי ה-Release ב-GitHub נשארים ציבוריים. מי שכבר מכיר את הכתובת הישירה יכול להוריד גם בלי סיסמת האתר:

- https://github.com/nadavi256/KONIMBEZOLBOT/releases/latest/download/RemoteSupport.exe
- https://github.com/nadavi256/KONIMBEZOLBOT/releases/latest/download/RemoteControl.exe

## טוב לדעת
- **"Windows protected your PC"**: מופיע כי הקובץ לא חתום דיגיטלית. לוחצים **More info → Run anyway**.
  כדי שזה ייעלם צריך תעודת חתימת קוד (בתשלום, בערך 200–400$ לשנה).
- **אנטי-וירוס**: תוכנות שליטה מרחוק לפעמים מסומנות בטעות כחשודות. חתימה דיגיטלית מצמצמת את זה.
- **שרת חינמי ב-Render** "נרדם" אחרי 15 דקות בלי שימוש, וההתעוררות לוקחת עד דקה.
  התוכנה של הלקוח מתחברת מחדש לבד. כדי שהחיבור יהיה מיידי תמיד, אפשר לשדרג ל-Starter (7$ לחודש).
- ב-Windows אין שליטה ב-Ctrl+Alt+Del ובחלונות "אישור מנהל" (UAC).

## הרצה מהקוד (למפתחים)
```bash
pip install -r requirements-host.txt
```
```bash
SITE_PASSWORD='choose-a-password' python server.py --port 8080
```
```bash
python host.py --server http://localhost:8080
```
ואז נכנסים בדפדפן ל-`http://localhost:8080`, מזינים את `SITE_PASSWORD`, ומשם ל-`/viewer`.
בלי המשתנה האתר נשאר סגור, אבל `/health` והחיבורים של התוכנות עדיין עובדים.

אפשרויות נוספות של `host.py`: `--password` (סיסמה קבועה), `--no-confirm` (גישה בלי אישור, רק למחשבים שלך),
`--view-only` (צפייה בלבד), `--monitor 2` (מסך שני).
