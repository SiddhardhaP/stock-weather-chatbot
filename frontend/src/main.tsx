import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx' // Explicitly import App.jsx
import './index.css'      // Import Tailwind CSS directives
 
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)