# Common Issues & Quick Fixes

## Issue: "Authentication failed" or "Email already registered" during Signup

### Problem
The database contains test data from previous testing, and the email you're trying to use is already registered.

### Solution

**Option 1: Use the Reset Script (Recommended)**
```bash
cd /app/scripts
./reset_database.sh
```

**Option 2: Manual Database Clear**
```bash
mongosh exportassist --eval "db.users.deleteMany({}); db.company_profiles.deleteMany({}); db.shipments.deleteMany({});"
```

**Option 3: Use a Different Email**
Simply try signing up with a different email address that hasn't been used before.

**Option 4: Login Instead**
If you created an account during testing, try logging in with those credentials instead of signing up again.

---

## Issue: Frontend shows blank page or won't load

### Solution
```bash
# Restart frontend
sudo supervisorctl restart frontend

# Wait 10 seconds
sleep 10

# Check status
sudo supervisorctl status frontend

# Clear browser cache
# Then refresh the page (Ctrl + Shift + R)
```

---

## Issue: "Cannot connect to backend" errors

### Solution
```bash
# Check if backend is running
sudo supervisorctl status backend

# If not running, restart it
sudo supervisorctl restart backend

# Check backend logs for errors
tail -f /var/log/supervisor/backend.err.log
```

---

## Issue: Login works but immediately logs out

### Solution
This was fixed in the latest version. Make sure you have the latest code with proper 401 error handling.

```bash
# Restart frontend to ensure latest code is loaded
sudo supervisorctl restart frontend
```

---

## Issue: "Gemini API key not configured" error

### This is Expected Behavior!
The app works perfectly without a Gemini API key. You have two options:

**Option 1: Use Manual Entry (No API Key Needed)**
1. Upload your PO document
2. Click "Skip & Enter Manually"
3. Fill in the form manually

**Option 2: Configure Gemini API**
1. Get API key from: https://makersuite.google.com/app/apikey
2. Edit `/app/backend/.env`:
   ```
   GEMINI_API_KEY=your-actual-key-here
   ```
3. Restart backend:
   ```bash
   sudo supervisorctl restart backend
   ```

---

## Issue: PDF not generating or downloading

### Solution
1. Ensure company profile is complete (including signature upload)
2. Ensure shipment form has all required fields filled
3. Check backend logs:
   ```bash
   tail -f /var/log/supervisor/backend.err.log
   ```

---

## Quick Health Check

Run this to verify everything is working:

```bash
# Check all services
sudo supervisorctl status

# Test backend API
curl http://localhost:8001/api/health

# Test frontend (should return HTML)
curl http://localhost:3000
```

Expected output:
- All services: `RUNNING`
- Backend health: `{"status":"healthy","service":"ExportAssist API"}`
- Frontend: HTML content

---

## Fresh Start

If nothing works, do a complete restart:

```bash
# Clear database
cd /app/scripts
./reset_database.sh

# Restart all services
sudo supervisorctl restart all

# Wait for services to start
sleep 15

# Check status
sudo supervisorctl status

# Open browser to http://localhost:3000
```

---

## Still Having Issues?

Check the logs for detailed error messages:

```bash
# Backend errors
tail -100 /var/log/supervisor/backend.err.log

# Backend requests
tail -100 /var/log/supervisor/backend.out.log

# Frontend compilation
tail -100 /var/log/supervisor/frontend.out.log
```

Look for lines containing:
- `ERROR`
- `FAILED`
- `Exception`
- Status codes like `500`, `401`, `403`
