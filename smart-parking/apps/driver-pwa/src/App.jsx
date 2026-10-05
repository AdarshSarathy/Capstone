import React, { useState, useEffect } from 'react';
import './index.css';

export default function DriverApp() {
  const [eta, setEta] = useState(60);
  const [reservation, setReservation] = useState(null);
  const [checkedIn, setCheckedIn] = useState(false);
  const [slot, setSlot] = useState(null);
  const [forecast, setForecast] = useState({ available: 0, message: 'Loading...' });

  const LOT_ID = "00000000-0000-0000-0000-000000000001";

  useEffect(() => {
    fetch(`http://localhost:8000/api/v1/forecast/occupancy?lot_id=${LOT_ID}&eta_minutes=${eta}`)
      .then(res => res.json())
      .then(data => {
        setForecast({ available: data.safe_capacity, message: data.message });
      })
      .catch(err => console.error("Forecast fetch error", err));
  }, [eta]);

  const handleReserve = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/forecast/reserve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lot_id: LOT_ID,
          user_id: 'user_frontend_1',
          vehicle_plate: 'UI-1234',
          eta_minutes: eta,
          slot_type: 'REGULAR'
        })
      });
      if (res.ok) {
        const data = await res.json();
        const start = new Date(data.eta_window_start).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        const end = new Date(data.eta_window_end).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        
        setReservation({
          id: data.reservation_id,
          eta_window: `${start} - ${end}`,
          qr_token: data.qr_token
        });
      } else {
        alert("Failed to reserve capacity.");
      }
    } catch(e) {
      console.error(e);
    }
  };

  const simulateCheckIn = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/gate/check-in', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lot_id: LOT_ID,
          qr_token: reservation.qr_token
        })
      });
      if (res.ok) {
        const data = await res.json();
        setCheckedIn(true);
        setSlot(data.slot_code);
      } else {
        alert("Check-in failed. Are you in the arrival window?");
      }
    } catch(e) {
      console.error(e);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-50 font-sans flex flex-col max-w-md mx-auto relative overflow-hidden shadow-2xl">
      {/* Decorative gradient background */}
      <div className="absolute top-[-10%] left-[-10%] w-96 h-96 bg-emerald-500/20 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-96 h-96 bg-blue-500/20 rounded-full blur-3xl pointer-events-none"></div>

      {checkedIn && (
        <div className="bg-emerald-500 text-white p-4 safe-area-top shadow-lg z-20 sticky top-0 flex justify-between items-center animate-slide-down">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-emerald-100">Assigned Slot</p>
            <h2 className="text-3xl font-black">{slot}</h2>
          </div>
          <div className="w-12 h-12 bg-emerald-400 rounded-full flex items-center justify-center border-2 border-emerald-300">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path></svg>
          </div>
        </div>
      )}

      <header className="p-6 pb-2 z-10">
        <h1 className="text-2xl font-bold tracking-tight text-white">Smart Parking</h1>
        <p className="text-slate-400 text-sm mt-1">Predictive Capacity Management</p>
      </header>

      <main className="flex-1 p-6 z-10 flex flex-col">
        {!reservation ? (
          <div className="space-y-6 flex-1 flex flex-col justify-center">
            <div className="bg-slate-800/60 backdrop-blur-xl border border-white/10 shadow-2xl rounded-3xl p-6 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-emerald-400 to-blue-500"></div>
              <h2 className="text-lg font-semibold mb-4 text-slate-200">Plan Arrival</h2>
              
              <div className="mb-8">
                <label className="text-sm font-medium text-slate-400 mb-2 block">ETA from now</label>
                <div className="flex items-baseline gap-2">
                  <span className="text-5xl font-black text-white tracking-tighter">{eta}</span>
                  <span className="text-lg font-medium text-slate-400">mins</span>
                </div>
                <input 
                  type="range" 
                  min="15" max="120" step="15" 
                  value={eta} 
                  onChange={(e) => setEta(parseInt(e.target.value))}
                  className="w-full mt-4 accent-emerald-500 h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer"
                />
              </div>

              <div className="bg-slate-800/50 rounded-2xl p-4 border border-slate-700">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm text-slate-400">Forecast</span>
                  <span className="text-xs font-bold text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded-md">HIGH CONFIDENCE</span>
                </div>
                <p className="text-lg font-medium">~{forecast.available} spots free</p>
                <p className="text-xs text-slate-500 mt-1">{forecast.message}</p>
              </div>
            </div>

            <button 
              onClick={handleReserve}
              className="w-full bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-bold py-4 rounded-2xl shadow-lg shadow-emerald-500/20 transition-all active:scale-95"
            >
              Reserve Capacity
            </button>
          </div>
        ) : (
          <div className="space-y-6 flex-1 flex flex-col justify-center">
            <div className="bg-slate-800/60 backdrop-blur-xl border border-white/10 shadow-2xl rounded-3xl p-8 flex flex-col items-center text-center">
              <div className="w-16 h-16 bg-emerald-500/20 rounded-full flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
              </div>
              <h2 className="text-2xl font-bold mb-1">Capacity Reserved</h2>
              <p className="text-slate-400 text-sm mb-8">Arrival Window: {reservation.eta_window}</p>
              
              <div className="bg-white p-4 rounded-2xl shadow-inner mb-6 relative">
                {/* Simulated QR Code using borders/SVG */}
                <svg viewBox="0 0 100 100" className="w-48 h-48">
                  <rect width="100" height="100" fill="#fff" />
                  <rect x="10" y="10" width="30" height="30" fill="#000" />
                  <rect x="60" y="10" width="30" height="30" fill="#000" />
                  <rect x="10" y="60" width="30" height="30" fill="#000" />
                  <rect x="15" y="15" width="20" height="20" fill="#fff" />
                  <rect x="65" y="15" width="20" height="20" fill="#fff" />
                  <rect x="15" y="65" width="20" height="20" fill="#fff" />
                  <rect x="20" y="20" width="10" height="10" fill="#000" />
                  <rect x="70" y="20" width="10" height="10" fill="#000" />
                  <rect x="20" y="70" width="10" height="10" fill="#000" />
                  {/* Random inner blocks */}
                  <rect x="50" y="50" width="40" height="40" fill="#000" />
                  <rect x="55" y="55" width="10" height="10" fill="#fff" />
                  <rect x="75" y="55" width="10" height="10" fill="#fff" />
                  <rect x="55" y="75" width="10" height="10" fill="#fff" />
                  <rect x="45" y="10" width="10" height="10" fill="#000" />
                  <rect x="45" y="25" width="10" height="10" fill="#000" />
                  <rect x="10" y="45" width="10" height="10" fill="#000" />
                  <rect x="25" y="45" width="10" height="10" fill="#000" />
                </svg>
                <div className="absolute inset-0 border-4 border-emerald-500 rounded-2xl opacity-50 pointer-events-none"></div>
              </div>

              <p className="text-xs text-slate-500 max-w-[200px]">Scan this pass at the entry gate barrier to receive your bay assignment.</p>
            </div>

            {!checkedIn && (
              <button 
                onClick={simulateCheckIn}
                className="w-full bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-300 font-semibold py-4 rounded-2xl transition-all"
              >
                Simulate Gate Scan (Demo)
              </button>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
