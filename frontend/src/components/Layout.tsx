import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import logo from '../assets/distill_light.svg';
import CategoryFilter from './CategoryFilter';
import { isLoggedIn } from '../utils/categories';

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const loggedIn = isLoggedIn();

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    navigate('/');
    window.location.reload();
  };

  return (
    <div className="min-h-screen bg-stone-50">
      {/* 헤더 */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/">
            <img src={logo} alt="DSTILL" className="h-14" />
          </Link>
          <nav className="flex items-center gap-4">
            <Link
              to="/"
              className={`text-sm ${
                isActive('/') ? 'text-amber-600 font-medium' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              캘린더
            </Link>
            <Link
              to="/issues"
              className={`text-sm ${
                isActive('/issues') ? 'text-amber-600 font-medium' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              이슈 목록
            </Link>

            {/* 카테고리 필터 - 비로그인도 사용 가능 */}
            <CategoryFilter />

            {loggedIn ? (
              <>
                <Link
                  to="/settings"
                  className={`text-sm ${
                    isActive('/settings') ? 'text-amber-600 font-medium' : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  설정
                </Link>
                <button
                  onClick={handleLogout}
                  className="text-sm text-gray-600 hover:text-gray-900"
                >
                  로그아웃
                </button>
              </>
            ) : (
              <>
                <Link
                  to="/register"
                  className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                  알림 받기
                </Link>
                <Link
                  to="/login"
                  className="text-sm bg-amber-500 hover:bg-amber-600 text-white px-4 py-1.5 rounded-lg transition-colors"
                >
                  로그인
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      {/* 본문 */}
      <main className="max-w-5xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}