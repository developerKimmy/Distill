import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { followIssue, unfollowIssue } from '../api/issues';
import { isLoggedIn } from '../utils/categories';
import type { Issue } from '../types';

interface UseFollowMutationOptions {
  // Query key to update optimistically
  queryKey: unknown[];
  // How to update the cache
  updateFn?: (old: unknown, issueId: string, isFollowing: boolean) => unknown;
}

const defaultUpdateFn = (old: unknown, issueId: string, isFollowing: boolean) => {
  if (!old || typeof old !== 'object') return old;

  // Handle paginated response { items: Issue[] }
  if ('items' in old && Array.isArray((old as { items: Issue[] }).items)) {
    return {
      ...old,
      items: (old as { items: Issue[] }).items.map((issue) =>
        issue.id === issueId ? { ...issue, isFollowing } : issue
      ),
    };
  }

  // Handle single issue detail
  if ('id' in old && (old as Issue).id === issueId) {
    return { ...old, isFollowing };
  }

  return old;
};

export function useFollowMutation({ queryKey, updateFn = defaultUpdateFn }: UseFollowMutationOptions) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const followMutation = useMutation({
    mutationFn: (issueId: string) => followIssue(issueId),
    onMutate: async (issueId) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData(queryKey);
      queryClient.setQueryData(queryKey, (old: unknown) => updateFn(old, issueId, true));
      return { previous };
    },
    onError: (_err, _issueId, context) => {
      queryClient.setQueryData(queryKey, context?.previous);
    },
  });

  const unfollowMutation = useMutation({
    mutationFn: (issueId: string) => unfollowIssue(issueId),
    onMutate: async (issueId) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData(queryKey);
      queryClient.setQueryData(queryKey, (old: unknown) => updateFn(old, issueId, false));
      return { previous };
    },
    onError: (_err, _issueId, context) => {
      queryClient.setQueryData(queryKey, context?.previous);
    },
  });

  const handleFollowClick = useCallback(
    (e: React.MouseEvent, issue: Issue) => {
      e.preventDefault();
      e.stopPropagation();

      if (!isLoggedIn()) {
        navigate('/register');
        return;
      }

      if (issue.isFollowing) {
        unfollowMutation.mutate(issue.id);
      } else {
        followMutation.mutate(issue.id);
      }
    },
    [navigate, followMutation, unfollowMutation]
  );

  const toggleFollow = useCallback(
    (issueId: string, isCurrentlyFollowing: boolean) => {
      if (!isLoggedIn()) {
        navigate('/register');
        return;
      }

      if (isCurrentlyFollowing) {
        unfollowMutation.mutate(issueId);
      } else {
        followMutation.mutate(issueId);
      }
    },
    [navigate, followMutation, unfollowMutation]
  );

  return {
    handleFollowClick,
    toggleFollow,
    isLoading: followMutation.isPending || unfollowMutation.isPending,
  };
}
