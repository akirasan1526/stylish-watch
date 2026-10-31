import os import time import json import hmac import hashlib from urllib.parse import parse_qsl
import httpx from fastapi import FastAPI, Request, HTTPException from fastapi.staticfiles import StaticFiles from fastapi.responses import FileResponse
app = FastAPI()
BOT_TOKEN = os.getenv("BOT_TOKEN", "") ADMIN_ID = os.getenv("ADMIN_CHAT_ID", "")
PRODUCTS = [ {"id": "zinvo", "brand": "ZINVO", "name": "ZINVO Watch"}, {"id": "d1", "brand": "D1 MILANO", "name": "D1 Milano Watch"} ]
app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/") async def home(): return FileResponse("static/index.html")
@app.get("/api/products") async def products(): return PRODUCTS
def validate_user(init_data): if not BOT_TOKEN or not init_data: return None
values = dict(parse_qsl(init_data))
received = values.pop("hash", None)

if not received:
    return None

data = "\n".join(
    f"{k}={v}" for k, v in sorted(values.items())
)

secret = hmac.new(
    b"WebAppData",
    BOT_TOKEN.encode(),
    hashlib.sha256
).digest()

calculated = hmac.new(
    secret, data.encode(), hashlib.sha256
).hexdigest()

if not hmac.compare_digest(received, calculated):
    return None

try:
    if time.time() - int(values["auth_date"]) > 86400:
        return None
    return json.loads(values["user"])
except (KeyError, ValueError, TypeError):
    return None
@app.post("/api/order") async def order(request: Request): user = validate_user( request.headers.get("X-Telegram-Init-Data", "") )
if not user:
    raise HTTPException(401, "Invalid Telegram session")

data = await request.json()
name = str(data.get("name", "")).strip()[:80]
phone = str(data.get("phone", "")).strip()[:30]
items = data.get("items", [])

if not name or not phone:
    raise HTTPException(400, "Enter your name and phone")

if not isinstance(items, list) or not items or len(items) > 30:
    raise HTTPException(400, "Invalid cart")

allowed = {p["id"]: p["name"] for p in PRODUCTS}

for item in items:
    if (
        not isinstance(item, dict)
        or item.get("id") not in allowed
        or type(item.get("qty")) is not int
        or not 1 <= item["qty"] <= 20
    ):
        raise HTTPException(400, "Invalid product")

if not ADMIN_ID or not BOT_TOKEN:
    raise HTTPException(503, "Admin not configured")

lines = [
    f"{allowed[item['id']]} x {item['qty']}"
    for item in items
]

message = (
    "NEW STYLIST WATCH ORDER\n\n"
    f"Customer: {name}\n"
    f"Phone: {phone}\n"
    f"Telegram ID: {user['id']}\n\n"
    + "\n".join(lines)
)

async with httpx.AsyncClient(timeout=15) as client:
    response = await client.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": ADMIN_ID, "text": message}
    )

if response.status_code != 200 or not response.json().get("ok"):
    raise HTTPException(502, "Order notification failed")

return {"success": True}