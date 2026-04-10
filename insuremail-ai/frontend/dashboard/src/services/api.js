import axios from 'axios'

const API_BASE_URL = import.meta.env.example.VITE_API_URL || 'http://localhost:8080'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Emails API
export const getEmails = async (params = {}) => {
  try {
    const response = await api.get('/emails', { params })
    return response.data
  } catch (error) {
    console.error('Error fetching emails:', error)
    throw error
  }
}

export const getEmailDetail = async (id) => {
  try {
    const response = await api.get(`/emails/${id}`)
    return response.data
  } catch (error) {
    console.error('Error fetching email detail:', error)
    throw error
  }
}

export const updateEmail = async (id, data) => {
  try {
    const response = await api.post(`/emails/${id}`, data)
    return response.data
  } catch (error) {
    console.error('Error updating email:', error)
    throw error
  }
}

// Metrics API
export const getMetrics = async (days = 7) => {
  try {
    const response = await api.get('/metrics', { params: { days } })
    return response.data
  } catch (error) {
    console.error('Error fetching metrics:', error)
    throw error
  }
}

export default api
