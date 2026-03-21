import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building, CreditCard, Upload, Save, ArrowLeft } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function Settings() {
  const [formData, setFormData] = useState({
    company_name: '',
    address_line1: '',
    address_line2: '',
    iec_code: '',
    gst_number: '',
    ad_code: '',
    bank_name: '',
    account_number: '',
    ifsc_code: '',
    swift_code: '',
    tally_sales_ledger_name: 'Export Sales'
  });
  const [signatureFile, setSignatureFile] = useState(null);
  const [signaturePreview, setSignaturePreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  const fetchProfile = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/api/profile`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.data.exists) {
        setFormData(response.data);
        if (response.data.signature_image_url) {
          setSignaturePreview(`${API_URL}${response.data.signature_image_url}`);
        }
      }
    } catch (err) {
      console.error('Error fetching profile:', err);
      if (err.response?.status === 401) {
        localStorage.clear();
        navigate('/login');
      }
    }
  }, [token, navigate]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSignatureChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSignatureFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setSignaturePreview(reader.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage({ type: '', text: '' });

    try {
      // Save profile data
      const profileFormData = new FormData();
      Object.keys(formData).forEach(key => {
        if (key !== '_id' && key !== 'exists' && key !== 'user_id' && key !== 'signature_image_url') {
          profileFormData.append(key, formData[key]);
        }
      });

      await axios.post(`${API_URL}/api/profile`, profileFormData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });

      // Upload signature if selected
      if (signatureFile) {
        const signatureFormData = new FormData();
        signatureFormData.append('signature', signatureFile);

        await axios.post(`${API_URL}/api/profile/signature`, signatureFormData, {
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'multipart/form-data'
          }
        });
      }

      setMessage({ type: 'success', text: 'Profile saved successfully!' });
      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to save profile' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-navy text-white shadow-lg" data-testid="settings-header">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center space-x-3">
            <img src="/TDA.png" alt="TradesdocAi Logo" className="w-8 h-8 rounded-full object-contain" />
            <h1 className="text-2xl font-bold">TradesdocAi</h1>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center space-x-2 text-slate hover:text-navy transition-colors"
            data-testid="back-button"
          >
            <ArrowLeft className="w-5 h-5" />
            <span>Back to Dashboard</span>
          </button>
        </div>

        <div className="bg-white rounded-lg shadow-md p-8">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-navy" data-testid="page-title">Company Profile Settings</h2>
            <p className="text-slate mt-1">Configure your company details for export documentation</p>
          </div>

          {message.text && (
            <div
              className={`mb-6 px-4 py-3 rounded-lg ${
                message.type === 'success'
                  ? 'bg-green-50 border border-green-200 text-green-700'
                  : 'bg-red-50 border border-red-200 text-red-700'
              }`}
              data-testid="message-banner"
            >
              {message.text}
            </div>
          )}

          <form onSubmit={handleSubmit} data-testid="settings-form">
            {/* Company Information */}
            <div className="mb-8">
              <h3 className="text-lg font-semibold text-navy mb-4 flex items-center">
                <Building className="w-5 h-5 mr-2" />
                Company Information
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-gray-700 text-sm font-medium mb-2">
                    Company Name *
                  </label>
                  <input
                    type="text"
                    name="company_name"
                    value={formData.company_name}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                    required
                    data-testid="company-name-input"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-gray-700 text-sm font-medium mb-2">
                    Address Line 1 *
                  </label>
                  <input
                    type="text"
                    name="address_line1"
                    value={formData.address_line1}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                    required
                    data-testid="address-line1-input"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-gray-700 text-sm font-medium mb-2">
                    Address Line 2
                  </label>
                  <input
                    type="text"
                    name="address_line2"
                    value={formData.address_line2}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                    data-testid="address-line2-input"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 text-sm font-medium mb-2">
                    IEC Code *
                  </label>
                  <input
                    type="text"
                    name="iec_code"
                    value={formData.iec_code}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                    required
                    data-testid="iec-code-input"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 text-sm font-medium mb-2">
                    GST Number *
                  </label>
                  <input
                    type="text"
                    name="gst_number"
                    value={formData.gst_number}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                    required
                    data-testid="gst-number-input"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-gray-700 text-sm font-medium mb-2">
                    AD Code
                  </label>
                  <input
                    type="text"
                    name="ad_code"
                    value={formData.ad_code}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                    data-testid="ad-code-input"
                  />
                </div>
              </div>
            </div>

            {/* Bank Details */}
            <div className="mb-8">
              <h3 className="text-lg font-semibold text-navy mb-4 flex items-center">
                <CreditCard className="w-5 h-5 mr-2" />
                Bank Details
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="block text-gray-700 text-sm font-medium mb-2">
                    Bank Name *
                  </label>
                  <input
                    type="text"
                    name="bank_name"
                    value={formData.bank_name}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                    required
                    data-testid="bank-name-input"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 text-sm font-medium mb-2">
                    Account Number *
                  </label>
                  <input
                    type="text"
                    name="account_number"
                    value={formData.account_number}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                    required
                    data-testid="account-number-input"
                  />
                </div>
                <div>
                  <label className="block text-gray-700 text-sm font-medium mb-2">
                    IFSC Code *
                  </label>
                  <input
                    type="text"
                    name="ifsc_code"
                    value={formData.ifsc_code}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                    required
                    data-testid="ifsc-code-input"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-gray-700 text-sm font-medium mb-2">
                    SWIFT Code
                  </label>
                  <input
                    type="text"
                    name="swift_code"
                    value={formData.swift_code}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                    data-testid="swift-code-input"
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="block text-gray-700 text-sm font-medium mb-2">
                    Tally Sales Ledger Name
                  </label>
                  <input
                    type="text"
                    name="tally_sales_ledger_name"
                    value={formData.tally_sales_ledger_name}
                    onChange={handleChange}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                    placeholder="Export Sales"
                    data-testid="tally-ledger-input"
                  />
                  <p className="text-sm text-slate mt-1">Used for Tally XML export (default: "Export Sales")</p>
                </div>
              </div>
            </div>

            {/* Signature Upload */}
            <div className="mb-8">
              <h3 className="text-lg font-semibold text-navy mb-4 flex items-center">
                <Upload className="w-5 h-5 mr-2" />
                Authorized Signature/Stamp
              </h3>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center">
                <input
                  type="file"
                  id="signature"
                  accept="image/*"
                  onChange={handleSignatureChange}
                  className="hidden"
                  data-testid="signature-file-input"
                />
                <label
                  htmlFor="signature"
                  className="cursor-pointer flex flex-col items-center"
                >
                  {signaturePreview ? (
                    <div>
                      <img
                        src={signaturePreview}
                        alt="Signature preview"
                        className="max-h-32 mb-4"
                        data-testid="signature-preview"
                      />
                      <p className="text-sm text-slate">Click to change signature</p>
                    </div>
                  ) : (
                    <>
                      <Upload className="w-12 h-12 text-gray-400 mb-2" />
                      <p className="text-gray-600 mb-1">Click to upload signature</p>
                      <p className="text-sm text-slate">PNG, JPG up to 5MB</p>
                    </>
                  )}
                </label>
              </div>
            </div>

            {/* Submit Button */}
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={loading}
                className="flex items-center space-x-2 px-8 py-3 bg-navy text-white rounded-lg hover:bg-slate-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                data-testid="save-profile-button"
              >
                <Save className="w-5 h-5" />
                <span>{loading ? 'Saving...' : 'Save Profile'}</span>
              </button>
            </div>
          </form>
        </div>
      </main>
    </div>
  );
}

export default Settings;
