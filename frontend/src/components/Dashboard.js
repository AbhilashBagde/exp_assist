import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Settings as SettingsIcon, LogOut, FileText, Calendar, User, Lock, Crown, Search, Trash2, RotateCcw, Filter, XCircle, AlertTriangle, CheckCircle, ClipboardCheck } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function Dashboard() {
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(null); // shipment_id to delete
  const [showRevertModal, setShowRevertModal] = useState(null); // shipment_id to revert
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [validating, setValidating] = useState(null);
  const [validationResults, setValidationResults] = useState({});
  const navigate = useNavigate();
  const token = localStorage.getItem('token');
  const isProMember = localStorage.getItem('is_pro_member') === 'true';

  const checkProfile = useCallback(async () => {
    try {
      const response = await axios.get(`${API_URL}/api/profile`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!response.data.exists) {
        navigate('/settings');
      }
    } catch (err) {
      console.error('Error checking profile:', err);
      if (err.response?.status === 401) {
        localStorage.clear();
        navigate('/login');
      }
    }
  }, [token, navigate]);

  const fetchShipments = useCallback(async () => {
    try {
      let url = `${API_URL}/api/shipments`;
      // Use search endpoint if filters are active
      if (searchQuery || statusFilter) {
        const params = new URLSearchParams();
        if (searchQuery) params.append('q', searchQuery);
        if (statusFilter) params.append('status_filter', statusFilter);
        url = `${API_URL}/api/shipments/search?${params.toString()}`;
      }
      const response = await axios.get(url, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setShipments(response.data);
    } catch (err) {
      console.error('Error fetching shipments:', err);
      if (err.response?.status === 401) {
        localStorage.clear();
        navigate('/login');
      }
    } finally {
      setLoading(false);
    }
  }, [token, navigate, searchQuery, statusFilter]);

  useEffect(() => {
    checkProfile();
    fetchShipments();
  }, [checkProfile, fetchShipments]);

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
  };

  const getTotalValue = (items) => {
    return items.reduce((sum, item) => sum + (item.total_amount || 0), 0);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-navy text-white shadow-lg" data-testid="dashboard-header">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center space-x-3">
              <img src="/TDA.png" alt="TradesdocAi Logo" className="w-8 h-8 rounded-full object-contain" />
              <h1 className="text-2xl font-bold">TradesdocAi</h1>
            </div>
            <div className="flex items-center space-x-4">
              <button
                onClick={() => navigate('/settings')}
                className="flex items-center space-x-2 px-4 py-2 bg-slate-700 rounded-lg hover:bg-slate-600 transition-colors"
                data-testid="settings-button"
              >
                <SettingsIcon className="w-5 h-5" />
                <span>Settings</span>
              </button>
              <button
                onClick={handleLogout}
                className="flex items-center space-x-2 px-4 py-2 bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
                data-testid="logout-button"
              >
                <LogOut className="w-5 h-5" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h2 className="text-3xl font-bold text-navy" data-testid="page-title">Dashboard</h2>
            <p className="text-slate mt-1">Manage your export shipments and invoices</p>
          </div>
          <div className="flex space-x-3">
            {/* GSTR-1 Button - Pro Feature */}
            <button
              onClick={() => {
                if (!isProMember) {
                  setShowUpgradeModal(true);
                  return;
                }
                (async () => {
                  try {
                    const response = await axios.get(`${API_URL}/api/reports/gstr1-export`, {
                      headers: { Authorization: `Bearer ${token}` },
                      responseType: 'blob'
                    });
                    const url = window.URL.createObjectURL(new Blob([response.data]));
                    const link = document.createElement('a');
                    link.href = url;
                    link.setAttribute('download', 'gstr1_export_data.csv');
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                  } catch (err) {
                    console.error('Error downloading GSTR-1:', err);
                  }
                })();
              }}
              className={`flex items-center space-x-2 px-4 py-3 rounded-lg transition-colors shadow-md ${
                isProMember 
                  ? 'bg-green-600 text-white hover:bg-green-700' 
                  : 'bg-gray-400 text-white cursor-not-allowed'
              }`}
              data-testid="gstr1-export-button"
            >
              {!isProMember && <Lock className="w-4 h-4" />}
              <FileText className="w-5 h-5" />
              <span className="font-medium">Download GSTR-1 Data</span>
            </button>
            <button
              onClick={() => navigate('/new-shipment')}
              className="flex items-center space-x-2 px-6 py-3 bg-navy text-white rounded-lg hover:bg-slate-800 transition-colors shadow-md"
              data-testid="new-shipment-button"
            >
              <Plus className="w-5 h-5" />
              <span className="font-medium">New Shipment</span>
            </button>
            {!isProMember && (
              <button
                onClick={() => navigate('/upgrade')}
                className="flex items-center space-x-2 px-4 py-3 bg-yellow-500 text-navy rounded-lg hover:bg-yellow-400 transition-colors shadow-md font-bold"
                data-testid="upgrade-cta-button"
              >
                <Crown className="w-5 h-5" />
                <span>Upgrade to Pro</span>
              </button>
            )}
          </div>
        </div>

        {/* Shipments Table */}
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
            <h3 className="text-lg font-semibold text-navy">Recent Shipments</h3>
          </div>

          {loading ? (
            <div className="p-8 text-center" data-testid="loading-indicator">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-navy"></div>
              <p className="mt-2 text-slate">Loading shipments...</p>
            </div>
          ) : shipments.length === 0 ? (
            <div className="p-12 text-center" data-testid="empty-state">
              <FileText className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h4 className="text-xl font-medium text-gray-600 mb-2">No shipments yet</h4>
              <p className="text-gray-500 mb-6">Create your first shipment to get started</p>
              <button
                onClick={() => navigate('/new-shipment')}
                className="px-6 py-2 bg-navy text-white rounded-lg hover:bg-slate-800 transition-colors"
                data-testid="create-first-shipment-button"
              >
                Create Shipment
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200" data-testid="shipments-table">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Date
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      PO Number
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Buyer
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Value
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {shipments.map((shipment) => (
                    <React.Fragment key={shipment._id}>
                    <tr className="hover:bg-gray-50" data-testid={`shipment-row-${shipment._id}`}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        <div className="flex items-center">
                          <Calendar className="w-4 h-4 mr-2 text-slate" />
                          {new Date(shipment.created_at).toLocaleDateString()}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-navy" data-testid={`po-number-${shipment._id}`}>
                        {shipment.po_number}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        <div className="flex items-center">
                          <User className="w-4 h-4 mr-2 text-slate" />
                          {shipment.buyer_name}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-medium">
                        {shipment.currency || 'USD'} {getTotalValue(shipment.items).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                            shipment.status === 'Final'
                              ? 'bg-green-100 text-green-800'
                              : 'bg-yellow-100 text-yellow-800'
                          }`}
                          data-testid={`status-${shipment._id}`}
                        >
                          {shipment.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        {shipment.status === 'Draft' && (
                          <button
                            onClick={async () => {
                              setValidating(shipment._id);
                              try {
                                const response = await axios.get(
                                  `${API_URL}/api/shipments/${shipment._id}/validate`,
                                  { headers: { Authorization: `Bearer ${token}` } }
                                );
                                setValidationResults(prev => ({ ...prev, [shipment._id]: response.data }));
                              } catch (err) {
                                console.error('Validation failed:', err);
                              } finally {
                                setValidating(null);
                              }
                            }}
                            disabled={validating === shipment._id}
                            className="font-medium text-blue-600 hover:text-blue-800 flex items-center space-x-1 disabled:opacity-50"
                            data-testid={`validate-${shipment._id}`}
                          >
                            <ClipboardCheck className="w-4 h-4" />
                            <span>{validating === shipment._id ? 'Checking…' : 'Validate'}</span>
                          </button>
                        )}
                        {shipment.status === 'Final' && (
                          <div className="flex flex-col space-y-1">
                            {shipment.pdf_url && (
                              <a
                                href={`${API_URL}${shipment.pdf_url}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-navy hover:text-slate-600 font-medium"
                                data-testid={`download-pdf-${shipment._id}`}
                              >
                                📄 Invoice PDF
                              </a>
                            )}
                            {/* Packing List - Pro Feature */}
                            <button
                              onClick={() => {
                                if (!isProMember) {
                                  setShowUpgradeModal(true);
                                  return;
                                }
                                (async () => {
                                  try {
                                    const response = await axios.post(
                                      `${API_URL}/api/shipments/${shipment._id}/generate-packing-list`,
                                      {},
                                      {
                                        headers: { Authorization: `Bearer ${token}` },
                                        responseType: 'blob'
                                      }
                                    );
                                    const url = window.URL.createObjectURL(new Blob([response.data]));
                                    const link = document.createElement('a');
                                    link.href = url;
                                    link.setAttribute('download', `packing_list_${shipment._id}.pdf`);
                                    document.body.appendChild(link);
                                    link.click();
                                    link.remove();
                                  } catch (err) {
                                    console.error('Error downloading packing list:', err);
                                  }
                                })();
                              }}
                              className={`font-medium text-left flex items-center ${
                                isProMember ? 'text-blue-600 hover:text-blue-800' : 'text-gray-400 cursor-not-allowed'
                              }`}
                              data-testid={`packing-list-${shipment._id}`}
                            >
                              {!isProMember && <Lock className="w-3 h-3 mr-1" />}
                              📦 Packing List
                            </button>
                            {/* Certificate of Origin - Pro Feature */}
                            <button
                              onClick={() => {
                                if (!isProMember) {
                                  setShowUpgradeModal(true);
                                  return;
                                }
                                (async () => {
                                  try {
                                    const response = await axios.post(
                                      `${API_URL}/api/shipments/${shipment._id}/generate-coo`,
                                      {},
                                      {
                                        headers: { Authorization: `Bearer ${token}` },
                                        responseType: 'blob'
                                      }
                                    );
                                    const url = window.URL.createObjectURL(new Blob([response.data]));
                                    const link = document.createElement('a');
                                    link.href = url;
                                    link.setAttribute('download', `coo_${shipment._id}.pdf`);
                                    document.body.appendChild(link);
                                    link.click();
                                    link.remove();
                                  } catch (err) {
                                    console.error('Error downloading COO:', err);
                                  }
                                })();
                              }}
                              className={`font-medium text-left flex items-center ${
                                isProMember ? 'text-green-600 hover:text-green-800' : 'text-gray-400 cursor-not-allowed'
                              }`}
                              data-testid={`coo-${shipment._id}`}
                            >
                              {!isProMember && <Lock className="w-3 h-3 mr-1" />}
                              🌿 Certificate of Origin
                            </button>
                            {/* Tally Export - Pro Feature */}
                            <button
                              onClick={() => {
                                if (!isProMember) {
                                  setShowUpgradeModal(true);
                                  return;
                                }
                                (async () => {
                                  try {
                                    const response = await axios.post(
                                      `${API_URL}/api/shipments/${shipment._id}/export-tally`,
                                      {},
                                      {
                                        headers: { Authorization: `Bearer ${token}` },
                                        responseType: 'blob'
                                      }
                                    );
                                    const url = window.URL.createObjectURL(new Blob([response.data]));
                                    const link = document.createElement('a');
                                    link.href = url;
                                    link.setAttribute('download', `tally_export_${shipment._id}.xml`);
                                    document.body.appendChild(link);
                                    link.click();
                                    link.remove();
                                  } catch (err) {
                                    console.error('Error downloading Tally XML:', err);
                                  }
                                })();
                              }}
                              className={`font-medium text-left flex items-center ${
                                isProMember ? 'text-purple-600 hover:text-purple-800' : 'text-gray-400 cursor-not-allowed'
                              }`}
                              data-testid={`tally-export-${shipment._id}`}
                            >
                              {!isProMember && <Lock className="w-3 h-3 mr-1" />}
                              💼 Tally XML
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                    {validationResults[shipment._id] && (() => {
                      const vr = validationResults[shipment._id];
                      const scoreBg = vr.score >= 80 ? 'bg-green-100 text-green-800' : vr.score >= 50 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800';
                      return (
                        <tr data-testid={`validation-panel-${shipment._id}`}>
                          <td colSpan={6} className="px-6 py-3 bg-gray-50 border-t border-gray-200">
                            <div className="flex items-start justify-between mb-2">
                              <span className="text-sm font-semibold text-gray-700">Validation Report</span>
                              <div className="flex items-center space-x-2">
                                <span className={`text-xs font-bold px-2 py-1 rounded-full ${scoreBg}`}>
                                  Score: {vr.score}%
                                </span>
                                <button
                                  onClick={() => setValidationResults(prev => { const n = {...prev}; delete n[shipment._id]; return n; })}
                                  className="text-gray-400 hover:text-gray-600 text-xs"
                                >
                                  ✕
                                </button>
                              </div>
                            </div>
                            {vr.errors.length === 0 && vr.warnings.length === 0 ? (
                              <div className="flex items-center space-x-2 text-green-700 text-sm">
                                <CheckCircle className="w-4 h-4" />
                                <span>All checks passed!</span>
                              </div>
                            ) : (
                              <div className="space-y-1">
                                {vr.errors.map((msg, i) => (
                                  <div key={i} className="flex items-start space-x-2 text-red-700 text-xs">
                                    <XCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                                    <span>{msg}</span>
                                  </div>
                                ))}
                                {vr.warnings.map((msg, i) => (
                                  <div key={i} className="flex items-start space-x-2 text-yellow-700 text-xs">
                                    <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                                    <span>{msg}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </td>
                        </tr>
                      );
                    })()}
                    </React.Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>

      {/* Upgrade Modal */}
      {showUpgradeModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setShowUpgradeModal(false)}>
          <div className="bg-white rounded-lg p-8 max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="text-center">
              <Lock className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-2xl font-bold text-navy mb-2">Upgrade to Pro</h3>
              <p className="text-gray-600 mb-6">
                Unlock Tally XML Export, GST Reports, and Packing Lists with TradesdocAi Pro.
              </p>
              <div className="space-y-3">
                <button
                  onClick={() => {
                    setShowUpgradeModal(false);
                    navigate('/upgrade');
                  }}
                  className="w-full px-6 py-3 bg-navy text-white rounded-lg hover:bg-slate-800 transition-colors font-bold"
                >
                  View Pro Plans
                </button>
                <button
                  onClick={() => setShowUpgradeModal(false)}
                  className="w-full px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Maybe Later
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
