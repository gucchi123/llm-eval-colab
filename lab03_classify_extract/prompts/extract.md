あなたはツバクロ少額短期保険（架空）の事務担当です。保険金の請求書から、次の 6 項目を取り出してください。

- policy_no: 証券番号。半角で「TB-26-123456」の形
- claimant: 請求者（契約者）の氏名。空白を入れない（例: 秋津彩花）
- incident_date: 事故の日。「YYYY-MM-DD」。年が書かれていなければ、提出日・送信日の年とする
- claim_amount: 請求する金額（円、整数）。購入価格や最初の見積もりではなく、請求すると書かれている金額
- category: 「携行品損害」「個人賠償責任」「傷害通院」のどれか
- receipt_attached: 領収書がこの請求書に添付・同封されていれば true。後日送る・無い・再発行中なら false

出力は JSON だけにしてください。
{"policy_no": "...", "claimant": "...", "incident_date": "YYYY-MM-DD", "claim_amount": 0, "category": "...", "receipt_attached": true}

請求書:
{doc}
