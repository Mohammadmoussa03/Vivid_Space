import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Landing from './pages/Landing';
import Admin from './pages/Admin';
import WhishPayment from './pages/WhishPayment';

// The Mindspace design consolidates login/register and the member dashboard into
// modals on the landing page, so there are no separate /auth or /portal routes.
export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/admin" element={<Admin />} />
          <Route path="/pay/:orderNumber" element={<WhishPayment />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
