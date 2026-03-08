"""
sunsyscon — 入金照合Webアプリ
FastAPI バックエンド
"""

import sys
import os
import csv
import io
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

# scriptsディレクトリをパスに追加（rules_furigana, phase01モジュール用）
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), 'scripts'))
from phase01_process_bank_csv import convert_furigana

app = FastAPI(title="sunsyscon - 入金照合システム")

# 静的ファイル配信
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ── インメモリデータストア（セッション中のみ保持） ──────────────────
store = {
    "bank_data": [],          # 楽天銀行CSV: [{date, amount, name_raw, name_converted}, ...]
    "customer_data": [],      # 顧客データCSV
    "delay_data": [],         # 遅延情報CSV
    "matched": [],            # 完全一致（入金済み）
    "needs_review": [],       # 要確認（複数ヒット・NA・金額不一致）
}


# ══════════════════════════════════════════════════════════════════
# ルートページ
# ══════════════════════════════════════════════════════════════════
@app.get("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# ══════════════════════════════════════════════════════════════════
# STEP 1 & 3: 楽天銀行CSVアップロード → フリガナ変換
# ══════════════════════════════════════════════════════════════════
@app.post("/api/upload/bank")
async def upload_bank_csv(file: UploadFile = File(...)):
    content = await file.read()

    # Shift-JIS → UTF-8 デコード
    try:
        text = content.decode('shift-jis')
    except UnicodeDecodeError:
        text = content.decode('utf-8-sig')

    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)

    bank_data = []
    for row in reader:
        if len(row) < 3:
            continue
        date = row[0].strip()
        try:
            amount = int(row[1].strip())
        except ValueError:
            continue
        name_raw = row[2].strip() if len(row) > 2 else ""

        # 入金のみ対象(amount > 0)
        name_converted = convert_furigana(name_raw)

        bank_data.append({
            "date": date,
            "amount": amount,
            "name_raw": name_raw,
            "name_converted": name_converted,
            "is_deposit": amount > 0,
        })

    store["bank_data"] = bank_data
    deposits = [d for d in bank_data if d["is_deposit"] and d["name_converted"]]

    return {
        "status": "ok",
        "total_rows": len(bank_data),
        "deposit_count": len(deposits),
        "skipped_count": len(bank_data) - len(deposits),
        "preview": deposits[:10],
    }


# ══════════════════════════════════════════════════════════════════
# STEP 2: kintone CSVアップロード（顧客データ）
# ══════════════════════════════════════════════════════════════════
@app.post("/api/upload/customer")
async def upload_customer_csv(file: UploadFile = File(...)):
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('shift-jis')

    reader = csv.DictReader(io.StringIO(text))
    customer_data = []
    for row in reader:
        customer_data.append({
            "record_no": row.get("レコード番号", ""),
            "name": row.get("氏名", ""),
            "furigana": row.get("フリガナ", ""),
            "contract_months": row.get("契約月数", ""),
            "payment_day": row.get("お支払日", ""),
            "total_amount": row.get("合計金額", ""),
            "payment_method": row.get("支払方法", ""),
            "excess_deficit": row.get("過不足", ""),
            "payment_status": row.get("支払ステータス", ""),
            "contract_status": row.get("契約状況ステータス", ""),
            "delay_auth": row.get("遅延認証", ""),
            "customer_id": row.get("顧客ID", ""),
        })

    store["customer_data"] = customer_data
    return {
        "status": "ok",
        "count": len(customer_data),
        "preview": customer_data[:5],
    }


# ══════════════════════════════════════════════════════════════════
# STEP 2: kintone CSVアップロード（遅延情報）
# ══════════════════════════════════════════════════════════════════
@app.post("/api/upload/delay")
async def upload_delay_csv(file: UploadFile = File(...)):
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('shift-jis')

    reader = csv.DictReader(io.StringIO(text))
    delay_data = []
    for row in reader:
        delay_data.append({
            "customer_id": row.get("顧客ID", ""),
            "record_no": row.get("レコード番号", ""),
            "name": row.get("氏名", ""),
            "delay_count": row.get("遅延回数", ""),
        })

    store["delay_data"] = delay_data
    return {
        "status": "ok",
        "count": len(delay_data),
    }


# ══════════════════════════════════════════════════════════════════
# STEP 4 & 5: 照合・計算・振り分け
# ══════════════════════════════════════════════════════════════════
def safe_int(val, default=0):
    try:
        return int(float(str(val).replace(",", "")))
    except (ValueError, TypeError):
        return default


@app.post("/api/match")
async def run_matching():
    bank_data = store.get("bank_data", [])
    customer_data = store.get("customer_data", [])

    if not bank_data:
        raise HTTPException(400, "楽天銀行CSVがアップロードされていません")
    if not customer_data:
        raise HTTPException(400, "顧客データCSVがアップロードされていません")

    # フリガナ → 顧客レコードのインデックスを作成
    furigana_index = {}
    for cust in customer_data:
        fg = cust.get("furigana", "").strip()
        if fg:
            furigana_index.setdefault(fg, []).append(cust)

    deposits = [d for d in bank_data if d["is_deposit"] and d["name_converted"]]

    matched = []
    needs_review = []

    for dep in deposits:
        key = dep["name_converted"]
        candidates = furigana_index.get(key, [])

        if len(candidates) == 0:
            # NA: 照合先なし
            needs_review.append({
                "type": "NA",
                "reason": "照合先が見つかりません",
                "bank": dep,
                "candidates": [],
            })
        elif len(candidates) == 1:
            # 1件ヒット: 過不足計算
            cust = candidates[0]
            result = calculate_excess_deficit(dep, cust)
            if result["new_excess_deficit"] == 0:
                matched.append(result)
            else:
                needs_review.append({
                    "type": "金額不一致",
                    "reason": f"過不足: {result['new_excess_deficit']}円",
                    "bank": dep,
                    "candidates": [result],
                })
        else:
            # 複数ヒット
            results = [calculate_excess_deficit(dep, c) for c in candidates]
            needs_review.append({
                "type": "複数ヒット",
                "reason": f"{len(candidates)}件の候補が見つかりました",
                "bank": dep,
                "candidates": results,
            })

    store["matched"] = matched
    store["needs_review"] = needs_review

    return {
        "status": "ok",
        "matched_count": len(matched),
        "review_count": len(needs_review),
        "matched_preview": matched[:5],
        "review_preview": needs_review[:5],
    }


def calculate_excess_deficit(dep: dict, cust: dict) -> dict:
    """過不足計算: 入金額 - (合計金額 - 過去過不足 + 手数料調整)"""
    deposit_amount = dep["amount"]
    total_amount = safe_int(cust.get("total_amount", 0))
    past_excess = safe_int(cust.get("excess_deficit", 0))
    payment_method = cust.get("payment_method", "").strip()
    contract_months = safe_int(cust.get("contract_months", 0))

    # リアルタイム料金計算
    realtime_charge = total_amount - past_excess

    # 手数料調整
    fee_adjustment = 0
    fee_note = ""
    if "口座" in payment_method:
        fee_adjustment = 1000
        fee_note = "口座振替→銀行振込 (+1000円)"
    elif "コンビニ" in payment_method:
        fee_adjustment = -330
        fee_note = "コンビニ払い→銀行振込 (-330円)"
    else:
        fee_note = "銀行振込（調整なし）"

    adjusted_charge = realtime_charge + fee_adjustment
    new_excess_deficit = deposit_amount - adjusted_charge
    new_contract_months = contract_months + 1

    return {
        "record_no": cust.get("record_no", ""),
        "customer_id": cust.get("customer_id", ""),
        "name": cust.get("name", ""),
        "furigana": cust.get("furigana", ""),
        "contract_months": new_contract_months,
        "new_excess_deficit": new_excess_deficit,
        "payment_status": "入金済み",
        "contract_status": "継続契約",
        "delay_auth": cust.get("delay_auth", "-"),
        # 詳細情報（UI確認用）
        "deposit_amount": deposit_amount,
        "total_amount": total_amount,
        "past_excess": past_excess,
        "payment_method": payment_method,
        "fee_adjustment": fee_adjustment,
        "fee_note": fee_note,
        "adjusted_charge": adjusted_charge,
        "bank_date": dep.get("date", ""),
        "bank_name_raw": dep.get("name_raw", ""),
    }


# ══════════════════════════════════════════════════════════════════
# STEP 5.5: 手動紐付け
# ══════════════════════════════════════════════════════════════════
@app.post("/api/resolve")
async def resolve_review(data: dict):
    """要確認リストの特定行を「入金済み」に移動する"""
    review_index = data.get("review_index")
    candidate_index = data.get("candidate_index")

    if review_index is None or candidate_index is None:
        raise HTTPException(400, "review_index と candidate_index が必要です")

    needs_review = store.get("needs_review", [])
    if review_index < 0 or review_index >= len(needs_review):
        raise HTTPException(400, "review_index が範囲外です")

    review_item = needs_review[review_index]
    candidates = review_item.get("candidates", [])

    if candidate_index < 0 or candidate_index >= len(candidates):
        raise HTTPException(400, "candidate_index が範囲外です")

    resolved = candidates[candidate_index]
    store["matched"].append(resolved)
    needs_review.pop(review_index)

    return {
        "status": "ok",
        "matched_count": len(store["matched"]),
        "review_count": len(store["needs_review"]),
    }


# ══════════════════════════════════════════════════════════════════
# STEP 6: インポートCSVダウンロード
# ══════════════════════════════════════════════════════════════════
@app.get("/api/download/csv")
async def download_csv():
    matched = store.get("matched", [])
    if not matched:
        raise HTTPException(400, "インポート対象のデータがありません")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "レコード番号", "顧客ID", "氏名", "フリガナ",
        "契約月数", "過不足", "支払ステータス", "契約状況ステータス", "遅延認証"
    ])

    for m in matched:
        writer.writerow([
            m.get("record_no", ""),
            m.get("customer_id", ""),
            m.get("name", ""),
            m.get("furigana", ""),
            m.get("contract_months", ""),
            m.get("new_excess_deficit", ""),
            m.get("payment_status", "入金済み"),
            m.get("contract_status", "継続契約"),
            m.get("delay_auth", "-"),
        ])

    output.seek(0)
    bom = b'\xef\xbb\xbf'  # UTF-8 BOM
    content = bom + output.getvalue().encode('utf-8')

    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kintone_import.csv"}
    )


# ══════════════════════════════════════════════════════════════════
# データ取得 API
# ══════════════════════════════════════════════════════════════════
@app.get("/api/status")
async def get_status():
    return {
        "bank_count": len(store.get("bank_data", [])),
        "customer_count": len(store.get("customer_data", [])),
        "delay_count": len(store.get("delay_data", [])),
        "matched_count": len(store.get("matched", [])),
        "review_count": len(store.get("needs_review", [])),
    }

@app.get("/api/matched")
async def get_matched():
    return store.get("matched", [])

@app.get("/api/review")
async def get_review():
    return store.get("needs_review", [])
