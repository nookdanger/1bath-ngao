# main.py
from fastapi import FastAPI, Request, Form, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
import os
import base64
from datetime import datetime
from fastapi.responses import JSONResponse

app = FastAPI()
templates = Jinja2Templates(directory="templates")
DB_PATH = os.path.join(os.path.dirname(__file__), "assets.db")

status_mapping = {
    "1": "รอดำเนินการจำหน่าย",
    "2": "จัดทำหนังสือขอความเห็นชอบ",
    "1": "รอดำเนินการจำหน่าย",
    "2": "จัดทำหนังสือขอความเห็นชอบ",
    "3": "แต่งตั้งคณะกรรมการตรวจสอบข้อเท็จจริง",
    "4": "รายงานผลการตรวจสอบ",
    "5": "ขออนุมัติจำหน่าย",
    "6": "ดำเนินการจำหน่าย",
    "7": "จำหน่ายแล้วเสร็จ",
    "8": "ตัดจำหน่ายในระบบ SAP",
    "9": "รายงานผลการจำหน่าย",
}

def get_assets():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM assets 
        ORDER BY asset_id ASC
        LIMIT 100
    """)
    assets = cursor.fetchall()
    conn.close()
    return assets

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, disposal_status: str = None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if disposal_status:
        cursor.execute("SELECT * FROM assets WHERE disposal_status = ? and book_value = 1 ORDER BY id ", (disposal_status,))
    else:
        cursor.execute("SELECT * FROM assets WHERE book_value = 1 ORDER BY id ")

    rows = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "assets": rows
    })

@app.post("/update-status", response_class=RedirectResponse)
async def update_status(
    id: str = Form(...),
    disposal_status: str = Form(...),
    image_file: UploadFile = None
):
    image_base64 = None
    if image_file and image_file.filename:
        image_data = await image_file.read()
        image_base64 = base64.b64encode(image_data).decode("utf-8")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE assets 
        SET disposal_status = ?, 
            image = COALESCE(?, image)
        WHERE id = ?
    """, (disposal_status, image_base64, id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=303)



@app.get("/delete-image/{id}")
def delete_image(id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE assets SET image = NULL WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/dashboard", status_code=303)



@app.get("/asset/{id}", response_class=HTMLResponse)
def asset_detail(request: Request, id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM assets WHERE id = ?", (id,))
    asset = cursor.fetchone()

    cursor.execute("""
        SELECT status_code, status_description, ref_document, changed_at
        FROM disposal_status_log
        WHERE asset_id = ?
        ORDER BY changed_at
    """, (id,))
    logs =  cursor.fetchall()

    return templates.TemplateResponse("asset_detail.html", {
        "request": request,
        "asset": asset,
        "logs": logs
    })



@app.post("/log-status")
def log_disposal_status(
    asset_id: str = Form(...),
    status_code: str = Form(...),
    status_description: str = Form(...),
    ref_document: str = Form(...),
    changed_by: str = Form("system")  # default เป็น system หรือใส่ user ได้
):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # เช็คว่ามี log เดิมไหม
    cursor.execute("""
        SELECT id FROM disposal_status_log
        WHERE asset_id = ? AND status_code = ?
    """, (asset_id, status_code))
    row = cursor.fetchone()

    now = datetime.utcnow().isoformat()

    if row:
        # update log เดิม
        cursor.execute("""
            UPDATE disposal_status_log
            SET ref_document = ?, changed_at = ?, changed_by = ?
            WHERE id = ?
        """, (ref_document, now, changed_by, row["id"]))
    else:
        # insert ใหม่
        cursor.execute("""
            INSERT INTO disposal_status_log (
                asset_id, status_code, status_description,
                ref_document, changed_at, changed_by
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (asset_id, status_code, status_description, ref_document, now, changed_by))

    conn.commit()
    conn.close()
    return JSONResponse(content={"message": "OK"})







