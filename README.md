# 🤖 KHQR Telegram Daily Report Bot (សម្រាប់ Merchant ធនាគារកម្ពុជា)

ប្រព័ន្ធស្វ័យប្រវត្តសម្រាប់អានសារជូនដំណឹងការទូទាត់ KHQR (ABA Merchant, Bakong, ACLEDA...) ពី Telegram Group រួចកត់ត្រា និងបូកសរុបប្រាក់ចំណូលប្រចាំថ្ងៃដោយបែងចែក **ប្រាក់ដុល្លារ ($)** និង **ប្រាក់រៀល (៛)** ដាច់ដោយឡែកពីគ្នា។

---

## ✨ មុខងារសំខាន់ៗ (Features)

1. **ស្វ័យប្រវត្តិកម្មអានសារ (Auto Parse KHQR Notifications):**
   - ស្គាល់ទម្រង់សារជូនដំណឹងរបស់ **ABA Merchant**, **Bakong KHQR** និងធនាគារផ្សេងទៀត (ទាំងភាសាខ្មែរ និងអង់គ្លេស)។
   - ចាប់យកទិន្នន័យសំខាន់ៗ៖ ចំនួនទឹកប្រាក់ (Amount), រូបិយប័ណ្ណ (USD/KHR), ឈ្មោះអតិថិជន (Payer), និងលេខកូដសម្គាល់ប្រតិបត្តិការ (Ref / Approval Code)។
   - ការពារការបូកជាន់គ្នា (Anti-Duplicate): ប្រសិនបើសារដដែលត្រូវផ្ញើពីរដង ប្រព័ន្ធនឹងមិនបូកបញ្ចូលទ្វេដងឡើយ។

2. **បូកសរុបប្រចាំថ្ងៃស្វ័យប្រវត្តិ (Daily Summary Report):**
   - កំណត់ម៉ោងផ្ញើរបាយការណ៍បូកសរុបស្វ័យប្រវត្តិ (ឧទាហរណ៍ ម៉ោង `22:00` យប់ ម៉ោងនៅកម្ពុជា UTC+7)។
   - បង្ហាញសរុប USD ($) ដាច់ដោយឡែក និង KHR (៛) ដាច់ដោយឡែក ព្រមទាំងចំនួនលើកនៃការទូទាត់។

3. **ពាក្យបញ្ជាពិនិត្យរបាយការណ៍ (Interactive Commands):**
   - `/today` ឬ `.today` : មើលរបាយការណ៍បូកសរុបថ្ងៃនេះភ្លាមៗ
   - `/yesterday` ឬ `.yesterday` : មើលរបាយការណ៍ម្សិលមិញ
   - `/week` ឬ `.week` : មើលរបាយការណ៍សប្តាហ៍នេះ (៧ថ្ងៃចុងក្រោយ)
   - `/month` ឬ `.month` : មើលរបាយការណ៍បូកសរុបប្រចាំខែនេះ
   - `/report YYYY-MM-DD` : មើលរបាយការណ៍តាមថ្ងៃជាក់លាក់ (ឧ. `/report 2026-09-28`)
   - `/recent` : បង្ហាញប្រតិបត្តិការ ៥ ចុងក្រោយ
   - `/sync` : ទាញយក និងពិនិត្យសារចាស់ៗក្នុង Group មុនពេល Add Bot
   - `/help` : បង្ហាញសេចក្តីណែនាំ

4. **ប្រព័ន្ធការពារសុវត្ថិភាពខ្ពស់ និងការគ្រប់គ្រងសិទ្ធិ (High Security & RBAC):**
   - **មានតែម្ចាស់ហាង (Owner/Admin) ឬបុគ្គលិកដែលមានការអនុញ្ញាតទើបអាចមើលរបាយការណ៍ចំណូលបាន** (ការពារមិនឱ្យមនុស្សទូទៅ ឬភ្ញៀវក្នុង Group ចុចមើលរបាយការណ៍បានឡើយ)។
   - `/myid` : មើល Telegram ID ផ្ទាល់ខ្លួន ដើម្បីផ្ញើទៅ Admin សុំសិទ្ធិ
   - `/adduser ID [role]` : ម្ចាស់ហាងបន្ថែមសិទ្ធិដល់បុគ្គលិក (Staff / Admin)
   - `/removeuser ID` : ដកសិទ្ធិបុគ្គលិកវិញភ្លាមៗ
   - `/users` : បង្ហាញបញ្ជីអ្នកដែលមានសិទ្ធិទាំងអស់

---

## ⚠️ ចំណុចសំខាន់អំពី Telegram Bot និង Bot របស់ធនាគារ (ABA Merchant Bot)

> **ចំណាំសំខាន់:** ច្បាប់របស់ប្រព័ន្ធ Telegram គឺ **Bot មិនអាចអានសារដែលផ្ញើដោយ Bot ផ្សេងទៀតនៅក្នុង Group បានឡើយ** (Telegram blocks bot-to-bot messages)។
>
> ដូច្នេះ ប្រសិនបើ Bank Bot (ដូចជា `@ABAMerchant_bot`) ផ្ញើសារចូលក្នុង Group៖
> - **វិធីសាស្ត្រដែលដំណើរការល្អបំផុត (Userbot Mode):** យើងប្រើប្រាស់ **Telethon Client** ជាមួយគណនី Telegram ផ្ទាល់ខ្លួន (លេខទូរសព្ទរបស់អ្នក ឬ Staff) ដែលស្ថិតនៅក្នុង Group នោះ។ វានឹងអាចអានសារពី Bot របស់ធនាគារបាន **១០០% ពេញលេញ**!

---

## 🛠 របៀបដំឡើង និងដំណើរការ (Quick Start)

### ជំហានទី ១: យក Telegram API Credentials
1. ចូលទៅកាន់គេហទំព័រ: https://my.telegram.org
2. វាយលេខទូរសព្ទ Telegram របស់អ្នក រួចយកលេខកូដបញ្ជាក់ពី Telegram
3. ចុចលើ **API development tools**
4. បំពេញឈ្មោះ App (ឧ. `KHQR_Reporter`) រួចចុច Create
5. អ្នកនឹងទទួលបាន **`api_id`** និង **`api_hash`**

### ជំហានទី ២: កំណត់ការកំណត់ក្នុងឯកសារ `.env`
ចម្លងឯកសារ `.env.example` ទៅជា `.env`:
```powershell
Copy-Item .env.example .env
```
បើកឯកសារ `.env` រួចបំពេញព័ត៌មាន៖
```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef1234567890abcdef
TELEGRAM_PHONE_NUMBER=+855XXXXXXXX
MONITOR_CHAT_ID=-1001234567890
REPORT_CHAT_ID=-1001234567890
DAILY_REPORT_TIME=22:00
ENABLE_INSTANT_ALERT=false
```

### ជំហានទី ៣: ដំណើរការ Bot
បើក Terminal ក្នុងថត `dailyreportbot` រួចវាយ៖
```powershell
.venv\Scripts\python main.py
```
*នៅពេលដំណើរការលើកដំបូង ប្រព័ន្ធនឹងទាមទារលេខកូដ Login Code ដែលផ្ញើទៅកាន់ Telegram របស់អ្នក (ត្រឹមតែម្តងគត់ បន្ទាប់មកវានឹងរក្សាទុកក្នុង file `khqr_session.session`)*។

---

## 🧪 របៀបតេស្តសាកល្បងមុនពេលភ្ជាប់ពិតប្រាកដ

អ្នកអាចសាកល្បងតេស្តមុខងារ Parser និង Database ភ្លាមៗដោយពុំទាន់បាច់ភ្ជាប់ Telegram ក៏បាន៖

1. **តេស្ត Parser និង Regex លើសារគំរូ KHQR:**
   ```powershell
   .venv\Scripts\python test_parser.py
   ```

2. **តេស្តបញ្ចូលទិន្នន័យគំរូ និងមើលរបាយការណ៍បូកសរុប (Preview Report):**
   ```powershell
   .venv\Scripts\python add_test_data.py
   ```

---

## 📁 រចនាសម្ព័ន្ធឯកសារក្នុងគម្រោង (Project Structure)

```
dailyreportbot/
├── .venv/               # Python Virtual Environment
├── config.py            # ការកំណត់ទូទៅ និងអានពី .env
├── database.py          # SQLite database (កត់ត្រា និងបូកសរុបប្រាក់)
├── parser.py            # Regex សម្រាប់ parse សារ KHQR (USD & KHR)
├── reporter.py          # តុបតែងអត្ថបទរបាយការណ៍ជាភាសាខ្មែរ
├── bot.py               # Telegram engine (Telethon + APScheduler)
├── main.py              # Entry point សម្រាប់ start bot
├── add_test_data.py     # Script បញ្ចូលទិន្នន័យគំរូដើម្បីតេស្ត
├── test_parser.py       # Script Unit test សម្រាប់ parser
├── requirements.txt     # បញ្ជី package ដែលបានដំឡើង
└── README.md            # សេចក្តីណែនាំ
```
