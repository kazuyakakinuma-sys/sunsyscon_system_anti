"""
Phase 01: 楽天銀行CSVの正規化処理
- 楽天銀行の入出金明細CSV（Shift-JIS）を読み込む
- 振込名義をフリガナに正規化・変換する（ルールは `rules_furigana.py` を参照）
- 処理したデータを csv_export フォルダへ出力する
"""

import csv
import os
import glob
from rules_furigana import (
    DAKUTEN_MAP, 
    HANDAKUTEN_MAP, 
    YOON_MAP, 
    PROTECTED_SUBSTRINGS, 
    CUSTOM_REPLACEMENTS, 
    EXCLUDED_PATTERNS
)

# ─────────────────────────────────────────────
# 変換ロジック
# ─────────────────────────────────────────────

def apply_custom_replacements(name: str) -> str:
    """事前の個別置換・削除を適用する（例: リユウシ→リユウジ、スマホ代削除など）"""
    for old_str, new_str in CUSTOM_REPLACEMENTS:
        name = name.replace(old_str, new_str)
    return name

def combine_dakuten(text: str) -> str:
    """独立した半濁点(゛)・半濁点(゜)を直前の文字と結合する"""
    result = []
    i = 0
    while i < len(text):
        if i + 1 < len(text) and text[i + 1] in ('゛', '\u3099'):
            result.append(DAKUTEN_MAP.get(text[i], text[i]))
            i += 2
        elif i + 1 < len(text) and text[i + 1] in ('゜', '\u309A'):
            result.append(HANDAKUTEN_MAP.get(text[i], text[i]))
            i += 2
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)

def apply_yoon(text: str) -> str:
    """拗音変換：全角スペースで割った単語ごとに適用する。
    ホワイトリストに登録された苗字・パターンはプレースホルダーで保護し変換をスキップする。
    """
    segments = text.split('　')  # 全角スペースで分割
    converted_segments = []

    for seg in segments:
        # 1. ホワイトリスト内のパターンをプレースホルダーに一時置換
        placeholder_map = {}  # {placeholder: original}
        for i, protected in enumerate(PROTECTED_SUBSTRINGS):
            if protected in seg:
                placeholder = f'\x00{i:04d}\x00'  # NULL文字を含むプレースホルダー
                placeholder_map[placeholder] = protected
                seg = seg.replace(protected, placeholder)

        # 2. 拗音変換を適用
        for before, after in YOON_MAP:
            seg = seg.replace(before, after)

        # 3. プレースホルダーを元の文字列に復元
        for placeholder, original in placeholder_map.items():
            seg = seg.replace(placeholder, original)

        converted_segments.append(seg)

    return ''.join(converted_segments)

def remove_non_katakana(text: str) -> str:
    """カタカナ以外（漢字・数字・記号・英字・ハイフン・スペース）を削除する"""
    return ''.join(c for c in text if '\u30A0' <= c <= '\u30FF')

def convert_furigana(name: str) -> str:
    """振込名義をフリガナに正規化する一連の処理
    - 除外パターンを含む場合は空欄を返す
    """
    # 0. 個別置換・削除（スマホ代など行の一部修正）
    name = apply_custom_replacements(name)

    # 1. 除外パターンチェック（自社出金や法人の一部など行全体の除外）
    for pattern in EXCLUDED_PATTERNS:
        if pattern in name:
            return ''

    # 2. 基本処理（半濁点結合 → 拗音変換 → カタカナ抽出）
    text = combine_dakuten(name)
    text = apply_yoon(text)
    text = remove_non_katakana(text)
    
    return text


# ─────────────────────────────────────────────
# CSVファイル処理フロー
# ─────────────────────────────────────────────

def process_csv(input_path: str, output_path: str):
    """1つのCSVを読み込み、Phase01の正規化処理を適用して出力する"""
    rows = []
    # 楽天銀行のダウンロードCSVは Shift-JIS
    with open(input_path, 'r', encoding='shift-jis', errors='replace') as f:
        reader = csv.reader(f)
        _header = next(reader, None)  # ヘッダー行をスキップ
        for row in reader:
            rows.append(row)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        
        # ヘッダー：変換前・変換後を並べて確認しやすくする
        writer.writerow(['取引日', '入出金(円)', '累計(円)', '振込名義（変換前）', '振込名義（変換後フリガナ）'])

        for row in rows:
            # A:取引日(0), B:入出金(1), C:累計(2), D:振込名義(3) の4列構成
            if len(row) < 4:
                continue
                
            date     = row[0].strip()
            amount   = row[1].strip()
            balance  = row[2].strip()
            name     = row[3].strip()
            
            # フリガナの正規化処理を実行
            furigana = convert_furigana(name)
            
            writer.writerow([date, amount, balance, name, furigana])

    print(f'  行数: {len(rows)} 件')

def main():
    base_dir   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_dir  = os.path.join(base_dir, 'csv_import')
    output_dir = os.path.join(base_dir, 'csv_export')

    csv_files = glob.glob(os.path.join(input_dir, '*.csv'))
    if not csv_files:
        print('[WARNING] csv_import/ にCSVファイルが見つかりません')
        return

    for input_file in csv_files:
        filename    = os.path.basename(input_file)
        # 出力ファイル名を相応しいプレフィックスに変更
        output_file = os.path.join(output_dir, f'phase01_{filename}')
        
        print(f'[変換中] {filename}')
        process_csv(input_file, output_file)
        print(f'[完了]   csv_export/phase01_{filename}')

    print('\n完了')

if __name__ == '__main__':
    main()
