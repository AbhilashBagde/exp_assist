import requests
import sys
import json
from datetime import datetime
import os

class ExportAssistAPITester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.test_email = f"test_user_{datetime.now().strftime('%H%M%S')}@example.com"
        self.test_password = "TestPass123!"

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if headers:
            test_headers.update(headers)
            
        if self.token and 'Authorization' not in test_headers:
            test_headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers)
            elif method == 'POST':
                if files:
                    # Remove Content-Type for file uploads
                    if 'Content-Type' in test_headers:
                        del test_headers['Content-Type']
                    response = requests.post(url, data=data, files=files, headers=test_headers)
                else:
                    response = requests.post(url, json=data, headers=test_headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers)
            elif method == 'OPTIONS':
                response = requests.options(url, headers=test_headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test health endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "api/health",
            200
        )
        return success

    def test_cors_preflight(self):
        """Test CORS preflight request"""
        success, response = self.run_test(
            "CORS Preflight",
            "OPTIONS",
            "api/auth/login",
            200,
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        return success

    def test_signup(self):
        """Test user signup"""
        success, response = self.run_test(
            "User Signup",
            "POST",
            "api/auth/signup",
            200,
            data={
                "email": self.test_email,
                "password": self.test_password
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if success and isinstance(response, dict) and 'token' in response:
            self.token = response['token']
            self.user_id = response['user_id']
            print(f"   Token received: {self.token[:20]}...")
            return True
        return False

    def test_login(self):
        """Test user login"""
        success, response = self.run_test(
            "User Login",
            "POST",
            "api/auth/login",
            200,
            data={
                "email": self.test_email,
                "password": self.test_password
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if success and isinstance(response, dict) and 'token' in response:
            self.token = response['token']
            self.user_id = response['user_id']
            return True
        return False

    def test_invalid_login(self):
        """Test login with invalid credentials"""
        success, response = self.run_test(
            "Invalid Login",
            "POST",
            "api/auth/login",
            401,
            data={
                "email": "invalid@example.com",
                "password": "wrongpassword"
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        return success

    def test_get_profile_empty(self):
        """Test getting profile when none exists"""
        success, response = self.run_test(
            "Get Empty Profile",
            "GET",
            "api/profile",
            200
        )
        
        if success and isinstance(response, dict) and response.get('exists') == False:
            print("   Profile correctly shows as non-existent")
            return True
        return False

    def test_save_profile(self):
        """Test saving company profile"""
        profile_data = {
            "company_name": "Test Export Co.",
            "address_line1": "123 Export Street",
            "address_line2": "Export District",
            "iec_code": "IEC1234567890",
            "gst_number": "GST123456789",
            "ad_code": "AD123456",
            "bank_name": "Test Bank",
            "account_number": "1234567890",
            "ifsc_code": "TEST0001234",
            "swift_code": "TESTINBB"
        }
        
        success, response = self.run_test(
            "Save Profile",
            "POST",
            "api/profile",
            200,
            data=profile_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        return success

    def test_get_profile_exists(self):
        """Test getting profile after saving"""
        success, response = self.run_test(
            "Get Saved Profile",
            "GET",
            "api/profile",
            200
        )
        
        if success and isinstance(response, dict) and response.get('exists') == True:
            print(f"   Profile loaded: {response.get('company_name', 'N/A')}")
            return True
        return False

    def test_create_shipment(self):
        """Test creating a shipment"""
        items_data = [
            {
                "description": "Basmati Rice",
                "quantity": 100,
                "unit_price": 50.0,
                "total_amount": 5000.0,
                "hs_code": "1006.30"
            },
            {
                "description": "Cotton Fabric",
                "quantity": 50,
                "unit_price": 25.0,
                "total_amount": 1250.0,
                "hs_code": "5208.00"
            }
        ]
        
        shipment_data = {
            "buyer_name": "ABC Imports Ltd",
            "buyer_address": "456 Import Ave, New York, USA",
            "po_number": "PO-2025-001",
            "po_date": "2025-01-08",
            "items": json.dumps(items_data)
        }
        
        success, response = self.run_test(
            "Create Shipment",
            "POST",
            "api/shipments",
            200,
            data=shipment_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if success and isinstance(response, dict) and 'shipment_id' in response:
            self.shipment_id = response['shipment_id']
            print(f"   Shipment created: {self.shipment_id}")
            return True
        return False

    def test_get_shipments(self):
        """Test getting all shipments"""
        success, response = self.run_test(
            "Get Shipments",
            "GET",
            "api/shipments",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   Found {len(response)} shipments")
            return True
        return False

    def test_get_single_shipment(self):
        """Test getting a single shipment"""
        if not hasattr(self, 'shipment_id'):
            print("   Skipping - no shipment ID available")
            return True
            
        success, response = self.run_test(
            "Get Single Shipment",
            "GET",
            f"api/shipments/{self.shipment_id}",
            200
        )
        
        if success and isinstance(response, dict) and response.get('_id') == self.shipment_id:
            print(f"   Shipment details loaded: {response.get('buyer_name', 'N/A')}")
            return True
        return False

    def test_generate_pdf(self):
        """Test PDF generation"""
        if not hasattr(self, 'shipment_id'):
            print("   Skipping - no shipment ID available")
            return True
            
        success, response = self.run_test(
            "Generate PDF",
            "POST",
            f"api/shipments/{self.shipment_id}/generate-pdf",
            200
        )
        return success

    def test_extract_po_data_no_api_key(self):
        """Test PO extraction without API key (should fail gracefully)"""
        # Create a dummy file for testing
        test_file_content = b"dummy pdf content"
        files = {'file': ('test.pdf', test_file_content, 'application/pdf')}
        
        success, response = self.run_test(
            "Extract PO Data (No API Key)",
            "POST",
            "api/shipments/extract",
            500,  # Should fail with 500 due to missing API key
            files=files
        )
        return success

    def test_unauthorized_access(self):
        """Test accessing protected endpoint without token"""
        # Temporarily remove token
        temp_token = self.token
        self.token = None
        
        success, response = self.run_test(
            "Unauthorized Access",
            "GET",
            "api/profile",
            401
        )
        
        # Restore token
        self.token = temp_token
        return success

def main():
    print("🚀 Starting ExportAssist API Tests")
    print("=" * 50)
    
    # Initialize tester
    tester = ExportAssistAPITester()
    
    # Run tests in sequence
    tests = [
        tester.test_health_check,
        tester.test_cors_preflight,
        tester.test_signup,
        tester.test_invalid_login,
        tester.test_login,
        tester.test_unauthorized_access,
        tester.test_get_profile_empty,
        tester.test_save_profile,
        tester.test_get_profile_exists,
        tester.test_create_shipment,
        tester.test_get_shipments,
        tester.test_get_single_shipment,
        tester.test_generate_pdf,
        tester.test_extract_po_data_no_api_key,
    ]
    
    # Execute all tests
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {str(e)}")
    
    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 Final Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())