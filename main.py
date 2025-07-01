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


def checkEmptyNone(value: str):
    return value and value != "None" and value != ""

@app.get("/asset", response_class=HTMLResponse)
def dashboard(request: Request, disposal_status: str = "" ,cost_center: str = None, asset_status:str =""):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    print("cost_center: ",cost_center ," disposal_status: ",disposal_status, "asset_status :",asset_status)

    if checkEmptyNone(disposal_status) and  checkEmptyNone(cost_center) and checkEmptyNone(asset_status):
        cursor.execute("SELECT * FROM assets WHERE disposal_status = ? and asset_status=? and cost_center=? ORDER BY book_value,id ", (disposal_status,asset_status,cost_center))
    elif checkEmptyNone(disposal_status) and checkEmptyNone(cost_center):
        cursor.execute("SELECT * FROM assets WHERE disposal_status = ? and cost_center= ? ORDER BY book_value,id ", (disposal_status,cost_center,))
    elif checkEmptyNone(disposal_status) and  not checkEmptyNone(cost_center):
        cursor.execute("SELECT * FROM assets WHERE disposal_status = ? ORDER BY book_value,id ", (disposal_status,))
  
    

    elif checkEmptyNone(asset_status) and checkEmptyNone(cost_center):
        cursor.execute("SELECT * FROM assets WHERE asset_status = ? and cost_center= ? ORDER BY book_value,id ", (asset_status,cost_center,))
    elif checkEmptyNone(asset_status) and  not checkEmptyNone(cost_center):
        cursor.execute("SELECT * FROM assets WHERE asset_status = ? ORDER BY book_value,id ", (asset_status,))

    elif  not checkEmptyNone(asset_status) and not checkEmptyNone(asset_status) and  checkEmptyNone(cost_center):
        cursor.execute("SELECT * FROM assets WHERE cost_center = ? ORDER BY book_value,id ", (cost_center,))
    else:
        cursor.execute("SELECT * FROM assets ORDER BY book_value,id ")

    rows = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("asset.html", {
        "request": request,
        "assets": rows
    })


@app.get("/main", response_class=HTMLResponse)
def dashboard(request: Request, cost_center: str = None ):
    conn = sqlite3.connect("assets.db")
    conn.row_factory = sqlite3.Row


    
    cursor = conn.cursor()
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
        where_clause = "WHERE cost_center = ?"
        params1 = (cost_center,cost_center)

    # ใส่ where_clause ลงใน SQL
    sql = base_sql.format(where_clause=where_clause)
    cursor.execute(sql, params1)
    rows = cursor.fetchall()
    disposal_labels = []
    disposal_values = []
    for disposal_status, count,percentage in rows:
        label = status_mapping.get(disposal_status, None)
        if label:
            disposal_labels.append(label)
            disposal_values.append(percentage)




    cursor = conn.cursor()
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
        where_clause = "WHERE cost_center = ?"
        params2 = (cost_center,cost_center)
    cursor.execute(sql, params2)
    rows = cursor.fetchall()
   
    assets_labels = []
    assets_values = []
    for status, count,percentage in rows:
        label = assets_status_mapping.get(status,None)
        if label:
            assets_labels.append(label)
            assets_values.append(percentage)
    
    
    cursor = conn.cursor()
    where_clause1 = ""
    params3 = ()
    if cost_center:
        where_clause1 = "AND assets.cost_center = ?"
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
            SUM(assets.book_value) AS total_book_value
        FROM status_map
        LEFT JOIN assets ON status_map.disposal_status = assets.disposal_status
        {where_clause1}
        GROUP BY status_map.disposal_status, status_map.status_name
        ORDER BY status_map.status_name
    """

    sql = base_sql.format(where_clause1=where_clause1)
    cursor.execute(sql, params3)
    disposal = cursor.fetchall()
    




    cursor = conn.cursor()
    where_clause =""
    params2 = ()
    if cost_center:
        where_clause  = "AND assets.cost_center = ?"
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
            SUM(assets.book_value) AS total_book_value
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
        where_clause5 = "WHERE cost_center = ?"
        params5 = (cost_center,)
    cursor = conn.cursor()
    base_sql = """
        SELECT
            ROUND(SUM(CASE WHEN asset_status = '2010' AND (disposal_status IS NULL OR disposal_status = '0') THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS percent_in_use,
            ROUND(SUM(CASE WHEN asset_status != '2010' AND disposal_status IN ('0','1','2','3','4','5','6','7','8','10') THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS percent_waiting_disposal,
            ROUND(SUM(CASE WHEN asset_status != '2010' AND disposal_status = '9' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS percent_disposed
        FROM assets
        {where_clause5}
        """
    sql = base_sql.format(where_clause5=where_clause5)
    
    
   
    cursor.execute(sql, params5)
    success_status = cursor.fetchone()

    success_values = list(success_status)

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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if disposal_status:
        cursor.execute("SELECT * FROM assets WHERE disposal_status = ? and book_value = 1 ORDER BY id ", (disposal_status,))
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
):
    image_base64 = None
    if image_file and image_file.filename:
        new_file = compress_image(image_file)
        new_file_data = new_file.read()
        image_base64 = base64.b64encode(new_file_data).decode("utf-8")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("xxxxx :",disposal_status)
    cursor.execute("""
        UPDATE assets 
        SET disposal_status = ?, 
            asset_status = ?,
            image = COALESCE(?, image)
        WHERE id = ?
    """, (disposal_status,asset_status, image_base64, id))


    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/asset?disposal_status={disposal_status_selected}&cost_center={cost_center}&asset_status={asset_status}", status_code=303)



@app.get("/delete-image/{id}")
def delete_image(id: int,disposal_status:str = "",cost_center:str ="",asset_status:str=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE assets SET image = NULL WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/asset?disposal_status={disposal_status}&cost_center={cost_center}&asset_status={asset_status}", status_code=303)



@app.get("/asset/{id}", response_class=HTMLResponse)
def asset_detail(request: Request, id: int,cost_center:str="",disposal_status:str="" ,asset_status:str=""):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM assets WHERE id = ?", (id,))
    asset = cursor.fetchone()

    cursor.execute("""
        SELECT id,status_code, status_description, ref_document, changed_at,asset_id
        FROM disposal_status_log
        WHERE asset_id = ?
        ORDER BY changed_at
    """, (id,))
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


@app.post("/assets/{asset_log_id}/delete")
def delete_asset(request: Request,asset_log_id: int ,disposal_status: str="",cost_center:str="",asset_status:str=""):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT asset_id FROM disposal_status_log WHERE id = ?", (asset_log_id,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return RedirectResponse(url="/assets", status_code=303)

    asset_id = row["asset_id"]
    # ลบ log
    cursor.execute("DELETE FROM disposal_status_log WHERE id = ?", (asset_log_id,))
    conn.commit()
    conn.close()

    # redirect กลับไปหน้าแสดง asset รายตัว
    return RedirectResponse(url=f"/asset/{asset_id}?disposal_status={disposal_status}&cost_center={cost_center}&asset_status={asset_status}", status_code=303)




@app.get("/download")
async def download_files(request: Request):
    files = [
        {"name": "0 หนังสือขอทราบมูลค่าทรัพย์สิน.pdf", "url": "/static/0 หนังสือขอทราบมูลค่าทรัพย์สิน.pdf"},
        {"name": "0.1 หนังสือแจ้งทรัพย์สินสภาพดีให้หน่วยงานอื่นใช้ต่อ.pdf", "url": "/static/0.1 หนังสือแจ้งทรัพย์สินสภาพดีให้หน่วยงานอื่นใช้ต่อ.pdf"},
        {"name": "1 หนังสือข้อความเห็นจากหน่วยงานที่เกี่ยวข้อง.pdf", "url": "/static/1 หนังสือข้อความเห็นจากหน่วยงานที่เกี่ยวข้อง.pdf"},
        {"name": "2 ขออนุมัติแต่งตั้งคณะกรรมการตรวจสอบข้อเท็จจริง.pdf", "url": "/static/2 ขออนุมัติแต่งตั้งคณะกรรมการตรวจสอบข้อเท็จจริง.pdf"},
        {"name": "2.2 ขออนุมัติแต่งตั้งคณะกรรมการตรวจสอบข้อเท็จจริง(ยานพาหนะ).pdf", "url": "/static/2.2 ขออนุมัติแต่งตั้งคณะกรรมการตรวจสอบข้อเท็จจริง(ยานพาหนะ).pdf"},
        {"name": "3 รายงานผลการตรวจสอบข้อเท็จจริง.pdf", "url": "/static/3 รายงานผลการตรวจสอบข้อเท็จจริง.pdf"},
        {"name": "3.1 รายงานผลการตรวจสอบข้อเท็จจริง (ทำลาย).pdf", "url": "/static/3.1 รายงานผลการตรวจสอบข้อเท็จจริง (ทำลาย).pdf"},
        {"name": "3.2 รายงานผลการตรวจสอบข้อเท็จจริง(ยานพาหนะ).pdf", "url": "/static/3.2 รายงานผลการตรวจสอบข้อเท็จจริง(ยานพาหนะ).pdf"},
        {"name": "4 ขออนุมัติใรหลักการจำหน่ายทรัพย์สิน.pdf", "url": "/static/4 ขออนุมัติใรหลักการจำหน่ายทรัพย์สิน.pdf"},
        {"name": "4.1 ขออนุมัติใรหลักการจำหน่ายทรัพย์สิน(ทำลาย).pdf", "url": "/static/4.1 ขออนุมัติใรหลักการจำหน่ายทรัพย์สิน(ทำลาย).pdf"},
        {"name": "4.2 ขออนุมัติใรหลักการจำหน่ายทรัพย์สิน(ยานพาหนะ).pdf", "url": "/static/4.2 ขออนุมัติใรหลักการจำหน่ายทรัพย์สิน(ยานพาหนะ).pdf"},
    ]
    return templates.TemplateResponse("downloads.html", {"request": request, "files": files})







@app.get("/report", response_class=HTMLResponse)
def dashboard(request: Request ,cost_center: str = "", asset_status:str =""):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    print("cost_center: ",cost_center ,"asset_status :",asset_status)
    if checkEmptyNone(cost_center) and  checkEmptyNone(asset_status) and asset_status == "2010":
        print(1)
        cursor.execute("SELECT * FROM assets where cost_center =? and asset_status =? ORDER BY book_value,id ", (cost_center,asset_status))
    elif checkEmptyNone(cost_center) and  checkEmptyNone(asset_status) and asset_status == "0000":
        print(11)
        cursor.execute("SELECT * FROM assets where cost_center =? and asset_status !=? ORDER BY book_value,id ", (cost_center,"2010"))
    elif checkEmptyNone(cost_center) and  not checkEmptyNone(asset_status):
        print(111)
        cursor.execute("SELECT * FROM assets where cost_center =?  ORDER BY book_value,id ", (cost_center,))
    elif not checkEmptyNone(cost_center) and   checkEmptyNone(asset_status) and asset_status == "2010":
        print(1111)
        cursor.execute("SELECT * FROM assets where asset_status =?  ORDER BY book_value,id ", (asset_status,))
    elif not checkEmptyNone(cost_center) and   checkEmptyNone(asset_status) and asset_status == "0000":
        print(11112)
        cursor.execute("SELECT * FROM assets where asset_status !=?  ORDER BY book_value,id ", ("2010",))
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
    cost_center: str = Form("")
):
    print("Selected asset IDs:", select)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # prepare SQL
    placeholders = ','.join(['?'] * len(select))  # '?, ?, ?, ?'
    query = f"SELECT * FROM assets WHERE id IN ({placeholders}) ORDER BY book_value, id"
    cursor.execute(query, select)
    rows = cursor.fetchall()
    conn.close()

    return templates.TemplateResponse("report-result.html", {
        "cost_center": cost_center,
        "request": request,
        "assets": rows,
        "today_date": datetime.today().strftime('%d/%m/%Y') , # 🗓️ ส่งวันที่วันนี้
        "cost_center_mapping": cost_center_mapping
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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE disposal_status_log
        SET ref_document = ?
        WHERE id = ?
    """, (ref_document, log_id))
    conn.commit()

    return RedirectResponse(
        url=f"/asset/{asset_id}?cost_center={cost_center}&disposal_status={disposal_status}&asset_status={asset_status}",
        status_code=303
    )

    


