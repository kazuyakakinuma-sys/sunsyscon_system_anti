"""
STEP 3: 振込名義の正規化・変換スクリプト
- 楽天銀行CSV（Shift-JIS）を読み込み、振込名義をフリガナに変換して csv_export に出力する
"""

import csv
import os
import glob


# ─────────────────────────────────────────────
# 変換処理
# ─────────────────────────────────────────────

DAKUTEN_MAP = {
    'カ': 'ガ', 'キ': 'ギ', 'ク': 'グ', 'ケ': 'ゲ', 'コ': 'ゴ',
    'サ': 'ザ', 'シ': 'ジ', 'ス': 'ズ', 'セ': 'ゼ', 'ソ': 'ゾ',
    'タ': 'ダ', 'チ': 'ヂ', 'ツ': 'ヅ', 'テ': 'デ', 'ト': 'ド',
    'ハ': 'バ', 'ヒ': 'ビ', 'フ': 'ブ', 'ヘ': 'ベ', 'ホ': 'ボ',
    'ウ': 'ヴ',
}

HANDAKUTEN_MAP = {
    'ハ': 'パ', 'ヒ': 'ピ', 'フ': 'プ', 'ヘ': 'ペ', 'ホ': 'ポ',
}

# 拗音変換マップ（ヤ行・ユ行・ヨ行）
YOON_MAP = [
    # ヤ行（安全に変換）
    ('キヤ', 'キャ'), ('シヤ', 'シャ'), ('チヤ', 'チャ'), ('ニヤ', 'ニャ'),
    ('ヒヤ', 'ヒャ'), ('ミヤ', 'ミャ'), ('リヤ', 'リャ'),
    ('ギヤ', 'ギャ'), ('ジヤ', 'ジャ'), ('ビヤ', 'ビャ'), ('ピヤ', 'ピャ'),
    # ユ行（ミユは名前として保持するため除外）
    ('キユ', 'キュ'), ('シユ', 'シュ'), ('チユ', 'チュ'), ('ニユ', 'ニュ'),
    ('ヒユ', 'ヒュ'), ('リユ', 'リュ'),
    ('ギユ', 'ギュ'), ('ジユ', 'ジュ'), ('ビユ', 'ビュ'), ('ピユ', 'ピュ'),
    # ヨ行
    ('キヨ', 'キョ'), ('シヨ', 'ショ'), ('チヨ', 'チョ'), ('ニヨ', 'ニョ'),
    ('ヒヨ', 'ヒョ'), ('ミヨ', 'ミョ'), ('リヨ', 'リョ'),
    ('ギヨ', 'ギョ'), ('ジヨ', 'ジョ'), ('ビヨ', 'ビョ'), ('ピヨ', 'ピョ'),
]

# 促音（ッ）に変換される前の文字として有効な子音開始カタカナ
# ※ 名前内で誤変換が多発するため促音変換は不使用
# SOKUON_TARGETS = set(...)


# ═════════════════════════════════════════════
# ホワイトリスト（変換保護対象の苗字・名前パターン）
# 追加する場合はこのリストに追記するだけでOK
# ═════════════════════════════════════════════
PROTECTED_SUBSTRINGS = [
    # ―― キヤを含む苗字 ――
    'アキヤマ', 'ツキヤマ', 'ワキヤマ', 'スキヤマ', 'オキヤマ',
    'アキヤス', 'アキヤット',
    # ―― シヤを含む苗字 ――
    'ニシヤマ', 'ヒガシヤマ', 'カシヤマ', 'イチシヤ',
    # ―― ヒヤを含む苗字 ――
    'ヒヤマ', 'コヒヤマ', 'オヒヤマ',
    # ―― ミヤを含む苗字（宀 改姓最多） ――
    'ミヤモト', 'ミヤザキ', 'ミヤケ', 'ミヤタ', 'ミヤハラ',
    'ミヤワキ', 'ミヤシタ', 'ミヤノ', 'ミヤムラ', 'ミヤコ',
    'ミヤナガ', 'ミヤチ', 'ミヤサト', 'ミヤウチ', 'ミヤカワ',
    'ミヤオカ', 'ミヤイ', 'ミヤカミ', 'ミヤスダ', 'ミヤオ',
    'ミヤタニ', 'ミヤグチ', 'ミヤジマ', 'ミヤウラ',
    # ―― ニヤを含む苗字 ――
    'タニヤマ', 'ニヤマ',
    # ―― ミユ（名前専用） ――
    'ミユ', 'ミユキ',
    # ―― ユウ・ヨウで始まる名前（ユウイチ等） ――
    # ユ／ヨが単獨先頭に来る場合は拗音変換マップの対象外なので不要
]

# 長い苗字を先に処理するため長さの降順にソート
PROTECTED_SUBSTRINGS.sort(key=len, reverse=True)


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


def remove_non_katakana(text: str) -> str:
    """カタカナ以外（漢字・数字・記号・英字・ハイフン・スペース）を削除する"""
    return ''.join(c for c in text if '\u30A0' <= c <= '\u30FF')


# ═════════════════════════════════════════════
# 除外パターン（この文字列を含む行は空欄に変換）
# ═════════════════════════════════════════════
EXCLUDED_PATTERNS = [
    # ── 自社出金・振替パターン ─────────────────────────────────────
    '依頼人名：',           # 自社出金行（依頼人名：カ）サンシスコン など）

    # ── 法人名・サービス名（個人顧客ではないため照合対象外）──────────────
    'ＣＳＳ（ＭＦＲＬ',   # CSS（MFRL賃料）  例：ＣＳＳ（ＭＦＲＬチンリヨウ
    'ロボツトペイメント',   # ロボットペイメント（決済代行会社）
    'コクリツケンキユウカイハツ',  # 国立研究開発法人医薬基盤健康
    'ラクテンカ−ト゛',     # 楽天カードサービス（−は長音符の変形、゛は独立半濁点）
    'ニホンセイメイホケン', # 日本生命保険
    # ── 追加はここに記載 ─────────────────────────────────────────
    # '(パターン)',         # （説明）
]
def apply_yoon(text: str) -> str:
    """拗音変換：全角スペースで割った単語ごとに適用する。
    ホワイトリストに登録された苗字・パターンはプレースホルダーで保護して変換をスキップする。
    """
    segments = text.split('　')  # 全角スペースで分割
    converted_segments = []

    for seg in segments:
        # 1. ホワイトリスト内のパターンをプレースホルダーに一時置換
        placeholder_map = {}  # {placeholder: original}
        for i, protected in enumerate(PROTECTED_SUBSTRINGS):
            if protected in seg:
                placeholder = f'\x00{i:04d}\x00'  # NUL包指のプレースホルダー
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


def convert_furigana(name: str) -> str:
    """振込名義をフリガナに正規化する（全変換ルール適用）
    - 除外パターン（依頼人名： など）を含む場合は空文字列を返す
    """
    # 除外パターンチェック（出金先情報行など）
    for pattern in EXCLUDED_PATTERNS:
        if pattern in name:
            return ''

    text = combine_dakuten(name)      # ① 半濁点結合
    text = apply_yoon(text)           # ② 拗音変換（単語分割して適用）
    text = remove_non_katakana(text)  # ③ 不要文字削除（カタカナのみ残す）
    # ④ 促音変換は名前で誤変換が多発するため不使用
    return text


# ─────────────────────────────────────────────
# CSV処理
# ─────────────────────────────────────────────

def process_csv(input_path: str, output_path: str):
    """1つのCSVを変換してoutput_pathに書き出す"""
    rows = []
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
            if len(row) < 4:
                continue
            date     = row[0].strip()
            amount   = row[1].strip()
            balance  = row[2].strip()
            name     = row[3].strip()
            furigana = convert_furigana(name)
            writer.writerow([date, amount, balance, name, furigana])

    print(f'  行数: {len(rows)} 件')


# ─────────────────────────────────────────────
# エントリポイント
# ─────────────────────────────────────────────

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
        output_file = os.path.join(output_dir, f'step3_{filename}')
        print(f'[変換中] {filename}')
        process_csv(input_file, output_file)
        print(f'[完了]   csv_export/step3_{filename}')

    print('\n完了')


if __name__ == '__main__':
    main()
