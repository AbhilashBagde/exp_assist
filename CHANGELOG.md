# TradesdocAi - Changelog

All notable changes to this project are documented in this file.

---

## [2.1.0] - 2026-01-09

### Added
- **Multi-Page PDF Support**
  - Page numbers displayed at bottom of every page
  - Compact header on continuation pages (company name, invoice no, date)
  - "...continued" indicator on pages 2+
  - Table headers repeat on each page for long item lists
  - Alternating row colors for better readability

- **Logistics & Shipping Fields**
  - `port_of_loading` - Port of Loading input field
  - `port_of_discharge` - Port of Discharge input field
  - `incoterms` - Incoterms dropdown (EXW, FCA, FOB, CFR, CIF, DDP, DAP)
  - `total_packages` - Total number of packages
  - `package_type` - Package type dropdown (Boxes, Cartons, Pallets, Bags, Drums, Crates, Bundles)

### Changed
- Updated shipment creation API to accept new logistics fields
- Updated shipment update API to handle new logistics fields
- Enhanced PDF Zone 3 (Logistics Strip) with actual port and incoterms data
- Enhanced PDF Zone 5 (Summary) with package count and type

### Fixed
- PDF footer layout overflow error (banking text word wrapping)
- Frontend error handling for FastAPI validation error objects
- "Objects are not valid as a React child" error on form submission

### Removed
- AI disclaimer text from Commercial Invoice PDF

---

## [2.0.0] - 2026-01-08

### Added
- **Automated Packing List PDF** (`/api/shipments/{id}/generate-packing-list`)
  - Generates separate packing list with weights (no prices)
  - Includes net and gross weight totals

- **GST GSTR-1 Export** (`/api/reports/gstr1-export`)
  - Downloads CSV file formatted for GSTR-1 Table 6A
  - Includes all finalized shipments

- **Tally XML Export** (`/api/shipments/{id}/export-tally`)
  - Generates Tally-compatible XML voucher
  - Configurable sales ledger name in company profile

- **Real-time Math Validation**
  - UI shows mismatch warning when Qty × Price ≠ Total
  - Highlighted cells for easy identification

- **AI Currency Detection**
  - Gemini Vision extracts currency from uploaded documents
  - Supports USD, EUR, GBP, INR, AED, SGD

- **Professional Currency Formatting**
  - Currency code displayed in table headers (e.g., "Rate (USD)")
  - Consistent formatting across UI and PDFs

- **Pro Subscription Tier**
  - `is_pro_member` flag for users
  - Feature-locking for Packing List, Tally XML, GSTR-1 exports
  - Upgrade modal and dedicated `/upgrade` page

- **Legal Compliance**
  - Legal disclaimer on login page
  - "Supply Meant for Export Under Bond/LUT" on invoices

### Changed
- Updated items schema to include `net_weight` and `gross_weight`
- Enhanced company profile with `tally_sales_ledger_name` field

---

## [1.0.0] - 2026-01-07

### Added
- **User Authentication**
  - JWT-based signup and login
  - Password hashing with bcrypt
  - Token expiration (7 days)

- **Company Profile Management**
  - Company information (name, address, IEC, GST, AD Code)
  - Banking details (account, IFSC, SWIFT)
  - Signature image upload

- **Shipment Creation Workflow**
  - Step 1: Upload Purchase Order (PDF/Image)
  - Step 2: AI Vision extraction with Gemini
  - Step 3: Human-in-the-loop review form
  - Step 4: Generate Commercial Invoice PDF

- **AI-Powered Data Extraction**
  - Gemini Vision API integration
  - Automatic buyer name, address, PO details extraction
  - HS Code prediction for items

- **Commercial Invoice PDF Generation**
  - 6-Zone professional layout
  - Zone 1: Header (Company, Title, Invoice box)
  - Zone 2: Parties (Exporter & Consignee)
  - Zone 3: Logistics Strip
  - Zone 4: Items Table with HS Codes
  - Zone 5: Summary (Packages, Weights, Total)
  - Zone 6: Footer (Banking & Signature)

- **Dashboard**
  - List all shipments with status
  - Download generated PDFs
  - Quick access to create new shipment

### Technical
- React frontend with Tailwind CSS
- FastAPI backend with MongoDB
- ReportLab for PDF generation
- Supervisor for process management

---

## File Structure

```
/app
├── backend/
│   ├── server.py          # Main API server
│   ├── requirements.txt   # Python dependencies
│   └── uploads/           # Generated PDFs and signatures
├── frontend/
│   └── src/
│       ├── App.js
│       └── components/
│           ├── Dashboard.js
│           ├── Login.js
│           ├── NewShipment.js
│           ├── Settings.js
│           └── Upgrade.js
├── memory/
│   └── PRD.md            # Product requirements
├── CHANGELOG.md          # This file
└── README.md             # Project documentation
```

---

## API Endpoints

| Version | Method | Endpoint | Description |
|---------|--------|----------|-------------|
| v1.0 | POST | `/api/auth/signup` | User registration |
| v1.0 | POST | `/api/auth/login` | User login |
| v1.0 | GET | `/api/user/me` | Get current user |
| v1.0 | GET/POST | `/api/profile` | Company profile CRUD |
| v1.0 | POST | `/api/profile/signature` | Upload signature |
| v1.0 | GET/POST | `/api/shipments` | List/Create shipments |
| v1.0 | GET/PUT | `/api/shipments/{id}` | Get/Update shipment |
| v1.0 | POST | `/api/shipments/extract` | AI PO extraction |
| v1.0 | POST | `/api/shipments/{id}/generate-pdf` | Generate invoice |
| v2.0 | POST | `/api/shipments/{id}/generate-packing-list` | Generate packing list |
| v2.0 | POST | `/api/shipments/{id}/export-tally` | Export Tally XML |
| v2.0 | GET | `/api/reports/gstr1-export` | Download GSTR-1 CSV |

---

## Contributors

- Built with Emergent AI Agent (E1)

## License

Proprietary - All rights reserved
