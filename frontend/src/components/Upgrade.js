import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, Lock, ArrowLeft, ExternalLink } from 'lucide-react';

function Upgrade() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-navy to-slate-700">
      {/* Header */}
      <header className="bg-navy/50 text-white backdrop-blur-sm" data-testid="upgrade-header">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <img src="/TDA.png" alt="TradesdocAi Logo" className="w-8 h-8 rounded-full object-contain" />
              <h1 className="text-2xl font-bold">TradesdocAi</h1>
            </div>
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center space-x-2 px-4 py-2 bg-slate-700 rounded-lg hover:bg-slate-600 transition-colors"
              data-testid="back-button"
            >
              <ArrowLeft className="w-5 h-5" />
              <span>Back to Dashboard</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center mb-12">
          <h2 className="text-4xl font-bold text-white mb-4" data-testid="page-title">
            Upgrade to TradesdocAi Pro
          </h2>
          <p className="text-xl text-gray-300">
            Unlock premium features and scale your export business
          </p>
        </div>

        {/* Pricing Card */}
        <div className="bg-white rounded-2xl shadow-2xl overflow-hidden max-w-2xl mx-auto">
          {/* Pro Badge */}
          <div className="bg-gradient-to-r from-yellow-400 to-yellow-500 py-3 text-center">
            <span className="text-navy font-bold text-lg">✨ PRO MEMBERSHIP ✨</span>
          </div>

          {/* Pricing */}
          <div className="p-8 text-center border-b border-gray-200">
            <div className="flex items-baseline justify-center mb-2">
              <span className="text-5xl font-bold text-navy">₹999</span>
              <span className="text-xl text-gray-600 ml-2">/ month</span>
            </div>
            <p className="text-gray-600 mt-2">Billed monthly. Cancel anytime.</p>
          </div>

          {/* Features */}
          <div className="p-8">
            <h3 className="text-xl font-semibold text-navy mb-6 text-center">
              Pro Features Include:
            </h3>
            <ul className="space-y-4">
              <li className="flex items-start" data-testid="feature-tally">
                <Check className="w-6 h-6 text-green-500 mr-3 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900">Tally XML Export</p>
                  <p className="text-sm text-gray-600">
                    Direct integration with Tally.ERP 9 / TallyPrime for seamless bookkeeping
                  </p>
                </div>
              </li>
              <li className="flex items-start" data-testid="feature-gst">
                <Check className="w-6 h-6 text-green-500 mr-3 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900">GST Refund Reports</p>
                  <p className="text-sm text-gray-600">
                    One-click GSTR-1 CSV export for easy GST return filing
                  </p>
                </div>
              </li>
              <li className="flex items-start" data-testid="feature-packing">
                <Check className="w-6 h-6 text-green-500 mr-3 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900">Packing List Generation</p>
                  <p className="text-sm text-gray-600">
                    Professional packing lists with weight tracking for customs
                  </p>
                </div>
              </li>
              <li className="flex items-start" data-testid="feature-history">
                <Check className="w-6 h-6 text-green-500 mr-3 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900">Unlimited History</p>
                  <p className="text-sm text-gray-600">
                    Access all your past shipments and documents anytime
                  </p>
                </div>
              </li>
              <li className="flex items-start" data-testid="feature-support">
                <Check className="w-6 h-6 text-green-500 mr-3 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-gray-900">Priority Support</p>
                  <p className="text-sm text-gray-600">
                    Get help faster with dedicated support for Pro members
                  </p>
                </div>
              </li>
            </ul>
          </div>

          {/* CTA Button */}
          <div className="p-8 bg-gray-50">
            <button
              onClick={() => window.open('https://razorpay.com', '_blank')}
              className="w-full flex items-center justify-center space-x-2 px-8 py-4 bg-navy text-white rounded-lg hover:bg-slate-800 transition-colors shadow-lg font-bold text-lg"
              data-testid="subscribe-button"
            >
              <span>Subscribe Now</span>
              <ExternalLink className="w-5 h-5" />
            </button>
            <p className="text-xs text-gray-500 text-center mt-4">
              Secure payment powered by Razorpay
            </p>
          </div>
        </div>

        {/* Free Tier Info */}
        <div className="mt-12 text-center">
          <p className="text-white mb-4">
            <strong>Free Tier Includes:</strong>
          </p>
          <div className="bg-white/10 backdrop-blur-sm rounded-lg p-6 max-w-xl mx-auto">
            <ul className="text-white space-y-2 text-left">
              <li className="flex items-center">
                <Check className="w-5 h-5 text-green-400 mr-3" />
                AI-powered PO extraction
              </li>
              <li className="flex items-center">
                <Check className="w-5 h-5 text-green-400 mr-3" />
                Commercial Invoice generation
              </li>
              <li className="flex items-center">
                <Check className="w-5 h-5 text-green-400 mr-3" />
                HS Code prediction
              </li>
              <li className="flex items-center">
                <Lock className="w-5 h-5 text-gray-400 mr-3" />
                Tally XML Export (Pro only)
              </li>
              <li className="flex items-center">
                <Lock className="w-5 h-5 text-gray-400 mr-3" />
                GST Reports (Pro only)
              </li>
              <li className="flex items-center">
                <Lock className="w-5 h-5 text-gray-400 mr-3" />
                Packing Lists (Pro only)
              </li>
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
}

export default Upgrade;
