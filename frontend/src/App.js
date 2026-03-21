import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import './App.css';
import Dashboard from './components/Dashboard';
import Settings from './components/Settings';
import NewShipment from './components/NewShipment';
import Upgrade from './components/Upgrade';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function App() {
  const [ready, setReady] = useState(!!localStorage.getItem('token'));

  useEffect(() => {
    if (!localStorage.getItem('token')) {
      axios.post(`${API_URL}/api/auth/auto-session`)
        .then(res => {
          localStorage.setItem('token', res.data.token);
          localStorage.setItem('user_id', res.data.user_id);
          localStorage.setItem('is_pro_member', String(res.data.is_pro_member));
        })
        .catch(err => console.error('Auto-session failed:', err))
        .finally(() => setReady(true));
    }
  }, []);

  if (!ready) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-navy"></div>
      </div>
    );
  }

  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/new-shipment" element={<NewShipment />} />
          <Route path="/upgrade" element={<Upgrade />} />
          <Route path="/" element={<Navigate to="/dashboard" />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
