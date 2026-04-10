import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { 
  Mail, 
  CheckCircle, 
  AlertCircle, 
  Clock,
  TrendingUp,
  Users,
  Brain
} from 'lucide-react'
import { format } from 'date-fns'
import { getMetrics, getEmails } from '../services/api'

const StatCard = ({ title, value, subtitle, icon: Icon, color, trend }) => (
  <div className="bg-white rounded-xl shadow-sm p-6">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-sm text-gray-500 mb-1">{title}</p>
        <h3 className="text-2xl font-bold text-gray-900">{value}</h3>
        {subtitle && <p className="text-sm text-gray-500 mt-1">{subtitle}</p>}
        {trend && (
          <div className="flex items-center gap-1 mt-2">
            <TrendingUp className="w-4 h-4 text-green-500" />
            <span className="text-sm text-green-600">{trend}</span>
          </div>
        )}
      </div>
      <div className={`p-3 rounded-lg ${color}`}>
        <Icon className="w-6 h-6 text-white" />
      </div>
    </div>
  </div>
)

const RecentEmailItem = ({ email }) => (
  <Link 
    to={`/emails/${email.email_id}`}
    className="flex items-center justify-between p-4 hover:bg-gray-50 rounded-lg transition-colors"
  >
    <div className="flex items-center gap-4">
      <div className={`w-2 h-2 rounded-full ${
        email.priority === 'high' ? 'bg-red-500' :
        email.priority === 'medium' ? 'bg-yellow-500' : 'bg-green-500'
      }`} />
      <div>
        <p className="font-medium text-gray-900 truncate max-w-md">{email.subject}</p>
        <p className="text-sm text-gray-500">{email.sender}</p>
      </div>
    </div>
    <div className="flex items-center gap-4">
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
        email.auto_send ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
      }`}>
        {email.auto_send ? 'Auto' : 'Review'}
      </span>
      <span className="text-sm text-gray-400">
        {format(new Date(email.timestamp), 'MMM d, HH:mm')}
      </span>
    </div>
  </Link>
)

const Dashboard = () => {
  const [metrics, setMetrics] = useState(null)
  const [recentEmails, setRecentEmails] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      const [metricsData, emailsData] = await Promise.all([
        getMetrics(7),
        getEmails({ limit: 5 })
      ])
      setMetrics(metricsData)
      setRecentEmails(emailsData.emails || [])
    } catch (error) {
      console.error('Error fetching data:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  const stats = metrics || {}

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Emails (7d)"
          value={stats.total_emails || 0}
          subtitle="Processed emails"
          icon={Mail}
          color="bg-blue-500"
          trend="+12% from last week"
        />
        <StatCard
          title="Auto-Send Rate"
          value={`${stats.auto_send_rate || 0}%`}
          subtitle="Emails sent automatically"
          icon={CheckCircle}
          color="bg-green-500"
        />
        <StatCard
          title="Avg Confidence"
          value={`${((stats.average_confidence || 0) * 100).toFixed(1)}%`}
          subtitle="Intent classification"
          icon={Brain}
          color="bg-purple-500"
        />
        <StatCard
          title="Pending Review"
          value={stats.human_review_rate || 0}
          subtitle="Need human attention"
          icon={AlertCircle}
          color="bg-orange-500"
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Emails */}
        <div className="lg:col-span-2 bg-white rounded-xl shadow-sm">
          <div className="p-6 border-b border-gray-100">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Recent Emails</h3>
              <Link 
                to="/emails" 
                className="text-sm text-primary-600 hover:text-primary-700 font-medium"
              >
                View All
              </Link>
            </div>
          </div>
          <div className="divide-y divide-gray-100">
            {recentEmails.length > 0 ? (
              recentEmails.map((email) => (
                <RecentEmailItem key={email.email_id} email={email} />
              ))
            ) : (
              <div className="p-8 text-center text-gray-500">
                <Mail className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p>No emails processed yet</p>
              </div>
            )}
          </div>
        </div>

        {/* Status Breakdown */}
        <div className="bg-white rounded-xl shadow-sm">
          <div className="p-6 border-b border-gray-100">
            <h3 className="text-lg font-semibold text-gray-900">Status Breakdown</h3>
          </div>
          <div className="p-6">
            {stats.status_breakdown && Object.entries(stats.status_breakdown).map(([status, count]) => (
              <div key={status} className="flex items-center justify-between mb-4 last:mb-0">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${
                    status === 'sent' ? 'bg-green-500' :
                    status === 'parsed' ? 'bg-blue-500' :
                    status === 'classified' ? 'bg-purple-500' :
                    'bg-gray-400'
                  }`} />
                  <span className="text-sm text-gray-700 capitalize">{status.replace('_', ' ')}</span>
                </div>
                <span className="text-sm font-medium text-gray-900">{count}</span>
              </div>
            ))}
          </div>
          
          {/* Intent Distribution */}
          <div className="p-6 border-t border-gray-100">
            <h4 className="text-sm font-medium text-gray-700 mb-4">Top Intents</h4>
            {stats.intent_distribution && Object.entries(stats.intent_distribution)
              .slice(0, 5)
              .map(([intent, count]) => (
                <div key={intent} className="flex items-center justify-between mb-2 last:mb-0">
                  <span className="text-sm text-gray-600 capitalize">{intent.replace('_', ' ')}</span>
                  <span className="text-sm text-gray-900">{count}</span>
                </div>
              ))
            }
          </div>
        </div>
      </div>

      {/* Model Performance */}
      {stats.model_performance && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Model Performance</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <p className="text-3xl font-bold text-primary-600">
                {(stats.model_performance.intent_classification_accuracy * 100).toFixed(1)}%
              </p>
              <p className="text-sm text-gray-500 mt-1">Intent Classification Accuracy</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-primary-600">
                {stats.model_performance.response_quality_average}/10
              </p>
              <p className="text-sm text-gray-500 mt-1">Response Quality Score</p>
            </div>
            <div className="text-center">
              <p className="text-3xl font-bold text-primary-600">
                {(stats.model_performance.retrieval_hit_rate * 100).toFixed(0)}%
              </p>
              <p className="text-sm text-gray-500 mt-1">Document Retrieval Hit Rate</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Dashboard
