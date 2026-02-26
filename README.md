# sunsyscon

楽天銀行の入金履歴CSVと、kintone各アプリからエクスポートしたCSVを照合・処理し、  
kintoneへ一括インポートできる更新用CSVを自動生成する **Webアプリ**。

---

## プロジェクト概要

| 項目 | 内容 |
|------|------|
| 目的 | 入金照合・kintone更新作業の効率化 |
| 入力① | 楽天銀行 入金履歴CSV（Shift-JIS） |
| 入力② | kintone各アプリからエクスポートしたCSV（6アプリ） |
| 出力 | kintoneインポート用CSV |
| kintone連携方法 | CSVインポート（API不使用） |
| 形態 | Webアプリ（開発中） |

---

## ディレクトリ構成

```
sunsyscon/
├── .gitignore               # csv_import/ csv_export/ は除外（個人情報保護）
├── README.md                # このファイル
├── docs/
│   ├── spec.md              # システム仕様書（随時更新）
│   └── dev_log.md           # 開発ログ・意思決定の記録
└── scripts/
    └── step3_convert_furigana.py  # STEP3: 振込名義フリガナ変換スクリプト
```

> ⚠️ `csv_import/` `csv_export/` フォルダはローカルに手動作成してください（個人情報保護のためGit管理外）

---

## セットアップ（別PCで引き継ぐ場合）

### 1. リポジトリをクローン
```bash
git clone https://github.com/kazuyakakinuma-sys/sunsyscon_system_anti.git
cd sunsyscon_system_anti
```

### 2. 必要なフォルダを手動作成
```bash
mkdir csv_import
mkdir csv_export
```

### 3. 動作確認（Python 3 が必要）
```bash
# 楽天銀行CSVを csv_import/ に配置してから実行
python3 scripts/step3_convert_furigana.py
# → csv_export/ に変換済みCSVが生成される
```

---

## 処理フロー（現在の実装状況）

| ステップ | 内容 | 状態 |
|---------|------|------|
| STEP 1 | 楽天銀行CSVを読み込む | ✅ スクリプト実装済み |
| STEP 2 | kintone各アプリCSVを読み込む | 🔲 未実装 |
| STEP 3 | 振込名義をフリガナに正規化・変換 | ✅ スクリプト実装済み |
| STEP 4〜 | 照合・算出処理 | 🔲 未実装（仕様整理中） |
| 最終STEP | kintoneインポート用CSV生成 | 🔲 未実装 |

---

## 必要環境

- Python 3.x（追加ライブラリ不要・標準ライブラリのみ使用）

---

## 詳細仕様

→ [`docs/spec.md`](docs/spec.md) を参照

## 開発ログ・意思決定の経緯

→ [`docs/dev_log.md`](docs/dev_log.md) を参照
