"""UR 木月住吉団地 8・9号棟の空室を監視し、変化があればLINEに通知する。"""
import html
import json
import os
import re
import urllib.parse
import urllib.request

API = "https://chintai.r6.ur-net.go.jp/chintai/api/bukken/detail/detail_bukken_room/"
PAGE = "https://www.ur-net.go.jp/chintai/kanto/kanagawa/40_3020.html"
TARGET_BLDGS = {"8", "9"}  # 7号棟は管理棟なので対象外
INQUIRY = "https://sumai.r6.ur-net.go.jp/chintai/s/otoiawase/danchi.html?in=1040302"
TEL = "UR賃貸ショップ日吉 045-620-8100（10-18時・水曜休）"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
# 部屋名の形を確認するため、団地全体の空室を最初の1回だけ通知する。通知済みならこのファイルができる
FORMAT_CHECK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "format_checked.txt")


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
    link = "https://www.ur-net.go.jp" + r["roomDetailLink"] if r.get("roomDetailLink") else PAGE
    return "\n".join([
        r["name"],
        f"間取り: {r.get('type', '')}",
        f"面積: {html.unescape(r.get('floorspace') or '')}",
        f"階数: {r.get('floor', '')}",
        f"家賃: {r.get('rent_normal', '')}（共益費 {r.get('commonfee', '')}）",
        f"物件: {link}",
        f"問い合わせ: {INQUIRY}",
        f"電話: {TEL}",
    ])


def notify(*texts):
    # 1回の送信に吹き出し5つまで（送信回数としては1通分）
    token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    for i in range(0, len(texts), 5):
        messages = [{"type": "text", "text": t[:4900]} for t in texts[i:i + 5]]
        req = urllib.request.Request(
            "https://api.line.me/v2/bot/message/broadcast",
            data=json.dumps({"messages": messages}).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )
        urllib.request.urlopen(req, timeout=30).read()


def main():
    if os.environ.get("TEST_NOTIFY") == "true":
        notify("【テスト】UR空室監視からの通知テストです")
    rooms = fetch_rooms()
    if rooms and not os.path.exists(FORMAT_CHECK_FILE):
        names = [r.get("name", "") for r in rooms]
        notify("【確認用・初回のみ】木月住吉団地の全空室の部屋名です\n" + "\n".join(names))
        with open(FORMAT_CHECK_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(names) + "\n")
    current = {r["id"]: describe(r) for r in rooms if is_target(r.get("name"))}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            previous = json.load(f)
    except FileNotFoundError:
        previous = None

    if previous is not None and current != previous:
        added = [v for k, v in current.items() if k not in previous]
        removed = [v.split("\n")[0] + "\n募集終了しました" for k, v in previous.items() if k not in current]
        if added or removed:
            notify(*added, *removed)
        print("\n\n".join(added + removed))
    else:
        print(f"変化なし（空室{len(current)}件）")

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
