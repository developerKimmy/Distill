import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import logo from '../assets/distill_light.svg';

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/';
    }
    return location.pathname.startsWith(path);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-stone-50">
      {/* 헤더 */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link to="/">
            <img src={logo} alt="DSTILL" className="h-14" />
          </Link>
          <nav className="flex items-center gap-6">
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