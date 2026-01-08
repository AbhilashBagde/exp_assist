import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Package, Plus, Settings as SettingsIcon, LogOut, FileText, Calendar, User, Lock, Crown } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function Dashboard() {
  const [shipments, setShipments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
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
      const response = await axios.get(`${API_URL}/api/shipments`, {
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
  }, [token, navigate]);

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
              <Package className="w-8 h-8" />
              <h1 className="text-2xl font-bold">ExportAssist</h1>
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
            <button
              onClick={async () => {
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
              }}
              className="flex items-center space-x-2 px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors shadow-md"
              data-testid="gstr1-export-button"
            >
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
                      Value (₹)
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
                    <tr key={shipment._id} className="hover:bg-gray-50" data-testid={`shipment-row-${shipment._id}`}>
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
                            <button
                              onClick={async () => {
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
                              }}
                              className="text-blue-600 hover:text-blue-800 font-medium text-left"
                              data-testid={`packing-list-${shipment._id}`}
                            >
                              📦 Packing List
                            </button>
                            <button
                              onClick={async () => {
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
                              }}
                              className="text-purple-600 hover:text-purple-800 font-medium text-left"
                              data-testid={`tally-export-${shipment._id}`}
                            >
                              💼 Tally XML
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default Dashboard;
