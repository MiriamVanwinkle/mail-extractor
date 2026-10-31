from flask import Flask, render_template, request, jsonify
import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

def extract_links_from_email(msg):
    links = []
    for part in msg.walk():
        content_type = part.get_content_type()
        content_disposition = str(part.get("Content-Disposition"))
        if "attachment" not in content_disposition:
            if content_type == "text/html":
                html_content = part.get_payload(decode=True).decode(errors='ignore')
                soup = BeautifulSoup(html_content, 'html.parser')
                for a_tag in soup.find_all('a', href=True):
                    href = a_tag['href']
                    if href.startswith('http'):
                        links.append(href)
            elif content_type == "text/plain":
                text_content = part.get_payload(decode=True).decode(errors='ignore')
                found_links = re.findall(r'https?://[^\s<>"]+', text_content)
                links.extend(found_links)
    return list(set(links))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract_emails():
    data = request.json
    email_user = data.get('email')
    app_password = data.get('password')
    category = data.get('category', 'Primary')
    count = int(data.get('count', 15))
    results = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_user, app_password)
        mail.select("inbox")
        search_query = f'(CATEGORY "{category}")'
        status, messages = mail.search(None, search_query)
        if status != "OK" or not messages[0]:
            return jsonify({"error": "No emails found."}), 404
        mail_ids = messages[0].split()
        latest_ids = mail_ids[-count:]
        latest_ids.reverse()
        for i in latest_ids:
            res, msg_data = mail.fetch(i, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    from_ = msg.get("From")
                    date_ = msg.get("Date")
                    if from_ and "<" in from_:
                        from_name = from_.split("<")[0].strip()
                        from_email = from_.split("<")[1].replace(">", "").strip()
                    else:
                        from_name = from_ if from_ else "Unknown"
                        from_email = from_ if from_ else "Unknown"
                    links = extract_links_from_email(msg)
                    results.append({
                        "from_name": from_name,
                        "from_email": from_email,
                        "subject": subject,
                        "date": date_,
                        "category": category,
                        "links": links
                    })
        mail.logout()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)