# 🇮🇷 Iranian Student Guide | راهنمای دانشجویان ایرانی

A Flask-based web application that helps Iranian students find practical information about studying and living abroad — country-by-country guides for shopping, housing, banking, SIM cards and the crucial first-days checklist.

🌐 **Live Demo:** [iranian-student-guide.onrender.com](https://iranian-student-guide.onrender.com)

## ✨ Features

* 🌍 **31 country guides** — Germany, Canada, USA, Turkey, UK, Italy, Netherlands, Australia, Malaysia, France, Austria, China, Russia, UAE, Spain, Sweden, Armenia, Hungary, Poland, Cyprus, Georgia, South Korea, Japan, Finland, Ireland, Norway, Denmark, Belgium, Switzerland, Portugal, Czechia
* 🧭 **First-days arrival checklist** — interactive, saved in your browser (`/checklist`)
* 🔎 **Global search** — full-text search across every guide (`/search` + live API `/api/search`)
* 🚨 **Emergency & essentials table** — capitals, currencies, languages, emergency numbers (`/emergency`)
* 📚 4 categorized guides per country (shopping / housing / admin & residence / student jobs) with external resources
* 🌙 **Dark mode**, SVG animations, reading progress, table of contents, print-friendly guides
* ⭐ **Favorites** — bookmark countries (localStorage), region filters, stats counters
* 📱 Fully responsive RTL Persian interface (Vazirmatn font)

## 🛠️ Tech Stack

* 🐍 Python + 🌐 Flask + 🎨 HTML/CSS/JS + 📄 JSON
* No database — content lives in `data/guides.json`, so anyone can contribute without touching code.

## 🚀 Run locally

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000`.

## 📁 Project Structure

```text
iran-student-guide/
├── app.py                  # Flask app: routes, search, stats, API
├── data/guides.json        # All guide content (add a country here, no code needed)
├── templates/
│   ├── base.html           # shared layout, nav, footer, SVG defs
│   ├── index.html          # hero + search + stats + country grid
│   ├── country.html        # category cards + essentials + related
│   ├── guide.html          # TOC + accordion + progress
│   ├── search.html         # results page
│   ├── checklist.html      # interactive arrival checklist
│   ├── emergency.html      # emergency/essentials table
│   └── 404.html
├── static/
│   ├── style.css           # design system + dark mode + animations
│   └── app.js              # theme, search, reveal, checklist, favorites
├── requirements.txt
├── render.yaml
└── README.md
```

## ➕ How to add a new guide

Open `data/guides.json`, copy an existing country block, add your items with `[label](https://…)` links — done. Categories currently supported: `shopping`, `housing` (extensible via `CATEGORY_META` in `app.py`).

## 🎯 Goal

One accessible place for the small-but-critical questions nobody tells you about a new country: where to buy a SIM, how to open a bank account, how deposits work, how to register your address.

## 👨‍💻 Author

**Matin Isapoor** — [GitHub](https://github.com/MatinIsapoor)

---

⭐ If you find this project useful, consider giving it a star!

---

## 🇮🇷 راهنمای فارسی

یک وب‌اپ Flask برای راهنمای زندگی دانشجویی ایرانی‌ها در کشورهای مختلف: خرید، مسکن، بانک، سیم‌کارت و چک‌لیست روزهای اول.

* اجرای محلی: دستورات بالا (بعدش `http://127.0.0.1:5000`)
* افزودن کشور/مطلب جدید: فقط `data/guides.json` را ویرایش کن، نیازی به تغییر کد نیست.
* صفحات جدید: `/search` جست‌وجو، `/checklist` چک‌لیست تعاملی، `/emergency` شماره‌های اضطراری.

پیشنهادها و مشارکت‌ها خوش‌آمدند! 🙌
