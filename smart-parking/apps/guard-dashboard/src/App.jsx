import React, { useState, useEffect } from 'react';
import './index.css';

export default function GuardDashboard() {
  const [grid, setGrid] = useState([]);
  const [selectedBay, setSelectedBay] = useState(null);
  const [stats, setStats] = useState({ available: 0, occupied: 0, reserved: 0, ev: 0, utilPct: 0 });

  useEffect(() => {
    // 1. Fetch Initial State
    fetch('http://localhost:8000/api/v1/gate/slots')
      .then(res => res.json())
      .then(data => {
        // Format into rows
        const rows = { 'A': [], 'B': [], 'C': [] };
        data.forEach(slot => {
          const rowLetter = slot.slot_code[0];
          if (rows[rowLetter]) {
            rows[rowLetter].push({
              id: slot.slot_code,
              status: slot.current_status,
              is_ev: slot.slot_type === 'EV'
            });
          }
        });
        
        const newGrid = [rows['A'], rows['B'], rows['C']];
        setGrid(newGrid);
        updateStats(newGrid);
      })
      .catch(err => console.error("Failed to fetch slots:", err));

    // 2. Connect WebSocket
    const ws = new WebSocket('ws://localhost:8000/ws/sync');
    ws.onmessage = (event) => { 
      const message = JSON.parse(event.data); 
      if (message.event.startsWith('SLOT_')) {
        const { slot_code, status } = message.data;
        setGrid(prev => {
          const next = [...prev];
          for (let r = 0; r < next.length; r++) {
            for (let c = 0; c < next[r].length; c++) {
              if (next[r][c].id === slot_code) {
                next[r][c] = { ...next[r][c], status };
              }
            }
          }
          updateStats(next);
          return next;
        });
      }
    };

    return () => ws.close();
  }, []);

  const updateStats = (currentGrid) => {
    let a=0, o=0, r=0, e=0, total=0;
    currentGrid.forEach(row => {
      row.forEach(slot => {
        total++;
        if (slot.status === 'AVAILABLE') a++;
        if (slot.status === 'OCCUPIED') o++;
        if (slot.status === 'RESERVED') r++;
        if (slot.is_ev) e++;
      });
    });
    setStats({ available: a, occupied: o, reserved: r, ev: e, utilPct: total ? Math.round((o+r)/total * 100) : 0 });
  };

  const getStatusColor = (status, is_ev) => {
    if (is_ev && status === 'OCCUPIED') return 'bg-blue-600';
    if (is_ev) return 'bg-blue-400';
    switch (status) {
      case 'AVAILABLE': return 'bg-emerald-500';
      case 'OCCUPIED': return 'bg-red-500';
      case 'RESERVED': return 'bg-amber-500';
      default: return 'bg-gray-300';
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-6 font-sans">
      <header className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Live 2D Bay Grid</h1>
          <p className="text-slate-500 mt-1">Target: &lt;100ms via WebSockets</p>
        </div>
        <div className="flex items-center gap-2 bg-emerald-100 text-emerald-800 px-4 py-2 rounded-full text-sm font-semibold shadow-sm">
          <span className="w-2.5 h-2.5 bg-emerald-500 rounded-full animate-pulse"></span>
          LIVE SYNC
        </div>
      </header>

      <div className="flex gap-8">
        {/* Legend Panel */}
        <aside className="w-64 shrink-0 bg-white p-6 rounded-2xl shadow-sm border border-slate-100 h-fit">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-4">Bay Status Legend</h3>
          <ul className="space-y-4">
            <li className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-emerald-500 mt-0.5 shadow-inner"></div>
              <div>
                <p className="font-semibold text-slate-800">Available</p>
                <p className="text-xs text-slate-500">Free for assignment</p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-red-500 mt-0.5 shadow-inner"></div>
              <div>
                <p className="font-semibold text-slate-800">Occupied</p>
                <p className="text-xs text-slate-500">Vehicle parked in bay</p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-amber-500 mt-0.5 shadow-inner"></div>
              <div>
                <p className="font-semibold text-slate-800">Reserved</p>
                <p className="text-xs text-slate-500">Held for QR arrival</p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-blue-500 mt-0.5 shadow-inner"></div>
              <div>
                <p className="font-semibold text-slate-800">EV Charging</p>
                <p className="text-xs text-slate-500">Active charging bay</p>
              </div>
            </li>
          </ul>
        </aside>

        {/* Grid Panel */}
        <main className="flex-1 bg-white p-8 rounded-2xl shadow-sm border border-slate-100 overflow-x-auto">
          <div className="min-w-max space-y-4">
            {grid.map((row, rIdx) => (
              <div key={rIdx} className="flex gap-4 items-center">
                <span className="w-8 text-center font-bold text-slate-400">{String.fromCharCode(65 + rIdx)}</span>
                {row.map((col) => (
                  <button 
                    key={col.id}
                    onClick={() => setSelectedBay(col)}
                    className={`w-16 h-12 rounded-lg flex items-center justify-center font-bold text-white shadow-sm transition-transform hover:scale-105 active:scale-95 ${getStatusColor(col.status, col.is_ev)}`}
                  >
                    {col.id}
                  </button>
                ))}
              </div>
            ))}
          </div>

          <div className="mt-8 bg-slate-50 rounded-xl p-4 flex justify-center text-sm font-medium text-slate-600 border border-slate-200">
            Summary: {stats.available} Available • {stats.occupied} Occupied • {stats.reserved} Reserved • {stats.ev} EV — {stats.utilPct}% Capacity Utilized
          </div>
        </main>
      </div>

      {/* Interactive Modal */}
      {selectedBay && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-xl transform transition-all">
            <h3 className="text-xl font-bold text-slate-900 mb-1">Bay {selectedBay.id}</h3>
            <p className="text-slate-500 mb-6 flex items-center gap-2">
              <span className={`w-3 h-3 rounded-full ${getStatusColor(selectedBay.status, selectedBay.is_ev)}`}></span>
              {selectedBay.status}
            </p>
            
            {selectedBay.status === 'OCCUPIED' && (
              <div className="space-y-4 mb-6">
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Vehicle Plate</p>
                  <p className="text-lg font-mono font-bold text-slate-800">MP04-AB-1234</p>
                </div>
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Elapsed Time</p>
                  <p className="text-lg font-mono font-bold text-slate-800">02:14:35</p>
                </div>
              </div>
            )}
            
            <div className="flex gap-3">
              <button 
                onClick={() => setSelectedBay(null)}
                className="flex-1 px-4 py-2.5 border border-slate-200 text-slate-600 font-semibold rounded-xl hover:bg-slate-50 transition-colors"
              >
                Close
              </button>
              {selectedBay.status === 'OCCUPIED' && (
                <button className="flex-1 px-4 py-2.5 bg-red-500 text-white font-semibold rounded-xl hover:bg-red-600 transition-colors shadow-sm">
                  Initiate Exit
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
