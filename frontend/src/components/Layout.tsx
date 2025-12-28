import { useState } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import logo from '../assets/distill_light.svg';
import CategoryFilter from './CategoryFilter';
import NotificationBell from './NotificationBell';
import { isLoggedIn } from '../utils/categories';

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const loggedIn = isLoggedIn();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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

  const closeMobileMenu = () => setMobileMenuOpen(false);

  const NavLinks = ({ mobile = false }: { mobile?: boolean }) => (
    <>
      <Link
        to="/"
        onClick={mobile ? closeMobileMenu : undefined}
        className={`${mobile ? 'block py-2' : ''} text-sm ${
          isActive('/') ? 'text-amber-600 font-medium' : 'text-gray-600 hover:text-gray-900'
        }`}
      >
        최근 이슈
      </Link>
      <Link
        to="/issues"
        onClick={mobile ? closeMobileMenu : undefined}
        className={`${mobile ? 'block py-2' : ''} text-sm ${
          isActive('/issues') ? 'text-amber-600 font-medium' : 'text-gray-600 hover:text-gray-900'
        }`}
      >
        이슈 목록
      </Link>

      {/* 카테고리 필터 */}
      <div className={mobile ? 'py-2' : ''}>
        <CategoryFilter />
      </div>

      {loggedIn ? (
        <>
          {/* 알림 벨 */}
          <div className={mobile ? 'py-2' : ''}>
            <NotificationBell />
          </div>
          <Link
            to="/settings"
            onClick={mobile ? closeMobileMenu : undefined}
            className={`${mobile ? 'block py-2' : ''} text-sm ${
              isActive('/settings') ? 'text-amber-600 font-medium' : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            설정
          </Link>
          <button
            onClick={() => {
              if (mobile) closeMobileMenu();
              handleLogout();
            }}
            className={`${mobile ? 'block py-2 w-full text-left' : ''} text-sm text-gray-600 hover:text-gray-900`}
          >
            로그아웃
          </button>
        </>
      ) : (
        <>
          <Link
            to="/register"
            onClick={mobile ? closeMobileMenu : undefined}
            className={`${mobile ? 'block py-2' : ''} text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            알림 받기
          </Link>
          <Link
            to="/login"
            onClick={mobile ? closeMobileMenu : undefined}
            className={`${mobile ? 'block py-2 text-center' : ''} text-sm bg-amber-500 hover:bg-amber-600 text-white px-4 py-1.5 rounded-lg transition-colors`}
          >
            로그인
          </Link>
        </>
      )}
    </>
  );

  return (
    <div className="min-h-screen bg-stone-50">
      {/* 헤더 */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/">
            <img src={logo} alt="DSTILL" className="h-10 sm:h-14" />
          </Link>

          {/* 데스크탑 네비게이션 */}
          <nav className="hidden md:flex items-center gap-4">
            <NavLinks />
          </nav>

          {/* 모바일 햄버거 버튼 */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 text-gray-600 hover:text-gray-900"
          >
            {mobileMenuOpen ? (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>

        {/* 모바일 메뉴 */}
        {mobileMenuOpen && (
          <nav className="md:hidden border-t border-gray-200 px-4 py-3 space-y-1 bg-white">
            <NavLinks mobile />
          </nav>
        )}
      </header>

      {/* 본문 */}
      <main className="max-w-5xl mx-auto px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}