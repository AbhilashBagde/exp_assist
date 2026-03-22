from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pymongo import MongoClient
from datetime import datetime, timedelta
from typing import Optional, List
from collections import defaultdict
import os
import jwt
import bcrypt
import json
import base64
import io
import re
import time
import httpx
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.platypus.frames import Frame
from PIL import Image as PILImage
from pdf2image import convert_from_bytes
import uuid
import certifi

# Load environment variables
load_dotenv()

app = FastAPI()

# CORS Configuration - restrict in production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple Rate Limiting (in-memory, per IP)
rate_limit_store = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 60  # max requests per window

@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    # Clean old entries
    rate_limit_store[client_ip] = [t for t in rate_limit_store[client_ip] if now - t < RATE_LIMIT_WINDOW]
    if len(rate_limit_store[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        return JSONResponse(status_code=429, content={"detail": "Too many requests. Please try again later."})
    rate_limit_store[client_ip].append(now)
    response = await call_next(request)
    return response

# MongoDB Connection
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/tradesdocai")

# Add tlsCAFile=certifi.where() to fix the SSL Handshake error
client = MongoClient(MONGO_URL, tlsCAFile=certifi.where()) 
db = client.tradesdocai

# Collections
users_collection = db.users
profiles_collection = db.company_profiles
shipments_collection = db.shipments

# Indexes (idempotent — safe to run on every startup)
users_collection.create_index("email", unique=True, background=True)
profiles_collection.create_index("user_id", unique=True, background=True)
shipments_collection.create_index("user_id", background=True)
shipments_collection.create_index("po_number", background=True)
shipments_collection.create_index([("user_id", 1), ("created_at", -1)], background=True)

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"

# Gemini AI Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Security
security = HTTPBearer()

# Create uploads directory
UPLOADS_DIR = Path("uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

# Auto Invoice Numbering
def get_next_invoice_number(user_id: str) -> str:
    """Generate next sequential invoice number for a user (INV-001, INV-002, etc.)"""
    # Find the highest invoice number for this user
    last_shipment = shipments_collection.find_one(
        {"user_id": user_id, "invoice_number": {"$exists": True, "$ne": ""}},
        sort=[("invoice_number", -1)]
    )
    if last_shipment and last_shipment.get("invoice_number"):
        # Extract number from INV-XXX format
        match = re.search(r'INV-(\d+)', last_shipment["invoice_number"])
        if match:
            next_num = int(match.group(1)) + 1
            return f"INV-{next_num:03d}"
    return "INV-001"

# Fallback Exchange Rates to INR (used when API fails)
FALLBACK_RATES_TO_INR = {
    "USD": 83.50,
    "EUR": 90.50,
    "GBP": 105.50,
    "AED": 22.75,
    "SGD": 62.00,
    "INR": 1.00,
    "JPY": 0.56,
    "CAD": 61.50,
    "AUD": 54.00,
}

# Cache for exchange rates (to avoid too many API calls)
exchange_rate_cache = {
    "rates": {},
    "last_updated": None
}

async def fetch_live_exchange_rates():
    """Fetch live exchange rates from free API"""
    try:
        # Check if cache is still valid (less than 1 hour old)
        if exchange_rate_cache["last_updated"]:
            time_diff = datetime.utcnow() - exchange_rate_cache["last_updated"]
            if time_diff.total_seconds() < 3600:  # 1 hour cache
                return exchange_rate_cache["rates"]
        
        # Fetch from free API (frankfurter.app - no API key required)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.frankfurter.app/latest?to=INR",
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                inr_rate_from_eur = data["rates"]["INR"]
                
                # Now get rates from EUR to other currencies
                response2 = await client.get(
                    "https://api.frankfurter.app/latest?from=EUR",
                    timeout=10.0
                )
                
                if response2.status_code == 200:
                    data2 = response2.json()
                    rates_from_eur = data2["rates"]
                    
                    # Calculate rates to INR for each currency
                    rates_to_inr = {"INR": 1.00, "EUR": inr_rate_from_eur}
                    for currency, rate_from_eur in rates_from_eur.items():
                        if currency != "INR":
                            # Convert: 1 currency = X EUR, 1 EUR = Y INR
                            # So 1 currency = Y/X INR
                            rates_to_inr[currency] = inr_rate_from_eur / rate_from_eur
                    
                    # Update cache
                    exchange_rate_cache["rates"] = rates_to_inr
                    exchange_rate_cache["last_updated"] = datetime.utcnow()
                    
                    return rates_to_inr
        
        # Return cached rates if available, else fallback
        return exchange_rate_cache["rates"] if exchange_rate_cache["rates"] else FALLBACK_RATES_TO_INR
        
    except Exception as e:
        print(f"Error fetching exchange rates: {e}")
        # Return cached rates if available, else fallback
        return exchange_rate_cache["rates"] if exchange_rate_cache["rates"] else FALLBACK_RATES_TO_INR

def get_inr_rate_sync(currency: str, rates: dict = None) -> float:
    """Get exchange rate to convert currency to INR (sync version)"""
    if rates:
        return rates.get(currency.upper(), FALLBACK_RATES_TO_INR.get(currency.upper(), 83.50))
    return FALLBACK_RATES_TO_INR.get(currency.upper(), 83.50)

# Helper Functions
def create_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Seed demo account on startup (credentials set via env vars)
DEMO_EMAIL = os.getenv("DEMO_EMAIL", "")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "")

if DEMO_EMAIL and DEMO_PASSWORD:
    existing = users_collection.find_one({"email": DEMO_EMAIL})
    if not existing:
        _hash = bcrypt.hashpw(DEMO_PASSWORD.encode('utf-8'), bcrypt.gensalt())
        users_collection.insert_one({
            "_id": str(__import__('uuid').uuid4()),
            "email": DEMO_EMAIL,
            "password_hash": _hash,
            "is_pro_member": True,
            "created_at": datetime.utcnow()
        })

# Auth Endpoints
@app.post("/api/auth/auto-session")
async def auto_session():
    """Single-user auto-authentication — creates default user on first run and returns a JWT."""
    DEFAULT_USER_ID = "default_user"
    DEFAULT_EMAIL = "admin@local"

    user = users_collection.find_one({"_id": DEFAULT_USER_ID})
    if not user:
        users_collection.insert_one({
            "_id": DEFAULT_USER_ID,
            "email": DEFAULT_EMAIL,
            "password_hash": b"",
            "is_pro_member": True,
            "created_at": datetime.utcnow()
        })

    token = create_token(DEFAULT_USER_ID)
    return {"token": token, "user_id": DEFAULT_USER_ID, "is_pro_member": True}


@app.post("/api/auth/signup")
async def signup(email: str = Form(...), password: str = Form(...)):
    if users_collection.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    user_id = str(uuid.uuid4())
    
    users_collection.insert_one({
        "_id": user_id,
        "email": email,
        "password_hash": password_hash,
        "is_pro_member": False,
        "created_at": datetime.utcnow()
    })
    
    token = create_token(user_id)
    return {"token": token, "user_id": user_id, "email": email}

@app.post("/api/auth/login")
async def login(email: str = Form(...), password: str = Form(...)):
    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not bcrypt.checkpw(password.encode('utf-8'), user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user["_id"])
    return {
        "token": token, 
        "user_id": user["_id"], 
        "email": user["email"],
        "is_pro_member": user.get("is_pro_member", False)
    }

# Get User Info (including pro status)
@app.get("/api/user/me")
async def get_user_info(user_id: str = Depends(verify_token)):
    user = users_collection.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_id": user["_id"],
        "email": user["email"],
        "is_pro_member": user.get("is_pro_member", False),
        "created_at": user["created_at"].isoformat()
    }

# Exchange Rate Endpoint
@app.get("/api/exchange-rates")
async def get_exchange_rates(currency: str = None):
    """Get live exchange rates to INR"""
    # Fetch live rates
    live_rates = await fetch_live_exchange_rates()
    
    is_live = exchange_rate_cache["last_updated"] is not None
    last_updated = exchange_rate_cache["last_updated"].isoformat() if exchange_rate_cache["last_updated"] else None
    
    if currency:
        rate = live_rates.get(currency.upper(), FALLBACK_RATES_TO_INR.get(currency.upper(), 83.50))
        return {
            "currency": currency.upper(),
            "rate_to_inr": round(rate, 2),
            "is_live": is_live,
            "last_updated": last_updated,
            "rates": {k: round(v, 2) for k, v in live_rates.items()}
        }
    return {
        "base": "INR",
        "is_live": is_live,
        "last_updated": last_updated,
        "rates": {k: round(v, 2) for k, v in live_rates.items()}
    }

# Company Profile Endpoints
@app.get("/api/profile")
async def get_profile(user_id: str = Depends(verify_token)):
    profile = profiles_collection.find_one({"user_id": user_id})
    if not profile:
        return {"exists": False}
    
    profile["_id"] = str(profile["_id"])
    profile["exists"] = True
    return profile

@app.post("/api/profile")
async def save_profile(
    user_id: str = Depends(verify_token),
    company_name: str = Form(...),
    address_line1: str = Form(...),
    address_line2: str = Form(""),
    iec_code: str = Form(...),
    gst_number: str = Form(...),
    ad_code: str = Form(""),
    bank_name: str = Form(...),
    account_number: str = Form(...),
    ifsc_code: str = Form(...),
    swift_code: str = Form(""),
    tally_sales_ledger_name: str = Form("Export Sales")
):
    profile_data = {
        "user_id": user_id,
        "company_name": company_name,
        "address_line1": address_line1,
        "address_line2": address_line2,
        "iec_code": iec_code,
        "gst_number": gst_number,
        "ad_code": ad_code,
        "bank_name": bank_name,
        "account_number": account_number,
        "ifsc_code": ifsc_code,
        "swift_code": swift_code,
        "tally_sales_ledger_name": tally_sales_ledger_name,
        "updated_at": datetime.utcnow()
    }
    
    profiles_collection.update_one(
        {"user_id": user_id},
        {"$set": profile_data},
        upsert=True
    )
    
    return {"success": True, "message": "Profile saved successfully"}

@app.post("/api/profile/signature")
async def upload_signature(
    user_id: str = Depends(verify_token),
    signature: UploadFile = File(...)
):
    # Save signature file
    file_ext = signature.filename.split('.')[-1]
    filename = f"signature_{user_id}.{file_ext}"
    file_path = UPLOADS_DIR / filename
    
    with open(file_path, "wb") as f:
        content = await signature.read()
        f.write(content)
    
    # Update profile with signature URL
    signature_url = f"/uploads/{filename}"
    profiles_collection.update_one(
        {"user_id": user_id},
        {"$set": {"signature_image_url": signature_url}},
        upsert=True
    )
    
    return {"success": True, "signature_url": signature_url}

# Next Invoice Number Endpoint
@app.get("/api/next-invoice-number")
async def next_invoice_number(user_id: str = Depends(verify_token)):
    return {"invoice_number": get_next_invoice_number(user_id)}

# Shipments Endpoints
@app.get("/api/shipments")
async def get_shipments(user_id: str = Depends(verify_token)):
    shipments = list(shipments_collection.find({"user_id": user_id}).sort("created_at", -1))
    for shipment in shipments:
        shipment["_id"] = str(shipment["_id"])
        shipment["created_at"] = shipment["created_at"].isoformat()
    return shipments

@app.get("/api/shipments/{shipment_id}")
async def get_shipment(shipment_id: str, user_id: str = Depends(verify_token)):
    shipment = shipments_collection.find_one({"_id": shipment_id, "user_id": user_id})
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    shipment["_id"] = str(shipment["_id"])
    shipment["created_at"] = shipment["created_at"].isoformat()
    return shipment

@app.post("/api/shipments")
async def create_shipment(
    user_id: str = Depends(verify_token),
    buyer_name: str = Form(...),
    buyer_address: str = Form(""),
    po_number: str = Form(...),
    po_date: str = Form(...),
    items: str = Form(...),  # JSON string
    currency: str = Form("USD"),  # Default to USD
    port_of_loading: str = Form(""),
    port_of_discharge: str = Form(""),
    incoterms: str = Form("FOB"),
    total_packages: int = Form(1),
    package_type: str = Form("BOXES"),
    include_inr_column: str = Form("false"),
    consignee: str = Form(""),
    notify_party: str = Form(""),
    payment_terms: str = Form(""),
    marks_and_numbers: str = Form(""),
    tariff_code: str = Form(""),
    invoice_number_override: str = Form("")
):
    items_list = json.loads(items)

    # Parse include_inr_column as boolean
    include_inr_bool = include_inr_column.lower() in ('true', '1', 'yes')

    # Use user-supplied invoice number or auto-generate
    invoice_number = invoice_number_override.strip() if invoice_number_override.strip() else get_next_invoice_number(user_id)

    shipment_id = str(uuid.uuid4())
    shipment_data = {
        "_id": shipment_id,
        "user_id": user_id,
        "invoice_number": invoice_number,
        "buyer_name": buyer_name,
        "buyer_address": buyer_address,
        "po_number": po_number,
        "po_date": po_date,
        "currency": currency,
        "port_of_loading": port_of_loading,
        "port_of_discharge": port_of_discharge,
        "incoterms": incoterms,
        "total_packages": total_packages,
        "package_type": package_type,
        "include_inr_column": include_inr_bool,
        "consignee": consignee,
        "notify_party": notify_party,
        "payment_terms": payment_terms,
        "marks_and_numbers": marks_and_numbers,
        "tariff_code": tariff_code,
        "status": "Draft",
        "items": items_list,
        "created_at": datetime.utcnow()
    }

    shipments_collection.insert_one(shipment_data)

    return {"success": True, "shipment_id": shipment_id, "invoice_number": invoice_number}

@app.put("/api/shipments/{shipment_id}")
async def update_shipment(
    shipment_id: str,
    user_id: str = Depends(verify_token),
    buyer_name: str = Form(...),
    buyer_address: str = Form(""),
    po_number: str = Form(...),
    po_date: str = Form(...),
    items: str = Form(...),
    currency: str = Form("USD"),
    status: str = Form("Draft"),
    port_of_loading: str = Form(""),
    port_of_discharge: str = Form(""),
    incoterms: str = Form("FOB"),
    total_packages: int = Form(1),
    package_type: str = Form("BOXES"),
    consignee: str = Form(""),
    notify_party: str = Form(""),
    payment_terms: str = Form(""),
    marks_and_numbers: str = Form(""),
    tariff_code: str = Form(""),
    include_inr_column: str = Form("false")
):
    items_list = json.loads(items)
    include_inr_bool = include_inr_column.lower() in ('true', '1', 'yes')

    result = shipments_collection.update_one(
        {"_id": shipment_id, "user_id": user_id},
        {"$set": {
            "buyer_name": buyer_name,
            "buyer_address": buyer_address,
            "po_number": po_number,
            "po_date": po_date,
            "currency": currency,
            "port_of_loading": port_of_loading,
            "port_of_discharge": port_of_discharge,
            "incoterms": incoterms,
            "total_packages": total_packages,
            "package_type": package_type,
            "consignee": consignee,
            "notify_party": notify_party,
            "payment_terms": payment_terms,
            "marks_and_numbers": marks_and_numbers,
            "tariff_code": tariff_code,
            "include_inr_column": include_inr_bool,
            "items": items_list,
            "status": status,
            "updated_at": datetime.utcnow()
        }}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Shipment not found")

    return {"success": True}

# Delete Shipment Endpoint
@app.delete("/api/shipments/{shipment_id}")
async def delete_shipment(shipment_id: str, user_id: str = Depends(verify_token)):
    """Delete a shipment and its associated files"""
    shipment = shipments_collection.find_one({"_id": shipment_id, "user_id": user_id})
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # Delete associated files (invoice PDF, packing list, tally XML)
    for prefix in ["invoice_", "packing_list_", "tally_export_"]:
        for ext in [".pdf", ".xml"]:
            file_path = UPLOADS_DIR / f"{prefix}{shipment_id}{ext}"
            if file_path.exists():
                file_path.unlink()
    
    result = shipments_collection.delete_one({"_id": shipment_id, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    return {"success": True, "message": "Shipment deleted successfully"}

# Duplicate PO Check Endpoint
@app.get("/api/shipments/check-duplicate-po")
async def check_duplicate_po(
    po_number: str = Query(...),
    user_id: str = Depends(verify_token)
):
    """Check if a PO number already exists for the user"""
    existing = shipments_collection.find_one({"user_id": user_id, "po_number": po_number})
    return {
        "is_duplicate": existing is not None,
        "existing_shipment_id": str(existing["_id"]) if existing else None,
        "buyer_name": existing.get("buyer_name", "") if existing else None
    }

# Revert Shipment to Draft (allow re-editing after finalization)
@app.post("/api/shipments/{shipment_id}/revert-to-draft")
async def revert_to_draft(shipment_id: str, user_id: str = Depends(verify_token)):
    """Revert a finalized shipment back to Draft for re-editing"""
    shipment = shipments_collection.find_one({"_id": shipment_id, "user_id": user_id})
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    shipments_collection.update_one(
        {"_id": shipment_id, "user_id": user_id},
        {"$set": {"status": "Draft", "updated_at": datetime.utcnow()}}
    )
    
    return {"success": True, "message": "Shipment reverted to Draft"}

# Search/Filter Shipments
@app.get("/api/shipments/search")
async def search_shipments(
    q: str = Query("", description="Search term"),
    status_filter: str = Query("", description="Filter by status: Draft, Final"),
    user_id: str = Depends(verify_token)
):
    """Search shipments by buyer name, PO number, or filter by status"""
    query = {"user_id": user_id}
    
    if q:
        query["$or"] = [
            {"buyer_name": {"$regex": q, "$options": "i"}},
            {"po_number": {"$regex": q, "$options": "i"}}
        ]
    
    if status_filter:
        query["status"] = status_filter
    
    shipments = list(shipments_collection.find(query).sort("created_at", -1))
    for shipment in shipments:
        shipment["_id"] = str(shipment["_id"])
        shipment["created_at"] = shipment["created_at"].isoformat()
    return shipments

# AI Vision Processing Endpoint
@app.post("/api/shipments/extract")
async def extract_po_data(
    user_id: str = Depends(verify_token),
    file: UploadFile = File(...)
):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Convert to images if PDF (support multi-page)
        if file.filename.lower().endswith('.pdf'):
            images = convert_from_bytes(file_content)
            # Process ALL pages for multi-page PO support
            page_images = []
            for page in images:
                img_byte_arr = io.BytesIO()
                page.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                page_images.append(PILImage.open(io.BytesIO(img_byte_arr.getvalue())))
        else:
            page_images = [PILImage.open(io.BytesIO(file_content))]
        
        prompt = """You are an expert at reading Indian export Purchase Order documents. Extract ALL fields carefully and return ONLY a valid JSON object with no markdown or extra text.

{
  "buyer_name": "Name of the buyer/importer company",
  "buyer_address": "Full address of the buyer",
  "po_number": "Purchase Order number",
  "po_date": "Date in YYYY-MM-DD format, or null if not found",
  "currency_code": "Currency code (USD, EUR, GBP, AED, SGD, INR)",
  "consignee": "Consignee if different from buyer; null if not stated",
  "notify_party": "Notify party if stated; null if not stated",
  "payment_terms": "Full payment terms exactly as written; null if not stated",
  "port_of_loading": "Port of loading if specified; null if not stated",
  "port_of_discharge": "Port of discharge / destination port if specified; null if not stated",
  "marks_and_numbers": "Shipping marks or marks & numbers if stated; null if not stated",
  "tariff_code": "HS/HTS/Tariff code stated in the PO at document level; null if not present",
  "total_net_weight": <total net weight as number, kg, or null>,
  "total_gross_weight": <total gross weight as number, kg, or null>,
  "items": [
    {
      "description": "Full item description as written in the PO",
      "quantity": <quantity as a plain number, e.g. 22000>,
      "unit_of_measure": "Unit exactly as written, e.g. KG, MT, NOS, PCS, LTR, CTN",
      "unit_price": <price per unit as a plain number, e.g. 1.285 — extract the numeric value only, strip currency symbols and unit text>,
      "hs_code": "8-digit ITC-HS code as string with NO dots/spaces — use any tariff/HS code stated in the PO for this product; if none stated use your expert knowledge of Indian ITC-HS schedule",
      "net_weight": <net weight for this line item as number in KG, or 0 if not stated>,
      "gross_weight": <gross weight for this line item as number in KG, or 0 if not stated>
    }
  ]
}

EXTRACTION RULES:

QUANTITY: Look for Qty, Quantity, Amount (units). Extract the plain number (e.g. 22000, not "22,000.0000 KG").

UNIT PRICE / RATE: Look for Rate, Price, Unit Price, Price/Unit columns. Extract ONLY the numeric value (e.g. if you see "1.2850 USD / KG" extract 1.2850).

NET / GROSS WEIGHT: Look for Net Wt, Gross Wt, Net Weight, Gross Weight anywhere in the document including marks/shipping sections. Distribute total weight across items proportionally if per-item weight is not stated.

HS CODE PER ITEM (CRITICAL):
- If the PO states a Tariff Code, HS Code, or HTS Code anywhere, USE IT for the relevant item
- Format as EXACTLY 8 digits, NO dots, dashes, or spaces (e.g. "15121100" not "1512.11")
- If only 6 digits given, append "00" (e.g. "151211" → "15121100")
- If no code is stated, use your expert knowledge of the Indian ITC-HS schedule to predict the correct 8-digit code

CURRENCY DETECTION:
- $ / USD → "USD" | £ / GBP → "GBP" | € / EUR → "EUR" | ₹ / Rs / INR → "INR" | د.إ / AED → "AED" | S$ / SGD → "SGD"
- Default → "USD"

Return ONLY the JSON object, no additional text or markdown."""

        # Try multimodal models in order, fall back on any error
        extraction_models = ['models/gemini-3-flash', 'models/gemini-2.5-flash']
        response = None
        last_error = None
        for model_name in extraction_models:
            try:
                m = genai.GenerativeModel(model_name)
                response = m.generate_content([prompt] + page_images)
                break
            except Exception as e:
                last_error = e
                continue
        if response is None:
            raise last_error
        
        # Parse the response
        result_text = response.text.strip()
        
        # Clean up response (remove markdown code blocks if present)
        if result_text.startswith('```json'):
            result_text = result_text[7:]
        if result_text.startswith('```'):
            result_text = result_text[3:]
        if result_text.endswith('```'):
            result_text = result_text[:-3]
        
        result_text = result_text.strip()
        
        # Parse JSON
        extracted_data = json.loads(result_text)
        print("DEBUG extraction raw:", json.dumps(extracted_data, indent=2)[:2000])

        items = extracted_data.get('items', [])
        doc_tariff = extracted_data.get('tariff_code') or ''  # treat null as ''
        total_net = extracted_data.get('total_net_weight') or 0
        total_gross = extracted_data.get('total_gross_weight') or 0
        n_items = len(items) if items else 1

        for item in items:
            # Ensure numeric types
            item['quantity'] = float(item.get('quantity') or 0)
            item['unit_price'] = float(item.get('unit_price') or 0)
            item['total_amount'] = round(item['quantity'] * item['unit_price'], 2)

            # Normalize hs_code: strip dots/spaces, pad to 8 digits
            # Use item-level code first, fall back to document tariff_code
            raw_hs = str(item.get('hs_code') or '').strip()
            if not raw_hs and doc_tariff:
                raw_hs = str(doc_tariff).strip()
            hs = re.sub(r'[^0-9]', '', raw_hs)  # strip dots, spaces, dashes
            if len(hs) == 6:
                hs += '00'
            item['hs_code'] = hs[:8] if len(hs) >= 6 else ''

            # Distribute document-level net/gross weight if per-item weights are missing
            if not item.get('net_weight') and total_net:
                item['net_weight'] = round(total_net / n_items, 2)
            else:
                item['net_weight'] = float(item.get('net_weight') or 0)

            if not item.get('gross_weight') and total_gross:
                item['gross_weight'] = round(total_gross / n_items, 2)
            else:
                item['gross_weight'] = float(item.get('gross_weight') or 0)

            # Ensure remaining dimension fields exist
            item.setdefault('length_cm', 0)
            item.setdefault('width_cm', 0)
            item.setdefault('height_cm', 0)

        extracted_data['items'] = items
        return extracted_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

# AI HS Code Suggestion Endpoint
@app.post("/api/suggest-hs-code")
async def suggest_hs_code(
    user_id: str = Depends(verify_token),
    description: str = Form(...)
):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")
    
    if not description or len(description.strip()) < 3:
        raise HTTPException(status_code=400, detail="Please provide a valid item description")
    
    try:
        prompt = f"""You are an expert in Indian ITC-HS Code classification for export goods.

Based on the following product description, predict the most appropriate Indian ITC-HS Code.

Product Description: "{description}"

Respond with ONLY a JSON object in this exact format:
{{
  "hs_code": "XXXXXXXX",
  "confidence": "high/medium/low",
  "category": "Brief category name",
  "notes": "Brief explanation"
}}

CRITICAL: hs_code must be EXACTLY 8 digits with NO dots, dashes or spaces.
Examples: Basmati Rice -> "10063000", Sunflower Oil -> "15121100", Cotton Fabric -> "52081200", Tea -> "09024090"

Return ONLY the JSON object, no additional text."""

        # Try all models in order, falling back on ANY error
        models_to_try = ['models/gemini-3-flash', 'models/gemini-2.5-flash']
        response = None
        last_error = None
        for model_name in models_to_try:
            try:
                m = genai.GenerativeModel(model_name)
                response = m.generate_content(prompt)
                break
            except Exception as e:
                last_error = e
                continue  # always try next model
        if response is None:
            raise last_error

        result_text = response.text.strip()
        if result_text.startswith('```json'):
            result_text = result_text[7:]
        if result_text.startswith('```'):
            result_text = result_text[3:]
        if result_text.endswith('```'):
            result_text = result_text[:-3]
        result_text = result_text.strip()

        suggestion = json.loads(result_text)

        # Normalize hs_code: strip non-digits, pad to 8
        raw = re.sub(r'[^0-9]', '', str(suggestion.get("hs_code", "")))
        if len(raw) == 6:
            raw += '00'
        hs_code = raw[:8] if len(raw) >= 6 else raw

        return {
            "success": True,
            "hs_code": hs_code,
            "confidence": suggestion.get("confidence", "medium"),
            "category": suggestion.get("category", ""),
            "notes": suggestion.get("notes", "")
        }

    except json.JSONDecodeError:
        hs_match = re.search(r'\d{6,8}', response.text if response else '')
        if hs_match:
            raw = hs_match.group()[:8]
            return {"success": True, "hs_code": raw, "confidence": "low", "category": "", "notes": "Extracted from AI response"}
        raise HTTPException(status_code=500, detail="Failed to parse AI response")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"HS Code suggestion failed: {str(e)}")

# PDF Generation Endpoint
@app.post("/api/shipments/{shipment_id}/generate-pdf")
async def generate_invoice_pdf(shipment_id: str, user_id: str = Depends(verify_token)):
    # Get shipment data
    shipment = shipments_collection.find_one({"_id": shipment_id, "user_id": user_id})
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # FEATURE 2: Recalculate all totals before generating PDF
    for item in shipment['items']:
        item['total_amount'] = item['quantity'] * item['unit_price']
    
    # Get company profile
    profile = profiles_collection.find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Company profile not found")
    
    # Create PDF
    pdf_filename = f"invoice_{shipment_id}.pdf"
    pdf_path = UPLOADS_DIR / pdf_filename
    
    styles = getSampleStyleSheet()
    currency = shipment.get('currency', 'USD')
    
    # Calculate totals upfront
    total_amount = sum(item['total_amount'] for item in shipment['items'])
    total_packages = shipment.get('total_packages', 1)
    package_type = shipment.get('package_type', 'BOXES')
    total_net_weight = sum(item.get('net_weight', 0) for item in shipment['items'])
    total_gross_weight = sum(item.get('gross_weight', 0) for item in shipment['items'])
    
    # ========== CUSTOM DOCUMENT CLASS FOR MULTI-PAGE SUPPORT ==========
    class InvoiceDocTemplate(BaseDocTemplate):
        def __init__(self, filename, **kwargs):
            self.company_name = kwargs.pop('company_name', '')
            self.invoice_no = kwargs.pop('invoice_no', '')
            self.invoice_date = kwargs.pop('invoice_date', '')
            BaseDocTemplate.__init__(self, filename, **kwargs)
            
            # Define frame for content
            frame = Frame(
                self.leftMargin, 
                self.bottomMargin + 0.4*inch,  # Leave space for footer
                self.width, 
                self.height - 0.8*inch,  # Leave space for header on later pages
                id='normal'
            )
            
            # First page template (full header)
            first_frame = Frame(
                self.leftMargin,
                self.bottomMargin + 0.4*inch,
                self.width,
                self.height - 0.4*inch,
                id='first'
            )
            
            # Later pages template (compact header)
            later_frame = Frame(
                self.leftMargin,
                self.bottomMargin + 0.4*inch,
                self.width,
                self.height - 0.8*inch,
                id='later'
            )
            
            self.addPageTemplates([
                PageTemplate(id='First', frames=[first_frame], onPage=self.on_first_page),
                PageTemplate(id='Later', frames=[later_frame], onPage=self.on_later_pages),
            ])
        
        def on_first_page(self, canvas, doc):
            canvas.saveState()
            # Page number at bottom
            canvas.setFont('Helvetica', 9)
            canvas.setFillColor(colors.grey)
            page_num_text = f"Page {doc.page}"
            canvas.drawCentredString(A4[0]/2, 0.3*inch, page_num_text)
            canvas.restoreState()
        
        def on_later_pages(self, canvas, doc):
            canvas.saveState()
            
            # Compact header for continuation pages
            canvas.setFont('Helvetica-Bold', 12)
            canvas.setFillColor(colors.HexColor('#0f172a'))
            canvas.drawString(0.5*inch, A4[1] - 0.4*inch, f"{self.company_name}")
            
            canvas.setFont('Helvetica', 10)
            canvas.drawString(0.5*inch, A4[1] - 0.6*inch, f"Invoice: {self.invoice_no} | Date: {self.invoice_date}")
            
            # "Continued" indicator
            canvas.setFont('Helvetica-Oblique', 9)
            canvas.setFillColor(colors.grey)
            canvas.drawRightString(A4[0] - 0.5*inch, A4[1] - 0.5*inch, "...continued")
            
            # Line separator
            canvas.setStrokeColor(colors.HexColor('#0f172a'))
            canvas.setLineWidth(1)
            canvas.line(0.5*inch, A4[1] - 0.7*inch, A4[0] - 0.5*inch, A4[1] - 0.7*inch)
            
            # Page number at bottom
            canvas.setFont('Helvetica', 9)
            canvas.setFillColor(colors.grey)
            page_num_text = f"Page {doc.page}"
            canvas.drawCentredString(A4[0]/2, 0.3*inch, page_num_text)
            
            canvas.restoreState()
        
        def afterFlowable(self, flowable):
            # Switch to 'Later' template after first page
            if self.page == 1:
                self._nextPageTemplateIndex = 1  # Switch to 'Later' template
    
    # Create document with custom template
    invoice_no = shipment.get('invoice_number', shipment['po_number'])
    doc = InvoiceDocTemplate(
        str(pdf_path), 
        pagesize=A4,
        topMargin=0.5*inch, 
        bottomMargin=0.5*inch,
        leftMargin=0.5*inch, 
        rightMargin=0.5*inch,
        company_name=profile['company_name'],
        invoice_no=invoice_no,
        invoice_date=shipment['po_date']
    )
    
    elements = []
    
    # ========== ZONE 1: THE HEADER (Top Strip) ==========
    header_data = [
        [
            Paragraph(f"<b>{profile['company_name']}</b>", ParagraphStyle(
                'CompanyName', parent=styles['Normal'], fontSize=16, textColor=colors.HexColor('#0f172a')
            )),
            Paragraph("<b><u>COMMERCIAL INVOICE</u></b>", ParagraphStyle(
                'Title', parent=styles['Heading1'], fontSize=16, 
                textColor=colors.HexColor('#0f172a'), alignment=TA_CENTER
            )),
            Paragraph(f"<b>Invoice No:</b> {invoice_no}<br/><b>Date:</b> {shipment['po_date']}", 
                     ParagraphStyle('InvoiceBox', parent=styles['Normal'], fontSize=10,
                                  borderWidth=1, borderColor=colors.black, borderPadding=8))
        ]
    ]
    
    header_table = Table(header_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
        ('BOX', (2, 0), (2, 0), 1, colors.black),
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#f0f0f0')),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # ========== ZONE 2: THE PARTIES (Two Columns) ==========
    exporter_text = f"<b>EXPORTER</b><br/>{profile['company_name']}<br/>{profile['address_line1']}"
    if profile.get('address_line2'):
        exporter_text += f"<br/>{profile['address_line2']}"
    exporter_text += f"<br/><b>IEC:</b> {profile['iec_code']}<br/><b>GSTIN:</b> {profile['gst_number']}"
    if profile.get('ad_code'):
        exporter_text += f"<br/><b>AD Code:</b> {profile['ad_code']}"
    
    consignee_text = f"<b>CONSIGNEE / BUYER</b><br/>{shipment['buyer_name']}"
    if shipment.get('buyer_address'):
        consignee_text += f"<br/>{shipment['buyer_address']}"
    if shipment.get('notify_party'):
        consignee_text += f"<br/><b>Notify Party:</b> {shipment['notify_party']}"
    consignee_text += f"<br/><b>PO Number:</b> {shipment['po_number']}<br/><b>PO Date:</b> {shipment['po_date']}"
    
    parties_data = [
        [
            Paragraph(exporter_text, styles['Normal']),
            Paragraph(consignee_text, styles['Normal'])
        ]
    ]
    
    parties_table = Table(parties_data, colWidths=[3.75*inch, 3.75*inch])
    parties_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LINEAFTER', (0, 0), (0, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(parties_table)
    elements.append(Spacer(1, 0.15*inch))
    
    # ========== ZONE 3: LOGISTICS STRIP ==========
    logistics_headers = ['Country of Origin', 'Port of Loading', 'Port of Discharge', 'Incoterms', 'Payment Terms']
    logistics_values = [
        'India',
        shipment.get('port_of_loading', 'N/A'),
        shipment.get('port_of_discharge', 'N/A'),
        shipment.get('incoterms', 'FOB'),
        shipment.get('payment_terms', 'As per PO')
    ]

    logistics_data = [logistics_headers, logistics_values]
    logistics_table = Table(logistics_data, colWidths=[1.5*inch]*5)
    logistics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d3d3d3')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(logistics_table)

    # Marks & Numbers row
    marks_data = [[
        Paragraph('<b>Marks &amp; Numbers:</b>', ParagraphStyle('MarksLabel', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold')),
        Paragraph(shipment.get('marks_and_numbers', 'As per PO'), ParagraphStyle('MarksValue', parent=styles['Normal'], fontSize=9))
    ]]
    marks_table = Table(marks_data, colWidths=[1.5*inch, 6.0*inch])
    marks_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('LINEAFTER', (0, 0), (0, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#d3d3d3')),
    ]))
    elements.append(marks_table)
    elements.append(Spacer(1, 0.15*inch))

    # ========== ZONE 4: THE GOODS (Main Table) - SPLIT FOR MULTI-PAGE ==========
    # Table header style
    table_header_style = ParagraphStyle('TableHeader', parent=styles['Normal'], fontSize=9, textColor=colors.whitesmoke)
    
    # Check if INR column should be included
    include_inr = shipment.get('include_inr_column', False) and currency != 'INR'
    # Get INR rate from cache or fallback
    inr_rate = get_inr_rate_sync(currency, exchange_rate_cache.get("rates")) if include_inr else 1
    
    # Create items table with repeatRows for header on each page
    if include_inr:
        items_data = [[
            Paragraph('<b>Description</b>', table_header_style),
            Paragraph('<b>HS Code</b>', table_header_style),
            Paragraph('<b>Qty</b>', table_header_style),
            Paragraph('<b>Unit</b>', table_header_style),
            Paragraph(f'<b>Rate ({currency})</b>', table_header_style),
            Paragraph(f'<b>Amount ({currency})</b>', table_header_style),
            Paragraph('<b>Amount (INR)</b>', table_header_style)
        ]]

        total_inr = 0
        for item in shipment['items']:
            inr_amount = item['total_amount'] * inr_rate
            total_inr += inr_amount
            items_data.append([
                item['description'],
                item.get('hs_code', ''),
                str(item['quantity']),
                item.get('unit_of_measure', ''),
                f"{item['unit_price']:.2f}",
                f"{item['total_amount']:,.2f}",
                f"{inr_amount:,.2f}"
            ])

        items_table = Table(items_data, colWidths=[2.1*inch, 0.8*inch, 0.5*inch, 0.5*inch, 0.9*inch, 1.0*inch, 1.7*inch], repeatRows=1)
    else:
        items_data = [[
            Paragraph('<b>Description</b>', table_header_style),
            Paragraph('<b>HS Code</b>', table_header_style),
            Paragraph('<b>Qty</b>', table_header_style),
            Paragraph('<b>Unit</b>', table_header_style),
            Paragraph(f'<b>Rate ({currency})</b>', table_header_style),
            Paragraph(f'<b>Amount ({currency})</b>', table_header_style)
        ]]

        for item in shipment['items']:
            items_data.append([
                item['description'],
                item.get('hs_code', ''),
                str(item['quantity']),
                item.get('unit_of_measure', ''),
                f"{item['unit_price']:.2f}",
                f"{item['total_amount']:,.2f}"
            ])

        items_table = Table(items_data, colWidths=[2.6*inch, 0.9*inch, 0.55*inch, 0.55*inch, 1.1*inch, 1.8*inch], repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        # Alternate row colors for better readability
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.1*inch))
    
    # ========== ZONE 5: THE SUMMARY ==========
    # Build summary text based on whether INR is included
    summary_right_text = f"<b>Total Net Weight:</b> {total_net_weight:.2f} kg<br/>"
    summary_right_text += f"<b>Total Gross Weight:</b> {total_gross_weight:.2f} kg<br/>"
    summary_right_text += f"<b>TOTAL ({currency}):</b> {total_amount:,.2f}"
    
    if include_inr:
        total_inr = total_amount * inr_rate
        summary_right_text += f"<br/><b>TOTAL (INR):</b> {total_inr:,.2f}"
        summary_right_text += f"<br/><i style='font-size:8'>Exchange Rate: 1 {currency} = INR {inr_rate:.2f}</i>"
    
    summary_data = [[
        Paragraph(f"<b>Total Packages:</b> {total_packages} {package_type}", styles['Normal']),
        Paragraph(summary_right_text,
                 ParagraphStyle('SummaryRight', parent=styles['Normal'], alignment=TA_RIGHT, fontName='Helvetica-Bold'))
    ]]
    
    summary_table = Table(summary_data, colWidths=[3.75*inch, 3.75*inch])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # ========== ZONE 6: THE FOOTER (Banking & Auth) ==========
    # Left Side: Banking Instructions - Use a style with proper wrapping
    banking_style = ParagraphStyle(
        'Banking',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        wordWrap='CJK'
    )
    
    banking_text = f"<b>BANKING INSTRUCTIONS</b><br/>"
    banking_text += f"<b>Bank Name:</b> {profile['bank_name']}<br/>"
    banking_text += f"<b>Account No:</b> {profile['account_number']}<br/>"
    banking_text += f"<b>IFSC Code:</b> {profile['ifsc_code']}"
    if profile.get('swift_code'):
        banking_text += f"<br/><b>SWIFT Code:</b> {profile['swift_code']}"
    banking_text += "<br/><br/><b>Declaration:</b> We hereby declare that the above information is true and correct and that the goods are of Indian origin."
    
    # Right Side: Signature Box
    sig_header = Paragraph(f"<b>For {profile['company_name']}</b>", 
                          ParagraphStyle('SigHeader', parent=styles['Normal'], 
                                       fontSize=10, alignment=TA_CENTER))
    
    # Signature image or placeholder
    if profile.get('signature_image_url'):
        sig_path = UPLOADS_DIR / profile['signature_image_url'].split('/')[-1]
        if sig_path.exists():
            sig_image = Image(str(sig_path), width=1.8*inch, height=0.8*inch)
        else:
            sig_image = Spacer(1, 0.8*inch)
    else:
        sig_image = Spacer(1, 0.8*inch)
    
    sig_footer = Paragraph("Authorized Signatory", 
                          ParagraphStyle('SigFooter', parent=styles['Normal'], 
                                       fontSize=9, alignment=TA_CENTER))
    
    # Create nested table for signature section
    sig_table_data = [
        [sig_header],
        [sig_image],
        [sig_footer]
    ]
    sig_table = Table(sig_table_data, colWidths=[2.8*inch])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    
    footer_data = [[
        Paragraph(banking_text, banking_style),
        sig_table
    ]]
    
    footer_table = Table(footer_data, colWidths=[4.5*inch, 3*inch])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LINEAFTER', (0, 0), (0, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(footer_table)
    elements.append(Spacer(1, 0.15*inch))
    
    # Compliance Text
    compliance_style = ParagraphStyle(
        'Compliance',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.grey
    )
    elements.append(Paragraph("Supply Meant for Export Under Bond/LUT Without Payment of Integrated Tax", compliance_style))
    elements.append(Paragraph("We hereby certify that the goods described herein are of Indian Origin.", compliance_style))
    
    # Build PDF
    doc.build(elements)
    
    # Update shipment status
    shipments_collection.update_one(
        {"_id": shipment_id},
        {"$set": {"status": "Final", "pdf_url": f"/uploads/{pdf_filename}"}}
    )
    
    return FileResponse(str(pdf_path), media_type='application/pdf', filename=pdf_filename)

# File serving endpoint
@app.get("/uploads/{filename}")
async def serve_upload(filename: str):
    file_path = UPLOADS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(file_path))

# Shipment Validation Endpoint
@app.get("/api/shipments/{shipment_id}/validate")
async def validate_shipment(shipment_id: str, user_id: str = Depends(verify_token)):
    shipment = shipments_collection.find_one({"_id": shipment_id, "user_id": user_id})
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    errors = []
    warnings = []
    total_checks = 0
    passed_checks = 0

    items = shipment.get('items', [])

    # ── ERRORS ────────────────────────────────────────────────────────────────

    # invoice_number
    total_checks += 1
    if not shipment.get('invoice_number', ''):
        errors.append("Invoice number is missing — cannot be submitted without one.")
    else:
        passed_checks += 1

    # buyer_name
    total_checks += 1
    if not shipment.get('buyer_name', ''):
        errors.append("Buyer name is missing.")
    else:
        passed_checks += 1

    # at least one item
    total_checks += 1
    if not items:
        errors.append("No items found — at least one item is required.")
    else:
        passed_checks += 1

    # per-item hs_code: exactly 8 digits, no dots, no spaces
    for idx, item in enumerate(items):
        total_checks += 1
        hs = str(item.get('hs_code', '') or '')
        desc_preview = (item.get('description', '') or '')[:30]
        if not re.match(r'^\d{8}$', hs):
            errors.append(
                f"Item {idx + 1} ('{desc_preview}'): HS code must be exactly 8 digits with no dots or spaces (current value: '{hs}')."
            )
        else:
            passed_checks += 1

    # ── WARNINGS ──────────────────────────────────────────────────────────────

    # port_of_loading
    total_checks += 1
    if not shipment.get('port_of_loading', ''):
        warnings.append("Port of loading is not set.")
    else:
        passed_checks += 1

    # port_of_discharge
    total_checks += 1
    if not shipment.get('port_of_discharge', ''):
        warnings.append("Port of discharge is not set.")
    else:
        passed_checks += 1

    # payment_terms
    total_checks += 1
    if not shipment.get('payment_terms', ''):
        warnings.append("Payment terms are not set.")
    else:
        passed_checks += 1

    # buyer_address
    total_checks += 1
    if not shipment.get('buyer_address', ''):
        warnings.append("Buyer address is empty.")
    else:
        passed_checks += 1

    # total gross weight across all items
    total_gross = sum(float(item.get('gross_weight', 0) or 0) for item in items)
    total_checks += 1
    if total_gross == 0:
        warnings.append("Total gross weight is 0 — please enter weights for packing list compliance.")
    else:
        passed_checks += 1

    # per-item checks
    for idx, item in enumerate(items):
        desc_preview = (item.get('description', '') or '')[:30]

        # unit_of_measure
        total_checks += 1
        if not (item.get('unit_of_measure', '') or ''):
            warnings.append(f"Item {idx + 1} ('{desc_preview}'): unit of measure is not set.")
        else:
            passed_checks += 1

        # gross_weight
        total_checks += 1
        if float(item.get('gross_weight', 0) or 0) == 0:
            warnings.append(f"Item {idx + 1} ('{desc_preview}'): gross weight is 0.")
        else:
            passed_checks += 1

        # quantity
        total_checks += 1
        if float(item.get('quantity', 0) or 0) == 0:
            warnings.append(f"Item {idx + 1} ('{desc_preview}'): quantity is 0.")
        else:
            passed_checks += 1

    score = round((passed_checks / total_checks) * 100) if total_checks > 0 else 100

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "score": score
    }


# VERSION 2.0 FEATURES

# FEATURE 1: Generate Packing List PDF
@app.post("/api/shipments/{shipment_id}/generate-packing-list")
async def generate_packing_list_pdf(shipment_id: str, user_id: str = Depends(verify_token)):
    # Get shipment data
    shipment = shipments_collection.find_one({"_id": shipment_id, "user_id": user_id})
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # Get company profile
    profile = profiles_collection.find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Company profile not found")
    
    # Create PDF
    pdf_filename = f"packing_list_{shipment_id}.pdf"
    pdf_path = UPLOADS_DIR / pdf_filename

    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        topMargin=0.6*inch, bottomMargin=0.6*inch,
        leftMargin=0.75*inch, rightMargin=0.75*inch
    )
    elements = []

    styles = getSampleStyleSheet()
    invoice_number = shipment.get('invoice_number', shipment.get('po_number', ''))

    # ---- shared styles ----
    title_style = ParagraphStyle(
        'PLTitle', parent=styles['Heading1'], fontSize=16,
        textColor=colors.HexColor('#0f172a'), spaceAfter=6, alignment=TA_CENTER
    )
    label_style = ParagraphStyle(
        'PLLabel', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold'
    )
    value_style = ParagraphStyle(
        'PLValue', parent=styles['Normal'], fontSize=9
    )
    th_style = ParagraphStyle(
        'PLTH', parent=styles['Normal'], fontSize=8,
        textColor=colors.whitesmoke, fontName='Helvetica-Bold', alignment=TA_CENTER
    )
    td_style = ParagraphStyle(
        'PLTD', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER
    )
    td_left_style = ParagraphStyle(
        'PLTDLeft', parent=styles['Normal'], fontSize=8, alignment=TA_LEFT
    )

    # ========== HEADER ==========
    elements.append(Paragraph("PACKING LIST", title_style))
    elements.append(Spacer(1, 0.1*inch))

    # Two-column header: exporter left, document details right
    exporter_lines = f"<b>{profile['company_name']}</b><br/>{profile['address_line1']}"
    if profile.get('address_line2'):
        exporter_lines += f"<br/>{profile['address_line2']}"
    exporter_lines += f"<br/><b>IEC:</b> {profile['iec_code']} | <b>GSTIN:</b> {profile['gst_number']}"

    doc_details = (
        f"<b>Invoice No:</b> {invoice_number}<br/>"
        f"<b>PO Number:</b> {shipment['po_number']}<br/>"
        f"<b>PO Date:</b> {shipment['po_date']}<br/>"
        f"<b>Port of Loading:</b> {shipment.get('port_of_loading', 'N/A')}<br/>"
        f"<b>Port of Discharge:</b> {shipment.get('port_of_discharge', 'N/A')}"
    )

    header_data = [[
        Paragraph(exporter_lines, value_style),
        Paragraph(doc_details, value_style)
    ]]
    header_table = Table(header_data, colWidths=[3.5*inch, 3.5*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LINEAFTER', (0, 0), (0, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.15*inch))

    # ========== BUYER / CONSIGNEE BLOCK ==========
    buyer_text = f"<b>CONSIGNEE / BUYER</b><br/>{shipment['buyer_name']}"
    if shipment.get('buyer_address'):
        buyer_text += f"<br/>{shipment['buyer_address']}"
    if shipment.get('notify_party'):
        buyer_text += f"<br/><b>Notify Party:</b> {shipment['notify_party']}"

    buyer_data = [[Paragraph(buyer_text, value_style)]]
    buyer_table = Table(buyer_data, colWidths=[7.0*inch])
    buyer_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(buyer_table)
    elements.append(Spacer(1, 0.15*inch))

    # ========== MARKS & NUMBERS BLOCK ==========
    marks_data = [[
        Paragraph('<b>Marks &amp; Numbers:</b>', label_style),
        Paragraph(shipment.get('marks_and_numbers', 'As per PO'), value_style)
    ]]
    marks_table = Table(marks_data, colWidths=[1.5*inch, 5.5*inch])
    marks_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.black),
        ('LINEAFTER', (0, 0), (0, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#d3d3d3')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(marks_table)
    elements.append(Spacer(1, 0.15*inch))

    # ========== ITEMS TABLE ==========
    # Columns: Sr No | Description | HS Code | Unit | Qty | Net Wt (kg) | Gross Wt (kg) | Dimensions (L×W×H cm) | CBM
    col_widths = [0.35*inch, 1.9*inch, 0.75*inch, 0.55*inch, 0.45*inch, 0.65*inch, 0.7*inch, 0.95*inch, 0.65*inch]

    items_data = [[
        Paragraph('<b>Sr<br/>No</b>', th_style),
        Paragraph('<b>Description</b>', th_style),
        Paragraph('<b>HS Code</b>', th_style),
        Paragraph('<b>Unit</b>', th_style),
        Paragraph('<b>Qty</b>', th_style),
        Paragraph('<b>Net Wt<br/>(kg)</b>', th_style),
        Paragraph('<b>Gross Wt<br/>(kg)</b>', th_style),
        Paragraph('<b>Dimensions<br/>(L×W×H cm)</b>', th_style),
        Paragraph('<b>CBM</b>', th_style),
    ]]

    total_qty = 0
    total_net_weight = 0.0
    total_gross_weight = 0.0
    total_cbm = 0.0

    for sr, item in enumerate(shipment['items'], start=1):
        net_wt = float(item.get('net_weight', 0) or 0)
        gross_wt = float(item.get('gross_weight', 0) or 0)
        qty = item.get('quantity', 0)
        l = float(item.get('length_cm', 0) or 0)
        w = float(item.get('width_cm', 0) or 0)
        h = float(item.get('height_cm', 0) or 0)
        cbm = (l * w * h) / 1_000_000

        total_qty += qty
        total_net_weight += net_wt
        total_gross_weight += gross_wt
        total_cbm += cbm

        dim_str = f"{l:.0f}×{w:.0f}×{h:.0f}" if (l or w or h) else "—"

        items_data.append([
            Paragraph(str(sr), td_style),
            Paragraph(item.get('description', ''), td_left_style),
            Paragraph(item.get('hs_code', ''), td_style),
            Paragraph(item.get('unit_of_measure', ''), td_style),
            Paragraph(str(qty), td_style),
            Paragraph(f"{net_wt:.2f}", td_style),
            Paragraph(f"{gross_wt:.2f}", td_style),
            Paragraph(dim_str, td_style),
            Paragraph(f"{cbm:.4f}", td_style),
        ])

    # Totals row
    items_data.append([
        Paragraph('', td_style),
        Paragraph('<b>TOTAL</b>', ParagraphStyle('TotalLabel', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold', alignment=TA_LEFT)),
        Paragraph('', td_style),
        Paragraph('', td_style),
        Paragraph(f'<b>{total_qty}</b>', ParagraphStyle('TotalVal', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER)),
        Paragraph(f'<b>{total_net_weight:.2f}</b>', ParagraphStyle('TotalVal2', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER)),
        Paragraph(f'<b>{total_gross_weight:.2f}</b>', ParagraphStyle('TotalVal3', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER)),
        Paragraph('', td_style),
        Paragraph(f'<b>{total_cbm:.4f}</b>', ParagraphStyle('TotalVal4', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER)),
    ])

    items_table = Table(items_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        # Data rows — alternate background
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8f9fa')]),
        # Totals row
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        # Grid and alignment
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.35*inch))

    # ========== FOOTER: SIGNATURE + CROSS-REFERENCE + DISCLAIMER ==========
    # Signature
    if profile.get('signature_image_url'):
        sig_path = UPLOADS_DIR / profile['signature_image_url'].split('/')[-1]
        if sig_path.exists():
            elements.append(Image(str(sig_path), width=2*inch, height=1*inch))
            elements.append(Spacer(1, 0.1*inch))

    elements.append(Paragraph(f"<b>For {profile['company_name']}</b>", styles['Normal']))
    elements.append(Paragraph("Authorized Signatory", value_style))
    elements.append(Spacer(1, 0.2*inch))

    # Cross-reference line
    xref_style = ParagraphStyle(
        'XRef', parent=styles['Normal'], fontSize=9,
        alignment=TA_CENTER, textColor=colors.HexColor('#0f172a')
    )
    elements.append(Paragraph(
        f"This packing list corresponds to Commercial Invoice No: <b>{invoice_number}</b> dated <b>{shipment['po_date']}</b>.",
        xref_style
    ))
    elements.append(Spacer(1, 0.1*inch))

    # Legal disclaimer
    disclaimer_style = ParagraphStyle(
        'PLDisclaimer', parent=styles['Normal'], fontSize=7,
        alignment=TA_CENTER, textColor=colors.HexColor('#808080')
    )
    elements.append(Paragraph(
        "Disclaimer: This document is generated using AI assistance. The Exporter is solely responsible for verifying all data, "
        "including HS Codes and values, before submission to Customs. TradesdocAi assumes no liability for errors or non-compliance.",
        disclaimer_style
    ))

    # Build PDF
    doc.build(elements)

    return FileResponse(str(pdf_path), media_type='application/pdf', filename=pdf_filename)

# FEATURE 2B: Generate Certificate of Origin PDF
@app.post("/api/shipments/{shipment_id}/generate-coo")
async def generate_coo_pdf(shipment_id: str, user_id: str = Depends(verify_token)):
    shipment = shipments_collection.find_one({"_id": shipment_id, "user_id": user_id})
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    profile = profiles_collection.find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Company profile not found")

    pdf_filename = f"coo_{shipment_id}.pdf"
    pdf_path = UPLOADS_DIR / pdf_filename

    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=A4,
        topMargin=0.6*inch, bottomMargin=0.6*inch,
        leftMargin=0.75*inch, rightMargin=0.75*inch
    )
    elements = []
    styles = getSampleStyleSheet()

    invoice_number = shipment.get('invoice_number', shipment.get('po_number', ''))

    # ---- shared styles ----
    center_bold = ParagraphStyle('COOCenterBold', parent=styles['Normal'],
                                 fontSize=18, fontName='Helvetica-Bold', alignment=TA_CENTER)
    center_normal = ParagraphStyle('COOCenter', parent=styles['Normal'],
                                   fontSize=11, alignment=TA_CENTER)
    label_s = ParagraphStyle('COOLabel', parent=styles['Normal'],
                              fontSize=9, fontName='Helvetica-Bold')
    value_s = ParagraphStyle('COOValue', parent=styles['Normal'], fontSize=9)
    th_s = ParagraphStyle('COOTH', parent=styles['Normal'], fontSize=8,
                          fontName='Helvetica-Bold', textColor=colors.whitesmoke, alignment=TA_CENTER)
    td_c = ParagraphStyle('COOTDC', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)
    td_l = ParagraphStyle('COOTDL', parent=styles['Normal'], fontSize=8, alignment=TA_LEFT)

    BOX_STYLE = TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ])

    # ========== HEADER ==========
    elements.append(Paragraph("CERTIFICATE OF ORIGIN", center_bold))
    elements.append(Spacer(1, 0.08*inch))
    elements.append(Paragraph("Country of Origin: <b>INDIA</b>", center_normal))
    elements.append(Spacer(1, 0.2*inch))

    # ========== BOX 1 & 2: Exporter (left) | Consignee (right) ==========
    exporter_txt = (
        f"<b>BOX 1 — EXPORTER</b><br/>"
        f"{profile['company_name']}<br/>"
        f"{profile['address_line1']}"
    )
    if profile.get('address_line2'):
        exporter_txt += f"<br/>{profile['address_line2']}"
    exporter_txt += f"<br/><b>IEC:</b> {profile['iec_code']}"

    # Consignee: prefer consignee field if set and differs from buyer_name
    consignee_name = shipment.get('consignee', '') or shipment.get('buyer_name', '')
    consignee_addr = shipment.get('buyer_address', '')
    consignee_txt = (
        f"<b>BOX 2 — CONSIGNEE</b><br/>"
        f"{consignee_name}"
    )
    if consignee_addr:
        consignee_txt += f"<br/>{consignee_addr}"

    parties_data = [[Paragraph(exporter_txt, value_s), Paragraph(consignee_txt, value_s)]]
    parties_table = Table(parties_data, colWidths=[3.5*inch, 3.5*inch])
    parties_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LINEAFTER', (0, 0), (0, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(parties_table)
    elements.append(Spacer(1, 0.12*inch))

    # ========== BOX 3: Transport ==========
    transport_headers = ['Port of Loading', 'Port of Discharge', 'Incoterms']
    transport_values = [
        shipment.get('port_of_loading', 'N/A'),
        shipment.get('port_of_discharge', 'N/A'),
        shipment.get('incoterms', 'FOB'),
    ]
    transport_data = [
        [Paragraph(f"<b>{h}</b>", ParagraphStyle('TH3', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', alignment=TA_CENTER)) for h in transport_headers],
        [Paragraph(v, ParagraphStyle('TV3', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)) for v in transport_values],
    ]
    transport_table = Table(transport_data, colWidths=[7.0*inch / 3] * 3)
    transport_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d3d3d3')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(transport_table)
    elements.append(Spacer(1, 0.12*inch))

    # ========== BOX 4: Goods Table ==========
    goods_headers = [
        Paragraph('<b>Sr No</b>', th_s),
        Paragraph('<b>HS Code</b>', th_s),
        Paragraph('<b>Description</b>', th_s),
        Paragraph('<b>Qty &amp; Unit</b>', th_s),
        Paragraph('<b>Gross Wt (kg)</b>', th_s),
        Paragraph('<b>Invoice No &amp; Date</b>', th_s),
    ]
    goods_col_widths = [0.45*inch, 0.85*inch, 2.3*inch, 0.9*inch, 0.9*inch, 1.6*inch]
    goods_data = [goods_headers]

    for sr, item in enumerate(shipment.get('items', []), start=1):
        qty_unit = str(item.get('quantity', ''))
        uom = item.get('unit_of_measure', '')
        if uom:
            qty_unit += f" {uom}"
        goods_data.append([
            Paragraph(str(sr), td_c),
            Paragraph(item.get('hs_code', ''), td_c),
            Paragraph(item.get('description', ''), td_l),
            Paragraph(qty_unit, td_c),
            Paragraph(f"{float(item.get('gross_weight', 0) or 0):.2f}", td_c),
            Paragraph(f"{invoice_number}<br/>{shipment.get('po_date', '')}", td_c),
        ])

    goods_table = Table(goods_data, colWidths=goods_col_widths, repeatRows=1)
    goods_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(goods_table)
    elements.append(Spacer(1, 0.12*inch))

    # ========== BOX 5: Declaration ==========
    declaration_txt = (
        "The undersigned hereby declares that the above details are correct, that all the goods "
        "were produced in <b>INDIA</b>, and that they comply with the origin requirements."
    )
    decl_data = [[Paragraph(f"<b>DECLARATION</b><br/>{declaration_txt}", value_s)]]
    decl_table = Table(decl_data, colWidths=[7.0*inch])
    decl_table.setStyle(BOX_STYLE)
    elements.append(decl_table)
    elements.append(Spacer(1, 0.12*inch))

    # ========== BOX 6: Signature Block ==========
    sig_header = Paragraph(f"<b>For {profile['company_name']}</b>",
                           ParagraphStyle('COOSigHdr', parent=styles['Normal'],
                                         fontSize=10, alignment=TA_CENTER))
    if profile.get('signature_image_url'):
        sig_path = UPLOADS_DIR / profile['signature_image_url'].split('/')[-1]
        sig_img = Image(str(sig_path), width=1.8*inch, height=0.8*inch) if sig_path.exists() else Spacer(1, 0.8*inch)
    else:
        sig_img = Spacer(1, 0.8*inch)

    sig_footer = Paragraph("Authorized Signatory",
                           ParagraphStyle('COOSigFtr', parent=styles['Normal'],
                                         fontSize=9, alignment=TA_CENTER))
    place_date = Paragraph("Place &amp; Date: ___________________________",
                           ParagraphStyle('COOPlaceDate', parent=styles['Normal'],
                                         fontSize=9, alignment=TA_CENTER))

    sig_inner = Table([[sig_header], [sig_img], [sig_footer], [place_date]],
                      colWidths=[3.0*inch])
    sig_inner.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    sig_data = [[sig_inner]]
    sig_table = Table(sig_data, colWidths=[7.0*inch])
    sig_table.setStyle(BOX_STYLE)
    elements.append(sig_table)
    elements.append(Spacer(1, 0.1*inch))

    # ========== Preferential Treatment note ==========
    pref_style = ParagraphStyle('COOPref', parent=styles['Normal'],
                                fontSize=8, fontName='Helvetica-Oblique',
                                alignment=TA_CENTER, textColor=colors.grey)
    elements.append(Paragraph(
        "Preferential Treatment Claimed Under: _______________________",
        pref_style
    ))

    doc.build(elements)
    return FileResponse(str(pdf_path), media_type='application/pdf', filename=pdf_filename)


# FEATURE 3: GST GSTR-1 Export
@app.get("/api/reports/gstr1-export")
async def export_gstr1_data(user_id: str = Depends(verify_token)):
    # Get all finalized shipments
    shipments = list(shipments_collection.find({"user_id": user_id, "status": "Final"}))
    
    # Generate CSV
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # CSV Headers for GSTR-1 Table 6A
    writer.writerow([
        'Invoice Number',
        'Invoice Date',
        'Buyer Name',
        'Currency',
        'Port Code',
        'Total Value',
        'Taxable Value',
        'Integrated Tax Amount'
    ])

    for shipment in shipments:
        total_value = sum(item.get('total_amount', 0) for item in shipment.get('items', []))
        writer.writerow([
            shipment.get('invoice_number', shipment.get('po_number', '')),
            shipment.get('po_date', ''),
            shipment.get('buyer_name', ''),
            shipment.get('currency', 'USD'),
            shipment.get('port_of_loading', 'INNSA1'),
            f"{total_value:.2f}",
            f"{total_value:.2f}",  # Assuming taxable value = total for exports
            '0.00'  # Zero-rated exports
        ])
    
    # Create response
    output.seek(0)
    from fastapi.responses import StreamingResponse
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=gstr1_export_data.csv"}
    )

# FEATURE 4: Tally XML Export
@app.post("/api/shipments/{shipment_id}/export-tally")
async def export_tally_xml(shipment_id: str, user_id: str = Depends(verify_token)):
    # Get shipment data
    shipment = shipments_collection.find_one({"_id": shipment_id, "user_id": user_id})
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # Get company profile
    profile = profiles_collection.find_one({"user_id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Company profile not found")
    
    # Get tally sales ledger name (default to "Export Sales")
    tally_ledger = profile.get('tally_sales_ledger_name', 'Export Sales')
    
    # Convert date to YYYYMMDD format
    from datetime import datetime as dt
    try:
        po_date_obj = dt.strptime(shipment['po_date'], '%Y-%m-%d')
        tally_date = po_date_obj.strftime('%Y%m%d')
    except:
        tally_date = dt.now().strftime('%Y%m%d')
    
    # Calculate total amount
    total_amount = sum(item.get('total_amount', 0) for item in shipment.get('items', []))
    
    # Build Tally XML
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<ENVELOPE>
    <HEADER>
        <TALLYREQUEST>Import Data</TALLYREQUEST>
    </HEADER>
    <BODY>
        <IMPORTDATA>
            <REQUESTDESC>
                <REPORTNAME>Vouchers</REPORTNAME>
            </REQUESTDESC>
            <REQUESTDATA>
                <TALLYMESSAGE xmlns:UDF="TallyUDF">
                    <VOUCHER REMOTEID="" VCHKEY="" VCHTYPE="Sales" ACTION="Create" OBJVIEW="Invoice Voucher View">
                        <DATE>{tally_date}</DATE>
                        <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
                        <VOUCHERNUMBER>{shipment['po_number']}</VOUCHERNUMBER>
                        <PARTYLEDGERNAME>{shipment['buyer_name']}</PARTYLEDGERNAME>
                        <EFFECTIVEDATE>{tally_date}</EFFECTIVEDATE>
                        <ISINVOICE>Yes</ISINVOICE>
"""
    
    # Add inventory entries
    for item in shipment.get('items', []):
        xml_content += f"""                        <ALLINVENTORYENTRIES.LIST>
                            <STOCKITEMNAME>{item['description']}</STOCKITEMNAME>
                            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                            <RATE>{item['unit_price']:.2f}</RATE>
                            <AMOUNT>-{item['total_amount']:.2f}</AMOUNT>
                            <ACTUALQTY>{item['quantity']}</ACTUALQTY>
                            <BILLEDQTY>{item['quantity']}</BILLEDQTY>
                        </ALLINVENTORYENTRIES.LIST>
"""
    
    # Add ledger entries
    xml_content += f"""                        <ALLLEDGERENTRIES.LIST>
                            <LEDGERNAME>{shipment['buyer_name']}</LEDGERNAME>
                            <GSTCLASS/>
                            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                            <AMOUNT>{total_amount:.2f}</AMOUNT>
                        </ALLLEDGERENTRIES.LIST>
                        <ALLLEDGERENTRIES.LIST>
                            <LEDGERNAME>{tally_ledger}</LEDGERNAME>
                            <GSTCLASS/>
                            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                            <AMOUNT>-{total_amount:.2f}</AMOUNT>
                        </ALLLEDGERENTRIES.LIST>
                    </VOUCHER>
                </TALLYMESSAGE>
            </REQUESTDATA>
        </IMPORTDATA>
    </BODY>
</ENVELOPE>"""
    
    # Save to file
    xml_filename = f"tally_export_{shipment_id}.xml"
    xml_path = UPLOADS_DIR / xml_filename
    
    with open(xml_path, 'w', encoding='utf-8') as f:
        f.write(xml_content)
    
    return FileResponse(
        str(xml_path),
        media_type='application/xml',
        filename=xml_filename,
        headers={"Content-Disposition": f"attachment; filename={xml_filename}"}
    )

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "TradesdocAi API v2.1"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
