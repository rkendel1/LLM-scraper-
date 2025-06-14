import hashlib
import os
import json

def get_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def load_history(domain):
    history_file = f"history/{domain}.json"
    if not os.path.exists("history"):
        os.makedirs("history")
    if os.path.exists(history_file):
        with open(history_file, 'r') as f:
            return json.load(f)
    return {}

def save_history(domain, data):
    with open(f"history/{domain}.json", 'w') as f:
        json.dump(data, f)

def has_changed(url, current_text, domain):
    history = load_history(domain)
    old_hash = history.get(url)
    new_hash = get_hash(current_text)
    if old_hash == new_hash:
        return False
    history[url] = new_hash
    save_history(domain, history)
    return True
