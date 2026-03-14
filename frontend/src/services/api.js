/**
 * PatientBridge API client.
 * All backend calls go through here for a single point of control.
 */

const BASE = '/api';

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.message || 'Request failed');
  }
  return resp.json();
}

// Auth
export const getAuthStatus = () => request('/auth/status');
export const getLoginUrl = () => request('/auth/login');
export const loginAuth = getLoginUrl;

// Referrals
export const uploadReferralFile = async (file) => {
  const form = new FormData();
  form.append('file', file);
  const resp = await fetch(`${BASE}/referrals/upload`, { method: 'POST', body: form });
  if (!resp.ok) throw new Error('Upload failed');
  return resp.json();
};

export const uploadReferralText = (text, filename) =>
  request('/referrals/upload-text', {
    method: 'POST',
    body: JSON.stringify({ text, filename }),
  });

export const listReferrals = (status) =>
  request(`/referrals${status ? `?status=${status}` : ''}`);

export const getReferral = (id) => request(`/referrals/${id}`);

export const approveReferral = (id, overrides) =>
  request(`/referrals/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify({ overrides }),
  });

export const rejectReferral = (id, reason) =>
  request(`/referrals/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });

// Scheduling
export const searchProviders = (specialty) =>
  request(`/scheduling/providers${specialty ? `?specialty=${specialty}` : ''}`);

export const verifyInsurance = (patientId) =>
  request(`/scheduling/insurance/${patientId}`);

// RCM
export const getRCMDashboard = () => request('/rcm/dashboard');
export const getPatientBilling = (patientId) => request(`/rcm/patient/${patientId}`);

// System
export const getSystemStatus = () => request('/status');
export const getStatus = getSystemStatus;
