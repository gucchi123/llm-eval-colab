"""UC5 ソラハ電機（架空）の返信の下書き。「そのまま送ってよいか」を判定させる題材。

- 返信は、問い合わせの事実から型で組み立てる（正しい返信）。そこへ欠陥を 1 つだけ入れたものを混ぜる。
  欠陥: 規程の誤り / 次の手順が無い / お客様を責める言い方 / 窓口が約束できないことを約束
- 人のラベル = 作った側が知っている正解（欠陥を入れたら fail）。
- 模擬の評価者 3 人（A・B・C）は、決めたくせ（下の ANNOTATOR_NOISE）と乱数で正解から少しずらす。
  🔴 本物の人のラベルではない。評価者どうしの一致の計算を練習するための模擬データ。
- 対比較（どちらが良いか）の組: 同じ質の言い換え / 中身が同じで長いだけ / 長いが誤り vs 短く正しい
"""
from __future__ import annotations

import random
import re

REPLY_POLICY = """# ソラハ電機 返信の決まり（架空）
- 不具合: 商品の到着日から 14 日以内は交換または返品。15 日目以降は保証期間（1 年）内の無償修理。
- 不具合でない返品（イメージ違いなど）: 未開封・到着から 30 日以内なら受ける。返送料はお客様の負担。
- 二重請求・身に覚えのない請求: 確認のうえ、5 営業日以内に取り消す。
- 送料・手数料・速達料金の誤り: 差額を返金する。
- 届かない: 追跡番号を案内し、配送業者に確認する。日時・届け先の変更は会員サイトか返信で受ける。
- 仕様（故障ではない）の症状: 仕様であることと対処を説明する。交換はしない。
- 窓口の判断で、お詫びのポイント・クーポン・送料の負担などの金品を約束しない。
- 返信には、お客様が次にすること（手順・送るもの・窓口）を必ず 1 つ以上書く。
- お客様を責める言い方をしない。
"""

DEFECTS = ["policy_error", "no_next_step", "blame_tone", "false_promise"]

SPEC_EXPLAIN = {
    "電気ケトル KT-20": "使い始めの数回は樹脂のにおいがすることがあり、仕様です。満水で 2〜3 回お湯を沸かして捨てていただくと、においは弱まります。",
    "空気清浄機 AP-300": "フィルター交換ランプは約 1 年で点灯する仕様で、故障ではありません。交換用フィルター（AP-F3）に替えると消えます。",
    "炊飯器 RC-5": "保温中の「カチッ」という音は温度を保つための部品の音で、仕様です。",
    "コードレス掃除機 VC-8": "強モードで連続 20 分ほど使うと過熱を防ぐために止まる仕様です。30 分ほど休ませると再び使えます。",
    "ワイヤレスイヤホン EB-1": "片耳だけつながるときは、両方をケースに戻して 10 秒待ってから取り出すと直ります。",
}


def _content(row: dict) -> tuple[list[str], str, str]:
    """(本文の文, 次の手順の文, 規程を誤らせた文)。"""
    f = row["facts"]
    sc = f["scenario"]
    days = f.get("days")
    if sc in ("defect_early", "multi_defect_howto") or (sc == "defect_boundary" and days <= 14):
        return (["ご不便をおかけして申し訳ございません。",
                 "商品の到着から 14 日以内の不具合ですので、交換または返品で承ります。"],
                "お手数ですが、注文番号と症状がわかる写真を、このメールへの返信でお送りください。確認後、回収の手配をいたします。",
                "商品の到着から 30 日以内の不具合ですので、交換または返品で承ります。")
    if sc in ("defect_late", "defect_boundary"):
        return (["ご不便をおかけして申し訳ございません。",
                 "到着から 15 日以上たっておりますので、保証期間内の無償修理でのご対応となります。"],
                "会員サイトの「修理のお申し込み」から、引き取りの希望日をご指定ください。",
                "到着から日数がたっておりますが、特別に新品と交換いたします。")
    if sc == "change_mind":
        return (["ご連絡ありがとうございます。", "未開封で、到着から 30 日以内でしたら返品を承ります。返送料はお客様のご負担となります。"],
                "会員サイトの「返品のお申し込み」から手続きをお願いします。",
                "未開封でしたら、到着からの日数にかかわらず返品を承ります。")
    if sc == "not_arrived":
        return (["お待たせしており申し訳ございません。", "ご注文の商品は発送済みで、配送業者に状況を確認しております。"],
                "追跡番号は会員サイトの「注文履歴」でご確認いただけます。明日までに、こちらから状況をご連絡します。",
                "配送の遅れは当社の規定により、ご注文を自動で取り消します。")
    if sc == "delivery_change":
        return (["ご連絡ありがとうございます。", "配達日・届け先の変更を承ります。"],
                "ご希望の日時または届け先を、このメールへの返信でお知らせください。",
                "発送後の変更はお受けできない決まりです。")
    if sc in ("shipping_fee", "multi_late_fee"):
        return (["ご迷惑をおかけして申し訳ございません。", "ご請求の内容を確認し、誤って請求した送料・手数料の差額を返金いたします。"],
                "返金先の確認のため、注文番号をこのメールへの返信でお送りください。",
                "送料はご注文時に確定しておりますので、返金はできかねます。")
    if sc in ("double_charge", "multi_account_charge"):
        return (["ご迷惑をおかけして申し訳ございません。", "ご請求を確認のうえ、誤りであれば 5 営業日以内に取り消します。"],
                "カードの明細のうち、該当する 2 件の日付と金額をお知らせください。",
                "ご請求を確認のうえ、誤りであれば翌月の請求で相殺いたします。")
    if sc == "payment_method":
        return (["ご連絡ありがとうございます。", "お支払い方法は、発送前でしたら変更できます。"],
                "会員サイトの「注文履歴」から、お支払い方法の変更をお選びください。",
                "一度お選びいただいたお支払い方法は変更できません。")
    if sc == "normal_behavior":
        return (["ご心配をおかけしております。", SPEC_EXPLAIN[f["product"]]],
                "それでも症状が続く場合は、このメールに返信いただければ詳しくお調べします。",
                "初期不良と考えられますので、新品と交換いたします。")
    if sc in ("howto", "multi_howto_account"):
        return (["お問い合わせありがとうございます。", "取扱説明書は会員サイトの「サポート」から PDF でご覧いただけます。"],
                "製品の型番で検索し、「取扱説明書」を開いてください。ご不明な点があれば、このメールにご返信ください。",
                "取扱説明書の再発行は有料となります。")
    if sc == "account":
        return (["お問い合わせありがとうございます。", "会員情報の変更・配信の停止・退会は、会員サイトの「マイページ」から手続きできます。"],
                "ログインできない場合は、ログイン画面の「パスワードを忘れた方」から再設定してください。",
                "退会の手続きは書面の郵送でのみ受け付けております。")
    raise ValueError(sc)


GREET = ["{name}様\n\nソラハ電機 サポート窓口です。", "{name}様\n\nいつもソラハ電機をご利用いただき、ありがとうございます。サポート窓口でございます。"]
CLOSE = ["よろしくお願いいたします。\nソラハ電機 サポート窓口", "今後ともよろしくお願い申し上げます。\nソラハ電機 サポート窓口"]
PADDING = ["当社では、お客様に安心してご利用いただけるよう、日々サービスの改善に努めております。",
           "いただいたご意見は、今後の製品づくりとサービスの向上に役立ててまいります。",
           "ソラハ電機は、これからもお客様の暮らしに寄り添う製品をお届けしてまいります。",
           "なお、季節の変わり目は家電製品の使い方が変わりやすい時期ですので、お困りの際はいつでもご相談ください。"]
BLAME = ["取扱説明書をよくお読みいただければ、このようなお問い合わせは不要だったかと存じます。",
         "お客様のご確認不足によるものと思われますが、"]
PROMISE = ["お詫びとして、次回使える 3,000 円分のポイントをお付けします。", "今回の送料・手数料はすべて当社で負担いたします。"]


def _name(row) -> str:
    t = row["text"]
    m = re.search(r"（(.+?)）$", t) or re.search(r"(\S+?)と申します", t) or re.search(r"】(\S+?)様より", t)
    return m.group(1) if m else "お客"


def compose(row: dict, defect: str | None = None, variant: int = 0, padding: int = 0, rng=None) -> str:
    body, nxt, wrong = _content(row)
    sents = list(body)
    if defect == "policy_error":
        sents[1] = wrong
    if defect == "blame_tone":
        sents.insert(1, BLAME[variant % 2])
    parts = sents + ([] if defect == "no_next_step" else [nxt])
    if defect == "false_promise":
        parts.append(PROMISE[variant % 2])
    parts += PADDING[:padding]
    return GREET[variant % 2].format(name=_name(row)) + "\n\n" + "\n".join(parts) + "\n\n" + CLOSE[variant % 2]


# 模擬の評価者のくせ: (正解を反転する確率, 欠陥の種類ごとに見逃す確率, 正しい返信を fail にする確率)
ANNOTATOR_NOISE = {
    "A": {"flip": 0.03, "miss": {}, "strict": 0.0},
    "B": {"flip": 0.03, "miss": {"blame_tone": 0.6}, "strict": 0.0},       # 言い方には甘い
    "C": {"flip": 0.03, "miss": {"false_promise": 0.3}, "strict": 0.15},  # 正しい返信にも厳しめ
}


def make(pool: list[dict], exclude: set[str], seed: int = 20261020) -> dict:
    rng = random.Random(seed)
    # 用件が複数ある問い合わせは使わない（片方にしか答えない返信を「正しい」と言えないため）
    cand = [r for r in pool if r["id"] not in exclude and r["difficulty"] != "multi"]
    rng.shuffle(cand)
    # 場面がかたよらないように、シナリオごとに順に拾う
    by_sc: dict[str, list] = {}
    for r in cand:
        by_sc.setdefault(r["facts"]["scenario"], []).append(r)
    picked = []
    while len(picked) < 132:
        for sc in sorted(by_sc):
            if by_sc[sc] and len(picked) < 132:
                picked.append(by_sc[sc].pop())
    graded = picked[:80]
    defects = [None] * 44 + [d for d in DEFECTS for _ in range(9)]
    rng.shuffle(defects)
    replies = []
    for r, d in zip(graded, defects):
        v = rng.randrange(2)
        replies.append({"id": f"RPL-{len(replies) + 1:03d}", "inquiry_id": r["id"], "inquiry": r["text"],
                        "received": r["received"], "channel": r["channel"],
                        "reply": compose(r, d, variant=v), "defect": d, "label": "fail" if d else "pass"})
    # 模擬の評価者
    for rep in replies:
        for who, nz in ANNOTATOR_NOISE.items():
            lab = rep["label"]
            if rep["defect"] and rng.random() < nz["miss"].get(rep["defect"], 0):
                lab = "pass"
            elif not rep["defect"] and rng.random() < nz["strict"]:
                lab = "fail"
            if rng.random() < nz["flip"]:
                lab = "pass" if lab == "fail" else "fail"
            rep.setdefault("annotators", {})[who] = lab
    # 対比較の組（残りの問い合わせを使う）
    rest = picked[80:]
    pairs = []
    for r in rest[:20]:
        pairs.append({"id": f"EQ-{len(pairs) + 1:02d}", "kind": "equal", "inquiry": r["text"], "received": r["received"],
                      "a": compose(r, None, variant=0), "b": compose(r, None, variant=1), "better": None})
    for r in rest[20:40]:
        pairs.append({"id": f"LEN-{len(pairs) - 19:02d}", "kind": "length", "inquiry": r["text"], "received": r["received"],
                      "a": compose(r, None, variant=0), "b": compose(r, None, variant=0, padding=4), "better": None})
    for r in rest[40:52]:
        pairs.append({"id": f"LW-{len(pairs) - 39:02d}", "kind": "long_wrong", "inquiry": r["text"], "received": r["received"],
                      "a": compose(r, None, variant=0), "b": compose(r, "policy_error", variant=1, padding=4), "better": "a"})
    return {"replies": replies, "pairs": pairs, "policy": REPLY_POLICY, "annotator_noise": ANNOTATOR_NOISE}
