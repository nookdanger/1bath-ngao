# main.py
from fastapi import FastAPI, Request, Form, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
import os
import base64

app = FastAPI()
templates = Jinja2Templates(directory="templates")
DB_PATH = os.path.join(os.path.dirname(__file__), "assets.db")



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
def dashboard(request: Request, status: str = None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if status:
        cursor.execute("SELECT * FROM assets WHERE disposal_status = ? ORDER BY id ", (status,))
    else:
        cursor.execute("SELECT * FROM assets ORDER BY id ")

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





