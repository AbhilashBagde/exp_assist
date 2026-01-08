"""
ExportAssist API Tests
Tests for: Auth, Profile, Shipments (with new logistics fields), PDF Generation
"""
import pytest
import requests
import os
import json
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test data
TEST_EMAIL = f"test_{uuid.uuid4().hex[:8]}@example.com"
TEST_PASSWORD = "Test123!"
TEST_TOKEN = None
TEST_USER_ID = None
TEST_SHIPMENT_ID = None


class TestHealthCheck:
    """Health check endpoint tests"""
    
    def test_health_endpoint(self):
        """Test API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "ExportAssist" in data["service"]
        print(f"✓ Health check passed: {data}")


class TestAuth:
    """Authentication endpoint tests"""
    
    def test_signup_new_user(self):
        """Test user signup with new account"""
        global TEST_TOKEN, TEST_USER_ID
        
        response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            data={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        assert response.status_code == 200, f"Signup failed: {response.text}"
        data = response.json()
        
        assert "token" in data
        assert "user_id" in data
        assert data["email"] == TEST_EMAIL
        
        TEST_TOKEN = data["token"]
        TEST_USER_ID = data["user_id"]
        print(f"✓ Signup successful for {TEST_EMAIL}")
    
    def test_signup_duplicate_email(self):
        """Test signup with existing email fails"""
        response = requests.post(
            f"{BASE_URL}/api/auth/signup",
            data={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json().get("detail", "").lower()
        print("✓ Duplicate email signup correctly rejected")
    
    def test_login_valid_credentials(self):
        """Test login with valid credentials"""
        global TEST_TOKEN
        
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "token" in data
        assert "user_id" in data
        assert data["email"] == TEST_EMAIL
        assert "is_pro_member" in data
        
        TEST_TOKEN = data["token"]
        print(f"✓ Login successful, is_pro_member: {data['is_pro_member']}")
    
    def test_login_invalid_credentials(self):
        """Test login with wrong password"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            data={"email": TEST_EMAIL, "password": "wrongpassword"}
        )
        
        assert response.status_code == 401
        print("✓ Invalid credentials correctly rejected")
    
    def test_get_user_info(self):
        """Test getting user info with token"""
        response = requests.get(
            f"{BASE_URL}/api/user/me",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["email"] == TEST_EMAIL
        assert "is_pro_member" in data
        assert "created_at" in data
        print(f"✓ User info retrieved: {data['email']}")


class TestCompanyProfile:
    """Company profile endpoint tests"""
    
    def test_get_profile_not_exists(self):
        """Test getting profile when none exists"""
        response = requests.get(
            f"{BASE_URL}/api/profile",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("exists") == False
        print("✓ Profile correctly shows as not existing")
    
    def test_create_profile(self):
        """Test creating company profile with all fields"""
        profile_data = {
            "company_name": "Test Export Company Pvt Ltd",
            "address_line1": "123 Export Street, Mumbai",
            "address_line2": "Maharashtra, India - 400001",
            "iec_code": "0123456789",
            "gst_number": "27AABCT1234A1ZV",
            "ad_code": "1234567",
            "bank_name": "State Bank of India",
            "account_number": "12345678901234",
            "ifsc_code": "SBIN0001234",
            "swift_code": "SBININBB",
            "tally_sales_ledger_name": "Export Sales"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/profile",
            data=profile_data,
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✓ Company profile created successfully")
    
    def test_get_profile_exists(self):
        """Test getting profile after creation"""
        response = requests.get(
            f"{BASE_URL}/api/profile",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("exists") == True
        assert data["company_name"] == "Test Export Company Pvt Ltd"
        assert data["iec_code"] == "0123456789"
        assert data["gst_number"] == "27AABCT1234A1ZV"
        assert data["bank_name"] == "State Bank of India"
        print(f"✓ Profile retrieved: {data['company_name']}")


class TestShipments:
    """Shipment CRUD tests with new logistics fields"""
    
    def test_get_shipments_empty(self):
        """Test getting shipments when none exist"""
        response = requests.get(
            f"{BASE_URL}/api/shipments",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Shipments list retrieved: {len(data)} shipments")
    
    def test_create_shipment_with_logistics_fields(self):
        """Test creating shipment with all new logistics fields"""
        global TEST_SHIPMENT_ID
        
        items = [
            {
                "description": "Basmati Rice Premium Grade",
                "quantity": 100,
                "unit_price": 25.50,
                "hs_code": "1006.30",
                "total_amount": 2550.00,
                "net_weight": 100,
                "gross_weight": 105
            },
            {
                "description": "Cotton Fabric - White",
                "quantity": 50,
                "unit_price": 15.00,
                "hs_code": "5208.00",
                "total_amount": 750.00,
                "net_weight": 50,
                "gross_weight": 52
            }
        ]
        
        shipment_data = {
            "buyer_name": "Global Imports LLC",
            "buyer_address": "456 Trade Avenue, New York, NY 10001, USA",
            "po_number": f"PO-TEST-{uuid.uuid4().hex[:6].upper()}",
            "po_date": "2025-01-08",
            "currency": "USD",
            "port_of_loading": "INNSA - Nhava Sheva",
            "port_of_discharge": "USLAX - Los Angeles",
            "incoterms": "FOB",
            "total_packages": 10,
            "package_type": "CARTONS",
            "items": json.dumps(items)
        }
        
        response = requests.post(
            f"{BASE_URL}/api/shipments",
            data=shipment_data,
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200, f"Create shipment failed: {response.text}"
        data = response.json()
        
        assert data["success"] == True
        assert "shipment_id" in data
        
        TEST_SHIPMENT_ID = data["shipment_id"]
        print(f"✓ Shipment created with ID: {TEST_SHIPMENT_ID}")
    
    def test_get_shipment_by_id(self):
        """Test getting shipment by ID and verify all fields"""
        response = requests.get(
            f"{BASE_URL}/api/shipments/{TEST_SHIPMENT_ID}",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify basic fields
        assert data["buyer_name"] == "Global Imports LLC"
        assert data["currency"] == "USD"
        assert data["status"] == "Draft"
        
        # Verify NEW logistics fields
        assert data["port_of_loading"] == "INNSA - Nhava Sheva"
        assert data["port_of_discharge"] == "USLAX - Los Angeles"
        assert data["incoterms"] == "FOB"
        assert data["total_packages"] == 10
        assert data["package_type"] == "CARTONS"
        
        # Verify items
        assert len(data["items"]) == 2
        assert data["items"][0]["description"] == "Basmati Rice Premium Grade"
        assert data["items"][0]["hs_code"] == "1006.30"
        
        print(f"✓ Shipment retrieved with all logistics fields verified")
        print(f"  - Port of Loading: {data['port_of_loading']}")
        print(f"  - Port of Discharge: {data['port_of_discharge']}")
        print(f"  - Incoterms: {data['incoterms']}")
        print(f"  - Total Packages: {data['total_packages']} {data['package_type']}")
    
    def test_update_shipment(self):
        """Test updating shipment with modified logistics fields"""
        items = [
            {
                "description": "Basmati Rice Premium Grade",
                "quantity": 150,  # Updated quantity
                "unit_price": 25.50,
                "hs_code": "1006.30",
                "total_amount": 3825.00,
                "net_weight": 150,
                "gross_weight": 157
            }
        ]
        
        update_data = {
            "buyer_name": "Global Imports LLC",
            "buyer_address": "456 Trade Avenue, New York, NY 10001, USA",
            "po_number": "PO-TEST-UPDATED",
            "po_date": "2025-01-08",
            "currency": "EUR",  # Changed currency
            "port_of_loading": "INMAA - Chennai",  # Changed port
            "port_of_discharge": "DEHAM - Hamburg",  # Changed port
            "incoterms": "CIF",  # Changed incoterms
            "total_packages": 15,  # Changed packages
            "package_type": "PALLETS",  # Changed type
            "status": "Draft",
            "items": json.dumps(items)
        }
        
        response = requests.put(
            f"{BASE_URL}/api/shipments/{TEST_SHIPMENT_ID}",
            data=update_data,
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        # Verify update by fetching
        get_response = requests.get(
            f"{BASE_URL}/api/shipments/{TEST_SHIPMENT_ID}",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        updated = get_response.json()
        assert updated["currency"] == "EUR"
        assert updated["port_of_loading"] == "INMAA - Chennai"
        assert updated["port_of_discharge"] == "DEHAM - Hamburg"
        assert updated["incoterms"] == "CIF"
        assert updated["total_packages"] == 15
        assert updated["package_type"] == "PALLETS"
        
        print("✓ Shipment updated and verified with new logistics fields")
    
    def test_get_shipments_list(self):
        """Test getting all shipments"""
        response = requests.get(
            f"{BASE_URL}/api/shipments",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) >= 1
        
        # Find our test shipment
        test_shipment = next((s for s in data if s["_id"] == TEST_SHIPMENT_ID), None)
        assert test_shipment is not None
        
        print(f"✓ Shipments list contains {len(data)} shipment(s)")


class TestPDFGeneration:
    """PDF generation endpoint tests"""
    
    def test_generate_invoice_pdf(self):
        """Test generating Commercial Invoice PDF"""
        response = requests.post(
            f"{BASE_URL}/api/shipments/{TEST_SHIPMENT_ID}/generate-pdf",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200, f"PDF generation failed: {response.text}"
        assert response.headers.get("content-type") == "application/pdf"
        
        # Verify PDF content (should start with %PDF)
        assert response.content[:4] == b'%PDF'
        
        print(f"✓ Invoice PDF generated successfully ({len(response.content)} bytes)")
    
    def test_generate_packing_list_pdf(self):
        """Test generating Packing List PDF"""
        response = requests.post(
            f"{BASE_URL}/api/shipments/{TEST_SHIPMENT_ID}/generate-packing-list",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200, f"Packing list generation failed: {response.text}"
        assert response.headers.get("content-type") == "application/pdf"
        
        # Verify PDF content
        assert response.content[:4] == b'%PDF'
        
        print(f"✓ Packing List PDF generated successfully ({len(response.content)} bytes)")
    
    def test_shipment_status_after_pdf(self):
        """Verify shipment status is 'Final' after PDF generation"""
        response = requests.get(
            f"{BASE_URL}/api/shipments/{TEST_SHIPMENT_ID}",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "Final"
        assert "pdf_url" in data
        
        print(f"✓ Shipment status is 'Final' with PDF URL: {data['pdf_url']}")


class TestTallyExport:
    """Tally XML export tests"""
    
    def test_export_tally_xml(self):
        """Test exporting Tally XML"""
        response = requests.post(
            f"{BASE_URL}/api/shipments/{TEST_SHIPMENT_ID}/export-tally",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200, f"Tally export failed: {response.text}"
        assert "xml" in response.headers.get("content-type", "").lower()
        
        # Verify XML content
        content = response.content.decode('utf-8')
        assert '<?xml version="1.0"' in content
        assert '<ENVELOPE>' in content
        assert '<VOUCHER' in content
        
        print(f"✓ Tally XML exported successfully ({len(response.content)} bytes)")


class TestGSTR1Export:
    """GSTR-1 export tests"""
    
    def test_export_gstr1_csv(self):
        """Test exporting GSTR-1 CSV data"""
        response = requests.get(
            f"{BASE_URL}/api/reports/gstr1-export",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        
        assert response.status_code == 200, f"GSTR-1 export failed: {response.text}"
        assert "csv" in response.headers.get("content-type", "").lower()
        
        # Verify CSV content
        content = response.content.decode('utf-8')
        assert "Invoice Number" in content
        assert "Invoice Date" in content
        
        print(f"✓ GSTR-1 CSV exported successfully ({len(response.content)} bytes)")


class TestErrorHandling:
    """Error handling tests"""
    
    def test_unauthorized_access(self):
        """Test accessing protected endpoint without token"""
        response = requests.get(f"{BASE_URL}/api/shipments")
        assert response.status_code in [401, 403]
        print("✓ Unauthorized access correctly rejected")
    
    def test_invalid_token(self):
        """Test accessing with invalid token"""
        response = requests.get(
            f"{BASE_URL}/api/shipments",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        assert response.status_code == 401
        print("✓ Invalid token correctly rejected")
    
    def test_shipment_not_found(self):
        """Test getting non-existent shipment"""
        response = requests.get(
            f"{BASE_URL}/api/shipments/non-existent-id",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"}
        )
        assert response.status_code == 404
        print("✓ Non-existent shipment returns 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
