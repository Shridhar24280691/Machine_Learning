import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  ArrowLeft, 
  Mail, 
  User, 
  Calendar, 
  Tag,
  CheckCircle,
  XCircle,
  Edit3,
  Send,
  Brain,
  FileText,
  AlertTriangle
} from 'lucide-react'
import { format } from 'date-fns'
import { getEmailDetail, updateEmail } from '../services/api'

const EmailDetail = () => {
  const { id } = useParams()
  const navigate = useNavigate()
  const [email, setEmail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [editedResponse, setEditedResponse] = useState('')
  const [actionLoading, setActionLoading] = useState(false)

  useEffect(() => {
    fetchEmailDetail()
  }, [id])

  const fetchEmailDetail = async () => {
    try {
      setLoading(true)
      const data = await getEmailDetail(id)
      setEmail(data)
      setEditedResponse(data.generated_response || '')
    } catch (error) {
      console.error('Error fetching email detail:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAction = async (action, additionalData = {}) => {
    try {
      setActionLoading(true)
      await updateEmail(id, { action, ...additionalData })
      await fetchEmailDetail()
    } catch (error) {
      console.error('Error performing action:', error)
    } finally {
      setActionLoading(false)
    }
  }

  const handleSaveEdit = async () => {
    await handleAction('edit_response', { response_text: editedResponse, editor: 'admin' })
    setEditing(false)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!email) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Email not found</p>
        <button
          onClick={() => navigate('/emails')}
          className="mt-4 text-primary-600 hover:text-primary-700"
        >
          Back to Emails
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/emails')}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="w-5 h-5" />
          Back to Emails
        </button>
        
        <div className="flex items-center gap-3">
          {email.status === 'response_generated' && (
            <>
              <button
                onClick={() => handleAction('approve', { approver: 'admin' })}
                disabled={actionLoading}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                <CheckCircle className="w-4 h-4" />
                Approve
              </button>
              <button
                onClick={() => handleAction('reject', { reviewer: 'admin', reason: 'Needs revision' })}
                disabled={actionLoading}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                <XCircle className="w-4 h-4" />
                Reject
              </button>
            </>
          )}
          {email.status === 'approved' && (
            <button
              onClick={() => handleAction('send', { sender: 'admin' })}
              disabled={actionLoading}
              className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
              Send Email
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Email Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Original Email */}
          <div className="bg-white rounded-xl shadow-sm">
            <div className="p-6 border-b border-gray-100">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <Mail className="w-5 h-5 text-gray-400" />
                Original Email
              </h3>
            </div>
            <div className="p-6">
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <User className="w-5 h-5 text-gray-400" />
                  <div>
                    <p className="text-sm text-gray-500">From</p>
                    <p className="text-gray-900">{email.sender}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <Calendar className="w-5 h-5 text-gray-400" />
                  <div>
                    <p className="text-sm text-gray-500">Date</p>
                    <p className="text-gray-900">
                      {email.date && format(new Date(email.date), 'PPP p')}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <Tag className="w-5 h-5 text-gray-400" />
                  <div>
                    <p className="text-sm text-gray-500">Subject</p>
                    <p className="text-gray-900 font-medium">{email.subject}</p>
                  </div>
                </div>
                <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                  <p className="text-gray-700 whitespace-pre-wrap">{email.body_text}</p>
                </div>
              </div>
            </div>
          </div>

          {/* AI Response */}
          <div className="bg-white rounded-xl shadow-sm">
            <div className="p-6 border-b border-gray-100 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                <Brain className="w-5 h-5 text-primary-500" />
                AI Generated Response
              </h3>
              {!editing && email.status !== 'sent' && (
                <button
                  onClick={() => setEditing(true)}
                  className="flex items-center gap-2 text-primary-600 hover:text-primary-700"
                >
                  <Edit3 className="w-4 h-4" />
                  Edit
                </button>
              )}
            </div>
            <div className="p-6">
              {editing ? (
                <div className="space-y-4">
                  <textarea
                    value={editedResponse}
                    onChange={(e) => setEditedResponse(e.target.value)}
                    className="w-full h-64 p-4 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                  <div className="flex items-center gap-3">
                    <button
                      onClick={handleSaveEdit}
                      className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
                    >
                      Save Changes
                    </button>
                    <button
                      onClick={() => {
                        setEditing(false)
                        setEditedResponse(email.generated_response || '')
                      }}
                      className="px-4 py-2 border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="p-4 bg-primary-50 rounded-lg">
                  <pre className="text-gray-700 whitespace-pre-wrap font-sans">
                    {email.generated_response || 'No response generated yet'}
                  </pre>
                </div>
              )}
            </div>
          </div>

          {/* Retrieved Documents */}
          {email.retrieved_documents && email.retrieved_documents.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm">
              <div className="p-6 border-b border-gray-100">
                <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-gray-400" />
                  Retrieved Documents
                </h3>
              </div>
              <div className="p-6">
                <div className="space-y-3">
                  {email.retrieved_documents.map((doc, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div>
                        <p className="font-medium text-gray-900">{doc.title}</p>
                        <p className="text-sm text-gray-500">{doc.category}</p>
                      </div>
                      <span className="text-sm font-medium text-primary-600">
                        {(doc.score * 100).toFixed(1)}% match
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Right Column - Metadata */}
        <div className="space-y-6">
          {/* Classification */}
          <div className="bg-white rounded-xl shadow-sm">
            <div className="p-6 border-b border-gray-100">
              <h3 className="text-lg font-semibold text-gray-900">Classification</h3>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <p className="text-sm text-gray-500">Intent</p>
                <p className="font-medium text-gray-900 capitalize">
                  {email.classification?.primary_intent?.replace('_', ' ')}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Confidence</p>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-primary-500 h-2 rounded-full"
                      style={{ width: `${(email.classification?.confidence || 0) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium">
                    {((email.classification?.confidence || 0) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
              <div>
                <p className="text-sm text-gray-500">Priority</p>
                <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium capitalize ${
                  email.classification?.priority === 'high' ? 'bg-red-100 text-red-800' :
                  email.classification?.priority === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                  'bg-green-100 text-green-800'
                }`}>
                  {email.classification?.priority}
                </span>
              </div>
              <div>
                <p className="text-sm text-gray-500">Assigned Team</p>
                <p className="font-medium text-gray-900 capitalize">
                  {email.classification?.assigned_team?.replace('_', ' ')}
                </p>
              </div>
            </div>
          </div>

          {/* CRM Validation */}
          <div className="bg-white rounded-xl shadow-sm">
            <div className="p-6 border-b border-gray-100">
              <h3 className="text-lg font-semibold text-gray-900">CRM Validation</h3>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <p className="text-sm text-gray-500">Customer Found</p>
                <p className="font-medium text-gray-900">
                  {email.crm_validation?.customer_found ? 'Yes' : 'No'}
                </p>
              </div>
              {email.crm_validation?.customer_profile && (
                <>
                  <div>
                    <p className="text-sm text-gray-500">Customer Name</p>
                    <p className="font-medium text-gray-900">
                      {email.crm_validation.customer_profile.name}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Policy Status</p>
                    <p className="font-medium text-gray-900 capitalize">
                      {email.crm_validation.customer_profile.policy_status}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Plan</p>
                    <p className="font-medium text-gray-900">
                      {email.crm_validation.customer_profile.plan_name}
                    </p>
                  </div>
                </>
              )}
              <div>
                <p className="text-sm text-gray-500">Eligibility</p>
                <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${
                  email.crm_validation?.eligibility?.eligible 
                    ? 'bg-green-100 text-green-800' 
                    : 'bg-red-100 text-red-800'
                }`}>
                  {email.crm_validation?.eligibility?.eligible ? 'Eligible' : 'Not Eligible'}
                </span>
              </div>
            </div>
          </div>

          {/* Quality Score */}
          {email.quality_score && (
            <div className="bg-white rounded-xl shadow-sm">
              <div className="p-6 border-b border-gray-100">
                <h3 className="text-lg font-semibold text-gray-900">Quality Score</h3>
              </div>
              <div className="p-6 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Overall</span>
                  <span className="font-medium text-primary-600">
                    {email.quality_score.overall}/10
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Faithfulness</span>
                  <span className="font-medium">{email.quality_score.faithfulness}/10</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Helpfulness</span>
                  <span className="font-medium">{email.quality_score.helpfulness}/10</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">Completeness</span>
                  <span className="font-medium">{email.quality_score.completeness}/10</span>
                </div>
              </div>
            </div>
          )}

          {/* Action Decision */}
          {email.action_decision && (
            <div className="bg-white rounded-xl shadow-sm">
              <div className="p-6 border-b border-gray-100">
                <h3 className="text-lg font-semibold text-gray-900">Action Decision</h3>
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <p className="text-sm text-gray-500">Auto Send</p>
                  <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${
                    email.action_decision.auto_send 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-yellow-100 text-yellow-800'
                  }`}>
                    {email.action_decision.auto_send ? 'Yes' : 'No - Human Review Required'}
                  </span>
                </div>
                {!email.action_decision.auto_send && (
                  <div>
                    <p className="text-sm text-gray-500">Reasons</p>
                    <ul className="mt-1 space-y-1">
                      {email.action_decision.reasons?.map((reason, idx) => (
                        <li key={idx} className="text-sm text-gray-700 flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-yellow-500" />
                          {reason.replace('_', ' ')}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default EmailDetail
