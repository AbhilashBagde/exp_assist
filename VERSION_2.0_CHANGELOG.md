# TradesdocAi Version 2.0 - Changelog

## 🎉 Major Upgrade: Critical Business Operations Features

Version 2.0 introduces four game-changing features that transform TradesdocAi from a basic documentation tool into a complete export business management system.

---

## ✨ NEW FEATURES

### 1. 📦 AUTOMATED PACKING LIST (The Workflow Completer)

**What It Does:**
Generates a professional Packing List PDF alongside the Commercial Invoice, essential for customs clearance and shipping.

**Key Changes:**
- **Database Schema**: Items now include `net_weight` and `gross_weight` fields (in kg)
- **UI Enhancement**: New columns in the Review Form table for weight entry
- **New Output**: "Download Packing List" button generates weight-focused PDF

**How to Use:**
1. In the New Shipment workflow, fill in Net Weight and Gross Weight for each item
2. After finalizing the shipment, go to Dashboard
3. Click "📦 Packing List" button to download the PDF

**Technical Details:**
- Backend endpoint: `POST /api/shipments/{id}/generate-packing-list`
- PDF format: Company header, buyer details, items table (Description, Qty, Net Wt, Gross Wt)
- Includes total weights at bottom

---

### 2. ⚠️ MATH VALIDATION (The Safety Layer)

**What It Does:**
Real-time validation prevents calculation errors that could cause payment disputes or compliance issues.

**Key Changes:**
- **Frontend**: Automatically validates `Quantity × Unit Price = Total Amount`
- **Backend**: Recalculates all totals before PDF generation
- **Visual Feedback**: Red highlighting with "Math Mismatch!" warning

**How to Use:**
1. Enter item quantities and rates in the Review Form
2. If the amount doesn't match the calculation, the cell turns red
3. Correct the values before proceeding
4. Backend automatically fixes any discrepancies during PDF generation

**Technical Details:**
- Validation threshold: 0.01 difference tolerance
- Frontend: Real-time visual feedback in NewShipment component
- Backend: Automatic recalculation in generate-pdf endpoint

---

### 3. 💰 GST REFUND REPORT (The Money Maker)

**What It Does:**
Generates GSTR-1 Table 6A formatted CSV for easy GST return filing, helping exporters claim zero-rated benefits.

**Key Changes:**
- **New Button**: "Download GSTR-1 Data" on Dashboard
- **Output Format**: CSV file with all finalized shipments
- **Compliance**: Structured per Indian GST requirements

**How to Use:**
1. Go to Dashboard
2. Click "Download GSTR-1 Data" button (green button, top-right)
3. Open the CSV file
4. Import into your GST return filing system

**CSV Columns:**
- Invoice Number (PO Number)
- Invoice Date (PO Date)
- Port Code (Default: INNSA1)
- Total Value (Sum of items)
- Taxable Value (Same as total for exports)
- Integrated Tax Amount (0.00 for zero-rated exports)

**Technical Details:**
- Backend endpoint: `GET /api/reports/gstr1-export`
- Only includes shipments with status = "Final"
- Auto-download as CSV file

---

### 4. 💼 TALLY XML INTEGRATION (The Retention Feature)

**What It Does:**
Exports shipments directly into Tally.ERP 9 / TallyPrime for seamless accounting integration.

**Key Changes:**
- **Settings Update**: New field "Tally Sales Ledger Name" (default: "Export Sales")
- **New Export**: "💼 Tally XML" button for each finalized shipment
- **Format**: Standard Tally XML voucher structure

**How to Use:**
1. In Settings, set your Tally Sales Ledger Name (e.g., "Export Sales")
2. Go to Dashboard
3. For any finalized shipment, click "💼 Tally XML"
4. Save the XML file
5. In Tally: Gateway → Import → Vouchers → Select the XML file

**XML Structure:**
- Voucher Type: Sales
- Party Ledger: Buyer Name
- Sales Ledger: Your configured ledger name
- Date: PO Date in YYYYMMDD format
- Inventory Entries: All items with description, quantity, rate, amount

**Technical Details:**
- Backend endpoint: `POST /api/shipments/{id}/export-tally`
- Compliant with Tally.ERP 9 and TallyPrime import schema
- All amounts formatted with 2 decimal precision

---

## 🔧 TECHNICAL IMPROVEMENTS

### Backend (FastAPI)
- ✅ Updated `save_profile` endpoint to support `tally_sales_ledger_name`
- ✅ Added math recalculation in `generate-pdf` endpoint
- ✅ New endpoint: `/api/shipments/{id}/generate-packing-list`
- ✅ New endpoint: `/api/reports/gstr1-export`
- ✅ New endpoint: `/api/shipments/{id}/export-tally`
- ✅ Health check now returns "v2.0"

### Frontend (React)
- ✅ NewShipment: Added net_weight and gross_weight columns
- ✅ NewShipment: Real-time math validation with visual feedback
- ✅ Settings: Added Tally Sales Ledger Name field
- ✅ Dashboard: Added GSTR-1 export button
- ✅ Dashboard: Enhanced actions column with 3 download options

### Database (MongoDB)
- ✅ Items schema now includes: `net_weight` and `gross_weight`
- ✅ Company profiles include: `tally_sales_ledger_name`
- ✅ Backward compatible (existing items default to 0 for weights)

---

## 📊 UI/UX ENHANCEMENTS

### New Shipment Page
- Wider table with 8 columns (was 6)
- Compact design with smaller padding for better visibility
- Red highlighting for math mismatches
- Helper text for weight columns

### Dashboard
- Two-button action bar (GSTR-1 + New Shipment)
- Three download options per shipment:
  - 📄 Invoice PDF
  - 📦 Packing List
  - 💼 Tally XML
- Color-coded buttons for easy identification

### Settings Page
- New "Tally Sales Ledger Name" field in Bank Details section
- Helper text explaining the field's purpose
- Default value: "Export Sales"

---

## 🚀 USAGE SCENARIOS

### Complete Export Workflow (Version 2.0)
1. **Setup** (One-time): Configure company profile including Tally ledger name
2. **Create Shipment**: Upload PO, review AI-extracted data, add weights
3. **Validate**: Check for math mismatches (red highlighting)
4. **Generate**: Create Invoice PDF with auto-corrected calculations
5. **Download**: Get Packing List for customs clearance
6. **Account**: Export to Tally for seamless bookkeeping
7. **GST Filing**: Download GSTR-1 CSV for return filing

### Business Benefits
- ⏱️ **Time Saving**: Automated packing lists and Tally export save 2-3 hours per shipment
- 💸 **Error Prevention**: Math validation prevents costly calculation mistakes
- 📊 **GST Compliance**: One-click GSTR-1 export simplifies return filing
- 📈 **Scalability**: Tally integration enables growth without manual data entry

---

## 🔐 BACKWARD COMPATIBILITY

- ✅ Existing shipments work without weights (default to 0)
- ✅ Old company profiles work without Tally field (default to "Export Sales")
- ✅ All Version 1.0 features remain unchanged
- ✅ No database migration required

---

## 📝 API DOCUMENTATION

### New Endpoints

**1. Generate Packing List**
```
POST /api/shipments/{shipment_id}/generate-packing-list
Authorization: Bearer {token}
Response: PDF file (packing_list_{id}.pdf)
```

**2. Export GSTR-1 Data**
```
GET /api/reports/gstr1-export
Authorization: Bearer {token}
Response: CSV file (gstr1_export_data.csv)
```

**3. Export to Tally**
```
POST /api/shipments/{shipment_id}/export-tally
Authorization: Bearer {token}
Response: XML file (tally_export_{id}.xml)
```

### Updated Endpoints

**Save Profile**
```
POST /api/profile
Authorization: Bearer {token}
Form Data:
  - All existing fields...
  - tally_sales_ledger_name: string (optional, default: "Export Sales")
```

---

## 🐛 BUG FIXES

- ✅ Fixed Gemini model name to use `models/gemini-2.5-flash`
- ✅ Added `load_dotenv()` for proper environment variable loading
- ✅ Updated frontend to use relative URLs for preview compatibility
- ✅ Fixed authentication persistence issues

---

## 📦 DEPENDENCIES

No new dependencies required. All features use existing libraries:
- ReportLab (PDF generation)
- csv module (GSTR-1 export)
- Built-in XML generation (Tally export)

---

## 🎯 NEXT STEPS

1. **Refresh your browser** to load Version 2.0
2. **Update Settings** with your Tally ledger name
3. **Create a test shipment** with weights
4. **Test all 4 new features**:
   - Generate Packing List
   - Verify math validation
   - Download GSTR-1 CSV
   - Export to Tally

---

## 📞 SUPPORT

For questions or issues with Version 2.0 features:
- Check `/app/TESTING_GUIDE.md` for detailed testing instructions
- Review `/app/README.md` for general documentation
- Check `/app/TROUBLESHOOTING.md` for common issues

---

**Version 2.0 - Built to Scale Your Export Business** 🚀
