import client from './client';

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export const login = async (email: string, password: string): Promise<LoginResponse> => {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);

  const { data } = await client.post('/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });

  // 토큰 저장
  localStorage.setItem('access_token', data.access_token);

  return data;
};

export const register = async (email: string, password: string) => {
  const { data } = await client.post('/auth/register', { email, password });
  return data;
};

export const logout = () => {
  localStorage.removeItem('access_token');
};