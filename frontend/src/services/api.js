import axios from 'axios';

// Use relative URLs when running in production (nginx reverse proxy)
// Use full URL when running in development
const API_BASE = process.env.NODE_ENV === 'production' ? '/api' : 'http://localhost:8000/api';

export const jobsApi = {
  createJob: async (jd, k = 10) => {
    const response = await axios.post(`${API_BASE}/job`, { jd, k });
    return response.data;
  },

  ragQuery: async (query, jobId = null, jd = null) => {
    const formData = new FormData();
    formData.append('query', query);
    if (jobId) formData.append('job_id', jobId);
    if (jd) formData.append('jd', jd);
    const response = await axios.post(`${API_BASE}/rag`, formData);
    return response.data;
  }
};

export const githubApi = {
  fetchUsers: async (params) => {
    const response = await axios.post(`${API_BASE}/fetch_github_bg`, params);
    return response.data;
  },

  getJobStatus: async (jobId) => {
    const response = await axios.get(`${API_BASE}/fetch_github_job/${jobId}`);
    return response.data;
  },

  inspectCollection: async () => {
    const response = await axios.get(`${API_BASE}/collection`);
    return response.data;
  },

  filterBySkill: async (skill, maxResults = 100) => {
    const response = await axios.get(`${API_BASE}/filter_by_skill`, {
      params: { skill, max_results: maxResults }
    });
    return response.data;
  },

  clearDatabase: async () => {
    const response = await axios.post(`${API_BASE}/clear_database`);
    return response.data;
  }
};

// Reading the API service file to understand current configuration
