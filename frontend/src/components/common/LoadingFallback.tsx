interface LoadingFallbackProps {
  isLoading: boolean;
  error: Error | null;
  loadingMessage?: string;
  errorMessage?: string;
  children: React.ReactNode;
}

export function LoadingFallback({
  isLoading,
  error,
  loadingMessage = '로딩 중...',
  errorMessage = '데이터를 불러올 수 없습니다.',
  children,
}: LoadingFallbackProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-gray-500">{loadingMessage}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-gray-500">{errorMessage}</p>
      </div>
    );
  }

  return <>{children}</>;
}
