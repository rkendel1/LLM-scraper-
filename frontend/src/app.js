import React, { useState } from 'react';
import './App.css';

function App() {
  const [domain, setDomain] = useState('');
  const [depth, setDepth] = useState(2);
  const [status, setStatus] = useState('');

  const startCrawl = async () => {
    setStatus('Starting crawl...');
    const res = await fetch('http://localhost:5000/start-crawl', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain, depth })
    });
    const result = await res.json();
    setStatus(`Completed: ${result.docs} docs`);
  };

  return (
    <div className="App">
      <h1>LLM Scraper Dashboard</h1>
      <input placeholder="example.com" value={domain} onChange={(e) => setDomain(e.target.value)} />
      <input type="number" min="1" max="5" value={depth} onChange={(e) => setDepth(e.target.value)} />
      <button onClick={startCrawl}>Start Crawl</button>
      <p>{status}</p>
    </div>
  );
}

export default App;
