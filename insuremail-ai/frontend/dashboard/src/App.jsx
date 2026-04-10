import React from 'react'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import EmailList from './pages/EmailList'
import EmailDetail from './pages/EmailDetail'
import Metrics from './pages/Metrics'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/emails" element={<EmailList />} />
        <Route path="/emails/:id" element={<EmailDetail />} />
        <Route path="/metrics" element={<Metrics />} />
      </Routes>
    </Layout>
  )
}

export default App
