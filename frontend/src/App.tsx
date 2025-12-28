import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import PrivateRoute from './components/PrivateRoute';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import MagicLinkPage from './pages/MagicLinkPage';
import CalendarPage from './pages/CalendarPage';
import ReportPage from './pages/ReportPage';
import IssuePage from './pages/IssuePage';
import IssueListPage from './pages/IssueListPage';
import SettingsPage from './pages/SettingsPage';
import NotificationsPage from './pages/NotificationsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* 공개 라우트 */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/auth/magic" element={<MagicLinkPage />} />

          {/* 메인 콘텐츠 - 비로그인 허용 */}
          <Route path="/" element={<Layout />}>
            <Route index element={<CalendarPage />} />
            <Route path="report/:date" element={<ReportPage />} />
            <Route path="issues" element={<IssueListPage />} />
            <Route path="issues/:issueId" element={<IssuePage />} />
            {/* 로그인 필요 페이지 */}
            <Route
              path="notifications"
              element={
                <PrivateRoute>
                  <NotificationsPage />
                </PrivateRoute>
              }
            />
            <Route
              path="settings"
              element={
                <PrivateRoute>
                  <SettingsPage />
                </PrivateRoute>
              }
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}