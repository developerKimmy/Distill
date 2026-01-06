import { LoadingOverlay } from './LoadingOverlay';

interface LoadingFallbackProps {
  isLoading: boolean;
  error: Error | null;
  errorMessage?: string;
  children: React.ReactNode;
}

export function LoadingFallback({
  isLoading,
  error,
  errorMessage = '데이터를 불러올 수 없습니다.',
  children,
}: LoadingFallbackProps) {
  if (isLoading) {
    return <LoadingOverlay isLoading={true} />;
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
