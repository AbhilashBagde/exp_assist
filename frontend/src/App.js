import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import './App.css';
import Dashboard from './components/Dashboard';
import Settings from './components/Settings';
import NewShipment from './components/NewShipment';
import Upgrade from './components/Upgrade';
import Login from './components/Login';

function PrivateRoute({ children }) {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/login" replace />;
}

function App() {
  const [ready, setReady] = useState(!!localStorage.getItem('token'));

  useEffect(() => {
    // If already authenticated, no need to do anything
    if (localStorage.getItem('token')) return;
    setReady(true);
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
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Login isSignup />} />
          <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/settings" element={<PrivateRoute><Settings /></PrivateRoute>} />
          <Route path="/new-shipment" element={<PrivateRoute><NewShipment /></PrivateRoute>} />
          <Route path="/upgrade" element={<PrivateRoute><Upgrade /></PrivateRoute>} />
          <Route path="/" element={<Navigate to="/login" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
