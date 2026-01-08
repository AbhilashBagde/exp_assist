# ExportAssist - Automated Documentation Tool for Indian Exporters

A scalable B2B SaaS application that automates documentation for Indian exporters by using AI Vision to extract data from Purchase Orders and generate compliant Commercial Invoices.

## 🚀 Features

- **AI-Powered Document Extraction**: Upload PDF or image files of Purchase Orders and let AI extract buyer details, items, and predict Indian ITC-HS Codes
- **Intelligent HS Code Prediction**: Automatic prediction of Indian Export HS Codes based on product descriptions
- **Human-in-the-Loop Review**: Verify and edit all AI-extracted data before generating invoices
- **Professional PDF Generation**: Generate compliance-ready Commercial Invoice PDFs with all required details
- **Company Profile Management**: One-time setup for company details, bank information, and authorized signatures
- **Shipment Dashboard**: Track all your export shipments and their statuses

## 🛠️ Tech Stack

### Backend
- **FastAPI** (Python) - High-performance web framework
- **MongoDB** - Document database for flexible data storage
- **Google Gemini AI** - Vision API for document extraction and HS Code prediction
- **ReportLab** - Professional PDF generation
- **PyJWT** - JWT-based authentication

### Frontend
- **React** - Modern UI framework
- **Tailwind CSS** - Utility-first styling
- **Lucide Icons** - Beautiful icon library
- **Axios** - HTTP client
- **React Router** - Client-side routing

## 📋 Prerequisites

- Python 3.11+
- Node.js 18+ & Yarn
- MongoDB
- Gemini API Key (for AI Vision)

## 🔧 Installation & Setup

### 1. Backend Setup

```bash
cd /app/backend

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
# Edit .env file with your settings:
MONGO_URL=mongodb://localhost:27017/exportassist
JWT_SECRET=your-secret-key-change-in-production
GEMINI_API_KEY=your-gemini-api-key-here
```

### 2. Frontend Setup

```bash
cd /app/frontend

# Install Node dependencies
yarn install

# Configure environment variables
# Edit .env file:
REACT_APP_BACKEND_URL=http://localhost:8001
```

### 3. Start Services

```bash
# Using supervisor (recommended)
sudo supervisorctl restart all

# Check service status
sudo supervisorctl status

# Or manually:
# Terminal 1 - Backend
cd /app/backend
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# Terminal 2 - Frontend
cd /app/frontend
yarn start
```

## 🌐 Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs

## 📖 User Guide

### First Time Setup

1. **Sign Up**: Create an account with your email and password
2. **Company Profile**: You'll be redirected to Settings page
   - Fill in company information (Name, Address, IEC Code, GST Number)
   - Enter bank details for invoice generation
   - **Important**: Upload your authorized signature/stamp image
3. **Save Profile**: Click "Save Profile" to complete setup

### Creating a Shipment

#### Step 1: Upload Purchase Order
- Click "New Shipment" from the dashboard
- Drag and drop or click to upload a PO file
- Supports: PDF, JPG, PNG formats

#### Step 2: AI Processing
- Click "Start Extraction"
- AI Vision will analyze the document and extract:
  - Buyer name and address
  - PO number and date
  - Table of items with descriptions and quantities
  - **Predicted Indian ITC-HS Codes** for each item

#### Step 3: Review & Edit
- Verify all extracted information
- **⚠️ Important**: Check the HS Codes highlighted in yellow
  - AI predictions are based on product descriptions
  - Incorrect codes can cause compliance issues
  - Edit if needed
- Adjust quantities, rates, or descriptions as needed
- Add or remove items

#### Step 4: Generate Invoice
- Click "Save & Generate Invoice"
- A professional Commercial Invoice PDF will be generated
- The PDF includes:
  - Your company details and logo
  - Buyer information
  - Itemized table with HS Codes
  - Bank details
  - Authorized signature
  - Compliance text: "Supply Meant for Export Under Bond/LUT"

### Dashboard

- View all shipments with their status (Draft/Final)
- See PO numbers, buyer names, and total values
- Download generated PDF invoices
- Track creation dates

## 🔑 API Endpoints

### Authentication
- `POST /api/auth/signup` - Create new account
- `POST /api/auth/login` - Login to existing account

### Company Profile
- `GET /api/profile` - Get company profile
- `POST /api/profile` - Save company profile
- `POST /api/profile/signature` - Upload signature image

### Shipments
- `GET /api/shipments` - List all shipments
- `GET /api/shipments/{id}` - Get specific shipment
- `POST /api/shipments` - Create new shipment
- `PUT /api/shipments/{id}` - Update shipment
- `POST /api/shipments/extract` - AI extraction from PO file
- `POST /api/shipments/{id}/generate-pdf` - Generate invoice PDF

## 🗄️ Database Schema

### Collections

**users**
```javascript
{
  _id: "uuid",
  email: "string",
  password_hash: "bcrypt_hash",
  created_at: "datetime"
}
```

**company_profiles**
```javascript
{
  _id: "uuid",
  user_id: "uuid",
  company_name: "string",
  address_line1: "string",
  address_line2: "string",
  iec_code: "string",
  gst_number: "string",
  ad_code: "string",
  bank_name: "string",
  account_number: "string",
  ifsc_code: "string",
  swift_code: "string",
  signature_image_url: "string"
}
```

**shipments** (with embedded items)
```javascript
{
  _id: "uuid",
  user_id: "uuid",
  buyer_name: "string",
  buyer_address: "string",
  po_number: "string",
  po_date: "date",
  status: "Draft" | "Final",
  created_at: "datetime",
  items: [
    {
      description: "string",
      quantity: number,
      unit_price: number,
      hs_code: "string",
      total_amount: number
    }
  ],
  pdf_url: "string" // Only for Final status
}
```

## 🎨 Design Theme

**Logistics Professional Theme**
- Primary Color: Navy Blue `#0f172a`
- Accent: Slate Grey `#64748b`
- Background: Light `#f8fafc`
- Highlight: Yellow (for HS Code warnings) `#fef3c7`

## 🔐 Security Features

- JWT-based authentication
- Bcrypt password hashing
- Protected API endpoints
- CORS configuration
- File upload validation

## 📝 Important Notes

### HS Code Compliance
The AI predicts Indian ITC-HS Codes based on product descriptions, but these should always be verified by the user. Incorrect HS Codes can lead to:
- Customs clearance delays
- Incorrect duty calculations
- Compliance violations

### File Upload Support
- **PDF**: Full document support
- **Images**: JPG, PNG, JPEG
- PDF files are converted to images for AI processing
- Maximum recommended file size: 10MB

### Invoice Compliance
Generated invoices include all required elements for Indian export documentation:
- IEC Code and GST Number
- Itemized HS Codes
- Bank details for payment
- Authorized signature
- Export compliance declaration

## 🚀 Deployment

The application is configured to work with:
- **Backend**: Port 8001 (mapped via Kubernetes ingress with /api prefix)
- **Frontend**: Port 3000
- **MongoDB**: Default port 27017

All routes to the backend must be prefixed with `/api` to ensure proper routing through the Kubernetes ingress.

## 🐛 Troubleshooting

### Backend not starting
```bash
# Check logs
tail -f /var/log/supervisor/backend.err.log

# Verify MongoDB is running
supervisorctl status mongodb

# Check if port 8001 is available
netstat -tuln | grep 8001
```

### Frontend not starting
```bash
# Check logs
tail -f /var/log/supervisor/frontend.out.log

# Clear node_modules and reinstall
cd /app/frontend
rm -rf node_modules
yarn install
```

### Gemini API not working
- Verify your API key is correct in `/app/backend/.env`
- Check if you have sufficient quota
- Test with Gemini API playground first

## 📦 Dependencies

### Backend (`requirements.txt`)
- fastapi==0.104.1
- pymongo==4.6.0
- google-generativeai==0.3.1
- reportlab==4.0.7
- PyJWT==2.8.0
- bcrypt==4.1.1
- pdf2image==1.16.3
- Pillow==10.1.0

### Frontend (`package.json`)
- react: ^18.2.0
- react-router-dom: ^6.20.0
- lucide-react: ^0.294.0
- axios: ^1.6.2

## 📄 License

Proprietary - ExportAssist B2B SaaS

## 👥 Support

For issues or questions, please contact the development team.

---

**Built with ❤️ for Indian Exporters**
