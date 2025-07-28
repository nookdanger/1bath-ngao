# main.py
from fastapi import FastAPI, Request, Form, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
import os
import base64
from datetime import datetime
from fastapi.responses import JSONResponse
from typing import Optional
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import shutil
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal


# Database connection parameters from environment
PG_HOST = os.getenv("PG_HOST", "dpg-d1lodf7diees73fu2pe0-a.oregon-postgres.render.com")
PG_DB = os.getenv("PG_DB", "db_1bath_ngao")
PG_USER = os.getenv("PG_USER", "db_1bath_ngao_user")
PG_PASSWORD = os.getenv("PG_PASSWORD", "8A9I3REUbc8tKzzAY3SKapz0nN4b5ZCm")
PG_PORT = os.getenv("PG_PORT", "5432")

app = FastAPI()
templates = Jinja2Templates(directory="templates")
DB_PATH = os.path.join(os.path.dirname(__file__), "assets.db")
app.mount("/static", StaticFiles(directory="static"), name="static")
status_mapping = {
    "1": "1.รอดำเนินการจำหน่าย/โอน",
    "2": "2.จัดทำหนังสือขอความเห็นชอบ",
    "3": "3.แต่งตั้งคณะกรรมการตรวจสอบข้อเท็จจริง",
    "4": "4.รายงานผลการตรวจสอบ",
    "5": "5.ขออนุมัติจำหน่าย",
    "6": "6.ดำเนินการจำหน่าย/รอส่งมอบ",
    "7": "7.ส่งมอบ/จำหน่ายแล้วเสร็จ",
    "8": "8.ตัดจำหน่าย/โอน ในระบบ SAP",
    "9": "9.รายงานผลการจำหน่าย/โอน",
}

assets_status_mapping = {
    "2010": "2010: ติดตั้ง/ใช้งาน",
    "2020": "2020: ชำรุด",
    "2030": "2030: สภาพดีแต่ไม่ได้ใช้งาน",
    "2040": "2040: อยู่ระหว่างขออนุมัติจำหน่าย",
    "2050": "2050: สูญหาย",
    "2060": "2060: ให้เช่า",
    "3010": "3010: จำหน่าย(ขาย)",
    "3020": "3020: จำหน่าย(แลกเปลี่ยน)",
    "3030": "3030: จำหน่าย(โอน)",
    "3040": "3040: จำหน่าย(แปรสภาพ)",
    "3050": "3050: จำหน่าย(ทำลาย)",
    "4010": "4010: จำหน่ายเป็นสูญ",
    "4020": "4020: สิ้นสุดสัญญาเช่า",
    }
cost_center_mapping = {
    "A303701000": "แผนกบริหาร",
    "A303701010": "แผนกก่อสร้างปฏิบัติการและบำรุงรักษา",
    "A303701020": "แผนกบริการลูกค้า",
    "A303701030": "แผนกสนับสนุน",
    "A303701040": "แผนกมิเตอร์และหม้อแปลง",
}

def convert_decimal(values):
    return [float(v or 0) for v in values]


def get_assets():
    # conn = sqlite3.connect(DB_PATH)
    conn = psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT
    )
    # conn.row_factory = sqlite3.Row
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT * FROM assets 
        ORDER BY asset_id ASC
        LIMIT 100
    """)
    assets = cursor.fetchall()
    conn.close()
    return assets

def convert_decimal(obj):
    if isinstance(obj, list):
        return [convert_decimal(x) for x in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj

def checkEmptyNone(value: str):
    return value and value != "None" and value != ""

@app.get("/asset", response_class=HTMLResponse)
def dashboard(
    request: Request,
    disposal_status: str = "",
    cost_center: str = None,
    asset_status: str = "",
    search: str = "",
):
    # conn = sqlite3.connect(DB_PATH)
    conn = psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    where_clauses = []
    params = []

    # เงื่อนไข search
    if checkEmptyNone(search):
        where_clauses.append("(a.description LIKE %s OR a.asset_id LIKE %s)")
        keyword = f"%{search}%"
        params.extend([keyword, keyword])

    # เงื่อนไขอื่น ๆ
    if checkEmptyNone(disposal_status):
        where_clauses.append("disposal_status = %s")
        params.append(disposal_status)

    if checkEmptyNone(cost_center):
        where_clauses.append("cost_center = %s")
        params.append(cost_center)

    if checkEmptyNone(asset_status):
        where_clauses.append("asset_status = %s")
        params.append(asset_status)

    # ✅ JOIN disposal_status_log เฉพาะ log ล่าสุดของ status 6-8
    sql = """
        SELECT 
            a.*, 
            l.end_date AS end_date, 
            l.status_code AS disposal_status_code
        FROM assets a
        LEFT JOIN (
            SELECT DISTINCT ON (asset_id)
                asset_id, end_date, status_code, changed_at
            FROM disposal_status_log
            WHERE status_code IN ('6', '7', '8')
            ORDER BY asset_id, changed_at DESC
        ) l ON a.id::text = l.asset_id
    """
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY a.book_value, a.id"

    # print(sql, params)  # debug ได้ถ้าต้องการ
    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse("asset.html", {
        "request": request,
        "assets": rows
    })



@app.get("/main", response_class=HTMLResponse)
def dashboard(request: Request, cost_center: str = None ):
    # conn = sqlite3.connect("assets.db")
    conn = psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT
    )
    # conn.row_factory = sqlite3.Row


    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    base_sql = """
        SELECT
            disposal_status,
            COUNT(*) AS count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM assets {where_clause}), 2) AS percentage
        FROM assets
        {where_clause}
        GROUP BY disposal_status
    """
    where_clause = ""
    params1 = ()
    if cost_center:
        where_clause = "WHERE cost_center = %s"
        params1 = (cost_center,cost_center)

    # ใส่ where_clause ลงใน SQL
    sql = base_sql.format(where_clause=where_clause)
    cursor.execute(sql, params1)
    rows = cursor.fetchall()
    disposal_labels = []
    disposal_values = []
    for row in rows:
        status = row['disposal_status']
        count = row['count']
        percentage = float(row['percentage']) if row['percentage'] is not None else 0
        label = status_mapping.get(status, None)
        if label:
            disposal_labels.append(label)
            disposal_values.append(percentage)
    




    cursor = conn.cursor(cursor_factory=RealDictCursor)
    base_sql = """
       SELECT
        asset_status,
        COUNT(*) AS count,
        ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM assets {where_clause}), 2) AS percentage
        FROM assets
        {where_clause}
        GROUP BY asset_status;
        """

    sql = base_sql.format(where_clause=where_clause)
    params2 = ()
    if cost_center:
        where_clause = "WHERE cost_center = %s"
        params2 = (cost_center,cost_center)
    cursor.execute(sql, params2)
    rows = cursor.fetchall()
    
    assets_labels = []
    assets_values = []
    for row in rows:
        status = row['asset_status']
        count = row['count']
        percentage = float(row['percentage']) if row['percentage'] is not None else 0

        label = assets_status_mapping.get(status, None)
        print("label:", label)
        print("count:", count)

        if label:
            assets_labels.append(label)
            assets_values.append(percentage)
    
    
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    where_clause1 = ""
    params3 = ()
    if cost_center:
        where_clause1 = "AND assets.cost_center = %s"
        params3 = (cost_center,)

    base_sql = """
        WITH status_map(disposal_status, status_name) AS (
            VALUES
                ('1', '1.รอดำเนินการจำหน่าย/โอน'),
                ('2', '2.จัดทำหนังสือขอความเห็นชอบ'),
                ('3', '3.แต่งตั้งคณะกรรมการตรวจสอบข้อเท็จจริง'),
                ('4', '4.รายงานผลการตรวจสอบ'),
                ('5', '5.ขออนุมัติจำหน่าย'),
                ('6', '6.ดำเนินการจำหน่าย/รอส่งมอบ'),
                ('7', '7.ส่งมอบ/จำหน่ายแล้วเสร็จ'),
                ('8', '8.ตัดจำหน่าย/โอน ในระบบ SAP'),
                ('9', '9.รายงานผลการจำหน่าย/โอน')
        )
        SELECT 
            status_map.disposal_status,
            status_map.status_name,
            COUNT(assets.id) AS asset_count,
            SUM(assets.acquisition_value) AS acquisition_value
        FROM status_map
        LEFT JOIN assets ON status_map.disposal_status = assets.disposal_status
        {where_clause1}
        GROUP BY status_map.disposal_status, status_map.status_name
        ORDER BY status_map.status_name
    """

    sql = base_sql.format(where_clause1=where_clause1)
    cursor.execute(sql, params3)
    disposal = cursor.fetchall()
    




    cursor = conn.cursor(cursor_factory=RealDictCursor)
    where_clause =""
    params2 = ()
    if cost_center:
        where_clause  = "AND assets.cost_center = %s"
        params2 = (cost_center,)


    base_sql = """
        WITH status_map(asset_status, status_name) AS (
            VALUES
                ('2010','2010: ติดตั้ง/ใช้งาน'),
                ('2020','2020: ชำรุด'),
                ('2030','2030: สภาพดีแต่ไม่ได้ใช้งาน'),
                ('2040','2040: อยู่ระหว่างขออนุมัติจำหน่าย'),
                ('2050','2050: สูญหาย'),
                ('2060','2060: ให้เช่า'),
                ('3010','3010: จำหน่าย(ขาย)'),
                ('3020','3020: จำหน่าย(แลกเปลี่ยน)'),
                ('3030','3030: จำหน่าย(โอน)'),
                ('3040','3040: จำหน่าย(แปรสภาพ)'),
                ('3050','3050: จำหน่าย(ทำลาย)'),
                ('4010','4010: จำหน่ายเป็นสูญ'),
                ('4020','4020: สิ้นสุดสัญญาเช่า')
            )
        SELECT 
            status_map.asset_status,
            status_map.status_name,
            COUNT(assets.id) AS asset_count,
            SUM(assets.acquisition_value) AS acquisition_value
        FROM status_map
        LEFT JOIN assets ON status_map.asset_status = assets.asset_status
        {where_clause}
        GROUP BY status_map.asset_status, status_map.status_name
        ORDER BY status_map.status_name
    """

    sql = base_sql.format(where_clause=where_clause)
    cursor.execute(sql, params2)
    asset_status = cursor.fetchall()


    # asset_status_desc = []
    # for asset_status_val in asset_status:
    #     status_desc = assets_status_mapping.get(asset_status_val, f"ไม่ระบุ ({asset_status_val})")
    #     asset_status_desc.append(status_desc)





    where_clause5 =""
    params5 =()
    if cost_center:
        where_clause5 = "WHERE cost_center = %s"
        params5 = (cost_center,)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    base_sql = """
        SELECT
               ROUND(SUM(
                CASE 
                    WHEN asset_status = '2010'
                    OR (asset_status != '2010' AND disposal_status = '9')
                    THEN 1 ELSE 0
                END) * 100.0 / COUNT(*), 2) AS percent_disposed,

            -- ยังไม่สำเร็จ = ที่เหลือทั้งหมด
            ROUND(SUM(
                CASE 
                    WHEN asset_status != '2010' AND (disposal_status IS NULL OR disposal_status != '9')
                    THEN 1 ELSE 0
                END) * 100.0 / COUNT(*), 2) AS percent_not_disposed
        FROM assets
        {where_clause5}
        """
    sql = base_sql.format(where_clause5=where_clause5)
    
    
   
    cursor.execute(sql, params5)
    success_status = cursor.fetchone()
    print("จำนวนแถวที่ได้", len(success_status))
    print("ค่าที่ได้", success_status)
    success_values = convert_decimal(success_status)

    conn.close()
    return templates.TemplateResponse("main.html", {
        "request": request,
        "disposal_labels": disposal_labels,     # <--- ต้องเพิ่มให้ครบ
        "disposal_values": disposal_values,
        "assets_labels": assets_labels,     # <--- ต้องเพิ่มให้ครบ
        "assets_values": assets_values,
        "disposal": disposal,
        "asset_status":asset_status,
        # "asset_status_desc":asset_status_desc,
        "assets_status_mapping": assets_status_mapping,
        "status_mapping": status_mapping,
        "success_values": success_values
    })

@app.get("/graph", response_class=HTMLResponse)
def dashboard(request: Request, disposal_status: str = None):
    # conn = sqlite3.connect(DB_PATH)
    conn = psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT
    )
    # conn.row_factory = sqlite3.Row
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    if disposal_status:
        cursor.execute("SELECT * FROM assets WHERE disposal_status = %s and book_value = 1 ORDER BY id ", (disposal_status,))
    else:
        cursor.execute("SELECT * FROM assets WHERE book_value = 1 ORDER BY id ")

    rows = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("graph.html", {
        "request": request,
        "assets": rows
    })

@app.post("/update-status", response_class=RedirectResponse)
async def update_status(
    id: str = Form(...),
    disposal_status: Optional[str] = Form(None),
    asset_status: str = Form(...),
    image_file: UploadFile = None,
    cost_center: str = Form(...),
    disposal_status_selected: str = Form(...),
    asset_status_selected: str = Form(...),
     search: str = Form(...),
    
):
    image_base64 = None
    if image_file and image_file.filename:
        new_file = compress_image(image_file)
        new_file_data = new_file.read()
        image_base64 = base64.b64encode(new_file_data).decode("utf-8")

    # conn = sqlite3.connect(DB_PATH)
    conn = psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    if asset_status and asset_status != "2010" and disposal_status == "":
        disposal_status = "1"
    
    cursor.execute("""
        UPDATE assets 
        SET disposal_status = %s, 
            asset_status = %s,
            image = COALESCE(%s, image)
        WHERE id = %s
    """, (disposal_status,asset_status, image_base64, id))


    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/asset?disposal_status={disposal_status_selected}&cost_center={cost_center}&asset_status={asset_status_selected}&search={search}", status_code=303)



@app.get("/delete-image/{id}")
def delete_image(id: int,disposal_status:str = "",cost_center:str ="",asset_status:str=""):
    # conn = sqlite3.connect(DB_PATH)
    conn = psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("UPDATE assets SET image = NULL WHERE id = %s", (id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/asset?disposal_status={disposal_status}&cost_center={cost_center}&asset_status={asset_status}", status_code=303)



@app.get("/asset/{id}", response_class=HTMLResponse)
def asset_detail(request: Request, id: int,cost_center:str="",disposal_status:str="" ,asset_status:str=""):
    # conn = sqlite3.connect(DB_PATH)
    conn = psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT
    )
    # conn.row_factory = sqlite3.Row
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT * FROM assets WHERE id = %s", (id,))
    asset = cursor.fetchone()

    cursor.execute("""
       SELECT id, status_code, status_description, ref_document, changed_at, asset_id, end_date
        FROM disposal_status_log
        WHERE asset_id = %s
        ORDER BY changed_at
    """, (str(id),))
    logs =  cursor.fetchall()

    return templates.TemplateResponse("asset_detail.html", {
        "request": request,
        "cost_center":cost_center,
        "disposal_status": disposal_status,
        "asset_status":asset_status,
        "asset": asset,
        "logs": logs
    })



@app.post("/log-status")
def log_disposal_status(
    asset_id: str = Form(...),
    status_code: str = Form(...),
    status_description: str = Form(...),
    ref_document: str = Form(...),
    start_date: str = Form(None),  # วันที่เริ่มต้น (nullable)
    end_date: str = Form(None),    # วันที่สิ้นสุด (nullable)
    changed_by: str = Form("system")
):
    conn = psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # ตรวจสอบว่ามี log เดิมอยู่หรือไม่
    cursor.execute("""
        SELECT id FROM disposal_status_log
        WHERE asset_id = %s AND status_code = %s
    """, (asset_id, status_code))
    row = cursor.fetchone()

    now = datetime.utcnow()

    if row:
        # อัปเดต log เดิม
        cursor.execute("""
            UPDATE disposal_status_log
            SET ref_document = %s,
                start_date = %s,
                end_date = %s,
                changed_at = %s,
                changed_by = %s
            WHERE id = %s
        """, (
            ref_document,
            start_date if start_date else None,
            end_date if end_date else None,
            now,
            changed_by,
            row["id"]
        ))
    else:
        # เพิ่ม log ใหม่
        cursor.execute("""
            INSERT INTO disposal_status_log (
                asset_id, status_code, status_description,
                ref_document, start_date, end_date,
                changed_at, changed_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            asset_id,
            status_code,
            status_description,
            ref_document,
            start_date if start_date else None,
            end_date if end_date else None,
            now,
            changed_by
        ))

    conn.commit()
    conn.close()
    return JSONResponse(content={"message": "OK"})


@app.post("/assets/{asset_log_id}/delete")
def delete_asset(request: Request,asset_log_id: int ,disposal_status: str="",cost_center:str="",asset_status:str=""):
    # conn = sqlite3.connect(DB_PATH)
    conn = psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT
    )
    # conn.row_factory = sqlite3.Row
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT asset_id FROM disposal_status_log WHERE id = %s", (asset_log_id,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return RedirectResponse(url="/assets", status_code=303)

    asset_id = row["asset_id"]
    # ลบ log
    cursor.execute("DELETE FROM disposal_status_log WHERE id = %s", (asset_log_id,))
    conn.commit()
    conn.close()

    # redirect กลับไปหน้าแสดง asset รายตัว
    return RedirectResponse(url=f"/asset/{asset_id}?disposal_status={disposal_status}&cost_center={cost_center}&asset_status={asset_status}", status_code=303)




@app.get("/download")
async def download_files(request: Request):
    beforeFiles = [
        {"name": "ตัวอย่างแนบ 1 - ขอแจ้งข้อมูลทรัพย์สินที่มีส.docx", "url": "/static/แบบฟอร์มก่อนได้รับอนุมัติ/ตัวอย่างแนบ 1 - ขอแจ้งข้อมูลทรัพย์สินที่มีส.docx"},
        {"name": "ตัวอย่างแนบ 2 - ขอทราบมูลค่าซื้อหรือได้มาขอ.docx", "url": "/static/แบบฟอร์มก่อนได้รับอนุมัติ/ตัวอย่างแนบ 2 - ขอทราบมูลค่าซื้อหรือได้มาขอ.docx"},
        {"name": "ตัวอย่างแนบ 3 - หน่วยงานบัญชียืนยันราคาซื้อ.pdf", "url": "/static/แบบฟอร์มก่อนได้รับอนุมัติ/ตัวอย่างแนบ 3 - หน่วยงานบัญชียืนยันราคาซื้อ.pdf"},
        {"name": "ตัวอย่างแนบ 4 - หนังสือขอความเห็นเพื่อประกอ.docx", "url": "/static/แบบฟอร์มก่อนได้รับอนุมัติ/ตัวอย่างแนบ 4 - หนังสือขอความเห็นเพื่อประกอ.docx"},
        {"name": "ตัวอย่างแนบ 5 - หนังสือขอแต่งตั้งคณะกรรมการ.docx", "url": "/static/แบบฟอร์มก่อนได้รับอนุมัติ/ตัวอย่างแนบ 5 - หนังสือขอแต่งตั้งคณะกรรมการ.docx"},
        {"name": "ตัวอย่างแนบ 6 - หนังสือรายงานผลของคณะกรรมกา.docx", "url": "/static/แบบฟอร์มก่อนได้รับอนุมัติ/ตัวอย่างแนบ 6 - หนังสือรายงานผลของคณะกรรมกา.docx"},
        {"name": "ตัวอย่างแนบ 7 - หนังสือรายงานผลของคณะกรรมกา.docx", "url": "/static/แบบฟอร์มก่อนได้รับอนุมัติ/ตัวอย่างแนบ 7 - หนังสือรายงานผลของคณะกรรมกา.docx"},
        {"name": "ตัวอย่างแนบ 8 - หนังสือขออนุมัติจำหน่ายทรัพ.docx", "url": "/static/แบบฟอร์มก่อนได้รับอนุมัติ/ตัวอย่างแนบ 8 - หนังสือขออนุมัติจำหน่ายทรัพ.docx"},
        {"name": "ตัวอย่างแนบ 9 - หนังสือขออนุมัติจำหน่ายทรัพ.docx", "url": "/static/แบบฟอร์มก่อนได้รับอนุมัติ/ตัวอย่างแนบ 9 - หนังสือขออนุมัติจำหน่ายทรัพ.docx"},
    ]
    afterFiles = [
        {"name": "00_หนังสือกำหนดเอกสารเพื่อเป็นแนวทางในการขาย (1).pdf", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/00_หนังสือกำหนดเอกสารเพื่อเป็นแนวทางในการขาย (1).pdf"},
        {"name": "01.1_แบบฟอร์มที่ 1.1 หนังสือขอแต่งตั้งกรรมการ (1).docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/01.1_แบบฟอร์มที่ 1.1 หนังสือขอแต่งตั้งกรรมการ (1).docx"},
        {"name": "01.2_แบบฟอร์มที่ 1.2 คำสั่งแต่งตั้งกรรมการ (1).docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/01.2_แบบฟอร์มที่ 1.2 คำสั่งแต่งตั้งกรรมการ (1).docx"},
        {"name": "02.1_แบบฟอร์มที่ 2.1 ขออนุมัติประเมินราคาขาย (กรณีขายพัสดุสำรองคลัง) (1).docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/02.1_แบบฟอร์มที่ 2.1 ขออนุมัติประเมินราคาขาย (กรณีขายพัสดุสำรองคลัง) (1).docx"},
        {"name": "02.2_แบบฟอร์มที่ 2.2 ขออนุมัติประเมินราคาขาย (กรณีขายเศษวัสดุ) (1).docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/02.2_แบบฟอร์มที่ 2.2 ขออนุมัติประเมินราคาขาย (กรณีขายเศษวัสดุ) (1).docx"},
        {"name": "03.1_แบบฟอร์มที่ 3.1 หนังสือเผยแพร่ประกาศขายเฉพาะเจาะจง (1).docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/03.1_แบบฟอร์มที่ 3.1 หนังสือเผยแพร่ประกาศขายเฉพาะเจาะจง (1).docx"},
        {"name": "03.2_แบบฟอร์มที่ 3.2 ประกาศขายเฉพาะเจาะจง (1).docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/03.2_แบบฟอร์มที่ 3.2 ประกาศขายเฉพาะเจาะจง (1).docx"},
        {"name": "04_แบบฟอร์มที่ 4 ใบเสนอราคาซื้อ (1).docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/04_แบบฟอร์มที่ 4 ใบเสนอราคาซื้อ (1).docx"},
        {"name": "05_แบบฟอร์มที่ 5 ทะเบียนคุมแจกแบบฟอร์มเสนอร (1).xlsx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/05_แบบฟอร์มที่ 5 ทะเบียนคุมแจกแบบฟอร์มเสนอร (1).xlsx"},

        {"name": "06_แบบฟอร์มที่ 6 ทะเบียนคุมรับซองเสนอราคา.xlsx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/06_แบบฟอร์มที่ 6 ทะเบียนคุมรับซองเสนอราคา.xlsx"},
        {"name": "07_แบบฟอร์มที่ 7 แบบฟอร์มสรุปผลใบเสนอราคา.xlsx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/07_แบบฟอร์มที่ 7 แบบฟอร์มสรุปผลใบเสนอราคา.xlsx"},
        {"name": "08.1_แบบฟอร์มที่ 8.1 รายงานผลการขายพัสดุเพื่อขาย วิธีเฉพาะเจาะจง ต่อรายการ.docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/08.1_แบบฟอร์มที่ 8.1 รายงานผลการขายพัสดุเพื่อขาย วิธีเฉพาะเจาะจง ต่อรายการ.docx"},
        {"name": "08.2_แบบฟอร์มที่ 8.2 รายงานผลการขายพัสดุเพื่อขาย วิธีเฉพาะเจาะจง รวมทุกรายการ.docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/08.2_แบบฟอร์มที่ 8.2 รายงานผลการขายพัสดุเพื่อขาย วิธีเฉพาะเจาะจง รวมทุกรายการ.docx"},
        {"name": "08.3_แบบฟอร์มที่ 8.3 รายงานผลการขายพัสดุเพื่อขาย โดยการเจรจาตกลงราคา รวมรายการ.docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/08.3_แบบฟอร์มที่ 8.3 รายงานผลการขายพัสดุเพื่อขาย โดยการเจรจาตกลงราคา รวมรายการ.docx"},
        {"name": "08.4_แบบฟอร์มที่ 8.4 รายงานผลการขายพัสดุเพื่อขาย โดยการเจรจาตกลงราคา ต่อรายการ.docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/08.4_แบบฟอร์มที่ 8.4 รายงานผลการขายพัสดุเพื่อขาย โดยการเจรจาตกลงราคา ต่อรายการ.docx"},
        {"name": "09_แบบฟอร์มที่ 9 หนังสือรับราคาเสนอซื้อ.docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/09_แบบฟอร์มที่ 9 หนังสือรับราคาเสนอซื้อ.docx"},
        {"name": "10_แบบฟอร์มที่ 10 หนังสือส่งมอบ รับมอบ.docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/10_แบบฟอร์มที่ 10 หนังสือส่งมอบ รับมอบ.docx"},
        {"name": "11_แบบฟอร์มที่ 11 รายงานผลการดำเนินการขายและ.docx", "url": "/static/แบบฟอร์มหลังจากได้รับอนุมัติ/11_แบบฟอร์มที่ 11 รายงานผลการดำเนินการขายและ.docx"},
    ]
    return templates.TemplateResponse("downloads.html", {"request": request, "beforeFiles": beforeFiles,"afterFiles":afterFiles})


@app.get("/other")
async def download_files(request: Request):
    otherFiles = [
        {"name": "แนวทางการจัดทำหนังสือขออนุมัติจำหน่ายทร.pdf", "url": "/static/แนวทางการจัดทำหนังสือขออนุมัติจำหน่ายทร.pdf"},
         {"name": "หลักเกณฑ์และวิธีปฏิบัติเกี่ยวกับการควบค.pdf", "url": "/static/หลักเกณฑ์และวิธีปฏิบัติเกี่ยวกับการควบค.pdf"},
          {"name": " คำสั่ง พ.(ม)34 -2566 เรื่องมอบอำนาจจำหน่ายพัสดุ.pdf", "url": "/static/ คำสั่ง พ.(ม)34 -2566 เรื่องมอบอำนาจจำหน่ายพัสดุ.pdf"},

        
    ]
    
    return templates.TemplateResponse("downloads-other.html", {"request": request, "otherFiles": otherFiles})









@app.get("/report", response_class=HTMLResponse)
def dashboard(request: Request ,cost_center: str = "", asset_status:str =""):
    # conn = sqlite3.connect(DB_PATH)
    # conn.row_factory = sqlite3.Row
    conn = psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    print("cost_center: ",cost_center ,"asset_status :",asset_status)
    if checkEmptyNone(cost_center) and  checkEmptyNone(asset_status) and asset_status == "2010":
        print(1)
        cursor.execute("SELECT * FROM assets where cost_center =%s and asset_status =%s ORDER BY book_value,id ", (cost_center,asset_status))
    elif checkEmptyNone(cost_center) and  checkEmptyNone(asset_status) and asset_status == "0000":
        print(11)
        cursor.execute("SELECT * FROM assets where cost_center =%s and asset_status !=%s ORDER BY book_value,id ", (cost_center,"2010"))
    elif checkEmptyNone(cost_center) and  not checkEmptyNone(asset_status):
        print(111)
        cursor.execute("SELECT * FROM assets where cost_center =%s  ORDER BY book_value,id ", (cost_center,))
    elif not checkEmptyNone(cost_center) and   checkEmptyNone(asset_status) and asset_status == "2010":
        print(1111)
        cursor.execute("SELECT * FROM assets where asset_status =%s  ORDER BY book_value,id ", (asset_status,))
    elif not checkEmptyNone(cost_center) and   checkEmptyNone(asset_status) and asset_status == "0000":
        print(11112)
        cursor.execute("SELECT * FROM assets where asset_status !=%s  ORDER BY book_value,id ", ("2010",))
    elif not checkEmptyNone(cost_center) and  not checkEmptyNone(asset_status):
        print(11111)
        cursor.execute("SELECT * FROM assets ORDER BY book_value,id ")

    rows = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("report.html", {
        "cost_center":cost_center,
        "request": request,
        "assets": rows,
        "status_mapping": status_mapping,
        "assets_status_mapping": assets_status_mapping,
    })


from typing import List

@app.post("/report-create")
async def report_create(
    request: Request,
    select: List[str] = Form(...),
    cost_center: str = Form(""),
    from_a: str = Form(""),
    to: str = Form(""),
    attention: str = Form(""),
    signature: str = Form(""),
    position: str = Form(""),
     tel: str = Form(""),
):
    print("Selected asset IDs:", select)
    print("from_a:",from_a)

    # conn = sqlite3.connect(DB_PATH)
    # conn.row_factory = sqlite3.Row
    conn = psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # prepare SQL
    placeholders = ','.join(['%s'] * len(select))  # '%s, %s, %s, %s'
    query = f"SELECT * FROM assets WHERE id IN ({placeholders}) ORDER BY book_value, id"
    cursor.execute(query, select)
    rows = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse("report-result.html", {
        "from_a": from_a,
        "to": to,
        "attention": attention,
        "signature": signature,
        "cost_center": cost_center,
        "position":position,
        "request": request,
        "assets": rows,
        "today_date": datetime.today().strftime('%d/%m/%Y') , # 🗓️ ส่งวันที่วันนี้
        "cost_center_mapping": cost_center_mapping,
        "tel":tel
    })



from PIL import Image
import io

def compress_image(uploaded_file, max_width=1600, quality=90):
    image = Image.open(uploaded_file.file)

    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    # Resize (ถ้าจำเป็น)
    if image.width > max_width:
        ratio = max_width / image.width
        new_size = (max_width, int(image.height * ratio))
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.ANTIALIAS
        image = image.resize(new_size, resample)

    compressed_io = io.BytesIO()
    image.save(
        compressed_io,
        format='JPEG',
        quality=90,
        subsampling=0,
        optimize=True
    )
    compressed_io.seek(0)
    return compressed_io



@app.get("/process")
async def report_create(
    request: Request,
):
    return templates.TemplateResponse("process.html", {"request":request})


@app.post("/assets/{asset_id}/{log_id}/edit-ref")
def edit_ref_document(
    asset_id: str,
    log_id: int,
    ref_document: str = Form(...),
    cost_center: str = "",
    disposal_status: str = "",
    asset_status: str = ""
):
    # conn = sqlite3.connect(DB_PATH)
    # conn.row_factory = sqlite3.Row
    conn = psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        UPDATE disposal_status_log
        SET ref_document = %s
        WHERE id = %s
    """, (ref_document, log_id))
    conn.commit()

    return RedirectResponse(
        url=f"/asset/{asset_id}?cost_center={cost_center}&disposal_status={disposal_status}&asset_status={asset_status}",
        status_code=303
    )



UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# Global storage (not recommended for production)
cached_valid_data = []

@app.get("/", response_class=HTMLResponse)
async def form_page(request: Request):
    return templates.TemplateResponse("upload_form.html", {"request": request})

@app.post("/upload", response_class=HTMLResponse)
async def upload_excel(request: Request, file: UploadFile):
    global cached_valid_data
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb") as f:
        shutil.copyfileobj(file.file, f)

    df = pd.read_excel(file_location)
    df.columns = [
        "asset_id", "sub_number", "inventory_code", "description",
        "product_code", "capitalized_date", "acquisition_value",
        "accumulated_depreciation", "book_value", "asset_status", "cost_center"
    ]

    df["valid_date"] = df["capitalized_date"].apply(lambda d: validate_date(d))
    df["duplicate"] = df.duplicated(subset=["asset_id", "sub_number"], keep=False)
    valid_df = df[df["valid_date"] & (~df["duplicate"])]
    invalid_df = df[~df["valid_date"] | df["duplicate"]]

    valid_df["capitalized_date"] = pd.to_datetime(valid_df["capitalized_date"]).dt.strftime("%Y-%m-%d")
    # 🔧 แปลง NaN เป็น None
    valid_df = valid_df.where(pd.notnull(valid_df), None)
    cached_valid_data = valid_df.to_dict(orient='records')

    return templates.TemplateResponse("preview.html", {
        "request": request,
        "valid_data": valid_df.values.tolist(),
        "invalid_data": invalid_df.values.tolist(),
        "columns": df.columns.tolist()
    })

def validate_date(date_str):
    try:
        pd.to_datetime(date_str, format="%Y-%m-%d")
        return True
    except:
        return False

SECRET_CODE = "123456"  # Secret code required for import

@app.post("/import", response_class=RedirectResponse)
async def import_data(request: Request):
    global cached_valid_data
    form = await request.form()
    secret_code_input = form.get("secret_code")
    if secret_code_input != SECRET_CODE:
        return HTMLResponse("<h3>Invalid secret code. <a href='/'>Go Back</a></h3>")
    # conn = sqlite3.connect(DB_PATH)
   
    conn = psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        port=PG_PORT
    )
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    # Truncate old data before import
    cursor.execute("DELETE FROM assets")
    cursor.execute("DELETE FROM disposal_status_log")
    for row in cached_valid_data:
        cursor.execute('''
            INSERT INTO assets (
                asset_id, sub_number, inventory_code, description,
                product_code, capitalized_date, acquisition_value,
                accumulated_depreciation, book_value, asset_status, cost_center
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            row['asset_id'], row['sub_number'], row['inventory_code'], row['description'],
            row['product_code'], row['capitalized_date'], row['acquisition_value'],
            row['accumulated_depreciation'], row['book_value'], row['asset_status'],
            row['cost_center']
        ))
    conn.commit()
    conn.close()
    cached_valid_data = []
    return RedirectResponse("/", status_code=303)