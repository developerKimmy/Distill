import { useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';

// Query keys that should be invalidated when category filter changes
const CATEGORY_DEPENDENT_QUERIES = [
  ['issues'],
  ['issues-calendar'],
  ['batchDates'],
  ['dailyReport'],
] as const;

export function useInvalidateCategoryQueries() {
  const queryClient = useQueryClient();

  const invalidateAll = useCallback(() => {
    // Batch all invalidations
    Promise.all(
      CATEGORY_DEPENDENT_QUERIES.map((key) =>
        queryClient.invalidateQueries({ queryKey: key })
      )
    );
  }, [queryClient]);

  return invalidateAll;
}

export function useInvalidateQueries() {
  const queryClient = useQueryClient();

  const invalidate = useCallback(
    (queryKeys: unknown[][]) => {
      Promise.all(
        queryKeys.map((key) => queryClient.invalidateQueries({ queryKey: key }))
      );
    },
    [queryClient]
  );

  return invalidate;
}
