import client from './client';
import type {
  SearchResponse,
  SuggestResponse,
  IssueSearchResult,
  ArticleSearchResult,
  ContentSearchResult
} from '../types';

// 통합 검색
export const searchAll = async (query: string, limit = 20): Promise<SearchResponse> => {
  const { data } = await client.get('/search', {
    params: { q: query, limit },
  });
  return data;
};

// 이슈 검색
export const searchIssues = async (query: string, limit = 10): Promise<IssueSearchResult[]> => {
  const { data } = await client.get('/search/issues', {
    params: { q: query, limit },
  });
  return data;
};

// 기사 검색
export const searchArticles = async (
  query: string,
  limit = 10,
  days = 30
): Promise<ArticleSearchResult[]> => {
  const { data } = await client.get('/search/articles', {
    params: { q: query, limit, days },
  });
  return data;
};

// 콘텐츠 검색
export const searchContents = async (query: string, limit = 10): Promise<ContentSearchResult[]> => {
  const { data } = await client.get('/search/contents', {
    params: { q: query, limit },
  });
  return data;
};

// 카테고리별 이슈 검색
export const searchByCategory = async (
  category: string,
  limit = 20
): Promise<IssueSearchResult[]> => {
  const { data } = await client.get(`/search/category/${encodeURIComponent(category)}`, {
    params: { limit },
  });
  return data;
};

// 검색어 자동완성
export const getSuggestions = async (query: string, limit = 5): Promise<SuggestResponse> => {
  const { data } = await client.get('/search/suggest', {
    params: { q: query, limit },
  });
  return data;
};
