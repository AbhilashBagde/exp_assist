import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Package, Upload, FileText, CheckCircle, ArrowLeft, Loader, AlertCircle, Edit, Sparkles } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function NewShipment() {
  const [step, setStep] = useState(1);
  const [file, setFile] = useState(null);
  const [filePreview, setFilePreview] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [formData, setFormData] = useState({
    buyer_name: '',
    buyer_address: '',
    po_number: '',
    po_date: '',
    currency: 'USD',
    port_of_loading: '',
    port_of_discharge: '',
    incoterms: 'FOB',
    total_packages: 1,
    package_type: 'BOXES',
    include_inr_column: false,
    items: []
  });
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  const [generatedShipmentId, setGeneratedShipmentId] = useState(null);
  const [suggestingHsCode, setSuggestingHsCode] = useState(null);
  const [exchangeRate, setExchangeRate] = useState(83.50); // Default USD to INR
  const [exchangeRates, setExchangeRates] = useState({}); // All rates
  const [ratesLoading, setRatesLoading] = useState(false);
  const [isLiveRate, setIsLiveRate] = useState(false);
  const [ratesLastUpdated, setRatesLastUpdated] = useState(null);
  const navigate = useNavigate();
  const token = localStorage.getItem('token');

  // Fallback exchange rates to INR
  const FALLBACK_RATES = {
    USD: 83.50,
    EUR: 90.50,
    GBP: 105.50,
    AED: 22.75,
    SGD: 62.00,
    INR: 1.00
  };

  // Fetch live exchange rates from API
  const fetchExchangeRates = async () => {
    setRatesLoading(true);
    try {
      const response = await axios.get(`${API_URL}/api/exchange-rates`);
      if (response.data.rates) {
        setExchangeRates(response.data.rates);
        setIsLiveRate(response.data.is_live);
        setRatesLastUpdated(response.data.last_updated);
        // Update current exchange rate based on selected currency
        const rate = response.data.rates[formData.currency] || FALLBACK_RATES[formData.currency] || 83.50;
        setExchangeRate(rate);
      }
    } catch (err) {
      console.error('Failed to fetch exchange rates:', err);
      setExchangeRates(FALLBACK_RATES);
      setExchangeRate(FALLBACK_RATES[formData.currency] || 83.50);
      setIsLiveRate(false);
    } finally {
      setRatesLoading(false);
    }
  };

  // Fetch rates on component mount
  React.useEffect(() => {
    if (token) {
      fetchExchangeRates();
    }
  }, [token]);

  // Update exchange rate when currency changes
  const updateExchangeRate = (currency) => {
    const rate = exchangeRates[currency] || FALLBACK_RATES[currency] || 83.50;
    setExchangeRate(rate);
  };

  // Step A: File Upload
  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      const fileType = selectedFile.type;
      const validTypes = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png'];
      
      if (!validTypes.includes(fileType)) {
        setError('Please upload a PDF, JPG, or PNG file');
        return;
      }

      setFile(selectedFile);
      setError('');
      
      // Create preview for images
      if (fileType.startsWith('image/')) {
        const reader = new FileReader();
        reader.onloadend = () => {
          setFilePreview(reader.result);
        };
        reader.readAsDataURL(selectedFile);
      } else {
        setFilePreview(null);
      }
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      const fakeEvent = { target: { files: [droppedFile] } };
      handleFileChange(fakeEvent);
    }
  };

  // Step B: AI Vision Processing
  const handleExtract = async () => {
    if (!file) {
      setError('Please upload a file first');
      return;
    }

    setExtracting(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post(`${API_URL}/api/shipments/extract`, formData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });

      // Map currency_code from AI to currency field
      const extractedData = response.data;
      if (extractedData.currency_code) {
        extractedData.currency = extractedData.currency_code;
      }

      setFormData(extractedData);
      setStep(3); // Move to Step C (Review Form)
    } catch (err) {
      // Handle error - ensure it's a string, not an object
      let errorMessage = 'Failed to extract data from document';
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (typeof detail === 'string') {
          errorMessage = detail;
        } else if (Array.isArray(detail)) {
          errorMessage = detail.map(e => e.msg || e.message || JSON.stringify(e)).join(', ');
        } else if (typeof detail === 'object') {
          errorMessage = detail.msg || detail.message || JSON.stringify(detail);
        }
      }
      setError(errorMessage);
      if (err.response?.status === 401) {
        localStorage.clear();
        navigate('/login');
      }
    } finally {
      setExtracting(false);
    }
  };

  // Step C: Form Handling
  const handleFormChange = (e) => {
    const { name, value, type, checked } = e.target;
    const newValue = type === 'checkbox' ? checked : value;
    
    setFormData({
      ...formData,
      [name]: newValue
    });
    
    // Update exchange rate when currency changes
    if (name === 'currency') {
      updateExchangeRate(value);
    }
  };

  const handleItemChange = (index, field, value) => {
    const updatedItems = [...formData.items];
    updatedItems[index] = {
      ...updatedItems[index],
      [field]: (field === 'quantity' || field === 'unit_price' || field === 'net_weight' || field === 'gross_weight') 
        ? parseFloat(value) || 0 
        : value
    };
    
    // Recalculate total_amount
    if (field === 'quantity' || field === 'unit_price') {
      updatedItems[index].total_amount = updatedItems[index].quantity * updatedItems[index].unit_price;
    }
    
    setFormData({ ...formData, items: updatedItems });
  };

  const addItem = () => {
    setFormData({
      ...formData,
      items: [...formData.items, { 
        description: '', 
        quantity: 0, 
        unit_price: 0, 
        hs_code: '', 
        total_amount: 0,
        net_weight: 0,
        gross_weight: 0
      }]
    });
  };

  const removeItem = (index) => {
    const updatedItems = formData.items.filter((_, i) => i !== index);
    setFormData({ ...formData, items: updatedItems });
  };

  // AI HS Code Suggestion
  const suggestHsCode = async (index) => {
    const item = formData.items[index];
    if (!item.description || item.description.trim().length < 3) {
      setError('Please enter an item description first (at least 3 characters)');
      return;
    }

    setSuggestingHsCode(index);
    setError('');

    try {
      const suggestionFormData = new FormData();
      suggestionFormData.append('description', item.description);

      const response = await axios.post(`${API_URL}/api/suggest-hs-code`, suggestionFormData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });

      if (response.data.success) {
        // Update the HS code for this item
        const updatedItems = [...formData.items];
        updatedItems[index] = {
          ...updatedItems[index],
          hs_code: response.data.hs_code
        };
        setFormData({ ...formData, items: updatedItems });
        
        // Show confidence info
        if (response.data.confidence === 'low') {
          setError(`HS Code suggested (Low confidence): ${response.data.notes || 'Please verify carefully'}`);
        }
      }
    } catch (err) {
      let errorMessage = 'Failed to suggest HS Code';
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (typeof detail === 'string') {
          errorMessage = detail;
        } else if (typeof detail === 'object') {
          errorMessage = detail.msg || JSON.stringify(detail);
        }
      }
      setError(errorMessage);
    } finally {
      setSuggestingHsCode(null);
    }
  };

  // Step D: Save & Generate PDF
  const handleSaveAndGenerate = async () => {
    setGenerating(true);
    setError('');

    try {
      // Create shipment
      const shipmentFormData = new FormData();
      shipmentFormData.append('buyer_name', formData.buyer_name);
      shipmentFormData.append('buyer_address', formData.buyer_address);
      shipmentFormData.append('po_number', formData.po_number);
      shipmentFormData.append('po_date', formData.po_date);
      shipmentFormData.append('currency', formData.currency);
      shipmentFormData.append('port_of_loading', formData.port_of_loading);
      shipmentFormData.append('port_of_discharge', formData.port_of_discharge);
      shipmentFormData.append('incoterms', formData.incoterms);
      shipmentFormData.append('total_packages', formData.total_packages);
      shipmentFormData.append('package_type', formData.package_type);
      shipmentFormData.append('include_inr_column', formData.include_inr_column);
      shipmentFormData.append('items', JSON.stringify(formData.items));

      const createResponse = await axios.post(`${API_URL}/api/shipments`, shipmentFormData, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });

      const shipmentId = createResponse.data.shipment_id;

      // Generate PDF
      const pdfResponse = await axios.post(
        `${API_URL}/api/shipments/${shipmentId}/generate-pdf`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` },
          responseType: 'blob'
        }
      );

      // Download PDF
      const url = window.URL.createObjectURL(new Blob([pdfResponse.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `invoice_${shipmentId}.pdf`);
      link.style.display = 'none';
      document.body.appendChild(link);
      link.click();
      
      // Cleanup after small delay to ensure download starts
      setTimeout(() => {
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      }, 100);

      setGeneratedShipmentId(shipmentId);
      setStep(4); // Success step
    } catch (err) {
      // Handle error - ensure it's a string, not an object
      let errorMessage = 'Failed to generate invoice';
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (typeof detail === 'string') {
          errorMessage = detail;
        } else if (Array.isArray(detail)) {
          // FastAPI validation errors come as array
          errorMessage = detail.map(e => e.msg || e.message || JSON.stringify(e)).join(', ');
        } else if (typeof detail === 'object') {
          errorMessage = detail.msg || detail.message || JSON.stringify(detail);
        }
      }
      setError(errorMessage);
      if (err.response?.status === 401) {
        localStorage.clear();
        navigate('/login');
      }
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-navy text-white shadow-lg" data-testid="new-shipment-header">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center space-x-3">
            <Package className="w-8 h-8" />
            <h1 className="text-2xl font-bold">ExportAssist</h1>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center space-x-2 text-slate hover:text-navy transition-colors"
            data-testid="back-to-dashboard"
          >
            <ArrowLeft className="w-5 h-5" />
            <span>Back to Dashboard</span>
          </button>
        </div>

        {/* Progress Steps */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            {[
              { num: 1, label: 'Upload PO' },
              { num: 2, label: 'AI Processing' },
              { num: 3, label: 'Review & Edit' },
              { num: 4, label: 'Generate PDF' }
            ].map((s, idx) => (
              <React.Fragment key={s.num}>
                <div className="flex flex-col items-center">
                  <div
                    className={`w-12 h-12 rounded-full flex items-center justify-center font-bold ${
                      step >= s.num
                        ? 'bg-navy text-white'
                        : 'bg-gray-300 text-gray-600'
                    }`}
                    data-testid={`step-indicator-${s.num}`}
                  >
                    {step > s.num ? <CheckCircle className="w-6 h-6" /> : s.num}
                  </div>
                  <span className="text-sm mt-2 text-gray-600">{s.label}</span>
                </div>
                {idx < 3 && (
                  <div
                    className={`flex-1 h-1 mx-2 ${
                      step > s.num ? 'bg-navy' : 'bg-gray-300'
                    }`}
                  />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center" data-testid="error-message">
            <AlertCircle className="w-5 h-5 mr-2" />
            {error}
          </div>
        )}

        {/* Step 1: Upload */}
        {step === 1 && (
          <div className="bg-white rounded-lg shadow-md p-8" data-testid="upload-step">
            <h2 className="text-2xl font-bold text-navy mb-4">Upload Purchase Order</h2>
            <p className="text-slate mb-6">Upload a PDF or photo of your Purchase Order document</p>

            <div
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-navy transition-colors cursor-pointer"
              data-testid="file-upload-zone"
            >
              <input
                type="file"
                id="po-file"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileChange}
                className="hidden"
                data-testid="file-input"
              />
              <label htmlFor="po-file" className="cursor-pointer flex flex-col items-center">
                <Upload className="w-16 h-16 text-gray-400 mb-4" />
                <p className="text-lg text-gray-700 mb-2">
                  {file ? file.name : 'Drag and drop your file here'}
                </p>
                <p className="text-sm text-slate">or click to browse</p>
                <p className="text-xs text-gray-500 mt-2">Supports: PDF, JPG, PNG</p>
              </label>

              {filePreview && (
                <div className="mt-6">
                  <img src={filePreview} alt="Preview" className="max-h-64 mx-auto" data-testid="file-preview" />
                </div>
              )}
            </div>

            {file && (
              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => setStep(2)}
                  className="px-8 py-3 bg-navy text-white rounded-lg hover:bg-slate-800 transition-colors font-medium"
                  data-testid="proceed-to-extraction"
                >
                  Proceed to Extraction
                </button>
              </div>
            )}
          </div>
        )}

        {/* Step 2: AI Processing */}
        {step === 2 && (
          <div className="bg-white rounded-lg shadow-md p-8" data-testid="processing-step">
            <h2 className="text-2xl font-bold text-navy mb-4">AI Processing</h2>
            <p className="text-slate mb-6">Our AI will extract information from your document</p>

            <div className="text-center py-12">
              {!extracting ? (
                <>
                  <FileText className="w-20 h-20 text-navy mx-auto mb-6" />
                  <p className="text-lg text-gray-700 mb-6">Ready to extract data from: <strong>{file?.name}</strong></p>
                  <div className="flex justify-center space-x-4">
                    <button
                      onClick={handleExtract}
                      className="px-8 py-3 bg-navy text-white rounded-lg hover:bg-slate-800 transition-colors font-medium"
                      data-testid="start-extraction-button"
                    >
                      Start AI Extraction
                    </button>
                    <button
                      onClick={() => {
                        setFormData({
                          buyer_name: '',
                          buyer_address: '',
                          po_number: '',
                          po_date: '',
                          currency: 'USD',
                          port_of_loading: '',
                          port_of_discharge: '',
                          incoterms: 'FOB',
                          total_packages: 1,
                          package_type: 'BOXES',
                          items: [{ description: '', quantity: 0, unit_price: 0, hs_code: '', total_amount: 0, net_weight: 0, gross_weight: 0 }]
                        });
                        setStep(3);
                      }}
                      className="px-8 py-3 border-2 border-navy text-navy rounded-lg hover:bg-gray-50 transition-colors font-medium"
                      data-testid="skip-to-manual-entry"
                    >
                      Skip & Enter Manually
                    </button>
                  </div>
                  <p className="text-sm text-slate mt-4">
                    AI extraction requires Gemini API key. You can skip and enter details manually.
                  </p>
                </>
              ) : (
                <>
                  <Loader className="w-20 h-20 text-navy mx-auto mb-6 animate-spin" />
                  <p className="text-lg text-gray-700">Extracting data using AI Vision...</p>
                  <p className="text-sm text-slate mt-2">This may take a few moments</p>
                </>
              )}
            </div>
          </div>
        )}

        {/* Step 3: Review Form */}
        {step === 3 && (
          <div className="bg-white rounded-lg shadow-md p-8" data-testid="review-step">
            <h2 className="text-2xl font-bold text-navy mb-4 flex items-center">
              <Edit className="w-6 h-6 mr-2" />
              Review & Edit Extracted Data
            </h2>
            <p className="text-slate mb-6">Please verify the extracted information and make any necessary corrections</p>

            <form onSubmit={(e) => { e.preventDefault(); handleSaveAndGenerate(); }} data-testid="review-form">
              {/* Buyer Details */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-navy mb-3">Buyer Information</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-gray-700 text-sm font-medium mb-2">
                      Buyer Name *
                    </label>
                    <input
                      type="text"
                      name="buyer_name"
                      value={formData.buyer_name}
                      onChange={handleFormChange}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                      required
                      data-testid="buyer-name-input"
                    />
                  </div>
                  <div>
                    <label className="block text-gray-700 text-sm font-medium mb-2">
                      PO Number *
                    </label>
                    <input
                      type="text"
                      name="po_number"
                      value={formData.po_number}
                      onChange={handleFormChange}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                      required
                      data-testid="po-number-input"
                    />
                  </div>
                  <div>
                    <label className="block text-gray-700 text-sm font-medium mb-2">
                      PO Date *
                    </label>
                    <input
                      type="date"
                      name="po_date"
                      value={formData.po_date}
                      onChange={handleFormChange}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                      required
                      data-testid="po-date-input"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-gray-700 text-sm font-medium mb-2">
                      Buyer Address
                    </label>
                    <textarea
                      name="buyer_address"
                      value={formData.buyer_address}
                      onChange={handleFormChange}
                      rows="2"
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                      data-testid="buyer-address-input"
                    />
                  </div>
                  <div>
                    <label className="block text-gray-700 text-sm font-medium mb-2">
                      Currency *
                    </label>
                    <select
                      name="currency"
                      value={formData.currency}
                      onChange={handleFormChange}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                      required
                      data-testid="currency-select"
                    >
                      <option value="USD">USD - US Dollar</option>
                      <option value="EUR">EUR - Euro</option>
                      <option value="GBP">GBP - British Pound</option>
                      <option value="INR">INR - Indian Rupee</option>
                      <option value="AED">AED - UAE Dirham</option>
                      <option value="SGD">SGD - Singapore Dollar</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Logistics & Shipping Details */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-navy mb-3">Logistics & Shipping Details</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-gray-700 text-sm font-medium mb-2">
                      Port of Loading
                    </label>
                    <input
                      type="text"
                      name="port_of_loading"
                      value={formData.port_of_loading}
                      onChange={handleFormChange}
                      placeholder="e.g., INNSA - Nhava Sheva"
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                      data-testid="port-of-loading-input"
                    />
                  </div>
                  <div>
                    <label className="block text-gray-700 text-sm font-medium mb-2">
                      Port of Discharge
                    </label>
                    <input
                      type="text"
                      name="port_of_discharge"
                      value={formData.port_of_discharge}
                      onChange={handleFormChange}
                      placeholder="e.g., USLAX - Los Angeles"
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                      data-testid="port-of-discharge-input"
                    />
                  </div>
                  <div>
                    <label className="block text-gray-700 text-sm font-medium mb-2">
                      Incoterms
                    </label>
                    <select
                      name="incoterms"
                      value={formData.incoterms}
                      onChange={handleFormChange}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                      data-testid="incoterms-select"
                    >
                      <option value="EXW">EXW - Ex Works</option>
                      <option value="FCA">FCA - Free Carrier</option>
                      <option value="FOB">FOB - Free on Board</option>
                      <option value="CFR">CFR - Cost and Freight</option>
                      <option value="CIF">CIF - Cost, Insurance & Freight</option>
                      <option value="DDP">DDP - Delivered Duty Paid</option>
                      <option value="DAP">DAP - Delivered at Place</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-gray-700 text-sm font-medium mb-2">
                      Total Packages
                    </label>
                    <input
                      type="number"
                      name="total_packages"
                      value={formData.total_packages}
                      onChange={handleFormChange}
                      min="1"
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                      data-testid="total-packages-input"
                    />
                  </div>
                  <div>
                    <label className="block text-gray-700 text-sm font-medium mb-2">
                      Package Type
                    </label>
                    <select
                      name="package_type"
                      value={formData.package_type}
                      onChange={handleFormChange}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-navy"
                      data-testid="package-type-select"
                    >
                      <option value="BOXES">Boxes</option>
                      <option value="CARTONS">Cartons</option>
                      <option value="PALLETS">Pallets</option>
                      <option value="BAGS">Bags</option>
                      <option value="DRUMS">Drums</option>
                      <option value="CRATES">Crates</option>
                      <option value="BUNDLES">Bundles</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Items Table */}
              <div className="mb-6">
                <div className="flex justify-between items-center mb-3">
                  <h3 className="text-lg font-semibold text-navy">Items</h3>
                  <button
                    type="button"
                    onClick={addItem}
                    className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium flex items-center space-x-2"
                    data-testid="add-item-button"
                  >
                    <span className="text-xl">+</span>
                    <span>Add Item</span>
                  </button>
                </div>

                <div className="overflow-x-auto">
                  <table className="min-w-full border border-gray-200" data-testid="items-table">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-2 py-3 text-left text-xs font-medium text-gray-700 uppercase">Description</th>
                        <th className="px-2 py-3 text-left text-xs font-medium text-gray-700 uppercase bg-yellow-50">HS Code ⚠️</th>
                        <th className="px-2 py-3 text-left text-xs font-medium text-gray-700 uppercase">Qty</th>
                        <th className="px-2 py-3 text-left text-xs font-medium text-gray-700 uppercase">Rate ({formData.currency})</th>
                        <th className="px-2 py-3 text-left text-xs font-medium text-gray-700 uppercase">Net Wt (kg)</th>
                        <th className="px-2 py-3 text-left text-xs font-medium text-gray-700 uppercase">Gross Wt (kg)</th>
                        <th className="px-2 py-3 text-left text-xs font-medium text-gray-700 uppercase">Amount ({formData.currency})</th>
                        {formData.currency !== 'INR' && (
                          <th className="px-2 py-3 text-left text-xs font-medium text-green-700 uppercase bg-green-50">Amount (INR)</th>
                        )}
                        <th className="px-2 py-3 text-left text-xs font-medium text-gray-700 uppercase">Action</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {formData.items.map((item, index) => {
                        // Feature 2: Math Validation
                        const calculatedAmount = item.quantity * item.unit_price;
                        const hasMathMismatch = Math.abs(calculatedAmount - item.total_amount) > 0.01;
                        
                        return (
                        <tr key={index} data-testid={`item-row-${index}`}>
                          <td className="px-2 py-3">
                            <input
                              type="text"
                              value={item.description}
                              onChange={(e) => handleItemChange(index, 'description', e.target.value)}
                              className="w-full px-2 py-1 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-navy text-sm"
                              required
                              data-testid={`item-description-${index}`}
                            />
                          </td>
                          <td className="px-2 py-3 bg-yellow-50">
                            <div className="flex items-center space-x-1">
                              <input
                                type="text"
                                value={item.hs_code}
                                onChange={(e) => handleItemChange(index, 'hs_code', e.target.value)}
                                className="w-full px-2 py-1 border-2 border-yellow-400 rounded focus:outline-none focus:ring-2 focus:ring-yellow-500 text-sm"
                                placeholder="Enter or AI suggest"
                                required
                                data-testid={`item-hs-code-${index}`}
                              />
                              <button
                                type="button"
                                onClick={() => suggestHsCode(index)}
                                disabled={suggestingHsCode === index}
                                className="px-2 py-1 bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors text-xs flex items-center disabled:opacity-50 disabled:cursor-wait"
                                title="AI Suggest HS Code"
                                data-testid={`suggest-hs-code-${index}`}
                              >
                                {suggestingHsCode === index ? (
                                  <Loader className="w-3 h-3 animate-spin" />
                                ) : (
                                  <Sparkles className="w-3 h-3" />
                                )}
                              </button>
                            </div>
                          </td>
                          <td className="px-2 py-3">
                            <input
                              type="number"
                              value={item.quantity}
                              onChange={(e) => handleItemChange(index, 'quantity', e.target.value)}
                              className="w-full px-2 py-1 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-navy text-sm"
                              required
                              min="0"
                              step="0.01"
                              data-testid={`item-quantity-${index}`}
                            />
                          </td>
                          <td className="px-2 py-3">
                            <input
                              type="number"
                              value={item.unit_price}
                              onChange={(e) => handleItemChange(index, 'unit_price', e.target.value)}
                              className="w-full px-2 py-1 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-navy text-sm"
                              required
                              min="0"
                              step="0.01"
                              data-testid={`item-unit-price-${index}`}
                            />
                          </td>
                          <td className="px-2 py-3">
                            <input
                              type="number"
                              value={item.net_weight || 0}
                              onChange={(e) => handleItemChange(index, 'net_weight', e.target.value)}
                              className="w-full px-2 py-1 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-navy text-sm"
                              min="0"
                              step="0.01"
                              data-testid={`item-net-weight-${index}`}
                            />
                          </td>
                          <td className="px-2 py-3">
                            <input
                              type="number"
                              value={item.gross_weight || 0}
                              onChange={(e) => handleItemChange(index, 'gross_weight', e.target.value)}
                              className="w-full px-2 py-1 border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-navy text-sm"
                              min="0"
                              step="0.01"
                              data-testid={`item-gross-weight-${index}`}
                            />
                          </td>
                          <td className={`px-2 py-3 font-medium text-sm ${hasMathMismatch ? 'bg-red-100 text-red-700' : ''}`} data-testid={`item-total-${index}`}>
                            {item.total_amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            {hasMathMismatch && (
                              <div className="text-xs text-red-600 mt-1">Math Mismatch!</div>
                            )}
                          </td>
                          {formData.currency !== 'INR' && (
                            <td className="px-2 py-3 font-medium text-sm bg-green-50 text-green-700" data-testid={`item-inr-${index}`}>
                              ₹{(item.total_amount * exchangeRate).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </td>
                          )}
                          <td className="px-2 py-3">
                            <button
                              type="button"
                              onClick={() => removeItem(index)}
                              className="text-red-600 hover:text-red-800 text-sm"
                              data-testid={`remove-item-${index}`}
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      )})}
                    </tbody>
                  </table>
                </div>

                {/* INR Total and Include Option */}
                {formData.currency !== 'INR' && formData.items.length > 0 && (
                  <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="text-sm text-green-800">
                          <strong>Total in INR:</strong> ₹{(formData.items.reduce((sum, item) => sum + item.total_amount, 0) * exchangeRate).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                        </p>
                        <div className="flex items-center space-x-2 mt-1">
                          <p className="text-xs text-green-600">
                            Exchange Rate: 1 {formData.currency} = ₹{exchangeRate.toFixed(2)}
                          </p>
                          {isLiveRate ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-200 text-green-800">
                              🟢 Live Rate
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-200 text-yellow-800">
                              ⚠️ Fallback Rate
                            </span>
                          )}
                          <button
                            type="button"
                            onClick={fetchExchangeRates}
                            disabled={ratesLoading}
                            className="text-xs text-blue-600 hover:text-blue-800 underline disabled:opacity-50"
                          >
                            {ratesLoading ? 'Refreshing...' : 'Refresh'}
                          </button>
                        </div>
                        {ratesLastUpdated && (
                          <p className="text-xs text-gray-500 mt-1">
                            Last updated: {new Date(ratesLastUpdated).toLocaleString()}
                          </p>
                        )}
                      </div>
                      <label className="flex items-center space-x-2 cursor-pointer">
                        <input
                          type="checkbox"
                          name="include_inr_column"
                          checked={formData.include_inr_column}
                          onChange={handleFormChange}
                          className="w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500"
                          data-testid="include-inr-checkbox"
                        />
                        <span className="text-sm font-medium text-green-800">Include INR column in PDF</span>
                      </label>
                    </div>
                  </div>
                )}

                <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <p className="text-sm text-yellow-800">
                    <strong>⚠️ Important:</strong> The HS Codes have been predicted by AI. Please verify them carefully before generating the invoice, as incorrect codes can cause compliance issues.
                  </p>
                </div>
              </div>

              {/* Submit */}
              <div className="flex justify-end space-x-4">
                <button
                  type="button"
                  onClick={() => setStep(2)}
                  className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                  data-testid="back-to-processing"
                >
                  Back
                </button>
                <button
                  type="submit"
                  disabled={generating}
                  className="px-8 py-3 bg-navy text-white rounded-lg hover:bg-slate-800 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                  data-testid="save-and-generate-button"
                >
                  {generating ? 'Generating...' : 'Save & Generate Invoice'}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Step 4: Success */}
        {step === 4 && (
          <div className="bg-white rounded-lg shadow-md p-8 text-center" data-testid="success-step">
            <CheckCircle className="w-20 h-20 text-green-500 mx-auto mb-6" />
            <h2 className="text-2xl font-bold text-navy mb-4">Invoice Generated Successfully!</h2>
            <p className="text-slate mb-4">Your Commercial Invoice PDF has been generated.</p>
            
            {/* Manual Download Button */}
            {generatedShipmentId && (
              <div className="mb-8">
                <button
                  onClick={async () => {
                    try {
                      const response = await axios.post(
                        `${API_URL}/api/shipments/${generatedShipmentId}/generate-pdf`,
                        {},
                        {
                          headers: { Authorization: `Bearer ${token}` },
                          responseType: 'blob'
                        }
                      );
                      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
                      const link = document.createElement('a');
                      link.href = url;
                      link.setAttribute('download', `invoice_${generatedShipmentId}.pdf`);
                      link.style.display = 'none';
                      document.body.appendChild(link);
                      link.click();
                      setTimeout(() => {
                        document.body.removeChild(link);
                        window.URL.revokeObjectURL(url);
                      }, 100);
                    } catch (err) {
                      console.error('Download failed:', err);
                      alert('Download failed. Please try again.');
                    }
                  }}
                  className="px-8 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium inline-flex items-center space-x-2"
                  data-testid="download-invoice-button"
                >
                  <FileText className="w-5 h-5" />
                  <span>Download Invoice PDF</span>
                </button>
                <p className="text-sm text-gray-500 mt-2">Click here if the download didn't start automatically</p>
              </div>
            )}
            
            <div className="flex justify-center space-x-4">
              <button
                onClick={() => navigate('/dashboard')}
                className="px-8 py-3 bg-navy text-white rounded-lg hover:bg-slate-800 transition-colors font-medium"
                data-testid="go-to-dashboard"
              >
                Go to Dashboard
              </button>
              <button
                onClick={() => window.location.reload()}
                className="px-8 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                data-testid="create-another"
              >
                Create Another
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default NewShipment;
