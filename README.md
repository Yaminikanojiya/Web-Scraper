#  Flask Web Scraper API

A secure and lightweight **Flask-based web scraper** that extracts **titles, quotes, images, or custom HTML elements** from any public webpage.  
Includes **SSRF protection**, **content-size limits**, and **CSS selector support** for safe, flexible data extraction.

---

##  Features
-  SSRF & private IP protection  
-  Smart HTML fetching with size checks  
-  Modes: `titles`, `quotes`, `images`, `custom`  
-  Clean JSON output  

---

##  Setup

```bash
git clone https://github.com/your-username/flask-web-scraper.git
cd flask-web-scraper
pip install -r requirements.txt
python app.py
