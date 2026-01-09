from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pymongo import MongoClient
from datetime import datetime, timedelta
from typing import Optional, List
import os
import jwt
import bcrypt
import json
import base64
import io
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

# Load environment variables
load_dotenv()

app = FastAPI()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB Connection
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/exportassist")
client = MongoClient(MONGO_URL)
db = client.exportassist

# Collections
users_collection = db.users
profiles_collection = db.company_profiles
shipments_collection = db.shipments

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
UPLOADS_DIR = Path("/app/backend/uploads")
UPLOADS_DIR.mkdir(exist_ok=True)

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

# Auth Endpoints
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
        "is_pro_member": False,  # Default to free tier
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
    include_inr_column: bool = Form(False)
):
    items_list = json.loads(items)
    
    shipment_id = str(uuid.uuid4())
    shipment_data = {
        "_id": shipment_id,
        "user_id": user_id,
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
        "include_inr_column": include_inr_column,
        "status": "Draft",
        "items": items_list,
        "created_at": datetime.utcnow()
    }
    
    shipments_collection.insert_one(shipment_data)
    
    return {"success": True, "shipment_id": shipment_id}

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
    package_type: str = Form("BOXES")
):
    items_list = json.loads(items)
    
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
            "items": items_list,
            "status": status,
            "updated_at": datetime.utcnow()
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    return {"success": True}

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
        
        # Convert to image if PDF
        if file.filename.lower().endswith('.pdf'):
            images = convert_from_bytes(file_content)
            # Use first page
            img_byte_arr = io.BytesIO()
            images[0].save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            image_data = img_byte_arr.getvalue()
        else:
            image_data = file_content
        
        # Prepare image for Gemini
        image = PILImage.open(io.BytesIO(image_data))
        
        # Use Gemini 2.5 Flash (stable multimodal model)
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        
        prompt = """Analyze this Purchase Order document image. Extract the following information and return ONLY a valid JSON object:

{
  "buyer_name": "Name of the buyer/customer",
  "buyer_address": "Full address of the buyer",
  "po_number": "Purchase Order number",
  "po_date": "Date in YYYY-MM-DD format",
  "currency_code": "Detected currency code",
  "items": [
    {
      "description": "Item description",
      "quantity": number,
      "unit_price": number,
      "hs_code": "Predicted Indian ITC-HS Code (6 or 8 digits)"
    }
  ]
}

CRITICAL - CURRENCY DETECTION:
STRICTLY look for currency indicators in the document. Scan the 'Total', 'Amount', 'Rate', or 'Price' columns/fields for:
- Currency symbols: ₹, $, €, £, ¥, د.إ
- Currency codes: INR, USD, EUR, GBP, AED, SGD, JPY
- Text indicators: Rs, Rupees, Dollars

Currency Detection Rules:
- If you see '₹', 'Rs', 'Rupees', or 'INR' → set currency_code to "INR"
- If you see '$' or 'USD' → set currency_code to "USD"
- If you see '£' or 'GBP' → set currency_code to "GBP"
- If you see '€' or 'EUR' → set currency_code to "EUR"
- If you see 'د.إ' or 'AED' → set currency_code to "AED"
- If you see 'S$' or 'SGD' → set currency_code to "SGD"
- If no clear currency found → default to "USD"

For the HS Code prediction:
- Analyze the item description carefully
- Predict the correct Indian ITC-HS Code based on the product type
- Examples: Basmati Rice -> 1006.30, Cotton Fabric -> 5208.00, Tea -> 0902.00
- Use your knowledge of Indian export classification

Return ONLY the JSON object, no additional text."""
        
        response = model.generate_content([prompt, image])
        
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
        
        # Calculate total_amount for each item
        for item in extracted_data.get('items', []):
            item['total_amount'] = item['quantity'] * item['unit_price']
        
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
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        
        prompt = f"""You are an expert in Indian ITC-HS Code classification for export goods.

Based on the following product description, predict the most appropriate Indian ITC-HS Code (6 or 8 digits).

Product Description: "{description}"

Respond with ONLY a JSON object in this exact format:
{{
  "hs_code": "XXXX.XX",
  "confidence": "high/medium/low",
  "category": "Brief category name",
  "notes": "Brief explanation of why this code was chosen"
}}

Common HS Code examples for reference:
- Basmati Rice: 1006.30
- Cotton Fabric: 5208.00
- Tea: 0902.00
- Spices (Turmeric): 0910.30
- Leather goods: 4202.00
- Textiles/Garments: 6109.00
- Machinery parts: 8479.00
- Chemicals: 2933.00
- Pharmaceuticals: 3004.00
- Jewelry: 7113.00

Return ONLY the JSON object, no additional text."""

        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        # Clean up response
        if result_text.startswith('```json'):
            result_text = result_text[7:]
        if result_text.startswith('```'):
            result_text = result_text[3:]
        if result_text.endswith('```'):
            result_text = result_text[:-3]
        result_text = result_text.strip()
        
        # Parse JSON
        suggestion = json.loads(result_text)
        
        return {
            "success": True,
            "hs_code": suggestion.get("hs_code", ""),
            "confidence": suggestion.get("confidence", "medium"),
            "category": suggestion.get("category", ""),
            "notes": suggestion.get("notes", "")
        }
        
    except json.JSONDecodeError:
        # If JSON parsing fails, try to extract HS code from text
        import re
        hs_match = re.search(r'\d{4}\.\d{2}', response.text if 'response' in dir() else '')
        if hs_match:
            return {
                "success": True,
                "hs_code": hs_match.group(),
                "confidence": "low",
                "category": "",
                "notes": "Extracted from AI response"
            }
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
    doc = InvoiceDocTemplate(
        str(pdf_path), 
        pagesize=A4,
        topMargin=0.5*inch, 
        bottomMargin=0.5*inch,
        leftMargin=0.5*inch, 
        rightMargin=0.5*inch,
        company_name=profile['company_name'],
        invoice_no=shipment['po_number'],
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
            Paragraph(f"<b>Invoice No:</b> {shipment['po_number']}<br/><b>Date:</b> {shipment['po_date']}", 
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
    
    consignee_text = f"<b>CONSIGNEE / BUYER</b><br/>{shipment['buyer_name']}"
    if shipment.get('buyer_address'):
        consignee_text += f"<br/>{shipment['buyer_address']}"
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
    logistics_headers = ['Country of Origin', 'Port of Loading', 'Port of Discharge', 'Incoterms']
    logistics_values = [
        'India',
        shipment.get('port_of_loading', 'N/A'),
        shipment.get('port_of_discharge', 'N/A'),
        shipment.get('incoterms', 'FOB')
    ]
    
    logistics_data = [logistics_headers, logistics_values]
    logistics_table = Table(logistics_data, colWidths=[1.875*inch]*4)
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
            Paragraph(f'<b>Rate ({currency})</b>', table_header_style),
            Paragraph(f'<b>Amount ({currency})</b>', table_header_style),
            Paragraph('<b>Amount (₹ INR)</b>', table_header_style)
        ]]
        
        total_inr = 0
        for item in shipment['items']:
            inr_amount = item['total_amount'] * inr_rate
            total_inr += inr_amount
            items_data.append([
                item['description'],
                item['hs_code'],
                str(item['quantity']),
                f"{item['unit_price']:.2f}",
                f"{item['total_amount']:,.2f}",
                f"{inr_amount:,.2f}"
            ])
        
        items_table = Table(items_data, colWidths=[2.4*inch, 0.9*inch, 0.6*inch, 1*inch, 1.1*inch, 1.5*inch], repeatRows=1)
    else:
        items_data = [[
            Paragraph('<b>Description</b>', table_header_style),
            Paragraph('<b>HS Code</b>', table_header_style),
            Paragraph('<b>Qty</b>', table_header_style),
            Paragraph(f'<b>Rate ({currency})</b>', table_header_style),
            Paragraph(f'<b>Amount ({currency})</b>', table_header_style)
        ]]
        
        for item in shipment['items']:
            items_data.append([
                item['description'],
                item['hs_code'],
                str(item['quantity']),
                f"{item['unit_price']:.2f}",
                f"{item['total_amount']:,.2f}"
            ])
        
        items_table = Table(items_data, colWidths=[3*inch, 1*inch, 0.7*inch, 1.15*inch, 1.65*inch], repeatRows=1)
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
        summary_right_text += f"<br/><b>TOTAL (₹ INR):</b> {total_inr:,.2f}"
        summary_right_text += f"<br/><i style='font-size:8'>Exchange Rate: 1 {currency} = ₹{inr_rate:.2f}</i>"
    
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
    elements.append(Paragraph("Supply Meant for Export Under Bond/LUT", compliance_style))
    
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
    
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    # Title
    elements.append(Paragraph("PACKING LIST", title_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Company Details
    company_data = [
        [Paragraph(f"<b>{profile['company_name']}</b>", styles['Normal'])],
        [Paragraph(profile['address_line1'], styles['Normal'])],
    ]
    if profile.get('address_line2'):
        company_data.append([Paragraph(profile['address_line2'], styles['Normal'])])
    company_data.extend([
        [Paragraph(f"IEC: {profile['iec_code']} | GST: {profile['gst_number']}", styles['Normal'])],
    ])
    
    company_table = Table(company_data, colWidths=[6*inch])
    company_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(company_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Buyer Details
    buyer_data = [
        [Paragraph("<b>BUYER DETAILS:</b>", styles['Normal'])],
        [Paragraph(shipment['buyer_name'], styles['Normal'])],
    ]
    if shipment.get('buyer_address'):
        buyer_data.append([Paragraph(shipment['buyer_address'], styles['Normal'])])
    
    buyer_table = Table(buyer_data, colWidths=[6*inch])
    buyer_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(buyer_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Shipment Details
    shipment_info = [
        [Paragraph(f"<b>PO Number:</b> {shipment['po_number']}", styles['Normal']),
         Paragraph(f"<b>PO Date:</b> {shipment['po_date']}", styles['Normal'])]]
    shipment_table = Table(shipment_info, colWidths=[3*inch, 3*inch])
    elements.append(shipment_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Items Table (No prices, includes weights)
    items_data = [['Description', 'Qty', 'Net Wt (kg)', 'Gross Wt (kg)']]
    total_net_weight = 0
    total_gross_weight = 0
    
    for item in shipment['items']:
        net_wt = item.get('net_weight', 0)
        gross_wt = item.get('gross_weight', 0)
        items_data.append([
            item['description'],
            str(item['quantity']),
            f"{net_wt:.2f}",
            f"{gross_wt:.2f}"
        ])
        total_net_weight += net_wt
        total_gross_weight += gross_wt
    
    items_data.append(['TOTAL:', '', f"{total_net_weight:.2f}", f"{total_gross_weight:.2f}"])
    
    items_table = Table(items_data, colWidths=[3*inch, 1*inch, 1.2*inch, 1.2*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 0.4*inch))
    
    # Signature
    if profile.get('signature_image_url'):
        sig_path = UPLOADS_DIR / profile['signature_image_url'].split('/')[-1]
        if sig_path.exists():
            elements.append(Image(str(sig_path), width=2*inch, height=1*inch))
            elements.append(Spacer(1, 0.1*inch))
    
    elements.append(Paragraph("Authorized Signatory", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
    # Legal Disclaimer
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#808080')
    )
    disclaimer_text = "Disclaimer: This document is generated using AI assistance. The Exporter is solely responsible for verifying all data, including HS Codes and values, before submission to Customs. ExportAssist assumes no liability for errors or non-compliance."
    elements.append(Paragraph(disclaimer_text, disclaimer_style))
    
    # Build PDF
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
        'Port Code',
        'Total Value',
        'Taxable Value',
        'Integrated Tax Amount'
    ])
    
    for shipment in shipments:
        total_value = sum(item.get('total_amount', 0) for item in shipment.get('items', []))
        writer.writerow([
            shipment.get('po_number', ''),
            shipment.get('po_date', ''),
            'INNSA1',  # Default port code
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
    return {"status": "healthy", "service": "ExportAssist API v2.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
