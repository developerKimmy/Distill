import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { register, login } from '../api/auth';
import { updateNotificationSettings } from '../api/settings';
import { AVAILABLE_CATEGORIES } from '../types';
import logo from '../assets/distill_light.svg';

export default function RegisterPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [categories, setCategories] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleStep1Submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== passwordConfirm) {
      setError('비밀번호가 일치하지 않습니다.');
      return;
    }

    if (password.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다.');
      return;
    }

    setStep(2);
  };

  const handleCategoryToggle = (category: string) => {
    setCategories((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category]
    );
  };

  const handleSelectAll = () => {
    if (categories.length === AVAILABLE_CATEGORIES.length) {
      setCategories([]);
    } else {
      setCategories([...AVAILABLE_CATEGORIES]);
    }
  };

  const handleStep2Submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (categories.length === 0) {
      setError('최소 1개 이상의 관심사를 선택해주세요.');
      return;
    }

    setLoading(true);

    try {
      // 1. 회원가입
      await register(email, password);

      // 2. 자동 로그인
      await login(email, password);

      // 3. 관심사 저장
      await updateNotificationSettings({ categories });

      // 4. 메인 페이지로 이동
      navigate('/');
    } catch {
      setError('회원가입에 실패했습니다. 이미 등록된 이메일일 수 있습니다.');
      setStep(1);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-stone-50">
      <div className="w-full max-w-md p-8 bg-white rounded-lg shadow-md">
        <div className="flex flex-col items-center mb-8">
          <img src={logo} alt="DISTILL" className="h-16 mb-2" />
          <span className="text-sm text-gray-500">회원가입</span>
        </div>

        {/* 단계 표시 */}
        <div className="flex items-center justify-center mb-8">
          <div className="flex items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                step >= 1 ? 'bg-amber-600 text-white' : 'bg-gray-200 text-gray-500'
              }`}
            >
              1
            </div>
            <div className={`w-12 h-1 ${step >= 2 ? 'bg-amber-600' : 'bg-gray-200'}`} />
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                step >= 2 ? 'bg-amber-600 text-white' : 'bg-gray-200 text-gray-500'
              }`}
            >
              2
            </div>
          </div>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-50 text-red-600 text-sm rounded-lg">
            {error}
          </div>
        )}

        {/* 1단계: 이메일/비밀번호 */}
        {step === 1 && (
          <form onSubmit={handleStep1Submit} className="space-y-6">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                이메일
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                비밀번호
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

            <div>
              <label htmlFor="passwordConfirm" className="block text-sm font-medium text-gray-700 mb-1">
                비밀번호 확인
              </label>
              <input
                id="passwordConfirm"
                type="password"
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
              />
            </div>

            <button
              type="submit"
              className="w-full py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700"
            >
              다음
            </button>
          </form>
        )}

        {/* 2단계: 관심사 선택 */}
        {step === 2 && (
          <form onSubmit={handleStep2Submit} className="space-y-6">
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="block text-sm font-medium text-gray-700">
                  관심 있는 분야를 선택해주세요
                </label>
                <button
                  type="button"
                  onClick={handleSelectAll}
                  className="text-sm text-amber-600 hover:text-amber-700"
                >
                  {categories.length === AVAILABLE_CATEGORIES.length ? '전체 해제' : '전체 선택'}
                </button>
              </div>
              <p className="text-sm text-gray-500 mb-4">
                선택한 분야의 이슈만 달력과 알림에 표시됩니다.
              </p>
              <div className="grid grid-cols-2 gap-3">
                {AVAILABLE_CATEGORIES.map((category) => (
                  <button
                    key={category}
                    type="button"
                    onClick={() => handleCategoryToggle(category)}
                    className={`py-3 px-4 rounded-lg text-sm font-medium transition-colors border-2 ${
                      categories.includes(category)
                        ? 'border-amber-600 bg-amber-50 text-amber-700'
                        : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
                    }`}
                  >
                    {category}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="flex-1 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
              >
                이전
              </button>
              <button
                type="submit"
                disabled={loading || categories.length === 0}
                className="flex-1 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:opacity-50"
              >
                {loading ? '가입 중...' : '가입 완료'}
              </button>
            </div>
          </form>
        )}

        <p className="mt-6 text-center text-sm text-gray-600">
          이미 계정이 있으신가요?{' '}
          <Link to="/login" className="text-amber-600 hover:underline">
            로그인
          </Link>
        </p>
      </div>
    </div>
  );
}
