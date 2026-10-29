# SELFCHECK ― 自己検査

- 実行日時: 2026-10-18 11:53
- 環境: Windows 11 ARM64 / Python 3.13.14

| 状態 | 結果 | pytest | 秒 |
|---|---|---|---:|
| きれいなコピー（記録なし・キーなし・provider=mock） | OK | 41 passed, 3 skipped in 1.53s | 2.0 |
| 講師の記録あり（再生が本物の実行と一致するか。API は呼ばない） | OK | 44 passed in 1.52s | 2.0 |

- コピー側に API の台帳ができていない（API を呼んでいない）: 確認
- キーらしい文字列（sk-ant-…）: 0 件

**全部 OK**
