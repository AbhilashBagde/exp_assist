# ExportAssist - Product Requirements Document

## Overview
ExportAssist is a B2B SaaS application for Indian Exporters that automates export documentation. Users upload Purchase Orders (PDFs/Images), AI extracts data and predicts HS Codes, and the system generates compliant Commercial Invoice and Packing List PDFs.

## Tech Stack
- **Frontend**: React, Tailwind CSS, Axios
- **Backend**: FastAPI, Python
- **Database**: MongoDB
- **AI**: Google Gemini (models/gemini-2.5-flash)
- **PDF Generation**: ReportLab

## Core Features

### Authentication
- [x] User signup/login with JWT tokens
- [x] Password hashing with bcrypt
- [x] Pro membership status tracking

### Company Profile
- [x] Company details (name, address, IEC, GST)
- [x] Banking information (account, IFSC, SWIFT)
- [x] Signature upload
- [x] Tally sales ledger name

### Shipment Workflow
- [x] Upload Purchase Order (PDF/Image)
- [x] AI Vision data extraction (Gemini)
- [x] HS Code prediction
- [x] Currency detection from documents
- [x] Human-in-the-loop review form
- [x] Real-time math validation (Qty × Price = Total)

### PDF Generation - 6-Zone Layout
- [x] Zone 1: Header (Company name, Title, Invoice box)
- [x] Zone 2: Parties (Exporter & Consignee columns)
- [x] Zone 3: Logistics Strip (Origin, Ports, Incoterms)
- [x] Zone 4: Goods Table (Items with HS codes)
- [x] Zone 5: Summary (Packages, Weights, Total)
- [x] Zone 6: Footer (Banking & Signature)

### V2.0 Features
- [x] Automated Packing List PDF
- [x] GST GSTR-1 CSV Export
- [x] Tally XML Export
- [x] Legal Disclaimer on all outputs
- [x] Pro subscription tier with feature-locking

## Data Models

### users
```
_id, email, password_hash, is_pro_member, created_at
```

### company_profiles
```
_id, user_id, company_name, address_line1, address_line2, 
iec_code, gst_number, ad_code, bank_name, account_number, 
ifsc_code, swift_code, signature_image_url, tally_sales_ledger_name
```

### shipments
```
_id, user_id, buyer_name, buyer_address, po_number, po_date, 
currency, port_of_loading, port_of_discharge, incoterms, 
total_packages, package_type, status, items[], created_at
```

### items[]
```
description, quantity, unit_price, hs_code, total_amount, 
net_weight, gross_weight
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/auth/signup | User registration |
| POST | /api/auth/login | User login |
| GET | /api/user/me | Get current user info |
| GET/POST | /api/profile | Company profile CRUD |
| POST | /api/profile/signature | Upload signature |
| GET/POST | /api/shipments | List/Create shipments |
| GET/PUT | /api/shipments/{id} | Get/Update shipment |
| POST | /api/shipments/extract | AI PO extraction |
| POST | /api/shipments/{id}/generate-pdf | Generate Commercial Invoice |
| POST | /api/shipments/{id}/generate-packing-list | Generate Packing List |
| POST | /api/shipments/{id}/export-tally | Export Tally XML |
| GET | /api/reports/gstr1-export | Download GSTR-1 CSV |

## Completed Work (Jan 2026)
- [x] Full application scaffolding
- [x] User authentication system
- [x] Company profile management
- [x] AI-powered shipment creation workflow
- [x] Commercial Invoice PDF with 6-zone layout
- [x] Packing List PDF generation
- [x] GST CSV and Tally XML exports
- [x] Real-time math validation
- [x] Currency detection and formatting
- [x] Pro subscription tier
- [x] Logistics fields (ports, incoterms, packages)
- [x] Critical PDF bug fix (KeepTogether → nested table)
- [x] PDF footer layout fix (banking text overflow)
- [x] Frontend error handling improvement (validation errors)

## Backlog

### P1 (High Priority)
- [ ] Connect "Subscribe Now" to real payment gateway (Razorpay)
- [ ] Email notifications for shipment status

### P2 (Medium Priority)
- [ ] Refactor server.py into modular structure
- [ ] Add shipment editing capability from dashboard
- [ ] Batch invoice generation

### P3 (Low Priority)
- [ ] Dark mode support
- [ ] Export history/audit log
- [ ] Multiple signature support
