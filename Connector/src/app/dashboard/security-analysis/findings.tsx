'use client';

interface FindingsProps {
  projectId?: string;
}

export default function Findings({ projectId }: FindingsProps) {
  return (
    <div className="bg-white dark:bg-[#0a0a0a] rounded-xl border border-gray-200 dark:border-[#1f1f1f] p-12">
      <div className="text-center">
        <div className="w-16 h-16 bg-gray-100 dark:bg-[#141414] rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Findings</h3>
        <p className="text-gray-500 dark:text-gray-400">Security findings will appear here</p>
      </div>
    </div>
  );
}