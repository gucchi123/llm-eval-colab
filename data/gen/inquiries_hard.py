"""UC1 の「育てた」試験セット v2（難問 48 件）。

v1（型から作った 120 件）は、Opus 5.5 も Sonnet 5.5 も 120/120 だった（2026-10-18 の本物の実行）。
飽和した試験では、モデルの差も、プロンプトを変えたときの劣化も見えない。そこで、手引きの規則の「境目」を
わざと突く問いを 6 種 × 8 件作った。正解は v1 と同じく、手引きの規則をコードで当てて決める。

A lookalike   : 仕様に似ているが、仕様の範囲を外れた本物の不具合（→ R2 の日数で決まる）
B month_cross : 月をまたぐ日付・相対表現で、到着から 13〜16 日の境目
C wish_vs_rule: お客様の希望（修理してほしい / 交換してほしい）と、規則のラベルが逆
D buried_money: 長い文の最後のほうに、お金の用件が埋もれている（R0）
E phone_terse : 電話受付メモの短い書き方（日付は M/D だけ）
F hedged_spec : 「故障ではないと思うが」など、仕様の症状を遠回しに書く（→ 使い方）
"""
from __future__ import annotations

import datetime as dt
import random

LOOKALIKE = [
    ("電気ケトル KT-20", "使い始めて 2 か月になりますが、樹脂のにおいが毎回だんだん強くなってきました"),
    ("コードレス掃除機 VC-8", "強モードで使うと、5 分ほどで止まってしまいます"),
    ("炊飯器 RC-5", "保温中に、カチッではなくバチッという大きな音がして、焦げたにおいがします"),
    ("ワイヤレスイヤホン EB-1", "片耳しかつながらないので、両方をケースに戻して 10 秒待ちましたが、何度やっても直りません"),
    ("空気清浄機 AP-300", "使い始めて 1 か月なのに、フィルター交換のランプが点灯しました"),
    ("コードレス掃除機 VC-8", "弱モードで使っていても 10 分で止まり、そのあと 1 時間たっても動きません"),
    ("電気ケトル KT-20", "においの件ではなく、沸騰しても自動でスイッチが切れません"),
    ("炊飯器 RC-5", "カチッという音は前からしていましたが、昨日から保温ができず冷たくなります"),
]
HEDGED = [
    ("電気ケトル KT-20", "故障ではないと思うのですが念のため。まだ 2 回しか使っていないケトルから、樹脂っぽいにおいがします"),
    ("炊飯器 RC-5", "たぶん大丈夫だと思いますが、保温にしていると時々カチッと鳴ります。気にしなくてよいですか"),
    ("コードレス掃除機 VC-8", "強モードで 20 分くらい続けて使ったら止まりました。少し置いたらまた動いたのですが、これは普通ですか"),
    ("ワイヤレスイヤホン EB-1", "片方だけ音が出ないことがあります。ケースに戻すと直るので困ってはいないのですが、不良でしょうか"),
    ("空気清浄機 AP-300", "1 年ほど使っていたらフィルターのランプがつきました。壊れたのか、交換の時期なのか教えてください"),
]
DEFECT_WORDS = {"電気ケトル KT-20": "底から水が漏れる", "炊飯器 RC-5": "ご飯が炊けずに芯が残る",
                "コードレス掃除機 VC-8": "ヘッドのブラシが回らない", "ワイヤレスイヤホン EB-1": "ケースに入れても充電できない",
                "空気清浄機 AP-300": "電源が入らない", "電子レンジ MW-7": "温めが始まらない"}


def _label_by_days(days: int) -> str:
    return "返品・交換" if days <= 14 else "修理・故障"


def make(seed: int = 20261021) -> list[dict]:
    rng = random.Random(seed)
    rows = []

    def add(kind, received, text, label, facts):
        rows.append({"id": f"HRD-{len(rows) + 1:03d}", "received": received.isoformat(), "channel": facts.pop("channel", "web"),
                     "text": text, "label": label, "difficulty": "hard", "facts": {"scenario": kind, **facts}})

    # A: 仕様に似た本物の不具合
    for prod, sym in LOOKALIKE:
        rec = dt.date(2026, 9, 1) + dt.timedelta(days=rng.randrange(30))
        days = rng.choice([4, 9, 12, 18, 26, 40])
        if "2 か月" in sym:
            days = 62        # 「使い始めて 2 か月」と矛盾しないように
        if "1 か月" in sym:
            days = 33
        arr = rec - dt.timedelta(days=days)
        text = f"{prod}についてです。{arr.month} 月 {arr.day} 日に届きました。{sym}。仕様でしょうか。\nよろしくお願いいたします。"
        add("lookalike", rec, text, _label_by_days(days), {"days": days})
    # B: 月またぎの境目
    for i in range(8):
        rec = dt.date(2026, 9, rng.choice([3, 5, 8, 10, 12]))
        days = [13, 14, 15, 16][i % 4]
        arr = rec - dt.timedelta(days=days)
        prod = rng.choice(list(DEFECT_WORDS))
        when = rng.choice([f"先月の {arr.day} 日に届いた", f"{arr.month} 月 {arr.day} 日（{'月火水木金土日'[arr.weekday()]}）に受け取った"])
        text = f"{when}{prod}ですが、{DEFECT_WORDS[prod]}状態です。どうしたらよいですか。"
        add("month_cross", rec, text, _label_by_days(days), {"days": days})
    # C: 希望と規則が逆
    for i in range(8):
        rec = dt.date(2026, 9, 1) + dt.timedelta(days=rng.randrange(30))
        prod = rng.choice(list(DEFECT_WORDS))
        if i % 2 == 0:
            days = rng.choice([3, 5, 8])
            text = (f"{days} 日前に届いた{prod}の{DEFECT_WORDS[prod]}です。返品や交換は考えていません。"
                    "気に入っているので、修理をお願いしたいです。")
        else:
            days = rng.choice([20, 35, 50])
            text = (f"{prod}が{days} 日前に届きましたが、{DEFECT_WORDS[prod]}です。修理だと時間がかかるので、"
                    "新品と交換してください。")
        add("wish_vs_rule", rec, text, _label_by_days(days), {"days": days})
    # D: 長い文に埋もれたお金の用件
    tails = [("そういえば、先月の請求で送料が 2 回分引かれていました。そちらも見てください。", "請求・支払い"),
             ("あと、カードの明細に同じ金額が 2 回載っていたので確認をお願いします。", "請求・支払い"),
             ("それと、間違えて注文した電子レンジ MW-7（未開封）は返品したいです。", "返品・交換"),
             ("最後に、速達にしたのに普通便で届いたので、速達料金を返してほしいです。", "請求・支払い")]
    for i in range(8):
        rec = dt.date(2026, 9, 1) + dt.timedelta(days=rng.randrange(30))
        prod = rng.choice(["炊飯器 RC-5", "空気清浄機 AP-300", "電気ケトル KT-20"])
        tail, lab = tails[i % 4]
        head = rng.choice([f"{prod}のタイマーの設定方法を教えてください。説明書を見たのですが、予約の時刻の合わせ方がわかりません。",
                           f"{prod}のお手入れの頻度を知りたいです。毎日使っているので、どこをどのくらい掃除すればよいか教えてください。"])
        mid = "それから、会員サイトに登録しているメールアドレスも新しいものに変えたいです。"
        add("buried_money", rec, f"{head}{mid}{tail}", lab, {})
    # E: 電話受付メモ（短い）
    for i in range(8):
        rec = dt.date(2026, 9, 1) + dt.timedelta(days=rng.randrange(28))
        prod = rng.choice(list(DEFECT_WORDS))
        days = [6, 14, 15, 22][i % 4]
        arr = rec - dt.timedelta(days=days)
        text = f"【電話メモ】{prod.split()[1]} {DEFECT_WORDS[prod]}。着 {arr.month}/{arr.day}。客は交換か修理か不明、要案内。"
        add("phone_terse", rec, text, _label_by_days(days), {"days": days, "channel": "phone"})
    # F: 遠回しの仕様（5 件）＋ 仕様の症状だが交換を強く求める（3 件）
    for prod, sym in HEDGED:
        rec = dt.date(2026, 9, 1) + dt.timedelta(days=rng.randrange(30))
        add("hedged_spec", rec, f"{sym}。", "使い方", {})
    for prod in ["電気ケトル KT-20", "コードレス掃除機 VC-8", "炊飯器 RC-5"]:
        rec = dt.date(2026, 9, 1) + dt.timedelta(days=rng.randrange(30))
        sym = {"電気ケトル KT-20": "使い始めたばかりなのに樹脂のにおいがします",
               "コードレス掃除機 VC-8": "強モードで 20 分ほど使ったら止まりました",
               "炊飯器 RC-5": "保温中にカチッと音がします"}[prod]
        add("hedged_spec", rec, f"3 日前に届いた{prod}、{sym}。不良品だと思います。すぐに新品と交換してください。", "使い方", {})
    return rows
