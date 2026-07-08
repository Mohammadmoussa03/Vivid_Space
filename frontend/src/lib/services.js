// Typed-ish wrappers around the Vivid Space REST API. Each returns response data.
import api from './api';

/* ============================ Public (no auth) ============================ */
export const getSite = () => api.get('/site/').then((r) => r.data);
export const getPublicPackages = (category) =>
  api.get('/packages/', { params: category ? { category } : {} }).then((r) => r.data);
export const getCategories = () => api.get('/categories/').then((r) => r.data);
export const getPublicSpaces = (params) =>
  api.get('/spaces/', { params: params || {} }).then((r) => r.data);
export const getPublicSpace = (key) => api.get(`/spaces/${key}/`).then((r) => r.data);
export const getAvailability = (space, date) =>
  api.get('/availability/', { params: { space, date } }).then((r) => r.data);
export const getFaqs = () => api.get('/faqs/').then((r) => r.data);
export const submitTour = (payload) => api.post('/tours/', payload).then((r) => r.data);
export const submitCustomization = (payload) => api.post('/customize/', payload).then((r) => r.data);

/* ============================ Member portal ============================ */
export const getOverview = () => api.get('/overview/').then((r) => r.data);
export const getSpaces = () => api.get('/spaces/').then((r) => r.data);

export const getBookings = (when) =>
  api.get('/bookings/', { params: when ? { when } : {} }).then((r) => r.data);

export const createBooking = (payload) =>
  api.post('/bookings/', payload).then((r) => r.data);

export const cancelBooking = (id) =>
  api.post(`/bookings/${id}/cancel/`).then((r) => r.data);

// Request a reschedule (new date/time) on an existing booking — goes to the
// admin for review; nothing changes until they approve.
export const requestBookingChange = (id, payload) =>
  api.post(`/bookings/${id}/request-change/`, payload).then((r) => r.data);

export const updateProfile = (payload) =>
  api.patch('/auth/me/', payload).then((r) => r.data);

// Propose an edit to the member's package schedule (days per package) — goes to
// the admin for review; nothing changes until they approve.
export const requestScheduleChange = (payload) =>
  api.post('/schedule-change/', payload).then((r) => r.data);

/* ============================ Admin ============================ */
export const adminDashboard = () => api.get('/admin/dashboard/').then((r) => r.data);

// Users
export const adminUsers = (status) =>
  api.get('/admin/users/', { params: status ? { status } : {} }).then((r) => r.data);
export const adminApproveUser = (id) => api.post(`/admin/users/${id}/approve/`).then((r) => r.data);
export const adminRejectUser = (id) => api.post(`/admin/users/${id}/reject/`).then((r) => r.data);
export const adminSetUserActive = (id, isActive) =>
  api.post(`/admin/users/${id}/set-active/`, isActive === undefined ? {} : { is_active: isActive }).then((r) => r.data);
export const adminUserMembership = (id) =>
  api.get(`/admin/users/${id}/membership/`).then((r) => r.data);
export const adminSetUserMembership = (id, payload) =>
  api.post(`/admin/users/${id}/set-membership/`, payload).then((r) => r.data);
export const adminApproveScheduleChange = (id) =>
  api.post(`/admin/users/${id}/approve-schedule-change/`).then((r) => r.data);
export const adminRejectScheduleChange = (id) =>
  api.post(`/admin/users/${id}/reject-schedule-change/`).then((r) => r.data);
export const adminClients = () => api.get('/admin/clients/').then((r) => r.data);

// Reservations
export const adminReservations = (filter) =>
  api.get('/admin/reservations/', { params: filter ? { filter } : {} }).then((r) => r.data);
export const adminApproveReservation = (id) =>
  api.post(`/admin/reservations/${id}/approve/`).then((r) => r.data);
export const adminCancelReservation = (id) =>
  api.post(`/admin/reservations/${id}/cancel/`).then((r) => r.data);
export const adminApproveChange = (id) =>
  api.post(`/admin/reservations/${id}/approve-change/`).then((r) => r.data);
export const adminRejectChange = (id) =>
  api.post(`/admin/reservations/${id}/reject-change/`).then((r) => r.data);
export const adminTogglePaid = (id) =>
  api.post(`/admin/reservations/${id}/toggle-paid/`).then((r) => r.data);
export const adminEditReservation = (id, payload) =>
  api.patch(`/admin/reservations/${id}/`, payload).then((r) => r.data);

// Spaces
export const adminSpaces = () => api.get('/admin/spaces/').then((r) => r.data);
export const adminCreateSpace = (payload) => api.post('/admin/spaces/', payload).then((r) => r.data);
export const adminUpdateSpace = (id, payload) =>
  api.patch(`/admin/spaces/${id}/`, payload).then((r) => r.data);
export const adminToggleSpace = (id) =>
  api.post(`/admin/spaces/${id}/toggle-active/`).then((r) => r.data);
export const adminDeleteSpace = (id) => api.delete(`/admin/spaces/${id}/`).then((r) => r.data);

// Packages
export const adminPackages = (includeArchived) =>
  api.get('/admin/packages/', { params: includeArchived ? { include_archived: 1 } : {} }).then((r) => r.data);
export const adminUpdatePackage = (id, payload) =>
  api.patch(`/admin/packages/${id}/`, payload).then((r) => r.data);
export const adminCreatePackage = (payload) =>
  api.post('/admin/packages/', payload).then((r) => r.data);
export const adminDeletePackage = (id) =>
  api.delete(`/admin/packages/${id}/`).then((r) => r.data);
export const adminDuplicatePackage = (id) =>
  api.post(`/admin/packages/${id}/duplicate/`).then((r) => r.data);
export const adminToggleArchivePackage = (id) =>
  api.post(`/admin/packages/${id}/toggle-archive/`).then((r) => r.data);

// Categories
export const adminCategories = () => api.get('/admin/categories/').then((r) => r.data);
export const adminCreateCategory = (payload) => api.post('/admin/categories/', payload).then((r) => r.data);
export const adminUpdateCategory = (id, payload) => api.patch(`/admin/categories/${id}/`, payload).then((r) => r.data);
export const adminDeleteCategory = (id) => api.delete(`/admin/categories/${id}/`).then((r) => r.data);

export const adminUploadImage = (file) => {
  const form = new FormData();
  form.append('file', file);
  return api.post('/admin/upload/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
    .then((r) => r.data);
};

// FAQ
export const adminFaqs = () => api.get('/admin/faqs/').then((r) => r.data);
export const adminCreateFaq = (payload) => api.post('/admin/faqs/', payload).then((r) => r.data);
export const adminUpdateFaq = (id, payload) => api.patch(`/admin/faqs/${id}/`, payload).then((r) => r.data);
export const adminDeleteFaq = (id) => api.delete(`/admin/faqs/${id}/`).then((r) => r.data);

// Promo codes
export const adminPromoCodes = () => api.get('/admin/promo-codes/').then((r) => r.data);
export const adminCreatePromo = (payload) => api.post('/admin/promo-codes/', payload).then((r) => r.data);
export const adminUpdatePromo = (id, payload) => api.patch(`/admin/promo-codes/${id}/`, payload).then((r) => r.data);
export const adminDeletePromo = (id) => api.delete(`/admin/promo-codes/${id}/`).then((r) => r.data);

// Tour requests
export const adminTours = (status) =>
  api.get('/admin/tours/', { params: status ? { status } : {} }).then((r) => r.data);
export const adminUpdateTour = (id, payload) => api.patch(`/admin/tours/${id}/`, payload).then((r) => r.data);
export const adminDeleteTour = (id) => api.delete(`/admin/tours/${id}/`).then((r) => r.data);

// Custom package requests (public "build your own" enquiries)
export const adminCustomizations = (status) =>
  api.get('/admin/customizations/', { params: status ? { status } : {} }).then((r) => r.data);
export const adminUpdateCustomization = (id, payload) => api.patch(`/admin/customizations/${id}/`, payload).then((r) => r.data);
export const adminDeleteCustomization = (id) => api.delete(`/admin/customizations/${id}/`).then((r) => r.data);

// Blocked slots (calendar)
export const adminBlockedSlots = (params) =>
  api.get('/admin/blocked-slots/', { params: params || {} }).then((r) => r.data);
export const adminCreateBlockedSlot = (payload) =>
  api.post('/admin/blocked-slots/', payload).then((r) => r.data);
export const adminDeleteBlockedSlot = (id) =>
  api.delete(`/admin/blocked-slots/${id}/`).then((r) => r.data);

// Content & settings
export const adminContent = () => api.get('/admin/content/').then((r) => r.data);
export const adminSaveContent = (payload) => api.put('/admin/content/', payload).then((r) => r.data);
export const adminSettings = () => api.get('/admin/settings/').then((r) => r.data);
export const adminSaveSettings = (payload) => api.put('/admin/settings/', payload).then((r) => r.data);
