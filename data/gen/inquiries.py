"""UC1 ソラハ電機（架空）のサポート窓口に届いた問い合わせ。

事実（到着からの日数・不具合か仕様か・用件の組み合わせ）を先に乱数で決め、
正解のラベルは「分類の手引き」（GUIDE）の規則をコードで当てて決める。文章はその事実を書き表すだけ。
LLM は使わない（同じ seed なら一字一句同じものができる）。
"""
from __future__ import annotations

import datetime as dt
import random

LABELS = ["返品・交換", "修理・故障", "配送", "請求・支払い", "使い方", "会員・解約"]

GUIDE = """# ソラハ電機 サポート窓口 問い合わせ分類の手引き（架空）

ラベルは次の 6 つから 1 つだけ選ぶ。
- 返品・交換 / 修理・故障 / 配送 / 請求・支払い / 使い方 / 会員・解約

規則
R0. 用件が複数あるときは、先に主な用件を 1 つに決める。お金が動く用件（返品・交換、返金、請求の訂正）があればそれ。
    どれも無ければ、先に書かれている用件。以下の規則は、その主な用件に当てる。
R1. 下の「仕様（故障ではない）」に当たる症状は「使い方」（不具合の言い方をしていても、交換を望んでいても）。
R2. 商品の不具合の申し出は、**商品の到着日から 14 日以内**なら「返品・交換」、15 日目以降なら「修理・故障」。
    日数は注文日ではなく到着日から、受付日までを数える。到着日当日は 0 日目。
R3. 不具合ではない返品の希望（イメージ違い・サイズ違い・誤って注文）は「返品・交換」。
R4. 送料・代引き手数料・配送料・速達料金の請求や返金は「請求・支払い」（配送の話に見えても、お金が用件なら請求）。
R5. 届かない・届く日時を変えたい・届け先を変えたい・再配達は「配送」。
R6. パスワード・会員情報・メール配信の停止・退会は「会員・解約」。

仕様（故障ではない）
- 電気ケトル KT-20: 使い始めの数回、樹脂のにおいがする
- 空気清浄機 AP-300: 約 1 年でフィルター交換ランプが点灯する（交換すれば消える）
- 炊飯器 RC-5: 保温中に「カチッ」という音がする
- コードレス掃除機 VC-8: 強モードで連続 20 分使うと過熱防止で止まる（30 分ほどで再開できる）
- ワイヤレスイヤホン EB-1: 片耳だけつながるときは、両方をケースに戻して 10 秒待つと直る
"""

PRODUCTS = {
    "電気ケトル KT-20": {"defects": ["底から水が漏れる", "スイッチを入れても沸かない", "電源ランプがつかない"],
                     "normal": "使い始めてから樹脂のようなにおいがする（まだ 2 回しか使っていない）"},
    "空気清浄機 AP-300": {"defects": ["電源が入らない", "ファンから異音がして止まる", "風がまったく出ない"],
                       "normal": "フィルター交換のランプが点灯した。買ってからちょうど 1 年くらい"},
    "炊飯器 RC-5": {"defects": ["ご飯が炊けずに芯が残る", "表示が消えて操作できない", "内ぶたのパッキンが割れていた"],
                  "normal": "保温中にカチッという音が時々する"},
    "コードレス掃除機 VC-8": {"defects": ["充電しても動かない", "ヘッドのブラシが回らない", "バッテリーが 2 分でなくなる"],
                         "normal": "強モードで 20 分ほど使っていたら止まってしまった"},
    "ワイヤレスイヤホン EB-1": {"defects": ["ケースに入れても充電できない", "右側から音がまったく出ない（ケースに戻しても同じ）",
                                     "電源が入らない"],
                            "normal": "片耳だけしかつながらない"},
    "電子レンジ MW-7": {"defects": ["温めが始まらない", "庫内灯がつかず回らない", "扉が閉まらない"], "normal": None},
}

NAMES = ["山岸", "小野寺", "三好", "大槻", "久保田", "相沢", "江口", "菅野", "土屋", "中津", "成瀬", "早瀬",
         "日比野", "深町", "真柴", "宮森", "八木沢", "吉成", "若菜", "朝比奈"]

CHANNELS = ["web", "mail", "phone"]

# シナリオ: (名前, 正解を決める関数, 難しさ, 重み)
SCENARIOS = [
    ("defect_early", "rule", 10), ("defect_late", "rule", 10), ("defect_boundary", "rule", 5),
    ("change_mind", "easy", 6), ("not_arrived", "easy", 7), ("delivery_change", "easy", 5),
    ("shipping_fee", "rule", 6), ("double_charge", "easy", 6), ("payment_method", "easy", 3),
    ("normal_behavior", "rule", 8), ("howto", "easy", 7), ("account", "easy", 8),
    ("multi_late_fee", "multi", 4), ("multi_howto_account", "multi", 3), ("multi_defect_howto", "multi", 4),
    ("multi_account_charge", "multi", 3),
]


def _date_phrase(rng, inquiry: dt.date, days: int) -> tuple[str, str]:
    """到着からの日数を、いろいろな書き方で。返り値: (文, 書き方の種類)"""
    arrived = inquiry - dt.timedelta(days=days)
    kind = rng.choice(["rel", "abs", "abs", "order_distractor"])
    if kind == "rel":
        s = {14: "ちょうど 2 週間前に届きました", 7: "1 週間前に届きました"}.get(days, f"{days} 日前に届きました")
        return s, kind
    if kind == "abs":
        return f"{arrived.month} 月 {arrived.day} 日に届きました", kind
    ordered = arrived - dt.timedelta(days=rng.choice([3, 4, 5, 6]))
    return (f"{ordered.month} 月 {ordered.day} 日に注文して、{arrived.month} 月 {arrived.day} 日に届きました"), kind


def _wrap(rng, channel: str, name: str, body: str, subject: str) -> str:
    if channel == "web":
        return f"{body}\nよろしくお願いいたします。（{name}）"
    if channel == "mail":
        return (f"件名: {subject}\n\nソラハ電機 サポートご担当者様\n\nいつもお世話になっております。{name}と申します。\n"
                f"{body}\nお手数ですが、ご確認のほどよろしくお願いいたします。\n\n{name}")
    # 電話の受付メモ（オペレーターの書き方）
    memo = body.replace("です。", "とのこと。").replace("ます。", "ますとのこと。")
    return f"【電話受付メモ】{name}様より入電。{memo}折り返し希望。"


def make(seed: int = 20261018, n: int = 600) -> list[dict]:
    rng = random.Random(seed)
    names = [s for s, _, w in SCENARIOS for _ in range(w)]
    diff = {s: d for s, d, _ in SCENARIOS}
    rows = []
    for i in range(n):
        sc = rng.choice(names)
        inquiry = dt.date(2026, 8, 1) + dt.timedelta(days=rng.randrange(61))
        channel = rng.choices(CHANNELS, weights=[5, 3, 2])[0]
        name = rng.choice(NAMES)
        prod = rng.choice(list(PRODUCTS))
        p = PRODUCTS[prod]
        facts: dict = {"scenario": sc, "product": prod}
        if sc in ("defect_early", "defect_late", "defect_boundary", "multi_defect_howto"):
            if sc == "defect_early" or sc == "multi_defect_howto":
                days = rng.choice([1, 2, 3, 5, 7, 9, 10, 12])
            elif sc == "defect_late":
                days = rng.choice([16, 18, 21, 25, 30, 45, 60])
            else:
                days = rng.choice([13, 14, 15, 16])
            phrase, kind = _date_phrase(rng, inquiry, days)
            d = rng.choice(p["defects"])
            want = rng.choice(["交換してもらえますか", "どうすればよいでしょうか", "対応をお願いします", "返金か交換を希望します"])
            body = f"{prod}を購入しました。{phrase}。{d}。{want}。"
            if sc == "multi_defect_howto":
                other = rng.choice([q for q in PRODUCTS if q != prod])
                body += f"あと、別に持っている{other}のタイマーの設定方法も教えてください。"
            label = "返品・交換" if days <= 14 else "修理・故障"
            facts.update(days=days, date_kind=kind)
            subject = f"{prod.split()[0]}の不具合について"
        elif sc == "change_mind":
            why = rng.choice(["思っていた色と違った", "サイズが置き場所に合わなかった", "同じものを家族が先に買っていた",
                              "型番を間違えて注文してしまった"])
            body = f"{prod}を注文しましたが、{why}ので返品したいです。箱は開けていません。"
            label, subject = "返品・交換", "返品の希望"
        elif sc == "not_arrived":
            days = rng.choice([5, 7, 10])
            body = f"{days} 日前に{prod}を注文しましたが、まだ届きません。発送されているか確認していただけますか。"
            label, subject = "配送", "商品が届きません"
        elif sc == "delivery_change":
            body = rng.choice([f"注文した{prod}の配達日を来週の土曜日に変えたいです。",
                               f"{prod}の届け先を実家の住所に変えたいのですが、間に合いますか。",
                               f"不在票が入っていた{prod}の再配達をお願いしたいです。"])
            label, subject = "配送", "配達について"
        elif sc == "shipping_fee":
            body = rng.choice([f"{prod}を注文したら、送料無料のはずなのに送料 800 円が請求されていました。配送の条件を確認して訂正してください。",
                               f"{prod}の配送で代引き手数料が 2 回分かかっています。配送業者の方にも聞きましたが、そちらで確認してくださいと言われました。",
                               f"{prod}をまとめて 2 台注文したのに、配送料が 2 回請求されています。同じ箱で届いたのですが。"])
            label, subject = "請求・支払い", "送料の請求について"
        elif sc == "double_charge":
            body = f"{prod}の代金がカードに 2 回請求されています。1 回分を取り消してください。"
            label, subject = "請求・支払い", "二重請求"
        elif sc == "payment_method":
            body = f"{prod}の支払い方法を、コンビニ払いからクレジットカードに変えられますか。"
            label, subject = "請求・支払い", "支払い方法の変更"
        elif sc == "normal_behavior":
            q = rng.choice([x for x in PRODUCTS if PRODUCTS[x]["normal"]])
            prod = q
            facts["product"] = q
            days = rng.choice([2, 4, 6, 20, 40])
            if q.startswith("空気清浄機"):
                body = f"{q}についてです。{PRODUCTS[q]['normal']}。故障でしょうか。交換が必要なら教えてください。"
            else:
                body = (f"{q}についてです。{PRODUCTS[q]['normal']}。故障でしょうか。"
                        f"{days} 日前に届いたばかりなので、不良品なら交換してほしいです。")
            label, subject = "使い方", f"{q.split()[0]}の様子がおかしい"
            facts["days"] = days
        elif sc == "howto":
            body = rng.choice([f"{prod}のタイマーの設定方法を教えてください。説明書をなくしてしまいました。",
                               f"{prod}のお手入れの方法が知りたいです。どのくらいの頻度で掃除すればよいですか。",
                               f"{prod}の省エネの使い方があれば教えてください。"])
            label, subject = "使い方", "使い方の質問"
        elif sc == "account":
            body = rng.choice(["会員サイトのパスワードを忘れてしまいログインできません。",
                               "メールマガジンの配信を止めたいです。", "会員を退会したいのですが、手続きを教えてください。",
                               "登録しているメールアドレスを変更したいです。"])
            label, subject = "会員・解約", "会員について"
        elif sc == "multi_late_fee":
            body = (f"{prod}が予定より 3 日遅れて届きました。急ぎで払った速達料金 500 円を返してほしいです。"
                    "配送が遅れた理由も教えてください。")
            label, subject = "請求・支払い", "配送の遅れと料金"
        elif sc == "multi_howto_account":
            first = rng.choice(["howto", "account"])
            h = f"{prod}のタイマーの使い方を教えてください。"
            a = "それと、登録しているメールアドレスを変えたいです。"
            if first == "howto":
                body, label = h + a, "使い方"
            else:
                body, label = "会員の登録メールアドレスを変えたいです。" + f"それと、{prod}のタイマーの使い方も教えてください。", "会員・解約"
            subject = "2 点お願いがあります"
            facts["first"] = first
        elif sc == "multi_account_charge":
            body = "会員を退会したいです。その前に、先月の請求に身に覚えのない 3,980 円があるので取り消してください。"
            label, subject = "請求・支払い", "退会と請求"
        else:  # pragma: no cover
            raise ValueError(sc)
        text = _wrap(rng, channel, name, body, subject)
        rows.append({"id": f"INQ-{i + 1:04d}", "received": inquiry.isoformat(), "channel": channel,
                     "text": text, "label": label, "difficulty": diff[sc], "facts": facts})
    return rows


def render(row: dict) -> str:
    """モデルに見せる形（受付日・窓口・本文）。"""
    ch = {"web": "Web フォーム", "mail": "メール", "phone": "電話"}[row["channel"]]
    return f"受付日: {row['received']}\n窓口: {ch}\n---\n{row['text']}"
