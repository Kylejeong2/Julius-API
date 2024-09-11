'use client'

import React, { useState } from 'react';
import axios from 'axios';

export default function CurlEditor() {
  const [curlCommand, setCurlCommand] = useState('');
  const [response, setResponse] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setResponse(null);
    setError(null);

    try {
      // Parse the curl command
      const url = curlCommand.match(/'(https?:\/\/[^']+)'/)?.[1];
      const method = curlCommand.includes('-X POST') ? 'POST' : 'GET';
      const headers: Record<string, string> = {};
      const headerMatches = Array.from(curlCommand.matchAll(/-H '([^:]+): ([^']+)'/g));
      for (const match of headerMatches) {
        headers[match[1]] = match[2];
      }
      const data = curlCommand.match(/-d '(.+)'/)?.[1];

      if (!url) {
        throw new Error('Invalid curl command: URL not found');
      }

      // Send the request
      const res = await axios({
        method,
        url,
        headers,
        data: data ? JSON.parse(data) : undefined,
      });

      setResponse(JSON.stringify(res.data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    }
  };

  return (
    <div className="max-w-2xl mx-auto mt-8">
      <h2 className="text-2xl font-bold mb-4 text-black">Curl Editor</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="curl-command" className="block text-sm font-medium text-black">
            Enter your curl command
          </label>
          <textarea
            id="curl-command"
            rows={4}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm text-black"
            value={curlCommand}
            onChange={(e) => setCurlCommand(e.target.value)}
            required
          />
        </div>
        <button
          type="submit"
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          Send Request
        </button>
      </form>

      {error && (
        <div className="mt-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
          {error}
        </div>
      )}

      {response && (
        <div className="mt-8">
          <h3 className="text-lg font-medium text-black">Response:</h3>
          <pre className="mt-2 p-4 bg-gray-100 rounded-md overflow-x-auto">
            <code className="text-black">{response}</code>
          </pre>
        </div>
      )}
    </div>
  );
}