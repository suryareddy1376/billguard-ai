import axios from 'axios'
import { supabase } from './context/AuthContext'

const api = axios.create({ 
  baseURL: import.meta.env.VITE_API_URL || '/api', 
  timeout: 30000 
})

// Intercept requests to inject the current securely verified user_id
api.interceptors.request.use(async (config) => {
  try {
    const { data } = await supabase.auth.getSession();
    const user = data?.session?.user;
    
    if (user) {
      // Inject into query params for GET requests like /history
      if (config.method === 'get') {
        config.params = { ...config.params, user_id: user.id };
      }
      
      // Inject Authorization header natively (good practice)
      config.headers['Authorization'] = `Bearer ${data.session.access_token}`;
      config.headers['X-User-Id'] = user.id;
    }
  } catch (error) {
    console.warn("Failed to attach auth token", error);
  }
  
  return config;
});

export const uploadBill = (formData) => api.post('/bills/upload', formData)
export const getStatus  = (jobId)    => api.get(`/bills/${jobId}/status`)
export const getAnalysis = (jobId)   => api.get(`/bills/${jobId}/analysis`)
export const getItems    = (jobId)   => api.get(`/bills/${jobId}/items`)
export const submitAction = (jobId, payload) => api.post(`/bills/${jobId}/actions`, payload)
export const getReport   = (jobId)   => api.get(`/bills/${jobId}/report`)
export const getComplaintLetter = (jobId) => api.get(`/bills/${jobId}/complaint-letter`)
export const getHistory  = ()        => api.get('/bills/history')
export const getSampleBill = (scenario = 'moderate') => api.get(`/demo/sample-bill?scenario=${scenario}`)
export const getTariff   = ()        => api.get('/config/tariff')
export const getAuditLog  = (jobId)  => api.get(`/audit/${jobId}`)

export default api
