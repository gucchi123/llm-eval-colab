"""UC2 ツバクロ少額短期保険（架空）に届いた保険金の請求書。

項目の正解（証券番号・請求者・事故日・請求額・事故の種類・領収書の添付）を先に決め、
書式（様式・手紙・メール）と表記（和暦・全角・漢数字・「万」）をばらして文章にする。
請求額と紛らわしい金額（購入価格・見積額）をわざと混ぜる。LLM は使わない。
"""
from __future__ import annotations

import datetime as dt
import random

FIELDS = ["policy_no", "claimant", "incident_date", "claim_amount", "category", "receipt_attached"]
CATEGORIES = ["携行品損害", "個人賠償責任", "傷害通院"]

SURNAMES = ["秋津", "飯塚", "石動", "梅宮", "大鳥", "加賀谷", "桐生", "九条", "小比類巻", "佐久間", "篠宮", "鈴鹿",
            "高遠", "千早", "鶴見", "時任", "七海", "羽生田", "日向", "御影"]
GIVEN = ["彩花", "一真", "絢子", "慎吾", "千尋", "大樹", "直美", "春香", "浩介", "美咲", "悠人", "陽菜"]

ZEN = str.maketrans("0123456789", "０１２３４５６７８９")
KAN = "〇一二三四五六七八九"


def _kanji_num(n: int) -> str:
    """12800 → 一万二千八百（請求書で時々ある書き方）。"""
    def under10k(x):
        s = ""
        for unit, word in ((1000, "千"), (100, "百"), (10, "十")):
            d = x // unit
            if d:
                s += ("" if d == 1 else KAN[d]) + word
            x %= unit
        return s + (KAN[x] if x else "")
    man, rest = divmod(n, 10000)
    return (under10k(man) + "万" if man else "") + under10k(rest)


def _fmt_amount(rng, n: int) -> str:
    k = rng.choice(["comma", "comma", "yen", "man", "zen", "kanji"])
    if k == "comma":
        return f"{n:,}円"
    if k == "yen":
        return f"¥{n:,}"
    if k == "man" and n >= 10000:
        man, rest = divmod(n, 10000)
        return f"{man}万{rest:,}円" if rest else f"{man}万円"
    if k == "zen":
        return f"{n:,}円".translate(ZEN)
    if k == "kanji":
        return f"金{_kanji_num(n)}円"
    return f"{n:,}円"


def _fmt_date(rng, d: dt.date, submitted: dt.date) -> str:
    k = rng.choice(["seireki", "wareki", "slash", "md_weekday", "r_dot"])
    if k == "seireki":
        return f"{d.year}年{d.month}月{d.day}日"
    if k == "wareki":
        return f"令和{d.year - 2018}年{d.month}月{d.day}日"
    if k == "slash":
        return f"{d.year}/{d.month:02d}/{d.day:02d}"
    if k == "md_weekday":
        return f"{d.month}月{d.day}日（{'月火水木金土日'[d.weekday()]}）"   # 年は提出日から読む
    return f"R{d.year - 2018}.{d.month}.{d.day}"


def make(seed: int = 20261019, n: int = 48) -> list[dict]:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        cat = CATEGORIES[i % 3]
        submitted = dt.date(2026, 9, 1) + dt.timedelta(days=rng.randrange(40))
        incident = submitted - dt.timedelta(days=rng.randrange(3, 50))
        if incident.year != submitted.year:
            incident = submitted - dt.timedelta(days=5)
        name = rng.choice(SURNAMES) + " " + rng.choice(GIVEN)
        policy = f"TB-26-{rng.randrange(100000, 999999)}"
        receipt = rng.random() < 0.6
        receipt_txt = rng.choice(["領収書を添付します。", "領収書：添付あり", "領収書のコピーを同封しました。"]) if receipt else \
            rng.choice(["領収書は後日郵送します。", "レシートはなくしてしまいました。", "領収書：なし（再発行を依頼中）"])
        if cat == "携行品損害":
            item = rng.choice(["デジタルカメラ", "スマートフォン", "腕時計", "ノートパソコン", "スーツケース"])
            price = rng.choice([35000, 48000, 62000, 89800, 120000])
            amount = rng.choice([8800, 12800, 15400, 23000, 31500, 46200])
            place = rng.choice(["旅行先の駅のホーム", "ホテルのロビー", "観光地の展望台", "空港の手荷物受取所"])
            story = (f"{place}で{item}を落として壊してしまいました。購入時の価格は{_fmt_amount(rng, price)}でしたが、"
                     f"修理の見積もりが{_fmt_amount(rng, amount)}でしたので、この修理代を請求します。")
        elif cat == "個人賠償責任":
            amount = rng.choice([18000, 27500, 54000, 76000, 98000])
            est2 = amount + rng.choice([12000, 20000, 33000])
            obj = rng.choice(["駐車中の車", "店の陳列棚", "隣家の植木鉢", "知人のタブレット"])
            story = (f"自転車で走行中に{obj}にぶつかり、傷をつけてしまいました。相手の方から最初は{_fmt_amount(rng, est2)}の見積もりを"
                     f"示されましたが、話し合いで{_fmt_amount(rng, amount)}を支払うことになり、この額を請求します。")
        else:
            days = rng.choice([3, 4, 6, 8, 10])
            daily = 3000
            amount = days * daily
            story = (f"階段で足をすべらせて転び、足首をねんざしました。整形外科に{days}日通院しました。"
                     f"通院保険金（日額{daily:,}円）として、{_fmt_amount(rng, amount)}を請求します。")
        fmt = rng.choice(["form", "letter", "mail"])
        d_txt = _fmt_date(rng, incident, submitted)
        if fmt == "form":
            text = (f"保険金請求書\n提出日：{submitted.year}年{submitted.month}月{submitted.day}日\n証券番号：{policy}\n"
                    f"ご請求者：{name}\n事故日：{d_txt}\n事故の内容：{story}\n{receipt_txt}")
        elif fmt == "letter":
            text = (f"ツバクロ少額短期保険 御中\n\n{submitted.year}年{submitted.month}月{submitted.day}日\n\n"
                    f"いつもお世話になっております。証券番号{policy}の契約者、{name}です。\n"
                    f"{d_txt}、{story}\n{receipt_txt}\nどうぞよろしくお願いいたします。")
        else:
            text = (f"件名：保険金の請求（{policy}）\n送信日：{submitted.isoformat()}\n\n"
                    f"{name.split()[0]}です（契約者 {name}）。{story}\n事故があったのは{d_txt}です。\n{receipt_txt}")
        if rng.random() < 0.3:
            text = text.replace(policy, policy.translate(ZEN))
        rows.append({"id": f"CLM-{i + 1:03d}", "text": text, "format": fmt,
                     "gold": {"policy_no": policy, "claimant": name.replace(" ", ""),
                              "incident_date": incident.isoformat(), "claim_amount": amount,
                              "category": cat, "receipt_attached": receipt}})
    return rows
