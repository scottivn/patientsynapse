/**
 * PatientSynapse API client.
 * All backend calls go through here for a single point of control.
 */

const BASE = '/api';

let _refreshing = null;

async function tryRefresh() {
  if (_refreshing) return _refreshing;
  _refreshing = fetch(`${BASE}/admin/refresh`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  }).then(r => r.ok).catch(() => false).finally(() => { _refreshing = null; });
  return _refreshing;
}

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });

  // On 401, try a silent token refresh (skip for login/refresh endpoints)
  if (resp.status === 401 && !path.startsWith('/admin/login') && !path.startsWith('/admin/refresh')) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      // Retry the original request once
      const retry = await fetch(`${BASE}${path}`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
      });
      if (retry.ok) return retry.json();
    }
    window.dispatchEvent(new Event('auth:session-expired'));
  }

  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || err.message || 'Request failed');
  }
  return resp.json();
}

// Admin auth
export const adminLogin = (username, password) =>
  request('/admin/login', { method: 'POST', body: JSON.stringify({ username, password }) });
export const adminLogout = () => request('/admin/logout', { method: 'POST' });
export const adminMe = () => request('/admin/me');
export const adminRefresh = () => request('/admin/refresh', { method: 'POST' });

// User management (admin only)
export const listUsers = () => request('/admin/users');
export const createUser = (username, password, role) =>
  request('/admin/users', { method: 'POST', body: JSON.stringify({ username, password, role }) });
export const updateUser = (id, data) =>
  request(`/admin/users/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const resetUserPassword = (id, password) =>
  request(`/admin/users/${id}/reset-password`, { method: 'POST', body: JSON.stringify({ password }) });
export const deleteUser = (id) =>
  request(`/admin/users/${id}`, { method: 'DELETE' });
export const getRoles = () => request('/admin/roles');

// SMART on FHIR auth
export const getAuthStatus = () => request('/auth/status');
export const getLoginUrl = () => request('/auth/login');
export const loginAuth = getLoginUrl;
export const connectService = () => request('/auth/connect-service', { method: 'POST' });

// Referrals
export const uploadReferralFile = async (file) => {
  const form = new FormData();
  form.append('file', file);
  const resp = await fetch(`${BASE}/referrals/upload`, { method: 'POST', body: form, credentials: 'include' });
  if (!resp.ok) throw new Error('Upload failed');
  return resp.json();
};

export const uploadReferralText = (text, filename) =>
  request('/referrals/upload-text', {
    method: 'POST',
    body: JSON.stringify({ text, filename }),
  });

export const listReferrals = (status, docType) => {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (docType) params.set('doc_type', docType);
  const qs = params.toString();
  return request(`/referrals${qs ? `?${qs}` : ''}`);
};

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

// Settings — EMR hot-swap
export const getEMRConfig = () => request('/settings/emr');
export const switchEMR = (provider) =>
  request('/settings/emr', {
    method: 'POST',
    body: JSON.stringify({ provider }),
  });

// Settings — LLM hot-swap
export const getLLMConfig = () => request('/settings/llm');
export const switchLLM = (provider) =>
  request('/settings/llm', {
    method: 'POST',
    body: JSON.stringify({ provider }),
  });

// Fax Ingestion (simulate eCW fax API)
export const pollFaxes = () => request('/faxes/poll', { method: 'POST' });
export const getFaxStatus = () => request('/faxes/status');
export const resetFaxInbox = () => request('/faxes/reset', { method: 'POST' });
export const retryFailedFaxes = () => request('/faxes/retry-failed', { method: 'POST' });
export const getFaxFileInfo = (filename) => request(`/faxes/file/${encodeURIComponent(filename)}/info`);
export const getFaxFileUrl = (filename) => `${BASE}/faxes/file/${encodeURIComponent(filename)}`;
export const getFaxPageUrl = (filename, page) => `${BASE}/faxes/file/${encodeURIComponent(filename)}/page/${page}`;

// DME (Durable Medical Equipment)
export const verifyDMEPatient = (patientId, dob) =>
  request('/dme/patient-verify', { method: 'POST', body: JSON.stringify({ patient_id: patientId, dob }) });

export const submitDMEOrder = (data) =>
  request('/dme/orders', { method: 'POST', body: JSON.stringify(data) });

export const listDMEOrders = (status) => {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  const qs = params.toString();
  return request(`/dme/orders${qs ? `?${qs}` : ''}`);
};

export const getDMEOrder = (id) => request(`/dme/orders/${id}`);
export const getDMEDashboard = () => request('/dme/dashboard');
export const getDMEAutoReplaceDue = () => request('/dme/orders/auto-replace-due');
export const getDMEIncoming = () => request('/dme/orders/incoming');
export const getDMEAutoRefillPending = () => request('/dme/orders/auto-refill-pending');
export const getDMEInProgress = () => request('/dme/orders/in-progress');

export const updateDMEEncounter = (id, data) =>
  request(`/dme/orders/${id}/encounter`, { method: 'POST', body: JSON.stringify(data) });

export const getDMEEncounterExpired = () => request('/dme/orders/encounter-expired');

export const getDMEEncounterTypes = () => request('/dme/encounter-types');

export const updateDMECompliance = (id, data) =>
  request(`/dme/orders/${id}/compliance`, { method: 'POST', body: JSON.stringify(data) });

export const addDMEDocument = (id, filename, documentType) =>
  request(`/dme/orders/${id}/documents`, { method: 'POST', body: JSON.stringify({ filename, document_type: documentType }) });

export const removeDMEDocument = (orderId, docId) =>
  request(`/dme/orders/${orderId}/documents/${docId}`, { method: 'DELETE' });

export const verifyDMEInsurance = (id) =>
  request(`/dme/orders/${id}/verify-insurance`, { method: 'POST' });

export const approveDMEOrder = (id, notes) =>
  request(`/dme/orders/${id}/approve`, { method: 'POST', body: JSON.stringify({ notes }) });

export const rejectDMEOrder = (id, reason) =>
  request(`/dme/orders/${id}/reject`, { method: 'POST', body: JSON.stringify({ reason }) });

export const fulfillDMEOrder = (id) =>
  request(`/dme/orders/${id}/fulfill`, { method: 'POST' });

// DME staff workflow
export const holdDMEOrder = (id, reason) =>
  request(`/dme/orders/${id}/hold`, { method: 'POST', body: JSON.stringify({ reason }) });
export const resumeDMEOrder = (id) =>
  request(`/dme/orders/${id}/resume`, { method: 'POST' });
export const sendDMEConfirmation = (id, sendVia = 'sms') =>
  request(`/dme/orders/${id}/send-confirmation`, { method: 'POST', body: JSON.stringify({ send_via: sendVia }) });
export const markDMEOrdered = (id, vendorName, vendorOrderId) =>
  request(`/dme/orders/${id}/mark-ordered`, { method: 'POST', body: JSON.stringify({ vendor_name: vendorName, vendor_order_id: vendorOrderId }) });
export const markDMEShipped = (id, trackingNumber, carrier, estimatedDelivery) =>
  request(`/dme/orders/${id}/mark-shipped`, { method: 'POST', body: JSON.stringify({ tracking_number: trackingNumber, carrier, estimated_delivery: estimatedDelivery }) });

// DME queue endpoints
export const getDMEAwaitingPatient = () => request('/dme/orders/awaiting-patient');
export const getDMEPatientConfirmed = () => request('/dme/orders/patient-confirmed');
export const getDMEOnHold = () => request('/dme/orders/on-hold');
export const getDMEEquipmentCategories = () => request('/dme/equipment-categories');

// DME admin — patient search and order creation
export const searchDMEPatients = (params) => {
  const qs = new URLSearchParams(params).toString();
  return request(`/dme/patients/search?${qs}`);
};
export const createAdminDMEOrder = (data) =>
  request('/dme/admin/orders', { method: 'POST', body: JSON.stringify(data) });

// DME patient confirmation (public — no auth)
export const validateDMEConfirmation = (token) => request(`/dme/confirm/${token}`);
export const submitDMEConfirmation = (token, data) =>
  request(`/dme/confirm/${token}`, { method: 'POST', body: JSON.stringify(data) });
export const rejectDMEConfirmation = (token, reason, callbackRequested) =>
  request(`/dme/confirm/${token}/reject`, { method: 'POST', body: JSON.stringify({ reason, callback_requested: callbackRequested }) });
export const toggleDMERefill = (token, autoReplace, frequency = 'quarterly') =>
  request(`/dme/confirm/${token}/toggle-refill`, { method: 'POST', body: JSON.stringify({ auto_replace: autoReplace, frequency }) });
export const getDMEExpiringEncounters = (days = 14) => request(`/dme/orders/expiring-encounters?days=${days}`);
export const processDMEAutoDeliveries = () => request('/dme/process-auto-deliveries', { method: 'POST' });
export const getDMEReceipt = (orderId) => request(`/dme/orders/${orderId}/receipt`);
export const getDMEDeliveryTicket = (orderId) => request(`/dme/orders/${orderId}/delivery-ticket`);

// Referral Authorizations (HMO/PCP referral tracking)
export const createReferralAuth = (data) =>
  request('/referral-auths', { method: 'POST', body: JSON.stringify(data) });

export const listReferralAuths = (status, patientId) => {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (patientId) params.set('patient_id', patientId);
  const qs = params.toString();
  return request(`/referral-auths${qs ? `?${qs}` : ''}`);
};

export const getReferralAuth = (id) => request(`/referral-auths/${id}`);
export const getReferralAuthDashboard = () => request('/referral-auths/dashboard');
export const getExpiringReferralAuths = (days = 14) =>
  request(`/referral-auths/expiring?days=${days}`);

export const updateReferralAuth = (id, data) =>
  request(`/referral-auths/${id}`, { method: 'PUT', body: JSON.stringify(data) });

export const recordReferralAuthVisit = (id) =>
  request(`/referral-auths/${id}/record-visit`, { method: 'POST' });

export const requestReferralAuthRenewal = (id) =>
  request(`/referral-auths/${id}/request-renewal`, { method: 'POST' });

export const getRenewalContent = (id) =>
  request(`/referral-auths/${id}/renewal-content`);

export const cancelReferralAuth = (id) =>
  request(`/referral-auths/${id}/cancel`, { method: 'POST' });

export const checkReferralAuth = (patientId) =>
  request(`/scheduling/referral-check/${patientId}`);

// Allowable Rates (Insurance pricing)
export const getAllowableRates = (payer, hcpcsCode, year) => {
  const params = new URLSearchParams();
  if (payer) params.set('payer', payer);
  if (hcpcsCode) params.set('hcpcs_code', hcpcsCode);
  if (year) params.set('year', year);
  const qs = params.toString();
  return request(`/allowable-rates${qs ? `?${qs}` : ''}`);
};

export const getRatePayers = (year) =>
  request(`/allowable-rates/payers${year ? `?year=${year}` : ''}`);

export const lookupRate = (payer, hcpcsCode, supplyMonths = 6, year) => {
  const params = new URLSearchParams({ payer, hcpcs_code: hcpcsCode, supply_months: supplyMonths });
  if (year) params.set('year', year);
  return request(`/allowable-rates/lookup?${params}`);
};

export const getBundlePricing = (payer, hcpcsCodes, supplyMonths = 6, year) =>
  request('/allowable-rates/bundle-pricing', {
    method: 'POST',
    body: JSON.stringify({ payer, hcpcs_codes: hcpcsCodes, supply_months: supplyMonths, year }),
  });

export const importAllowableRates = (year) =>
  request(`/allowable-rates/import${year ? `?year=${year}` : ''}`, { method: 'POST' });

export const createAllowableRate = (data) =>
  request('/allowable-rates', { method: 'POST', body: JSON.stringify(data) });

export const updateAllowableRate = (id, data) =>
  request(`/allowable-rates/${id}`, { method: 'PUT', body: JSON.stringify(data) });

export const deleteAllowableRate = (id) =>
  request(`/allowable-rates/${id}`, { method: 'DELETE' });

// Prescription Monitor (Rx → DME order pipeline)
export const pollPrescriptions = () => request('/prescriptions/poll', { method: 'POST' });
export const getPrescriptionStatus = () => request('/prescriptions/status');
export const listPrescriptions = (status) => {
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  const qs = params.toString();
  return request(`/prescriptions${qs ? `?${qs}` : ''}`);
};
export const getPrescription = (id) => request(`/prescriptions/${id}`);
export const resetPrescriptionMonitor = () => request('/prescriptions/reset', { method: 'POST' });
