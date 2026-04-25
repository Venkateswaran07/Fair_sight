import React from 'react';

export default function HistoryPage() {
  return (
    <div style={{ 
      padding: '50px', 
      textAlign: 'center', 
      fontFamily: 'sans-serif',
      backgroundColor: '#f0f0f0',
      minHeight: '100vh' 
    }}>
      <h1 style={{ color: '#333' }}>History Page - Bare Bones Test</h1>
      <p>If you see this, the routing is PERFECT. The issue was in the components.</p>
      <div style={{ marginTop: '20px' }}>
        <a href="/" style={{ color: 'blue', textDecoration: 'underline' }}>Go Back Home</a>
      </div>
      
      <div style={{ marginTop: '50px', padding: '20px', backgroundColor: 'white', borderRadius: '10px' }}>
        <h2 style={{ fontSize: '18px' }}>Checking for Database Connection...</h2>
        <button onClick={() => {
          fetch('http://localhost:8000/audit/history')
            .then(res => res.json())
            .then(data => alert('Database is OK! Found ' + data.history.length + ' audits.'))
            .catch(err => alert('Error connecting to database: ' + err.message))
        }} style={{ padding: '10px 20px', cursor: 'pointer' }}>
          Test Database Connection
        </button>
      </div>
    </div>
  );
}
