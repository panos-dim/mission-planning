import { Suspense, type ReactNode } from "react";
import ErrorBoundary from "./ErrorBoundary";

interface SuspenseWrapperProps {
  children: ReactNode;
  fallback?: ReactNode;
}

const DefaultFallback = () => (
  <div className="flex items-center justify-center h-full w-full bg-gray-900/50">
    <div className="flex flex-col items-center gap-2">
      <div className="w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
      <span className="text-sm text-gray-400">Loading...</span>
    </div>
  </div>
);

export default function SuspenseWrapper({
  children,
  fallback,
}: SuspenseWrapperProps): JSX.Element {
  return (
    <ErrorBoundary>
      <Suspense fallback={fallback ?? <DefaultFallback />}>
        {children}
      </Suspense>
    </ErrorBoundary>
  );
}
