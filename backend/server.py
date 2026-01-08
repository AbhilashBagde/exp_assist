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
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
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
    return {"token": token, "user_id": user["_id"], "email": user["email"]}

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
    items: str = Form(...)  # JSON string
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
    status: str = Form("Draft")
):
    items_list = json.loads(items)
    
    result = shipments_collection.update_one(
        {"_id": shipment_id, "user_id": user_id},
        {"$set": {
            "buyer_name": buyer_name,
            "buyer_address": buyer_address,
            "po_number": po_number,
            "po_date": po_date,
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
  "items": [
    {
      "description": "Item description",
      "quantity": number,
      "unit_price": number,
      "hs_code": "Predicted Indian ITC-HS Code (6 or 8 digits)"
    }
  ]
}

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
    elements.append(Paragraph("COMMERCIAL INVOICE", title_style))
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
    
    # Invoice Details
    invoice_info = [
        [Paragraph(f"<b>PO Number:</b> {shipment['po_number']}", styles['Normal']),
         Paragraph(f"<b>PO Date:</b> {shipment['po_date']}", styles['Normal'])]
    ]
    invoice_table = Table(invoice_info, colWidths=[3*inch, 3*inch])
    elements.append(invoice_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Items Table
    items_data = [['Description', 'HS Code', 'Qty', 'Rate', 'Amount']]
    total_amount = 0
    
    for item in shipment['items']:
        items_data.append([
            item['description'],
            item['hs_code'],
            str(item['quantity']),
            f"₹{item['unit_price']:.2f}",
            f"₹{item['total_amount']:.2f}"
        ])
        total_amount += item['total_amount']
    
    items_data.append(['', '', '', 'TOTAL:', f"₹{total_amount:.2f}"])
    
    items_table = Table(items_data, colWidths=[2.5*inch, 1*inch, 0.8*inch, 1*inch, 1.2*inch])
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
    
    # Bank Details
    bank_data = [
        [Paragraph("<b>BANK DETAILS:</b>", styles['Normal'])],
        [Paragraph(f"Bank: {profile['bank_name']}", styles['Normal'])],
        [Paragraph(f"Account No: {profile['account_number']}", styles['Normal'])],
        [Paragraph(f"IFSC: {profile['ifsc_code']}", styles['Normal'])],
    ]
    if profile.get('swift_code'):
        bank_data.append([Paragraph(f"SWIFT: {profile['swift_code']}", styles['Normal'])])
    
    bank_table = Table(bank_data, colWidths=[6*inch])
    elements.append(bank_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Signature
    if profile.get('signature_image_url'):
        sig_path = UPLOADS_DIR / profile['signature_image_url'].split('/')[-1]
        if sig_path.exists():
            elements.append(Image(str(sig_path), width=2*inch, height=1*inch))
            elements.append(Spacer(1, 0.1*inch))
    
    elements.append(Paragraph("Authorized Signatory", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))
    
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
