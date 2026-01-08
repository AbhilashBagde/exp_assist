# ExportAssist - Testing & Verification Guide

## Quick Test Checklist

### ✅ Step 1: Start the Application

```bash
# Check if services are running
sudo supervisorctl status

# Should show:
# backend   RUNNING
# frontend  RUNNING
# mongodb   RUNNING
```

### ✅ Step 2: Access the Application

1. Open your browser and go to: **http://localhost:3000**
2. You should see the ExportAssist login page

### ✅ Step 3: Create an Account

1. Click "Sign Up" on the login page
2. Enter:
   - Email: `test@example.com`
   - Password: `test123456`
3. Click "Sign Up" button
4. You should be automatically redirected to the Settings page

### ✅ Step 4: Complete Company Profile (First-Time Setup)

Fill in the following test data:

**Company Information:**
- Company Name: `Test Export Company Ltd`
- Address Line 1: `123 Export Street, Industrial Area`
- Address Line 2: `Mumbai, Maharashtra 400001`
- IEC Code: `IEC1234567890`
- GST Number: `27AABCT1234A1Z5`
- AD Code: `1234567` (optional)

**Bank Details:**
- Bank Name: `State Bank of India`
- Account Number: `12345678901234`
- IFSC Code: `SBIN0001234`
- SWIFT Code: `SBININBB123` (optional)

**Signature Upload:**
- Click on the upload area
- Select any image file (PNG/JPG)
- See preview appear

Click **"Save Profile"** - You should see a success message and be redirected to Dashboard.

### ✅ Step 5: Test Dashboard

1. You should now see the Dashboard
2. Verify these elements are present:
   - ExportAssist header with logo
   - "New Shipment" button (green, top-right)
   - "Settings" button
   - "Logout" button
   - Empty state message: "No shipments yet"

### ✅ Step 6: Create a New Shipment

#### Option A: With Gemini API Key (AI Extraction)

**Prerequisites:** You must have configured `GEMINI_API_KEY` in `/app/backend/.env`

1. Click "New Shipment" button
2. **Step 1 - Upload PO:**
   - Drag & drop or click to upload a Purchase Order (PDF/Image)
   - You should see file name appear
   - Click "Proceed to Extraction"

3. **Step 2 - AI Processing:**
   - Click "Start AI Extraction"
   - Wait for AI to process (may take 10-30 seconds)
   - AI will extract buyer details, items, and predict HS Codes

4. **Step 3 - Review Form:**
   - Verify extracted data is shown
   - **Important:** Check HS Codes (highlighted in yellow)
   - Edit any incorrect information
   - Click "Save & Generate Invoice"

5. **Step 4 - Success:**
   - PDF will be automatically downloaded
   - Click "Go to Dashboard" to see your shipment

#### Option B: Manual Entry (No API Key Required)

1. Click "New Shipment" button
2. **Step 1 - Upload PO:**
   - Upload any document (just for workflow testing)
   - Click "Proceed to Extraction"

3. **Step 2 - AI Processing:**
   - Click **"Skip & Enter Manually"** button
   - This bypasses AI extraction

4. **Step 3 - Manual Entry Form:**
   Enter this test data:

   **Buyer Information:**
   - Buyer Name: `ABC Trading Inc`
   - PO Number: `PO-2025-001`
   - PO Date: `2025-01-08`
   - Buyer Address: `456 Import Avenue, New York, USA`

   **Items Table:**
   
   Click "Add Item" and fill:
   
   Item 1:
   - Description: `Basmati Rice - Premium Quality`
   - HS Code: `1006.30` (highlight should be yellow ⚠️)
   - Quantity: `1000`
   - Rate: `75.50`
   - Amount: (auto-calculated: 75,500.00)

   Item 2:
   - Description: `Organic Turmeric Powder`
   - HS Code: `0910.30`
   - Quantity: `500`
   - Rate: `120.00`
   - Amount: (auto-calculated: 60,000.00)

   Click **"Save & Generate Invoice"**

5. **Step 4 - Success:**
   - Commercial Invoice PDF will download automatically
   - Open the PDF and verify it contains:
     ✓ Your company details
     ✓ Buyer information
     ✓ Items table with HS Codes
     ✓ Bank details
     ✓ Compliance text at bottom
     ✓ Signature (if uploaded)

### ✅ Step 7: Verify Dashboard Shows Shipment

1. Go back to Dashboard
2. You should now see:
   - Table with your shipment
   - PO Number, Buyer Name, Date
   - Total Value: ₹1,35,500.00
   - Status: **"Final"** (green badge)
   - "Download PDF" link

3. Click "Download PDF" to re-download the invoice

### ✅ Step 8: Test Logout & Login

1. Click "Logout" button
2. You should be redirected to login page
3. Login again with:
   - Email: `test@example.com`
   - Password: `test123456`
4. Should redirect to Dashboard with your shipment still there

---

## Backend API Testing (Command Line)

### Test 1: Health Check
```bash
curl http://localhost:8001/api/health
# Expected: {"status":"healthy","service":"ExportAssist API"}
```

### Test 2: User Signup
```bash
curl -X POST "http://localhost:8001/api/auth/signup" \
  -F "email=apitest@example.com" \
  -F "password=test12345"
# Expected: {"token":"...","user_id":"...","email":"apitest@example.com"}
```

### Test 3: User Login
```bash
curl -X POST "http://localhost:8001/api/auth/login" \
  -F "email=apitest@example.com" \
  -F "password=test12345"
# Expected: {"token":"...","user_id":"...","email":"apitest@example.com"}
```

### Test 4: Get Profile (with auth)
```bash
# Replace YOUR_TOKEN with actual token from login
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8001/api/profile
# Expected: {"exists":false} or profile data
```

### Test 5: Get Shipments
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8001/api/shipments
# Expected: [] or array of shipments
```

---

## Troubleshooting Common Issues

### Issue 1: "Cannot connect to backend"
**Solution:**
```bash
# Check backend logs
tail -f /var/log/supervisor/backend.err.log

# Restart backend
sudo supervisorctl restart backend
```

### Issue 2: "Gemini API key not configured" error
**Solution:**
1. Get API key from: https://makersuite.google.com/app/apikey
2. Edit `/app/backend/.env`:
   ```
   GEMINI_API_KEY=your-actual-key-here
   ```
3. Restart backend: `sudo supervisorctl restart backend`
4. OR use "Skip & Enter Manually" option

### Issue 3: Frontend shows blank page
**Solution:**
```bash
# Check frontend logs
tail -f /var/log/supervisor/frontend.out.log

# Clear cache and restart
cd /app/frontend
rm -rf node_modules/.cache
sudo supervisorctl restart frontend
```

### Issue 4: Authentication keeps logging out
**Solution:**
- Clear browser cache and cookies
- Try incognito/private browsing mode
- Check browser console for errors (F12)

### Issue 5: PDF not generating
**Solution:**
1. Ensure company profile is complete with signature
2. Check backend logs for errors
3. Verify all required fields are filled in shipment form
4. Make sure items table has at least one item

### Issue 6: HS Code fields not highlighted yellow
**Solution:**
- The highlight should appear in Step 3 (Review Form)
- Check if CSS is loading properly
- Try hard refresh (Ctrl+Shift+R)

---

## Expected File Structure

```
/app/
├── backend/
│   ├── server.py           (Main FastAPI app)
│   ├── requirements.txt    (Python dependencies)
│   ├── .env               (Environment variables)
│   └── uploads/           (Uploaded files & generated PDFs)
├── frontend/
│   ├── src/
│   │   ├── App.js
│   │   ├── components/
│   │   │   ├── Login.js
│   │   │   ├── Dashboard.js
│   │   │   ├── Settings.js
│   │   │   └── NewShipment.js
│   │   └── ...
│   ├── package.json
│   └── .env
└── README.md
```

---

## Performance Benchmarks

- Login/Signup: < 1 second
- Dashboard load: < 2 seconds
- AI Extraction: 10-30 seconds (depends on Gemini API)
- Manual entry form: Instant
- PDF Generation: 2-5 seconds

---

## Security Notes

- ✅ Passwords are hashed with bcrypt
- ✅ JWT tokens expire after 7 days
- ✅ All API endpoints require authentication (except signup/login)
- ✅ CORS is configured for localhost development
- ⚠️ For production: Change JWT_SECRET and use HTTPS

---

## Next Steps After Testing

If all tests pass:
1. ✅ Add real company profile
2. ✅ Configure Gemini API key for production use
3. ✅ Start creating real shipments
4. ✅ Download and verify Commercial Invoices
5. ✅ Share invoices with buyers

If you encounter issues:
- Check the troubleshooting section above
- Review logs in `/var/log/supervisor/`
- Ensure all dependencies are installed
- Verify MongoDB is running

---

**Happy Exporting! 🚢📦**
