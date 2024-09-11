'use client'

import React, { useState } from 'react';
import axios from 'axios';

export default function JuliusPrompt() {
  const [prompt, setPrompt] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [response, setResponse] = useState<{ text: string; code: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [useAnon, setUseAnon] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await axios.post('http://localhost:3001/api/prompt', { prompt, email, password });
      setResponse(res.data);
    } catch (error) {
      console.error('Error:', error);
      setResponse(null);
    }
    setLoading(false);
  };

  return (
    <div className="max-w-2xl mx-auto mt-8">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700">
            Email
          </label>
          <input
            type="email"
            id="email"
            name="email"
            className="mt-1 block w-full rounded-md text-black border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-gray-700">
            Password
          </label>
          <input
            type="password"
            id="password"
            name="password"
            className="mt-1 block w-full rounded-md text-black border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="prompt" className="block text-sm font-medium text-gray-700">
            Enter your prompt for Julius
          </label>
          <textarea
            id="prompt"
            name="prompt"
            rows={3}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="use-anon" className="flex items-center">
            <input
              type="checkbox"
              id="use-anon"
              checked={useAnon}
              onChange={(e) => setUseAnon(e.target.checked)}
              className="mr-2"
            />
            <span className="text-sm font-medium text-gray-700">Use Anon for authentication</span>
          </label>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          {loading ? 'Loading...' : 'Submit'}
        </button>
      </form>

      {response && (
        <div className="mt-8">
          <h3 className="text-lg font-medium text-gray-900">Response:</h3>
          <div className="mt-2 space-y-4">
            <div>
              <h4 className="text-sm font-medium text-gray-700">Text:</h4>
              <p className="mt-1 text-sm text-gray-500">{response.text}</p>
            </div>
            <div>
              <h4 className="text-sm font-medium text-gray-700">Code:</h4>
              <pre className="mt-1 p-2 bg-gray-100 rounded-md overflow-x-auto">
                <code>{response.code}</code>
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}