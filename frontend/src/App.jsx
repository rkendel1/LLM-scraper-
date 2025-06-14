// src/App.jsx

import React, { useState } from 'react';
import axios from 'axios';

const api = axios.create({ baseURL: 'http://localhost:5000' });

function App() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [pdfPath, setPdfPath] = useState('');
  const [crawlDomain, setCrawlDomain] = useState('');
  const [isCrawling, setIsCrawling] = useState(false);

  // Ask LLM via /rag/ask
  const askQuestion = async () => {
    try {
      const res = await api.post('/rag/ask', { question });
      setAnswer(res.data.improved_answer || res.data.answer || "No answer found.");
    } catch (e) {
      setAnswer("Error getting answer.");
    }
  };

  // Upload PDF via /upload/pdf
  const handlePDFUpload = async (e) => {
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch('http://localhost:5000/upload/pdf', {
        method: 'POST',
        body: formData
      });

      if (res.ok) {
        alert("✅ PDF uploaded and processed");
        setPdfPath(file.name);
      }
    } catch (e) {
      alert("❌ Error uploading PDF");
    }
  };

  // Run Web Crawler
  const runScraper = async () => {
    setIsCrawling(true);
    try {
      const res = await api.post('/start-crawl', {
        domain: crawlDomain,
        depth: 2
      });
      alert(`✅ Found ${res.data.docs_updated} documents`);
    } catch (e) {
      alert("❌ Crawling failed");
    } finally {
      setIsCrawling(false);
    }
  };

  return (
    <div style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1>LLM Scraper Chatbot</h1>

      {/* QA Section */}
      <section style={{ margin: "2rem 0" }}>
        <h2>Ask a Question</h2>
        <input
          placeholder="What is AI ethics?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          style={{ width: "300px", padding: "0.5rem" }}
        />
        <button onClick={askQuestion} style={{ marginLeft: "0.5rem", padding: "0.5rem 1rem" }}>
          Ask Mistral
        </button>
        <p style={{ marginTop: "1rem" }}>
          <strong>Answer:</strong> {answer || "Awaiting response..."}
        </p>
      </section>

      {/* PDF Upload */}
      <section style={{ margin: "2rem 0" }}>
        <h2>Upload PDF</h2>
        <input type="file" accept=".pdf" onChange={handlePDFUpload} />
        {pdfPath && <p>Uploaded: {pdfPath}</p>}
      </section>

      {/* Web Crawler */}
      <section style={{ margin: "2rem 0" }}>
        <h2>Run Web Scraper</h2>
        <input
          placeholder="example.com"
          value={crawlDomain}
          onChange={(e) => setCrawlDomain(e.target.value)}
          style={{ padding: "0.5rem", width: "300px" }}
        />
        <button
          onClick={runScraper}
          disabled={isCrawling}
          style={{ marginLeft: "0.5rem", padding: "0.5rem 1rem" }}
        >
          {isCrawling ? "Crawling..." : "Start Crawl"}
        </button>
      </section>
    </div>
  );
}

export default App;