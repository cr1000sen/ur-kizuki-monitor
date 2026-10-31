"""UR 木月住吉団地 7・8・9号棟の空室を監視し、変化があればLINEに通知する。"""
import json
import os
import re
import urllib.parse
import urllib.request

API = "https://chintai.r6.ur-net.go.jp/chintai/api/bukken/detail/detail_bukken_room/"
PAGE = "https://www.ur-net.go.jp/chintai/kanto/kanagawa/40_3020.html"
TARGET_BLDGS = {"7", "8", "9"}
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")


def fetch_rooms():
    rooms, page = [], 0
    while True:
        data = urllib.parse.urlencode({
            "shisya": "40", "danchi": "302", "shikibetu": "0",
            "orderByField": "0", "orderBySort": "0", "pageIndex": str(page), "sp": "",
        }).encode()
        req = urllib.request.Request(API, data=data, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read().decode("utf-8")) or []  # 空室なしだと null
        rooms += body
        if not body or len(rooms) >= int(body[0].get("allCount") or 0):
            return rooms
        page += 1


def is_target(name):
    m = re.match(r"\s*(\d+)号棟", name or "")
    return bool(m) and m.group(1) in TARGET_BLDGS


def describe(r):
    return f"{r['name']} {r.get('type','')} {r.get('rent_normal','')}(共益費{r.get('commonfee','')})"


def notify(text):
    token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/broadcast",
        data=json.dumps({"messages": [{"type": "text", "text": text[:4900]}]}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    urllib.request.urlopen(req, timeout=30).read()


def main():
    if os.environ.get("TEST_NOTIFY") == "true":
        notify("【テスト】UR空室監視からの通知テストです")
    current = {r["id"]: describe(r) for r in fetch_rooms() if is_target(r.get("name"))}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            previous = json.load(f)
    except FileNotFoundError:
        previous = None

    if previous is not None and current != previous:
        added = [v for k, v in current.items() if k not in previous]
        removed = [v for k, v in previous.items() if k not in current]
        lines = ["【木月住吉団地 7〜9号棟 空室更新】"]
        if added:
            lines += ["▼新着"] + added
        if removed:
            lines += ["▼募集終了"] + removed
        lines += [f"現在の空室: {len(current)}件", PAGE]
        notify("\n".join(lines))
        print("\n".join(lines))
    else:
        print(f"変化なし（空室{len(current)}件）")

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
