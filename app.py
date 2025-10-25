from flask import Flask, request, jsonify, render_template
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import ipaddress
import socket

app = Flask(__name__)

# ---- Basic SSRF protection helpers ----
def is_valid_scheme(url):
    p = urlparse(url)
    return p.scheme in ('http', 'https')

def resolve_hostname_host_is_private(hostname):
    """Resolve hostname and return True if it's private/reserved/loopback."""
    try:
        # If hostname is already an IP string, ipaddress handles it
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_link_local
    except Exception:
        # If we cannot resolve, fail safe: treat as not private (or you can treat as private)
        return False

def is_safe_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False
    host = parsed.hostname
    if not host:
        return False
    # reject if hostname looks like localhost or resolves to private IP
    if host in ('localhost', '127.0.0.1'):
        return False
    if resolve_hostname_host_is_private(host):
        return False
    return True

# ---- Scrape helpers ----
def fetch_html(url, timeout=8, max_content_size=2 * 1024 * 1024):
    """Fetch the URL with a timeout and a content-length limit check."""
    headers = {
        "User-Agent": "BooksScraperDemo/1.0 (+https://example.com)"
    }
    with requests.get(url, headers=headers, timeout=timeout, stream=True) as r:
        r.raise_for_status()
        # Check Content-Length header if present
        cl = r.headers.get('Content-Length')
        if cl and int(cl) > max_content_size:
            raise ValueError("Content too large")
        # read up to max_content_size
        content = r.raw.read(max_content_size + 1)
        if len(content) > max_content_size:
            raise ValueError("Content too large")
        return content.decode(r.encoding or 'utf-8', errors='replace')

def make_absolute(base_url, link):
    return urljoin(base_url, link)

# ---- Routes ----
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    """
    Request JSON body:
    {
      "url": "https://example.com/page",
      "mode": "titles" | "quotes" | "images" | "custom",
      "selector": ".myclass"  # required only if mode == "custom"
    }
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    url = data.get('url', '').strip()
    mode = data.get('mode', 'titles')
    selector = data.get('selector', '').strip()

    if not url:
        return jsonify({"error": "Please provide a URL."}), 400

    if not is_valid_scheme(url) or not is_safe_url(url):
        return jsonify({"error": "URL scheme not allowed or host is blocked for safety."}), 400

    try:
        html = fetch_html(url)
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Network error fetching URL: {str(e)}"}), 502
    except ValueError as e:
        return jsonify({"error": str(e)}), 413
    except Exception as e:
        return jsonify({"error": f"Unexpected fetch error: {str(e)}"}), 500

    soup = BeautifulSoup(html, 'html.parser')

    results = []
    try:
        if mode == 'titles':
            # gather h1..h3 text
            for h in soup.find_all(['h1', 'h2', 'h3']):
                text = h.get_text(strip=True)
                if text:
                    results.append({"type": "title", "text": text})
        elif mode == 'quotes':
            # common site pattern for quotes is .text or blockquote
            # We try both: <span class="text"> and <blockquote>
            found = soup.find_all('span', class_='text')
            if not found:
                found = soup.find_all('blockquote')
            for el in found:
                txt = el.get_text(strip=True)
                if txt:
                    results.append({"type": "quote", "text": txt})
        elif mode == 'images':
            imgs = soup.find_all('img')
            for img in imgs:
                src = img.get('src') or img.get('data-src')
                alt = img.get('alt', '')
                if src:
                    abs_url = make_absolute(url, src)
                    results.append({"type": "image", "src": abs_url, "alt": alt})
        elif mode == 'custom':
            if not selector:
                return jsonify({"error": "Custom selector mode requires 'selector' value."}), 400
            elements = soup.select(selector)
            for el in elements:
                # if it's an image element, prefer src
                if el.name == 'img':
                    src = el.get('src') or el.get('data-src')
                    if src:
                        results.append({"type": "image", "src": make_absolute(url, src), "alt": el.get('alt', '')})
                else:
                    text = el.get_text(separator=' ', strip=True)
                    results.append({"type": "custom", "text": text, "html": str(el)})
        else:
            return jsonify({"error": "Invalid mode chosen."}), 400

    except Exception as e:
        return jsonify({"error": f"Error parsing HTML: {str(e)}"}), 500

    return jsonify({"url": url, "mode": mode, "count": len(results), "results": results})

if __name__ == '__main__':
    # Use host=0.0.0.0 if you deploy; debug False in production
    app.run(debug=True)
